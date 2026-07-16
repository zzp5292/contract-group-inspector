#!/bin/bash

# 飞书协商群巡检工具
# 双击此文件即可运行

BASE_DIR="$HOME/feishu_inspector"
LOG_DIR="$BASE_DIR/logs"

# 颜色
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
NC='\033[0m'

echo "=================================="
echo "  飞书协商群巡检工具"
echo "=================================="
echo ""

# ── 1. 安装 lark-cli（直接下载二进制，无需 Homebrew）──
if ! command -v lark-cli &>/dev/null; then
    echo -e "${YELLOW}⏳ 正在下载 lark-cli...${NC}"

    # 检测 CPU 架构
    ARCH="amd64"
    [ "$(uname -m)" = "arm64" ] && ARCH="arm64"

    LARK_URL="https://github.com/larksuite/cli/releases/download/v1.0.70/lark-cli-1.0.70-darwin-${ARCH}.tar.gz"

    curl -sSL -o /tmp/lark-cli.tar.gz "$LARK_URL" || {
        echo -e "${RED}❌ 下载失败${NC}"
        read -p "按回车退出"
        exit 1
    }

    tar xzf /tmp/lark-cli.tar.gz -C /tmp 2>/dev/null
    # 解压出来的二进制在 /tmp/lark-cli 目录下
    INSTALL_DIR="/usr/local/bin"
    if [ ! -w "$INSTALL_DIR" ]; then
        INSTALL_DIR="$HOME/.local/bin"
        mkdir -p "$INSTALL_DIR"
    fi

    cp /tmp/lark-cli-1.0.70-darwin-${ARCH}/lark-cli "$INSTALL_DIR/" 2>/dev/null
    rm -rf /tmp/lark-cli.tar.gz /tmp/lark-cli-1.0.70-darwin-${ARCH}

    if command -v lark-cli &>/dev/null; then
        echo -e "${GREEN}✅ lark-cli 安装完成${NC}"
    elif [ -f "$INSTALL_DIR/lark-cli" ]; then
        # 刚安装的可能不在当前 PATH 中
        echo -e "${GREEN}✅ lark-cli 已安装到 $INSTALL_DIR${NC}"
        export PATH="$INSTALL_DIR:$PATH"
    else
        echo -e "${RED}❌ 安装失败${NC}"
        read -p "按回车退出"
        exit 1
    fi
fi

# ── 2. 检查/下载脚本 ──
mkdir -p "$BASE_DIR" "$LOG_DIR"
cd "$BASE_DIR"

FILES=("inspector_common.py" "inspector_sync.py" "inspector_check.py" "inspector_run.py")
NEED_DOWNLOAD=false
for f in "${FILES[@]}"; do
    if [ ! -f "$f" ]; then
        NEED_DOWNLOAD=true
        break
    fi
done

if [ "$NEED_DOWNLOAD" = true ]; then
    echo -e "${YELLOW}⏳ 正在下载脚本...${NC}"
    curl -sS -O "https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_common.py" \
         -O "https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_sync.py" \
         -O "https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_check.py" \
         -O "https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/inspector_run.py" \
         -O "https://raw.githubusercontent.com/zzp5292/contract-group-inspector/main/auth_warn.py" 2>/dev/null
    echo -e "${GREEN}✅ 脚本下载完成${NC}"
fi

# ── 4. 检查登录状态 ──
LOGIN_CHECK=$(lark-cli auth status 2>/dev/null)
OPEN_ID=$(echo "$LOGIN_CHECK" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('identities', {}).get('user', {}).get('openId', ''))
except:
    print('')
" 2>/dev/null)

if [ -z "$OPEN_ID" ]; then
    echo -e "${YELLOW}⚠️  尚未登录飞书，请在浏览器中完成授权${NC}"
    echo ""
    lark-cli auth login --domain im --scope "im:message.send_as_user"
    echo ""
    echo -e "${GREEN}✅ 授权完成${NC}"
fi

# ── 5. 运行巡检 ──
echo -e "${GREEN}🚀 开始巡检...${NC}"
echo ""
python3 inspector_run.py 2>&1 | tee -a "$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"

echo ""
echo -e "${GREEN}✅ 巡检完成${NC}"
echo ""
read -p "按回车退出"
