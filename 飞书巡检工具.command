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

# ── 1. 检查 lark-cli ──
if ! command -v lark-cli &>/dev/null; then
    echo -e "${YELLOW}⏳ 正在安装 lark-cli...${NC}"
    brew install lark-cli 2>/dev/null || {
        echo -e "${RED}❌ 安装失败，请先运行：brew install lark-cli${NC}"
        read -p "按回车退出"
        exit 1
    }
    echo -e "${GREEN}✅ lark-cli 安装完成${NC}"
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

# ── 3. 检查登录状态 ──
LOGIN_CHECK=$(lark-cli auth status 2>/dev/null)
if ! echo "$LOGIN_CHECK" | grep -q '"status": "ready"'; then
    echo -e "${YELLOW}⚠️  尚未登录飞书，请扫码登录${NC}"
    echo ""
    lark-cli auth login --domain im --scope "im:message.send_as_user"
    echo ""
fi

# ── 4. 运行巡检 ──
echo -e "${GREEN}🚀 开始巡检...${NC}"
echo ""
python3 inspector_run.py 2>&1 | tee -a "$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"

echo ""
echo -e "${GREEN}✅ 巡检完成${NC}"
echo ""
read -p "按回车退出"
