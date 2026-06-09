#!/bin/bash
# ──────────────────────────────────────────────────────
# A股大屏 - 电视全屏显示脚本 (Kiosk Mode)
# 在连接HDMI的电视/显示器上全屏显示看板
# ──────────────────────────────────────────────────────
set -e

# ─── 安装模式：注册 systemd 自启服务 ────────────────────
if [ "$1" = "--install" ] || [ "$1" = "-i" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    
    echo ""
    echo "📌 安装 Kiosk 自启服务..."
    echo "   项目路径: ${PROJECT_DIR}"
    
    # 拷贝 service 文件并修改路径
    sed "s|/opt/agushare|${PROJECT_DIR}|g" "${SCRIPT_DIR}/agushare-kiosk.service" > /etc/systemd/system/agushare-kiosk.service
    
    systemctl daemon-reload
    systemctl enable agushare-kiosk.service
    systemctl start agushare-kiosk.service
    
    echo ""
    echo "✅ Kiosk 自启服务已安装并启动！"
    echo "   管理命令："
    echo "     systemctl status agushare-kiosk   查看状态"
    echo "     systemctl stop agushare-kiosk     停止"
    echo "     systemctl disable agushare-kiosk  关闭自启"
    echo ""
    echo "⚠️  注意：需要在连接 HDMI 的电视/显示器环境下运行"
    echo "   如果电视无显示，请确认："
    echo "   1. Armbian 已连接 HDMI"
    echo "   2. X11 桌面环境已安装 (apt install xorg xserver-xorg-video-fbdev)"
    echo "   3. 浏览器已安装 (脚本会自动安装 chromium-browser)"
    exit 0
fi

SERVICE_URL="http://127.0.0.1:8081"
BROWSER=""

# ─── 颜色 ────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     A股大屏 - 电视全屏启动脚本           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ─── 1. 等待服务就绪 ──────────────────────────────────
echo -e "${YELLOW}⏳ 等待 A股大屏服务就绪...${NC}"
for i in $(seq 1 30); do
    if curl -sf "${SERVICE_URL}/api/health" >/dev/null 2>&1; then
        echo -e "${GREEN}   ✅ 服务已就绪 (${SERVICE_URL})${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e "${RED}   ❌ 服务启动超时，请检查 podman-compose logs${NC}"
        exit 1
    fi
    sleep 2
done

# ─── 2. 检测可用浏览器 ────────────────────────────────
echo -e "${YELLOW}🔍 检测可用浏览器...${NC}"

# 浏览器优先级列表
BROWSERS=(
    "chromium-browser:chromium-browser --kiosk --no-sandbox --disable-gpu --disable-software-rasterizer --disable-infobars --disable-features=TranslateUI --no-first-run --check-for-update-interval=604800 --enable-features=OverlayScrollbar"
    "chromium:chromium --kiosk --no-sandbox --disable-gpu --disable-software-rasterizer --disable-infobars --no-first-run"
    "google-chrome:google-chrome --kiosk --no-sandbox --disable-gpu --disable-infobars --no-first-run"
    "firefox:firefox --kiosk"
    "luakit:luakit -u"
    "surf:surf"
)

for entry in "${BROWSERS[@]}"; do
    cmd="${entry%%:*}"
    args="${entry#*:}"
    if command -v "$cmd" &>/dev/null; then
        BROWSER="$args"
        echo -e "${GREEN}   ✅ 找到浏览器: ${cmd}${NC}"
        break
    fi
done

if [ -z "$BROWSER" ]; then
    echo -e "${YELLOW}   ⚠️  未找到已有浏览器，正在安装 chromium-browser...${NC}"
    apt-get update -qq && apt-get install -y -qq chromium-browser || true
    
    if command -v chromium-browser &>/dev/null; then
        BROWSER="chromium-browser --kiosk --no-sandbox --disable-gpu --disable-software-rasterizer --disable-infobars --disable-features=TranslateUI --no-first-run --check-for-update-interval=604800"
        echo -e "${GREEN}   ✅ chromium-browser 安装成功${NC}"
    else
        echo -e "${RED}   ❌ 无法安装浏览器，请手动安装chromium-browser或surf${NC}"
        exit 1
    fi
fi

# ─── 3. 检测显示环境 ──────────────────────────────────
echo -e "${YELLOW}🖥️  检测显示环境...${NC}"

if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
    echo "   → 设置 DISPLAY=:0"
fi

# 检查 X 服务是否运行
if ! xset q &>/dev/null; then
    echo -e "${YELLOW}   ⚠️  X 服务未运行，尝试启动...${NC}"
    if command -v startx &>/dev/null; then
        startx &
        sleep 3
    fi
fi

# 获取屏幕分辨率
RESOLUTION=$(xrandr 2>/dev/null | grep '*' | awk '{print $1}' | head -1)
if [ -n "$RESOLUTION" ]; then
    echo -e "${GREEN}   ✅ 分辨率: ${RESOLUTION}${NC}"
else
    echo -e "${YELLOW}   ⚠️  无法检测分辨率，使用默认 1920x1080${NC}"
fi

# ─── 4. 禁用屏幕保护/休眠 ────────────────────────────
echo -e "${YELLOW}🔌 禁用屏幕休眠...${NC}"
xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
xset s noblank 2>/dev/null || true
echo -e "${GREEN}   ✅ 屏幕休眠已禁用${NC}"

# ─── 5. 启动 Kiosk 浏览器 ────────────────────────────
echo ""
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}🚀 启动全屏看板: ${SERVICE_URL}${NC}"
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""

# 关闭已有的chromium进程
pkill -f "chromium.*kiosk" 2>/dev/null || true
sleep 1

# 启动浏览器（自动重启）
while true; do
    echo -e "${GREEN}[$(date +%H:%M:%S)] 启动浏览器...${NC}"
    $BROWSER "${SERVICE_URL}" 2>/dev/null || true
    echo -e "${YELLOW}[$(date +%H:%M:%S)] 浏览器退出，5秒后重启...${NC}"
    sleep 5
done
