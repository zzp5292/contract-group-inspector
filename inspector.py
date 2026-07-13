#!/usr/bin/env python3
"""
协商群巡检器 v2.0 — 三段式全自动巡检脚本

Phase 1: 全量群同步到 Bitable，存储 chat_id + 初始化为"待处理"
Phase 2: 分批 5 个群巡检，读取消息，语义判断法务确认状态
Phase 3: 循环续跑，直到 Bitable 无待处理/未确认记录

用法:
  python3 inspector.py                # 完整运行
  python3 inspector.py --skip-phase1  # 仅巡检

依赖: lark-cli (brew install lark-cli || npm i -g @larksuite/cli)
"""

import json
import os
import re
import subprocess
import sys
import time

# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

# Bitable
BASE_TOKEN = "OQN0brHE9abpI1s1ZSncSTUGnqd"
TABLE_ID = "tblR1Ye2FEInH1IL"
FIELD_群名 = "fldJZimG6U"         # 群名 (文本)
FIELD_chat_id = "fld40aawF0"      # chat_id (文本)
FIELD_法务确认 = "fldaNcfZss"    # 法务确认状态 (状态/单选)

# Bitable 选项值（带空格，与字段定义完全一致）
# Bitable 选项值
STATUS_待处理 = "待处理"
STATUS_已确认 = "✅ 已确认"
STATUS_未确认 = "❌ 未确认"

# 巡检目标状态（默认同时查"待处理"和"❌ 未确认"，避免遗漏法务期间已处理但未更新的群）
TARGET_STATUSES_DEFAULT = {STATUS_待处理, STATUS_未确认}

# API 限制
PAGE_SIZE = 5   # 严格限制（需求规定）

# 当前用户（运行时从 whoami 自动获取）
USER_OPEN_ID = None
USER_NAME = None

# 确认关键词
CONFIRM_KEYWORDS = [
    "没问题", "没有问题了", "无异议", "暂无意见",
    "已确认", "法务已确认", "确认",
    "可以", "同意", "可以推进",
    "无修改意见", "没有意见",
    "我这边没问题", "法务这边没问题",
    "没有问题", "无问题", "通过",
]

# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def run(cmd: str, timeout: int = 120) -> str:
    """执行 shell 命令，返回 stdout。失败则抛出异常。"""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"exit={result.returncode} | {detail[:500]}"
        )
    return result.stdout


def extract_json(text: str):
    """从可能带前缀行的文本中提取第一个完整 JSON。"""
    start = re.search(r'[\[{]', text)
    if not start:
        raise ValueError(f"未找到 JSON，前 300 字符: {text[:300]}")
    stack = []
    for i, ch in enumerate(text[start.start():]):
        if ch in '{[':
            stack.append(ch)
        elif ch == '}':
            if stack and stack[-1] == '{':
                stack.pop()
                if not stack:
                    return json.loads(text[start.start():start.start() + i + 1])
        elif ch == ']':
            if stack and stack[-1] == '[':
                stack.pop()
                if not stack:
                    return json.loads(text[start.start():start.start() + i + 1])
    raise ValueError("JSON 未闭合")


def detect_user():
    """从 lark-cli whoami 获取当前登录用户信息，设置全局 USER_OPEN_ID 和 USER_NAME。"""
    global USER_OPEN_ID, USER_NAME
    output = run("lark-cli whoami", timeout=10)
    data = extract_json(output)
    info = data.get("onBehalfOf", {})
    USER_OPEN_ID = info.get("openId", "")
    USER_NAME = info.get("userName", "")
    if not USER_OPEN_ID:
        raise RuntimeError("无法获取当前用户信息，请先通过 lark-cli auth login 登录")
    print(f"  检测到当前用户: {USER_NAME} ({USER_OPEN_ID})")


def bitable_list(filter_json=None, limit=200):
    """通用 Bitable 查询（自动从返回中提取 data.data）。"""
    cmd = (
        f'lark-cli base +record-list --as user '
        f'--base-token {BASE_TOKEN} '
        f'--table-id {TABLE_ID} '
        f'--limit {limit} '
        f'--format json'
    )
    if filter_json:
        cmd += f" --filter-json '{json.dumps(filter_json, ensure_ascii=False)}'"
    output = run(cmd, timeout=30)
    raw = extract_json(output)
    return raw.get("data", {})  # 直接返回 data 子对象


