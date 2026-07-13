# 协商群巡检器 v2.0

三段式全自动巡检脚本，检查飞书中以"协商"开头的群聊的法务确认状态。

## 环境要求

- Python 3.8+
- lark-cli（飞书命令行工具）

## 安装 lark-cli

```bash
# macOS（推荐）
brew install lark-cli

# 或用 npm
npm install -g @larksuite/cli
```

## 登录（第一次使用）

```bash
lark-cli auth login --domain im --no-wait
# 用手机飞书扫码授权
```

## 使用

```bash
# 完整运行（同步所有群 + 巡检）
python3 inspector.py

# 仅巡检（跳过群同步，适用于已有数据后）
python3 inspector.py --skip-phase1

# 重新巡检已标记为"未确认"的群
python3 inspector.py --skip-phase1 --include-unconfirmed
```

## 依赖说明

本脚本仅使用 Python 标准库，无需 pip install 任何第三方包。
