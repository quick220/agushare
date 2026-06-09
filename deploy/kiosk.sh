#!/bin/bash
# Agushare Kiosk - v8 (continuous resize for late-arriving child windows)
URL="http://localhost:8081"

killall Xorg 2>/dev/null; sleep 2

X :0 vt1 -keeptty &
for i in $(seq 1 20); do
    [ -f /tmp/.X0-lock ] && break
    sleep 1
done
export DISPLAY=:0

# ─── 防休眠心跳（每55秒微移鼠标）──────────────────
(while true; do
    sleep 55
    DISPLAY=:0 xdotool mousemove_relative 1 0 2>/dev/null
    DISPLAY=:0 xdotool mousemove_relative -1 0 2>/dev/null
    echo "[kiosk] keepalive ping"
done) &
KEEPER_PID=$!
trap "kill $KEEPER_PID 2>/dev/null; exit" SIGTERM SIGINT

while true; do
    killall surf 2>/dev/null; sleep 1
    /usr/bin/surf -db "$URL" &
    SURF_PID=$!
    echo "[kiosk] surf PID=$SURF_PID"

    # Keep resizing for up to 15 seconds (catches late child windows)
    for second in $(seq 1 15); do
        sleep 1
        ALL_WINS=$(xdotool search --pid $SURF_PID 2>/dev/null)
        if [ -z "$ALL_WINS" ]; then continue; fi
        COUNT=0
        for wid in $ALL_WINS; do
            xdotool windowmove $wid 0 0 windowsize $wid 1920 1080 2>/dev/null && COUNT=$((COUNT+1))
        done
        echo "[kiosk] second $second: resized $COUNT windows"
    done

    wait $SURF_PID 2>/dev/null
    echo "[kiosk] surf exited, restarting..."
    sleep 2
done
