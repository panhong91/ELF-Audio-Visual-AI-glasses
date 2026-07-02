#!/usr/bin/env bash
set -u

CTL="$HOME/elf_glasses_usb_ctl.sh"
PID_FILE="/tmp/elf_glasses_usb_watchdog.pid"
LOG_FILE="/tmp/elf_glasses_usb_watchdog.log"
DISABLE_FILE="/tmp/elf_glasses_usb_watchdog.disabled"

INTERVAL="${WATCHDOG_INTERVAL:-15}"
COOLDOWN="${WATCHDOG_COOLDOWN:-30}"

log() {
  echo "[$(date '+%F %T')] $*" >> "$LOG_FILE"
}

pid_alive() {
  [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null
}

read_pid() {
  [ -f "$PID_FILE" ] && cat "$PID_FILE" 2>/dev/null || true
}

controller_ok() {
  pgrep -f "$HOME/audio_module/elf_glasses_controller_usb.py" >/dev/null 2>&1
}

dashboard_ok() {
  python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/", timeout=3).read(1)' >/dev/null 2>&1
}

tunnel_ok() {
  pgrep -f "$HOME/start_dashboard_tunnel.sh" >/dev/null 2>&1 &&
  pgrep -f 'ssh .*18080:127.0.0.1:8080' >/dev/null 2>&1
}

kill_pattern() {
  name="$1"
  pattern="$2"

  if pgrep -f "$pattern" >/dev/null 2>&1; then
    log "fallback stop: $name"
    pkill -TERM -f "$pattern" 2>/dev/null || true
    sleep 1
  fi

  if pgrep -f "$pattern" >/dev/null 2>&1; then
    log "fallback force stop: $name"
    pkill -KILL -f "$pattern" 2>/dev/null || true
  fi
}

run_loop() {
  if [ ! -x "$CTL" ]; then
    log "ERROR: 控制脚本不存在或不可执行: $CTL"
    exit 1
  fi

  old_pid="$(read_pid)"
  if pid_alive "$old_pid" && [ "$old_pid" != "$$" ]; then
    log "watchdog already running: pid=$old_pid"
    exit 0
  fi

  rm -f "$DISABLE_FILE"
  echo "$$" > "$PID_FILE"
  trap 'rm -f "$PID_FILE"; log "watchdog exit"; exit 0' INT TERM EXIT

  log "watchdog started, interval=${INTERVAL}s, cooldown=${COOLDOWN}s"

  last_state=""
  last_start=0

  while true; do
    if [ -f "$DISABLE_FILE" ]; then
      sleep "$INTERVAL"
      continue
    fi

    missing=""
    controller_ok || missing="$missing USB主控"
    dashboard_ok || missing="$missing Dashboard"
    tunnel_ok || missing="$missing 公网隧道"

    state="${missing:-OK}"
    if [ "$state" != "$last_state" ]; then
      log "state: $state"
      last_state="$state"
    fi

    if [ -n "$missing" ]; then
      now="$(date +%s)"
      if [ $((now - last_start)) -ge "$COOLDOWN" ]; then
        log "missing:$missing -> run: $CTL start"
        "$CTL" start >> "$LOG_FILE" 2>&1
        last_start="$now"
      fi
    fi

    sleep "$INTERVAL"
  done
}

start_watchdog_only() {
  rm -f "$DISABLE_FILE"

  pid="$(read_pid)"
  if pid_alive "$pid"; then
    echo "USB watchdog 已运行: pid=$pid"
    return 0
  fi

  rm -f "$PID_FILE"
  nohup "$0" run >/tmp/elf_glasses_usb_watchdog.nohup 2>&1 &
  sleep 1

  pid="$(read_pid)"
  if pid_alive "$pid"; then
    echo "USB watchdog 启动成功: pid=$pid"
  else
    echo "USB watchdog 启动失败，查看日志: $LOG_FILE"
    return 1
  fi
}

stop_watchdog_only() {
  touch "$DISABLE_FILE"

  pid="$(read_pid)"
  if pid_alive "$pid"; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    if pid_alive "$pid"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "USB watchdog 已停止"
  else
    rm -f "$PID_FILE"
    echo "USB watchdog 未运行"
  fi
}

start_stack() {
  rm -f "$DISABLE_FILE"

  if [ ! -x "$CTL" ]; then
    echo "控制脚本不存在或不可执行: $CTL"
    exit 1
  fi

  echo "启动 USB 完整链路..."
  "$CTL" start

  start_watchdog_only
}

stop_stack() {
  touch "$DISABLE_FILE"

  stop_watchdog_only

  echo "停止 USB 完整链路..."
  if [ -x "$CTL" ]; then
    "$CTL" stop
  fi

  sleep 1

  kill_pattern "USB主控" "$HOME/audio_module/elf_glasses_controller_usb.py"
  kill_pattern "USB视频控制" "$HOME/rknn_demo/video_mode_voice_stop_usb.py"
  kill_pattern "USB推流管线" "glasses_unified"
  kill_pattern "Dashboard" "$HOME/ai_dashboard.py"
  kill_pattern "公网隧道脚本" "$HOME/start_dashboard_tunnel.sh"
  kill_pattern "公网隧道SSH" "ssh .*18080:127.0.0.1:8080"

  echo "USB 完整链路已停止"
}

status_stack() {
  pid="$(read_pid)"
  if pid_alive "$pid"; then
    echo "[OK] USB watchdog 运行中: pid=$pid"
  else
    echo "[WARN] USB watchdog 未运行"
  fi

  controller_ok && echo "[OK] USB主控" || echo "[WARN] USB主控缺失"
  dashboard_ok && echo "[OK] Dashboard" || echo "[WARN] Dashboard不可访问"
  tunnel_ok && echo "[OK] 公网隧道" || echo "[WARN] 公网隧道缺失"
}

case "${1:-start}" in
  run)
    run_loop
    ;;
  start)
    start_stack
    ;;
  stop)
    stop_stack
    ;;
  restart)
    stop_stack
    sleep 1
    start_stack
    ;;
  status)
    status_stack
    ;;
  logs)
    tail -n "${2:-120}" "$LOG_FILE"
    ;;
  stop-watchdog)
    stop_watchdog_only
    ;;
  stop-all)
    stop_stack
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status|logs|stop-watchdog}"
    exit 1
    ;;
esac
