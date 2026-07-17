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

# ── 1. 检查 Homebrew ──
if ! command -v brew &>/dev/null; then
    echo -e "${YELLOW}⏳ 正在安装 Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" 2>/dev/null || {
        echo -e "${RED}❌ Homebrew 安装失败，请手动安装:${NC}"
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        read -p "按回车退出"
        exit 1
    }
    # M 芯片需要额外配置 PATH
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    echo -e "${GREEN}✅ Homebrew 安装完成${NC}"
fi

# ── 2. 检查 lark-cli ──
if ! command -v lark-cli &>/dev/null; then
    echo -e "${YELLOW}⏳ 正在安装 lark-cli...${NC}"
    brew install lark-cli 2>/dev/null || {
        echo -e "${RED}❌ lark-cli 安装失败，请手动运行: brew install lark-cli${NC}"
        read -p "按回车退出"
        exit 1
    }
    echo -e "${GREEN}✅ lark-cli 安装完成${NC}"
fi

# ── 3. 检查/下载脚本 ──
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
