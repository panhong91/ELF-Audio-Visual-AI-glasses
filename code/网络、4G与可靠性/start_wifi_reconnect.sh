#!/usr/bin/env bash
set -u

SERVER="${SERVER:-49.232.181.138}"
WIFI_IF="${WIFI_IF:-p2p0}"
LTE_IF="${LTE_IF:-wwan0}"
CONNECT_BIN="${CONNECT_BIN:-/usr/bin/cmddemo_wifi.sh}"
CONFIG_FILE="${CONFIG_FILE:-/home/elf/.config/elf_glasses_wifi_reconnect.conf}"
LOG="${LOG:-/tmp/start_wifi_reconnect.log}"
INTERVAL="${INTERVAL:-15}"
COOLDOWN="${COOLDOWN:-120}"

WIFI_SSID=""
WIFI_PASSWORD=""

log(){ echo "[$(date '+%F %T')] [wifi-reconnect] $*" | tee -a "$LOG"; }

[ -f "$CONFIG_FILE" ] && . "$CONFIG_FILE"

route_dev(){
  ip route get "$SERVER" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}'
}

has_ipv4(){
  ip -4 addr show dev "$1" 2>/dev/null | grep -q 'inet '
}

reachable(){
  has_ipv4 "$1" && ping -I "$1" -c 1 -W 2 "$SERVER" >/dev/null 2>&1
}

reconnect_wifi(){
  if [ -z "${WIFI_SSID:-}" ] || [ -z "${WIFI_PASSWORD:-}" ]; then
    log "missing WIFI_SSID/WIFI_PASSWORD in $CONFIG_FILE"
    return 1
  fi
  if [ ! -x "$CONNECT_BIN" ]; then
    log "connect tool missing: $CONNECT_BIN"
    return 1
  fi
  log "run: $CONNECT_BIN -s $WIFI_SSID"
  "$CONNECT_BIN" -s "$WIFI_SSID" -p "$WIFI_PASSWORD" >>"$LOG" 2>&1
}

run_once(){
  dev="$(route_dev)"
  if reachable "$WIFI_IF"; then
    [ "$dev" != "$WIFI_IF" ] && log "wifi reachable, current route=$dev"
    return 0
  fi

  if reachable "$LTE_IF"; then lte="reachable"; else lte="not-reachable"; fi
  if has_ipv4 "$WIFI_IF"; then
    log "wifi has ipv4 but server not reachable, route=${dev:-none}, lte=$lte, try reconnect"
  else
    log "wifi has no ipv4, route=${dev:-none}, lte=$lte, try reconnect"
  fi
  reconnect_wifi
}

case "${1:-run}" in
  once) run_once ;;
  run)
    log "start: server=$SERVER wifi=$WIFI_IF lte=$LTE_IF config=$CONFIG_FILE"
    last=0
    while true; do
      if ! reachable "$WIFI_IF"; then
        now="$(date +%s)"
        if [ $((now-last)) -ge "$COOLDOWN" ]; then
          run_once || true
          last="$now"
        fi
      fi
      sleep "$INTERVAL"
    done
    ;;
  *) echo "usage: $0 [run|once]" >&2; exit 2 ;;
esac