def bitable_create(fields: dict) -> str:
    """创建 Bitable 记录，返回 record_id。"""
    output = run(
        f'lark-cli base +record-upsert --as user '
        f'--base-token {BASE_TOKEN} '
        f'--table-id {TABLE_ID} '
        f"--json '{json.dumps(fields, ensure_ascii=False)}'",
        timeout=15
    )
    data = extract_json(output)
    rids = data.get("data", {}).get("record_id_list", [])
    return rids[0] if rids else ""


def bitable_update(record_id: str, fields: dict):
    """更新 Bitable 记录。"""
    run(
        f'lark-cli base +record-upsert --as user '
        f'--base-token {BASE_TOKEN} '
        f'--table-id {TABLE_ID} '
        f'--record-id {record_id} '
        f"--json '{json.dumps(fields, ensure_ascii=False)}'",
        timeout=15
    )


def parse_records(body: dict) -> list[dict]:
    """
    解析 Bitable +record-list 返回的 data 子对象。
    返回 [{record_id, group_name, chat_id, status}].
    """
    records_data = body.get("data", [])
    field_ids = body.get("field_id_list", [])
    record_ids = body.get("record_id_list", [])

    if not records_data:
        return []

    # 建立 field_id → index 映射
    idx_map = {fid: i for i, fid in enumerate(field_ids)}
    name_idx = idx_map.get(FIELD_群名, 0)
    chat_idx = idx_map.get(FIELD_chat_id, -1)
    status_idx = idx_map.get(FIELD_法务确认, len(field_ids) - 1)

    result = []
    for i, rec in enumerate(records_data):
        if not isinstance(rec, list):
            continue

        group_name = ""
        if name_idx < len(rec) and rec[name_idx]:
            group_name = str(rec[name_idx])

        chat_id = ""
        if chat_idx >= 0 and chat_idx < len(rec) and rec[chat_idx]:
            chat_id = str(rec[chat_idx])

        status = ""
        if status_idx < len(rec):
            raw = rec[status_idx]
            if isinstance(raw, list) and len(raw) > 0:
                status = str(raw[0])
            elif isinstance(raw, str):
                status = raw

        rid = record_ids[i] if i < len(record_ids) else ""

        result.append({
            "record_id": rid,
            "group_name": group_name,
            "chat_id": chat_id,
            "status": status,
        })
    return result


def get_user_messages(chat_id: str, page_size: int = 50) -> list[dict]:
    """读取群聊最近消息，返回消息列表。"""
    output = run(
        f'lark-cli im +chat-messages-list --as user '
        f'--chat-id {chat_id} --page-size {page_size} --sort desc --format json',
        timeout=30
    )
    data = extract_json(output)
    return data.get("data", {}).get("messages", [])


def has_user_confirmed(messages: list[dict]) -> tuple[bool, str]:
    """语义分析：当前用户是否已确认。返回 (是否确认, 匹配片段)。"""
    for msg in messages:
        sender = msg.get("sender", {})
        if sender.get("sender_type") != "user":
            continue
        if sender.get("id_type") != "open_id":
            continue
        if sender.get("id") != USER_OPEN_ID:
            continue
        if msg.get("msg_type") != "text":
            continue
        content = msg.get("content", "")
        if not isinstance(content, str) or not content:
            continue
        for kw in CONFIRM_KEYWORDS:
            if kw in content:
                return True, content[:200]
    return False, ""


# ═══════════════════════════════════════════════════════════
# Phase 1: 全量群同步
# ═══════════════════════════════════════════════════════════

