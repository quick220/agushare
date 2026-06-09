#!/bin/bash
# ──────────────────────────────────────────────────────
# A股大屏 - Armbian 一键部署脚本
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
if [ "$ARCH" != "aarch64" ]; then
    echo "⚠️  非 ARM64 架构，Podman 镜像可能需要额外配置"
fi

# ─── 安装 Podman ────────────────────────────────────
echo ""
echo "📦 1/5 安装 Podman & podman-compose..."

if ! command -v podman &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq podman podman-compose
    echo "   ✅ Podman 已安装: $(podman --version)"
else
    echo "   ✅ Podman 已存在: $(podman --version)"
fi

if ! command -v podman-compose &>/dev/null; then
    pip3 install podman-compose 2>/dev/null || apt-get install -y -qq podman-compose
fi

# ─── 配置 Podman Rootless 兼容 ──────────────────────
echo ""
echo "🔧 2/5 配置 Podman..."

# 确保使用 crun 运行时（更轻量）
if podman info 2>/dev/null | grep -q "ociRuntime"; then
    CURRENT_RUNTIME=$(podman info 2>/dev/null | grep -A1 "ociRuntime" | grep "name" | awk -F'"' '{print $2}')
    echo "   当前 OCI 运行时: ${CURRENT_RUNTIME:-默认}"
fi

# 启用 Podman socket（供 podman-compose 使用）
systemctl enable --now podman.socket 2>/dev/null || true

# ─── 拉取镜像 ────────────────────────────────────────
echo ""
echo "🐳 3/5 拉取 & 构建镜像（首次可能较慢）..."

cd "$(dirname "$0")/.."

echo "   → 构建 backend 镜像..."
podman build -t agushare-backend:latest ./backend

echo "   → 拉取 nginx:alpine-slim..."
podman pull docker.io/nginx:alpine-slim

# ─── SELinux 处理 ────────────────────────────────────
echo ""
echo "🛡️  4/5 处理 SELinux 权限..."

if command -v getenforce &>/dev/null; then
    if [ "$(getenforce)" = "Enforcing" ]; then
        echo "   ⚠️  SELinux 为 Enforcing 模式，设置 volume 上下文..."
        chcon -Rt container_file_t ./frontend 2>/dev/null || true
        chcon -Rt container_file_t ./nginx 2>/dev/null || true
        echo "   ✅ SELinux 上下文已设置"
    else
        echo "   ✅ SELinux 未启用，跳过"
    fi
else
    echo "   ✅ SELinux 不可用，跳过"
fi

# ─── 启动服务 ────────────────────────────────────────
echo ""
echo "🚀 5/5 启动 A股大屏服务..."

podman-compose down 2>/dev/null || true
podman-compose up -d

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          ✅ 部署完成！                     ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  访问地址：                                ║"
echo "║  http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080    ║"
echo "║                                          ║"
echo "║  管理命令：                                ║"
echo "║  podman-compose logs -f  查看日志          ║"
echo "║  podman-compose down     停止服务          ║"
echo "║  podman-compose up -d    启动服务          ║"
echo "║  podman-compose restart 重启服务           ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
