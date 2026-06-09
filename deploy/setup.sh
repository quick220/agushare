#!/bin/bash
# ──────────────────────────────────────────────────────
# A股大屏 - Armbian 一键部署脚本（Systemd + 原生Python）
# 适用于 aarch64 架构的 Armbian 系统
# ──────────────────────────────────────────────────────
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "❌ 请使用 root 用户或 sudo 运行此脚本"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║        A股大屏 - 一键部署脚本             ║"
echo "║        A-Share Big Screen                ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ─── 检测架构 ───────────────────────────────────────
ARCH=$(uname -m)
echo "🔍 检测架构: $ARCH"

# ─── 安装系统依赖 ────────────────────────────────────
echo ""
echo "📦 1/5 安装系统依赖..."

apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx
echo "   ✅ 系统依赖安装完成"

# ─── 安装 Python 依赖 ────────────────────────────────
echo ""
echo "🐍 2/5 安装 Python 依赖..."

cd "$(dirname "$0")/.."
pip3 install -r backend/requirements.txt
echo "   ✅ Python 依赖安装完成"

# ─── 配置 Nginx 反向代理 ─────────────────────────────
echo ""
echo "🔧 3/5 配置 Nginx..."

cp nginx/default.conf /etc/nginx/sites-enabled/agushare 2>/dev/null || \
    cp nginx/default.conf /etc/nginx/conf.d/agushare.conf
systemctl enable nginx
systemctl restart nginx
echo "   ✅ Nginx 已配置（端口 8081）"

# ─── 配置后端 Systemd 服务 ───────────────────────────
echo ""
echo "🚀 4/5 配置后端服务..."

cat > /etc/systemd/system/agushare-backend.service << 'SERVICE'
[Unit]
Description=A股大屏 Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/agushare/backend
ExecStart=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 5000
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable agushare-backend
systemctl restart agushare-backend
echo "   ✅ 后端服务已启动（端口 5000）"

# ─── 安装 kiosk 全屏显示（可选）──────────────────────
echo ""
echo "🖥️  5/5 安装 HDMI 全屏显示..."

if command -v xorg &>/dev/null; then
    echo "   ✅ Xorg 已安装"
else
    echo "   ⚠️  未检测到 Xorg。如需电视全屏显示，请运行："
    echo "      apt install xorg surf xdotool xserver-xorg-video-fbdev"
    echo "      bash deploy/kiosk.sh --install"
fi

# ─── 完成 ────────────────────────────────────────────
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          ✅ 部署完成！                     ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  访问地址：                                ║"
echo "║  http://${IP:-localhost}:8081             ║"
echo "║                                          ║"
echo "║  管理命令：                                ║"
echo "║  systemctl status agushare-backend        ║"
echo "║  systemctl restart agushare-backend       ║"
echo "║  journalctl -u agushare-backend -f        ║"
echo "║                                          ║"
echo "║  电视全屏显示：                             ║"
echo "║  bash deploy/kiosk.sh       启动一次        ║"
echo "║  bash deploy/kiosk.sh --install 开机自启   ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
