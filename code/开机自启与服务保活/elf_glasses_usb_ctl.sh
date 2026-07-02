#!/usr/bin/env bash
# ELF_USB_CTL_WRAPPER_TALKBACK
set -u

CORE="$HOME/elf_glasses_usb_ctl_core.sh"
TALKBACK="$HOME/talkback_player_usb.sh"
TALKBACK_LOG="/tmp/talkback_player_usb.log"
TALKBACK_NOHUP="/tmp/talkback_player_usb.nohup"

log() {
  echo "[$(date '+%F %T')] $*"
}

talkback_running() {
  pgrep -f "$TALKBACK" >/dev/null 2>&1
}

start_talkback() {
  if [ ! -x "$TALKBACK" ]; then
    log "USB对讲播放器不存在或不可执行: $TALKBACK"
    return 0
  fi

  if talkback_running; then
    log "USB对讲播放器 已运行"
    return 0
  fi

  log "启动 USB对讲播放器"
  nohup "$TALKBACK" >"$TALKBACK_NOHUP" 2>&1 &
  sleep 1

  if talkback_running; then
    log "USB对讲播放器 启动成功"
  else
    log "USB对讲播放器 启动失败，查看: $TALKBACK_LOG"
  fi
}

stop_talkback() {
  if talkback_running || pgrep -f "gst-launch.*glasses_talkback" >/dev/null 2>&1; then
    log "停止 USB对讲播放器"
  else
    log "USB对讲播放器 未运行"
  fi

  pkill -TERM -f "$TALKBACK" 2>/dev/null || true
  pkill -TERM -f "gst-launch.*glasses_talkback" 2>/dev/null || true
  sleep 1
  pkill -KILL -f "$TALKBACK" 2>/dev/null || true
  pkill -KILL -f "gst-launch.*glasses_talkback" 2>/dev/null || true
}

status_talkback() {
  echo
  echo "== talkback =="
  if talkback_running; then
    echo "[OK] USB对讲播放器运行中"
  else
    echo "[WARN] USB对讲播放器未运行"
  fi

  if pgrep -f "gst-launch.*glasses_talkback" >/dev/null 2>&1; then
    echo "[OK] glasses_talkback 拉流进程运行中"
  else
    echo "[WARN] glasses_talkback 当前未拉到流或正在等待浏览器开始对讲"
  fi
}

if [ ! -x "$CORE" ]; then
  echo "原始控制脚本不存在或不可执行: $CORE"
  exit 1
fi

cmd="${1:-status}"
shift || true

case "$cmd" in
  start)
    "$CORE" start "$@"
    start_talkback
    ;;
  stop)
    stop_talkback
    "$CORE" stop "$@"
    ;;
  restart)
    stop_talkback
    "$CORE" restart "$@"
    start_talkback
    ;;
  status)
    "$CORE" status "$@"
    status_talkback
    ;;
  logs)
    "$CORE" logs "$@" || true
    echo
    echo "== talkback logs =="
    tail -n "${1:-80}" "$TALKBACK_LOG" 2>/dev/null || echo "暂无 USB 对讲日志"
    ;;
  *)
    "$CORE" "$cmd" "$@"
    ;;
esac
