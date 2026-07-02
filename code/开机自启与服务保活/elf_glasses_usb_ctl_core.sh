#!/usr/bin/env bash
set -u

USB_LAUNCHER="$HOME/start_voice_assistant_usb.sh"
DASHBOARD_PY="$HOME/ai_dashboard.py"
TUNNEL_SH="$HOME/start_dashboard_tunnel.sh"

USB_LOG="/tmp/voice_assistant_usb.log"
DASHBOARD_LOG="/tmp/ai_dashboard.log"
TUNNEL_NOHUP="/tmp/start_dashboard_tunnel.nohup"

log() {
  echo "[$(date '+%F %T')] $*"
}

is_running() {
  pgrep -f "$1" >/dev/null 2>&1
}

start_one() {
  local name="$1"
  local pattern="$2"
  local cmd="$3"
  local logfile="$4"

  if is_running "$pattern"; then
    log "$name 已运行"
  else
    log "启动 $name"
    nohup bash -lc "$cmd" >> "$logfile" 2>&1 &
    sleep 1
  fi
}

stop_pattern() {
  local name="$1"
  local pattern="$2"

  if is_running "$pattern"; then
    log "停止 $name"
    pkill -f "$pattern" || true
    sleep 1
  else
    log "$name 未运行"
  fi
}

case "${1:-status}" in
  start)
    start_one "USB主控" "elf_glasses_controller_usb.py|video_mode_voice_stop_usb.py|start_voice_assistant_usb.sh" "$USB_LAUNCHER" "$USB_LOG"
    start_one "Dashboard" "python3 .*ai_dashboard.py|python .*ai_dashboard.py" "python3 $DASHBOARD_PY" "$DASHBOARD_LOG"
    start_one "公网隧道" "start_dashboard_tunnel.sh|ssh .*18080:127.0.0.1:8080" "$TUNNEL_SH" "$TUNNEL_NOHUP"
    ;;
  stop)
    stop_pattern "USB主控" "elf_glasses_controller_usb.py|video_mode_voice_stop_usb.py|start_voice_assistant_usb.sh"
    stop_pattern "USB推流管线" "gst-launch-1.0"
    ;;
  restart)
    "$0" stop
    sleep 2
    "$0" start
    ;;
  status)
    echo "== USB branch =="
    if is_running "elf_glasses_controller_usb.py|video_mode_voice_stop_usb.py|start_voice_assistant_usb.sh"; then
      echo "[OK] USB主控运行中"
    else
      echo "[FAIL] USB主控未运行"
    fi

    if is_running "python3 .*ai_dashboard.py|python .*ai_dashboard.py"; then
      echo "[OK] Dashboard运行中"
    else
      echo "[FAIL] Dashboard未运行"
    fi

    if is_running "start_dashboard_tunnel.sh|ssh .*18080:127.0.0.1:8080"; then
      echo "[OK] 公网隧道运行中"
    else
      echo "[FAIL] 公网隧道未运行"
    fi

    echo
    echo "== devices =="
    arecord -l | grep -E "KT USB Audio|Audio" || true
    aplay -l | grep -E "KT USB Audio|Audio" || true
    v4l2-ctl -d /dev/video52 --all 2>/dev/null | head -40 || true

    echo
    echo "公网地址: http://49.232.181.138:18080/"
    ;;
  logs)
    echo "== USB主控日志 =="
    tail -120 "$USB_LOG" 2>/dev/null || true
    echo
    echo "== Dashboard日志 =="
    tail -80 "$DASHBOARD_LOG" 2>/dev/null || true
    echo
    echo "== 隧道日志 =="
    tail -80 /tmp/dashboard_tunnel.log 2>/dev/null || true
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status|logs}"
    exit 2
    ;;
esac
