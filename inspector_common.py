#!/usr/bin/env python3
"""协商群巡检器 - 公共模块（配置 + 工具函数）"""

import json
import os
import re
import shlex
import subprocess
import sys
import time

# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

BASE_TOKEN = "OQN0brHE9abpI1s1ZSncSTUGnqd"
TABLE_ID = "tblR1Ye2FEInH1IL"
FIELD_群名 = "fldJZimG6U"
FIELD_chat_id = "fld40aawF0"
FIELD_法务确认 = "fldaNcfZss"
FIELD_已拉机器人 = "fldViXp38L"
FIELD_用户 = "fldZn1JcEF"

# Bitable 选项值
STATUS_待处理 = "待处理"
STATUS_已确认 = "✅ 已确认"
STATUS_未确认 = "❌ 未确认"

# 新群自动邀请的机器人
BOT_APP_ID = "cli_a8e50c6e3c7f900b"  # legal助手

# API 限制
PAGE_SIZE = 5

# 当前用户（运行时自动获取）
USER_OPEN_ID = None
USER_NAME = None

# 法务人员白名单——只认这些人的确认发言
# 格式: {"姓名": "open_id_or_None"}
LEGAL_WHITELIST = {
    "郑梦雪": None,  # None 表示仅按名称匹配，填 open_id 则精确匹配
}

# 版本检测：确认必须在一个文件消息或机器人发送的合同卡片之后才算
# 合同通常以文件形式发送，也可能是智书等机器人发送的飞书卡片
CHECK_LAST_FILE = True  # True=确认须在最后一个版本之后；False=不检查版本

# 发送新版合同的机器人名称列表（sender.name 匹配）
# 这些机器人的消息被视为"新版合同"，确认须在其之后才算
VERSION_BOT_NAMES = ["智书合同"]

# 确认关键词（正则匹配）
CONFIRM_PATTERNS = [
    r"法务侧?[都这]?边?没有问题了?[哈哦]?$",
    r"法务侧?[都这]?边?没问题了?[哈哦]?$",
    r"法务侧?[都这]?边?已确认$",
    r"法务侧?[都这]?边?无异议$",
    r"法务侧?[都这]?边?暂?无[修改]?意见$",
    r"法务没有问题[了]?$",
    r"法务没问题[了]?[哈哦]?$",
    r"法务已确认$",
    r"我[这]?边没问题了?[哈哦]?$",
    r"我[这]?边没有问题了?[哈哦]?$",
    r"我[这]?边已确认$",
    r"没有问题[了]?$",
    r"没问题[了]?[哈哦]?$",
    r"没有问题了[哈哦]?$",
    r"无异议$",
    r"暂无意见$",
    r"已确认$",
    r"确认$",
    r"无修改意见$",
    r"没有意见$",
    r"可以推进$",
    r"同意$",
    r"通过$",
]


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def run(cmd, timeout=120):
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"exit={result.returncode} | {detail[:500]}")
    return result.stdout


def extract_json(text):
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
    global USER_OPEN_ID, USER_NAME
    output = run("lark-cli auth status", timeout=10)
    data = extract_json(output)
    info = data.get("identities", {}).get("user", {})
    USER_OPEN_ID = info.get("openId", "")
    USER_NAME = info.get("userName", "")
    if not USER_OPEN_ID:
        raise RuntimeError("无法获取用户信息，请先 lark-cli auth login")
    print(f"  当前用户: {USER_NAME} ({USER_OPEN_ID})")


def bitable_list(filter_json=None, limit=200):
    """通用 Bitable 查询。自动翻页直到 has_more=false，合并返回所有记录。"""
    offset = 0
    all_data = None

    while True:
        cmd = (
            f'lark-cli base +record-list --as user '
            f'--base-token {BASE_TOKEN} --table-id {TABLE_ID} '
            f'--limit {limit} --offset {offset} --format json'
        )
        if filter_json:
            filter_str = json.dumps(filter_json, ensure_ascii=False)
            cmd += f" --filter-json '{filter_str}'"

        output = run(cmd, timeout=30)
        raw = extract_json(output)
        body = raw.get("data", {})

        if all_data is None:
            all_data = body
        else:
            all_data["data"] = all_data.get("data", []) + body.get("data", [])
            all_data["record_id_list"] = all_data.get("record_id_list", []) + body.get("record_id_list", [])

        if not body.get("has_more", False):
            break
        offset += len(body.get("data", []))

    return all_data or {}


def bitable_create(fields):
    json_str = json.dumps(fields, ensure_ascii=False)
    output = run(
        f'lark-cli base +record-upsert --as user '
        f'--base-token {BASE_TOKEN} --table-id {TABLE_ID} '
        f'--json {shlex.quote(json_str)}',
        timeout=15
    )
    data = extract_json(output)
    record = data.get("data", {}).get("record", {})
    rids = record.get("record_id_list", [])
    return rids[0] if rids else ""


