#!/usr/bin/env python3
"""
授权过期预警脚本

检查 lark-cli user token 是否即将过期，快过期时通过 lark-cli 发送消息提醒自己。

用法: python3 auth_warn.py
建议 cron: 0 9 * * * /usr/bin/python3 /path/to/auth_warn.py
"""

import json
import os
import shlex
import subprocess
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

# 提前多少天预警
WARN_DAYS = 2

# 推送频率限制：同一用户 N 小时内不重复推送
COOLDOWN_HOURS = 6

# 状态文件
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".auth_warn_state.json")


def run_cmd(cmd, timeout=15):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip()[:300])
    return proc.stdout


def send_message(open_id, text):
    """通过 lark-cli 发送私聊消息（用户发给自己）"""
    cmd = (
        f'lark-cli im +messages-send --as bot '
        f'--user-id {open_id} '
        f'--text {shlex.quote(text)}'
    )
    run_cmd(cmd, timeout=15)
    return True


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def should_notify(open_id, state):
    last_time = state.get(open_id)
    if not last_time:
        return True
    last = datetime.fromisoformat(last_time)
    return datetime.now() - last > timedelta(hours=COOLDOWN_HOURS)


def main():
    print("授权检查:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    try:
        output = run_cmd("lark-cli auth status")
        data = json.loads(output)
        user_info = data.get("identities", {}).get("user", {})
        open_id = user_info.get("openId", "")
        user_name = user_info.get("userName", "未知")
        refresh_expires = user_info.get("refreshExpiresAt", "")
    except Exception as e:
        print("  [ERROR] 获取认证状态失败:", e)
        state = load_state()
        open_id = state.get("last_open_id", "")
        if not open_id:
            print("  [WARN] 没有已知 open_id，跳过")
            return
        refresh_expires = ""
        user_name = "用户"

    msg = None
    if refresh_expires:
        expires_dt = datetime.fromisoformat(refresh_expires)
        remaining = expires_dt - datetime.now().astimezone()
        days_left = remaining.days
        hours_left = remaining.seconds // 3600

        print(f"  用户: {user_name} ({open_id})")
        print(f"  刷新令牌过期: {refresh_expires}")
        print(f"  剩余: {days_left} 天 {hours_left} 小时")

        if days_left < 0 or (days_left == 0 and hours_left < 0):
            msg = (
                "⚠️ 你的飞书 lark-cli 授权已过期！\n\n"
                "请重新扫码登录：\n"
                "  lark-cli auth login --domain im"
            )
        elif days_left < WARN_DAYS or (days_left == WARN_DAYS and hours_left == 0):
            msg = (
                "⚠️ 你的飞书 lark-cli 授权即将过期\n\n"
                f"过期时间: {refresh_expires}\n"
                f"剩余: {days_left} 天 {hours_left} 小时\n\n"
                "请尽快重新扫码登录：\n"
                "  lark-cli auth login --domain im\n\n"
                "过期后将无法自动巡检群聊。"
            )
    else:
        if open_id:
            msg = (
                "⚠️ 飞书 lark-cli 授权状态获取失败\n\n"
                "请检查：lark-cli auth status\n"
                "重新登录：lark-cli auth login --domain im"
            )

    if not msg:
        print("  [OK] 授权正常，无需提醒")
        return

    state = load_state()
    if not should_notify(open_id, state):
        print(f"  [SKIP] 冷却期内（{COOLDOWN_HOURS}小时），跳过")
        return

    try:
        import shlex
        send_message(open_id, msg)
        print(f"  [OK] 已发送提醒给 {user_name}")
        state[open_id] = datetime.now().isoformat()
        state["last_open_id"] = open_id
        save_state(state)
    except Exception as e:
        print(f"  [ERROR] 发送失败: {e}")


if __name__ == "__main__":
    main()
