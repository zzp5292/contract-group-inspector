#!/usr/bin/env python3
"""
协商群巡检器 - 巡检脚本（用于手动/定时确认检查）

职责: 查 Bitable → 读群消息 → 关键词匹配 → 更新确认状态
用法: python3 inspector_check.py
       python3 inspector_check.py --include-unconfirmed
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspector_common import *

PHASE = "巡检"


def phase2_3(target_statuses=None):
    """查 Bitable → 读消息 → 关键词匹配 → 更新状态。一次拉完所有待处理记录，分批处理。"""
    if target_statuses is None:
        target_statuses = {STATUS_待处理, STATUS_未确认}

    # 构建 filter 条件
    filter_conditions = []
    for s in target_statuses:
        filter_conditions.append(["法务确认状态", "==", s])
    filter_json = {"conditions": filter_conditions}
    if len(filter_conditions) > 1:
        filter_json["logic"] = "or"

    print("=" * 60)
    print(f"  {PHASE}: 分批巡检")
    print("=" * 60)

    # ── Step 1: 一次拉取所有待处理/未确认记录 ──
    try:
        body = bitable_list(filter_json=filter_json, limit=200)
        all_records = parse_records(body)
    except Exception as e:
        print(f"  [ERROR] 查询失败: {e}")
        return 0, 0, 0

    all_records = [r for r in all_records if r["status"] in target_statuses]

    if not all_records:
        print(f"\n  ✅ 全部巡检完成！")
        return 0, 0, 0

    print(f"  共 {len(all_records)} 条待处理记录\n")

    # ── Step 2: 分批处理 ──
    batch_size = PAGE_SIZE  # 每批 5 个
    total_processed = 0
    total_confirmed = 0
    total_unconfirmed = 0
    confirmed_list = []
    unconfirmed_list = []

    for batch_start in range(0, len(all_records), batch_size):
        batch = all_records[batch_start:batch_start + batch_size]
        print(f"{'='*40}")
        print(f"  批次 {batch_start//batch_size + 1}: {len(batch)} 个群")
        print(f"{'='*40}")

        for i, rec in enumerate(batch):
            name = rec["group_name"]
            rid = rec["record_id"]
            chat_id = rec["chat_id"]
            print(f"\n  [{i+1}/{len(batch)}] {name}")

            if not chat_id:
                print(f"  ⚠️  chat_id 为空，标记为 {STATUS_未确认}")
                try:
                    bitable_update(rid, {"法务确认状态": STATUS_未确认})
                except:
                    pass
                total_processed += 1
                total_unconfirmed += 1
                unconfirmed_list.append(name)
                continue

            try:
                messages = get_user_messages(chat_id)
            except Exception:
                print(f"  ⏭️  不在群中，跳过")
                try:
                    bitable_update(rid, {"法务确认状态": STATUS_未确认})
                except:
                    pass
                total_processed += 1
                total_unconfirmed += 1
                unconfirmed_list.append(name)
                continue

            print(f"  最近 {len(messages)} 条消息（法务白名单: {', '.join(LEGAL_WHITELIST.keys())}，确认须在最后版本之后）")

            has_confirm, snippet = has_legal_confirmed(messages)
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

            try:
                bitable_update(rid, {"法务确认状态": new_status})
                total_processed += 1
                print(f"  ➡️  已更新为 {new_status}")
            except Exception as e:
                print(f"  ❌ 更新失败: {e}")

    # 汇总
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


if __name__ == "__main__":
    print(f"  协商群巡检器 v2.0")
    print(f"  启动: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    detect_user()

    targets = {STATUS_待处理, STATUS_未确认}
    print(f"  模式: 待处理 + ❌ 未确认")
    print()

    phase2_3(target_statuses=targets)
    print(f"\n  结束: {time.strftime('%Y-%m-%d %H:%M:%S')}")
