#!/bin/bash
cd /root/agushare/backend
pkill -f "uvicorn app:app" 2>/dev/null
sleep 1
nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 5000 > /tmp/agushare-backend.log 2>&1 &
echo "Backend started, PID: $!"
