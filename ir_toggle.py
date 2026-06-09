#!/usr/bin/env python3
"""
红外遥控器开关A股看板显示 (使用ir-ctl)
- 自动设置NEC协议
- 监听 /dev/lirc0 解码NEC信号
- Power键 (nec:0x22dc) 切换agushare-kiosk显示
"""
import subprocess
import time
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('ir_toggle')

SCANCODE = 0x22dc  # Power键 scancode
DEBOUNCE = 2       # 防抖秒数

last_toggle = 0


def setup_nec_protocol():
    """设置接收器为NEC协议"""
    try:
        subprocess.run(['bash', '-c', 'echo nec > /sys/class/rc/rc1/protocols 2>/dev/null'], 
                      capture_output=True, timeout=3)
        result = subprocess.run(['cat', '/sys/class/rc/rc1/protocols'],
                               capture_output=True, text=True, timeout=3)
        if 'nec' in result.stdout:
            log.info(f"✅ NEC协议已设置: {result.stdout.strip()}")
            return True
        else:
            log.warning(f"⚠️ NEC协议设置失败: {result.stdout.strip()}")
            return False
    except Exception as e:
        log.warning(f"⚠️ 设置NEC协议失败: {e}")
        return False


def decode_nec_scan(line):
    """解析ir-ctl输出的脉冲串，返回scancode或None"""
    parts = line.strip().split()
    if not parts:
        return None
    
    vals = []
    for i, p in enumerate(parts):
        p = p.strip()
        if p.startswith('+'):
            try:
                pulse = int(p[1:])
            except ValueError:
                continue
            if i + 1 < len(parts) and parts[i+1].startswith('-'):
                try:
                    space = int(parts[i+1][1:])
                except ValueError:
                    continue
                if pulse > 8000 and 4000 < space < 5000:
                    # NEC leader code
                    vals = []
                    continue
                if 400 < pulse < 800:
                    if 400 < space < 800:
                        vals.append(0)
                    elif 1200 < space < 2200:
                        vals.append(1)
    
    if len(vals) < 32:
        return None
    
    addr = sum(vals[i] << i for i in range(8))
    cmd = sum(vals[16+i] << i for i in range(8))
    addr_inv = sum(vals[8+i] << i for i in range(8))
    cmd_inv = sum(vals[24+i] << i for i in range(8))
    
    if addr + addr_inv == 0xFF and cmd + cmd_inv == 0xFF:
        return (addr << 8) | cmd
    return None


def is_surf_running():
    try:
        r = subprocess.run(['pgrep', '-x', 'surf'], capture_output=True, text=True)
        return r.returncode == 0
    except:
        return False


def toggle_display():
    global last_toggle
    now = time.time()
    if now - last_toggle < DEBOUNCE:
        log.info("🛡️ 防抖 - 忽略")
        return
    last_toggle = now
    
    if is_surf_running():
        log.info("🔴 关闭A股看板显示")
        subprocess.run(['systemctl', 'stop', 'agushare-kiosk'], capture_output=True)
        time.sleep(2)
        if is_surf_running():
            subprocess.run(['pkill', '-9', '-x', 'surf'], capture_output=True)
            subprocess.run(['pkill', '-9', '-x', 'Xorg'], capture_output=True)
        log.info("✅ 显示已关闭")
    else:
        log.info("🟢 启动A股看板显示")
        subprocess.run(['systemctl', 'start', 'agushare-kiosk'], capture_output=True)
        time.sleep(3)
        if is_surf_running():
            log.info("✅ 显示已启动")
        else:
            log.warning("⚠️ 显示启动可能失败，surf未运行")


def listen():
    log.info("📡 红外监听已启动，按遥控器Power键切换显示...")
    
    try:
        proc = subprocess.Popen(
            ['ir-ctl', '-r', '-d', '/dev/lirc0'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True
        )
    except FileNotFoundError:
        log.error("❌ ir-ctl 未找到，请安装 v4l-utils")
        return
    
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            code = decode_nec_scan(line)
            if code == SCANCODE:
                log.info(f"📡 收到Power键 (nec:0x{code:04x})")
                toggle_display()
    except Exception as e:
        log.error(f"监听错误: {e}")
    finally:
        if proc.poll() is None:
            proc.terminate()


if __name__ == '__main__':
    log.info("===== IR Toggle Service Starting =====")
    
    # 启动时设置NEC协议
    setup_nec_protocol()
    
    # 持续监听循环
    while True:
        try:
            listen()
        except FileNotFoundError:
            log.error("❌ ir-ctl 未找到，请安装 v4l-utils")
            time.sleep(30)
        except Exception as e:
            log.error(f"❌ 错误: {e}")
            time.sleep(5)
