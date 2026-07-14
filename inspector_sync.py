#!/usr/bin/env python3
"""
协商群巡检器 - 同步脚本（用于轮询）

职责: 发现新协商群 → 新增 Bitable → 拉机器人进群
用法: python3 inspector_sync.py
"""

import sys
import os
# 确保能找到同目录下的公共模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspector_common import *

PHASE = "同步"


def phase1():
    """搜索协商群，发现新群则新增到 Bitable 并拉机器人。"""
    print("=" * 60)
    print(f"  {PHASE}: 全量群同步与拉机器人")
    print("=" * 60)

    body = bitable_list(limit=200)
    existing = parse_records(body)
    existing_names = {r["group_name"] for r in existing if r["group_name"]}
    existing_chat_ids = {r["chat_id"] for r in existing if r["chat_id"]}
    print(f"  Bitable 已有: {len(existing_names)} 个群")

    page_token = None
    has_more = True
    page_num = 0
    total_found = 0
    total_new = 0

    while has_more:
        page_num += 1
        cmd = f'lark-cli im +chat-search --as user --query "协商" --page-size {PAGE_SIZE} --format json'
        if page_token:
            cmd += f' --page-token "{page_token}"'

        try:
            output = run(cmd)
            body = extract_json(output).get("data", {})
        except Exception as e:
            print(f"  [ERROR] 第 {page_num} 页: {e}")
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

            # 新增记录
            rid = bitable_create({
                "群名": name,
                "chat_id": chat_id,
                "法务确认状态": STATUS_待处理,
                "是否已拉机器人": False if BOT_APP_ID else True,
            })
            existing_names.add(name)
            existing_chat_ids.add(chat_id)
            total_new += 1
            print(f"  ✅ 新增: {name}")

            # 拉机器人
            if BOT_APP_ID:
                print(f"  🔄 正在邀请机器人...", end=" ")
                if invite_bot_to_group(chat_id, BOT_APP_ID):
                    bitable_update(rid, {"是否已拉机器人": True})
                    print("✅")
                else:
                    print("❌")

        if not has_more:
            print(f"\n  ✅ 同步完毕")

    print(f"\n  {PHASE} 完成: 发现 {total_found} 个协商群, 新增 {total_new} 条")
    return total_new


def phase1_retry():
    """补拉：处理 Bitable 中未拉过机器人的旧群。"""
    if not BOT_APP_ID:
        return
    print(f"\n  --- 补拉机器人到已有群 ---")
    body = bitable_list(limit=200)
    all_records = parse_records(body)
    pending = [r for r in all_records if not r["bot_invited"] and r["chat_id"]]
    if not pending:
        print(f"  无需补拉")
        return
    print(f"  需要补拉: {len(pending)} 个群")
    for r in pending:
        print(f"  🔄 {r['group_name']}...", end=" ")
        if invite_bot_to_group(r["chat_id"], BOT_APP_ID):
            bitable_update(r["record_id"], {"是否已拉机器人": True})
            print("✅")
        else:
            print("❌")


if __name__ == "__main__":
    print(f"  协商群同步器 v1.0")
    print(f"  启动: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    detect_user()
    print()

    phase1()
    phase1_retry()

    print(f"\n  结束: {time.strftime('%Y-%m-%d %H:%M:%S')}")