def bitable_update(record_id, fields):
    json_str = json.dumps(fields, ensure_ascii=False)
    run(
        f'lark-cli base +record-upsert --as user '
        f'--base-token {BASE_TOKEN} --table-id {TABLE_ID} '
        f'--record-id {record_id} '
        f'--json {shlex.quote(json_str)}',
        timeout=15
    )


def parse_records(body):
    records_data = body.get("data", [])
    field_ids = body.get("field_id_list", [])
    record_ids = body.get("record_id_list", [])
    if not records_data:
        return []

    idx_map = {fid: i for i, fid in enumerate(field_ids)}
    name_idx = idx_map.get(FIELD_群名, 0)
    chat_idx = idx_map.get(FIELD_chat_id, -1)
    status_idx = idx_map.get(FIELD_法务确认, len(field_ids) - 1)
    bot_idx = idx_map.get(FIELD_已拉机器人, -1)
    user_idx = idx_map.get(FIELD_用户, -1)

    result = []
    for i, rec in enumerate(records_data):
        if not isinstance(rec, list):
            continue
        group_name = str(rec[name_idx]) if name_idx < len(rec) and rec[name_idx] else ""
        chat_id = str(rec[chat_idx]) if chat_idx >= 0 and chat_idx < len(rec) and rec[chat_idx] else ""
        status = ""
        if status_idx < len(rec):
            raw = rec[status_idx]
            if isinstance(raw, list) and len(raw) > 0:
                status = str(raw[0])
            elif isinstance(raw, str):
                status = raw
        rid = record_ids[i] if i < len(record_ids) else ""
        bot_invited = False
        if bot_idx >= 0 and bot_idx < len(rec):
            bot_invited = bool(rec[bot_idx])
        user_name = ""
        if user_idx >= 0 and user_idx < len(rec) and rec[user_idx]:
            user_name = str(rec[user_idx])
        result.append({"record_id": rid, "group_name": group_name, "chat_id": chat_id, "status": status, "bot_invited": bot_invited, "user": user_name})
    return result


def get_user_messages(chat_id, page_size=50):
    output = run(
        f'lark-cli im +chat-messages-list --as user '
        f'--chat-id {chat_id} --page-size {page_size} --sort desc --format json',
        timeout=30
    )
    data = extract_json(output)
    return data.get("data", {}).get("messages", [])


def invite_bot_to_group(chat_id, bot_app_id=None):
    if not bot_app_id:
        return False
    # 先检查机器人是否已在群内
    try:
        output = run(
            f'lark-cli im +chat-members-list --as user '
            f'--chat-id {chat_id} --page-all --format json',
            timeout=15
        )
        data = extract_json(output)
        for b in data.get("data", {}).get("bots", []):
            if b.get("app_id") == bot_app_id:
                return True
    except Exception:
        pass
    # 不在则拉入
    try:
        data_json = json.dumps({"id_list": [bot_app_id]})
        result = run(
            f'lark-cli im chat.members create --as user '
            f'--chat-id {chat_id} --member-id-type app_id '
            f"--data '{data_json}' --succeed-type 1",
            timeout=15
        )
        data = extract_json(result)
        invalid = data.get("data", {}).get("invalid_id_list", [])
        return bot_app_id not in invalid
    except Exception:
        return False


def has_legal_confirmed(messages):
    """
    消息按时间降序排列（最新在前）。
    逻辑:
    1. 如果 CHECK_LAST_FILE=True，找到最近一条"版本标记"的位置
       - msg_type=file 的文件消息
       - 或机器人发送的合同卡片（sender_type=bot 且名称在 VERSION_BOT_NAMES 中）
    2. 只检查在此消息之后的消息中，白名单法务人员的确认发言
    3. 如果没有版本标记，则检查全部消息
    """
    # 找到最新的一条版本标记（文件消息或机器人合同卡片）
    newest_version_idx = -1
    if CHECK_LAST_FILE:
        for i, msg in enumerate(messages):
            if msg.get("msg_type") == "file":
                newest_version_idx = i
                break
            sender = msg.get("sender", {})
            if sender.get("sender_type") == "bot" and sender.get("name") in VERSION_BOT_NAMES:
                newest_version_idx = i
                break

    # 只检查版本标记之后的（索引更小，更新）
    scan_limit = newest_version_idx if newest_version_idx >= 0 else len(messages)

    for i in range(scan_limit):
        msg = messages[i]
        sender = msg.get("sender", {})
        if sender.get("sender_type") != "user":
            continue
        sender_name = sender.get("name", "")
        sender_open_id = sender.get("id", "")

        # 判断是否在白名单中
        in_whitelist = False
        for name, open_id in LEGAL_WHITELIST.items():
            if open_id and sender_open_id == open_id:
                in_whitelist = True
                break
            if not open_id and sender_name == name:
                in_whitelist = True
                break
        if not in_whitelist:
            continue

        if msg.get("msg_type") != "text":
            continue
        content = msg.get("content", "")
        if not isinstance(content, str) or not content:
            continue
        sentences = re.split(r"[。！？\n\r]+", content)
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            for pattern in CONFIRM_PATTERNS:
                if re.search(pattern, s):
                    return True, s[:200]
    return False, ""