def phase1() -> int:
    """
    使用 +chat-search --query "协商" (page_size=5) 搜索群聊，
    再用 startswith("协商") 硬过滤确保精确，与 Bitable 比对后新增。
    新增时同时存储群名、chat_id、法务确认状态="待处理"。
    """
    print("=" * 60)
    print("  Phase 1: 全量群同步与初始化")
    print("=" * 60)

    # 读取 Bitable 现有记录（去重用）
    body = bitable_list(limit=200)
    existing = parse_records(body)
    existing_names = {r["group_name"] for r in existing if r["group_name"]}
    print(f"  Bitable 已有记录: {len(existing_names)} 个")

    # 分页遍历所有群
    page_token = None
    has_more = True
    page_num = 0
    total_found = 0
    total_new = 0

    while has_more:
        page_num += 1
        cmd = (
            f'lark-cli im +chat-search --as user '
            f'--query "协商" --page-size {PAGE_SIZE} --format json'
        )
        if page_token:
            cmd += f' --page-token "{page_token}"'

        try:
            output = run(cmd)
            body = extract_json(output).get("data", {})
        except Exception as e:
            print(f"  [ERROR] 第 {page_num} 页请求失败: {e}")
            break

        chats = body.get("chats", [])
        has_more = body.get("has_more", False)
        page_token = body.get("page_token", "")
        print(f"\n  第 {page_num} 页: {len(chats)} 个群, has_more={has_more}")

        for chat in chats:
            name = chat.get("name", "")
            if not name.startswith("协商"):
                continue
            total_found += 1
            chat_id = chat.get("chat_id", "")

            if name in existing_names:
                print(f"  ⏭️  跳过(已存在): {name}")
                continue

            bitable_create({
                "群名": name,
                "chat_id": chat_id,
                "法务确认状态": STATUS_待处理,
            })
            existing_names.add(name)
            total_new += 1
            print(f"  ✅ 新增: {name}  (chat_id={chat_id[:20]}...)")

        if not has_more:
            print(f"\n  ✅ 所有群已同步完毕")

    print(f"\n  Phase 1 完成: 发现 {total_found} 个协商群, 新增 {total_new} 条")
    return total_new


# ═══════════════════════════════════════════════════════════
# Phase 2 + 3: 分批巡检循环
# ═══════════════════════════════════════════════════════════

