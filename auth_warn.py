#!/usr/bin/env python3
"""
授权过期预警脚本

检查 lark-cli user token 是否即将过期，快过期时通过 lark-cli bot 发送消息提醒。

用法: python3 auth_warn.py
建议 cron: 0 9 * * * /usr/bin/python3 /path/to/auth_warn.py
"""

import json
import os
import shlex
import subprocess
from datetime import datetime, timedelta

# 配置
WARN_DAYS = 2
COOLDOWN_HOURS = 6
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".auth_warn_state.json")


def run_cmd(cmd, timeout=15):
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip()[:300])
    return proc.stdout


def send_bot_message(open_id, text):
    """用 lark-cli 的 bot 身份发私聊消息"""
    cmd = ("lark-cli im +messages-send --as user "
           "--user-id " + open_id + " "
           "--text " + shlex.quote(text))
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


def should_notify(oid, state):
    t = state.get(oid)
    if not t:
        return True
    return datetime.now() - datetime.fromisoformat(t) > timedelta(hours=COOLDOWN_HOURS)


def main():
    print("auth check:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    try:
        out = run_cmd("lark-cli auth status")
        data = json.loads(out)
        ui = data["identities"]["user"]
        open_id = ui["openId"]
        user_name = ui["userName"]
        expires = ui.get("refreshExpiresAt", "")
    except Exception as e:
        print("  [ERROR] get auth status:", e)
        state = load_state()
        open_id = state.get("last_open_id", "")
        if not open_id:
            print("  [WARN] no known open_id, skip")
            return
        expires = ""
        user_name = "user"

    msg = None
    if expires:
        dt = datetime.fromisoformat(expires)
        rem = dt - datetime.now().astimezone()
        dl, hl = rem.days, rem.seconds // 3600
        print(f"  user: {user_name} ({open_id})")
        print(f"  refresh token expires: {expires}")
        print(f"  remaining: {dl}d {hl}h")

        if dl < 0 or (dl == 0 and hl < 0):
            msg = ("⚠️ 你的飞书 lark-cli 授权已过期！\n\n"
                   "巡检脚本无法继续运行，请重新扫码登录：\n\n"
                   "  运行以下命令：\n"
                   "    lark-cli auth login --domain im --scope \"im:message.send_as_user\"\n\n"
                   "终端会显示二维码，用飞书手机端扫码即可完成授权。\n"
                   "（注意：必须带上 --scope 参数，否则预警消息发不出去）")
        elif dl < WARN_DAYS or (dl == WARN_DAYS and hl == 0):
            msg = ("⚠️ 你的飞书 lark-cli 授权即将过期\n\n"
                   "过期时间: " + expires + "\n"
                   "剩余: " + str(dl) + " 天 " + str(hl) + " 小时\n\n"
                   "请尽快重新扫码登录，过期后将无法自动巡检群聊：\n\n"
                   "  运行以下命令：\n"
                   "    lark-cli auth login --domain im --scope \"im:message.send_as_user\"\n\n"
                   "终端会显示二维码，用飞书手机端扫码即可完成授权。\n"
                   "授权有效期为 7 天，建议到期前重新登录以免影响巡检。\n"
                   "（注意：必须带上 --scope 参数，否则预警消息发不出去）")
    else:
        if open_id:
            msg = ("⚠️ 飞书 lark-cli 授权状态获取失败\n\n"
                   "请检查认证状态：\n"
                   "  lark-cli auth status\n\n"
                   "如已过期请重新扫码登录：\n"
                   "  lark-cli auth login --domain im --scope \"im:message.send_as_user\"\n\n"
                   "终端会显示二维码，用飞书手机端扫码即可完成授权。\n"
                   "（必须带上 --scope 参数，否则预警消息发不出去）")

    if not msg:
        print("  [OK] token valid, skip")
        return

    state = load_state()
    if not should_notify(open_id, state):
        print("  [SKIP] cooldown")
        return

    try:
        send_bot_message(open_id, msg)
        print("  [OK] sent to", user_name)
        state[open_id] = datetime.now().isoformat()
        state["last_open_id"] = open_id
        save_state(state)
    except Exception as e:
        print("  [ERROR] send failed:", e)


if __name__ == "__main__":
    main()
