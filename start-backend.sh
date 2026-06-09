#!/bin/bash
# 推荐使用 systemd 管理后端，而非此脚本
# systemctl restart agushare-backend
# systemctl status agushare-backend

# 如需手动启动（无 systemd 环境）：
DIR="$(cd "$(dirname "$0")" && pwd)"
pkill -f "uvicorn app:app" 2>/dev/null
sleep 1
cd "$DIR/backend"
nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 5000 > /tmp/agushare-backend.log 2>&1 &
echo "Backend started, PID: $!"
echo "Log: tail -f /tmp/agushare-backend.log"
