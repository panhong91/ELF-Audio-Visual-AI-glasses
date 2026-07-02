#!/usr/bin/env bash
set -u

CONF="${CONF:-/home/elf/.config/elf_glasses_button_recovery.conf}"
[ -r "$CONF" ] && . "$CONF"

GPIO="${RECOVERY_GPIO:-228}"
PRESSED_VALUE="${PRESSED_VALUE:-0}"
HOLD_SECONDS="${HOLD_SECONDS:-5}"
SERVICE="${SERVICE:-elf-glasses-usb-watchdog.service}"
LOG="${LOG:-/tmp/elf_glasses_button_recovery.log}"

log() {
  echo "[$(date '+%F %T')] [button-recovery] $*" | tee -a "$LOG"
}

say_recovery() {
  text="$1"

  if [ -x /home/elf/say_usb.sh ]; then
    /home/elf/say_usb.sh "$text" || true
    return
  fi

  if [ -x /home/elf/usb_say.sh ]; then
    /home/elf/usb_say.sh "$text" || true
    return
  fi

  if command -v espeak-ng >/dev/null 2>&1; then
    espeak-ng -v zh "$text" >/dev/null 2>&1 || true
    return
  fi

  log "no tts command found, skip say: $text"
}

ensure_gpio() {
  if [ ! -e "/sys/class/gpio/gpio$GPIO/value" ]; then
    echo "$GPIO" > /sys/class/gpio/export 2>/dev/null || true
    sleep 0.2
  fi
  echo in > "/sys/class/gpio/gpio$GPIO/direction" 2>/dev/null || true
}

read_value() {
  cat "/sys/class/gpio/gpio$GPIO/value" 2>/dev/null || echo ""
}

run_loop() {
  ensure_gpio
  log "start: gpio=$GPIO pressed=$PRESSED_VALUE hold=${HOLD_SECONDS}s service=$SERVICE"

  pressed_since=0
  fired=0

  while true; do
    ensure_gpio
    v="$(read_value)"
    now="$(date +%s)"

    if [ "$v" = "$PRESSED_VALUE" ]; then
      if [ "$pressed_since" -eq 0 ]; then
        pressed_since="$now"
        fired=0
        log "button pressed"
      fi

      elapsed=$((now - pressed_since))
      if [ "$fired" -eq 0 ] && [ "$elapsed" -ge "$HOLD_SECONDS" ]; then
        fired=1
        log "long press detected, restarting $SERVICE"
        say_recovery "正在恢复视频服务"

        systemctl restart "$SERVICE"
        rc=$?

        if [ "$rc" -eq 0 ]; then
          log "restart finished, code=0"
          say_recovery "恢复完成"
        else
          log "restart failed, code=$rc"
          say_recovery "恢复失败"
        fi
      fi
    else
      pressed_since=0
      fired=0
    fi

    sleep 0.1
  done
}

case "${1:-run}" in
  run) run_loop ;;
  once)
    ensure_gpio
    echo "gpio=$GPIO value=$(read_value) pressed_value=$PRESSED_VALUE"
    ;;
  *) echo "usage: $0 {run|once}" >&2; exit 2 ;;
esac
