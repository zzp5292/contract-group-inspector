#!/usr/bin/env python3
"""一键运行：先同步（发现新群、拉机器人），再巡检（判断确认状态）"""

import subprocess
import sys
import os

scripts = ["inspector_sync.py", "inspector_check.py"]

base_dir = os.path.dirname(os.path.abspath(__file__))

for script in scripts:
    path = os.path.join(base_dir, script)
    if not os.path.exists(path):
        print(f"❌ 找不到 {path}，确保三个 .py 文件在同一个目录下")
        sys.exit(1)

print("=" * 40)
print("🔄 第一步：同步新群")
print("=" * 40)
ret = subprocess.run([sys.executable, "inspector_sync.py"], cwd=base_dir)
if ret.returncode != 0:
    print("❌ 同步失败，退出")
    sys.exit(ret.returncode)

print()
print("=" * 40)
print("🔍 第二步：巡检确认状态")
print("=" * 40)
ret = subprocess.run([sys.executable, "inspector_check.py"], cwd=base_dir)
if ret.returncode != 0:
    print("❌ 巡检失败")
    sys.exit(ret.returncode)

print()
print("✅ 全部完成")