def phase2_3(target_statuses=None):
    """
    分批巡检循环，直到所有群处理完毕。

    Args:
        target_statuses: 要巡检的状态集合。默认只查"待处理"。
                         加 --include-unconfirmed 时同时查"✅ 已确认"和"❌ 未确认"中的待处理项。
    """
    if target_statuses is None:
        target_statuses = TARGET_STATUSES_DEFAULT.copy()

    # 构建 filter 条件
    filter_conditions = []
    for s in target_statuses:
        filter_conditions.append(["法务确认状态", "==", s])
    filter_json = {"conditions": filter_conditions}
    # 多条件时需要用 OR 逻辑
    if len(filter_conditions) > 1:
        filter_json["logic"] = "or"
    print("\n" + "=" * 60)
    print("  Phase 2+3: 分批巡检与断点续跑")
    print("=" * 60)

    round_num = 0
    total_processed = 0
    total_confirmed = 0
    total_unconfirmed = 0
    confirmed_list = []
    unconfirmed_list = []
    processed_ids = set()  # 本轮已处理的 record_id，避免重复巡检

    while True:
        round_num += 1
        print(f"\n{'='*40}")
        print(f"  巡检轮次 #{round_num} (page_size={PAGE_SIZE})")
        print(f"{'='*40}")

        # ── Step 1: 查询 Bitable ──
        records = []
        try:
            body = bitable_list(
                filter_json=filter_json,
                limit=PAGE_SIZE,
            )
            records = parse_records(body)
        except Exception as e:
            # 降级：无过滤全量拉取后客户端过滤
            print(f"  [WARN] 过滤查询异常: {e}")
            try:
                body = bitable_list(limit=PAGE_SIZE)
                records = parse_records(body)
            except Exception as e2:
                print(f"  [ERROR] 降级查询也失败: {e2}")
                break

        # 客户端二次过滤 & 去重
        records = [r for r in records if r["status"] in target_statuses]
        records = [r for r in records if r["record_id"] not in processed_ids]

        # ── Step 2: 无记录则结束 ──
        if not records:
            print(f"\n  {'✅' if round_num == 1 else ''} "
                  f"{'所有群已处理完毕！' if round_num == 1 else '全部巡检完成！'}")
            break

        print(f"  待处理记录: {len(records)} 个")

        # ── Step 3: 逐群处理 ──
        for i, rec in enumerate(records):
            name = rec["group_name"]
            rid = rec["record_id"]
            chat_id = rec["chat_id"]
            print(f"\n  [{i+1}/{len(records)}] {name}")

            if not chat_id:
                print(f"  ⚠️  chat_id 为空，标记为 {STATUS_未确认}")
                try:
                    bitable_update(rid, {"法务确认状态": STATUS_未确认})
                except Exception as ex:
                    print(f"  ❌ 更新失败: {ex}")
                total_processed += 1
                total_unconfirmed += 1
                unconfirmed_list.append(name)
                processed_ids.add(rid)
                continue

            # 读取最近 50 条消息
            try:
                messages = get_user_messages(chat_id)
            except Exception as e:
                # 降级：尝试搜索 chat_id
                print(f"  ⚠️  直接读取失败 ({e})，尝试搜索群名...")
                try:
                    search_out = run(
                        f'lark-cli im +chat-search --as user '
                        f'--query "{name[:10]}" --page-size 5 --format json',
                        timeout=15
                    )
                    search_data = extract_json(search_out)
                    chats = search_data.get("data", {}).get("chats", [])
                    found = None
                    for c in chats:
                        if c.get("name") == name:
                            found = c.get("chat_id", "")
                            break
                    if found:
                        chat_id = found
                        # 更新 Bitable 中的 chat_id
                        bitable_update(rid, {"chat_id": chat_id})
                        print(f"  🔄 chat_id 已更新: {chat_id[:20]}...")
                        messages = get_user_messages(chat_id)
                    else:
                        raise RuntimeError("搜索未找到该群")
                except Exception as e2:
                    print(f"  ⚠️  搜索也失败: {e2}")
                    try:
                        bitable_update(rid, {"法务确认状态": STATUS_未确认})
                    except:
                        pass
                    total_processed += 1
                    total_unconfirmed += 1
                    unconfirmed_list.append(name)
                    continue

            print(f"  最近 {len(messages)} 条消息")

            # 语义分析
            has_confirm, snippet = has_user_confirmed(messages)
            if has_confirm:
                new_status = STATUS_已确认
                total_confirmed += 1
                confirmed_list.append(name)
                print(f"  ✅ 检测到确认: \"{snippet[:80]}\"")
            else:
                new_status = STATUS_未确认
                total_unconfirmed += 1
                unconfirmed_list.append(name)
                print(f"  ❌ 未检测到确认")

            # 更新 Bitable
            try:
                bitable_update(rid, {"法务确认状态": new_status})
                total_processed += 1
                print(f"  ➡️  已更新为 {new_status}")
            except Exception as e:
                print(f"  ❌ 状态更新失败: {e}")
            processed_ids.add(rid)

        # ── Phase 3: 自动回到 Step 1 ──
        print(f"\n  本轮 {len(records)} 个群完成，继续下一轮...\n")

    # ═════════════════════════════════════════════════════
    # 汇总
    # ═════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  巡检完成！最终汇总")
    print("=" * 60)
    print(f"\n  总处理: {total_processed} 个群")
    print(f"  ✅ 已确认: {total_confirmed} 个")
    print(f"  ❌ 未确认: {total_unconfirmed} 个")

    if confirmed_list:
        print("\n  ✅ 已确认:")
        for g in confirmed_list:
            print(f"    • {g}")

    if unconfirmed_list:
        print("\n  ❌ 未确认:")
        for g in unconfirmed_list:
            print(f"    • {g}")

    return total_processed, total_confirmed, total_unconfirmed


# ═══════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    skip_p1 = "--skip-phase1" in sys.argv
    include_unconfirmed = "--include-unconfirmed" in sys.argv

    print("  协商群巡检器 v2.0")
    print(f"  启动: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 自动检测当前用户
    detect_user()

    print(f"  Bitable: {BASE_TOKEN[:12]}... table={TABLE_ID}")
    if include_unconfirmed:
        print(f"  模式: 包含 ❌ 未确认（定时任务模式）")
    print()

    if not skip_p1:
        phase1()
    else:
        print("  (跳过 Phase 1)")

    # 构建巡检目标状态
    targets = TARGET_STATUSES_DEFAULT.copy()
    if include_unconfirmed:
        targets.add(STATUS_未确认)

    phase2_3(target_statuses=targets)

    print(f"\n  结束: {time.strftime('%Y-%m-%d %H:%M:%S')}")
