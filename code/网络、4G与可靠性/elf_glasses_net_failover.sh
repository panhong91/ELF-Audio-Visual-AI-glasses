#!/usr/bin/env bash
set -u

SERVER="${SERVER:-49.232.181.138}"
WIFI_IF="${WIFI_IF:-p2p0}"
LTE_IF="${LTE_IF:-wwan0}"
QMI_DEV="${QMI_DEV:-/dev/cdc-wdm0}"
APN="${APN:-ctnet}"
INTERVAL="${INTERVAL:-8}"
LOG="${LOG:-/tmp/elf_glasses_net_failover.log}"

log() {
  echo "[$(date '+%F %T')] $*" | tee -a "$LOG"
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

link_exists() {
  [ -e "/sys/class/net/$1" ]
}

has_ipv4() {
  ip -4 addr show dev "$1" 2>/dev/null | grep -q 'inet '
}

gw_for() {
  ip route show default dev "$1" 2>/dev/null | awk '
    /default/ {
      for (i=1; i<=NF; i++) {
        if ($i=="via") {
          print $(i+1)
          exit
        }
      }
    }'
}

route_dev() {
  ip route get "$SERVER" 2>/dev/null | awk '
    {
      for (i=1; i<=NF; i++) {
        if ($i=="dev") {
          print $(i+1)
          exit
        }
      }
    }'
}

normalize_default_routes() {
  local wifi_gw lte_gw
  wifi_gw="$(gw_for "$WIFI_IF")"
  lte_gw="$(gw_for "$LTE_IF")"

  if [ -n "$wifi_gw" ]; then
    ip route replace default via "$wifi_gw" dev "$WIFI_IF" metric 100 2>/dev/null || true
  fi

  if [ -n "$lte_gw" ]; then
    ip route replace default via "$lte_gw" dev "$LTE_IF" metric 700 2>/dev/null || true
  fi
}

route_server_via() {
  local iface="$1"
  local gw
  gw="$(gw_for "$iface")"

  if [ -n "$gw" ]; then
    ip route replace "$SERVER/32" via "$gw" dev "$iface"
  else
    ip route replace "$SERVER/32" dev "$iface"
  fi
}

ensure_lte() {
  link_exists "$LTE_IF" || {
    log "4G接口不存在: $LTE_IF"
    return 1
  }

  if has_ipv4 "$LTE_IF"; then
    return 0
  fi

  has_cmd qmicli || {
    log "缺少 qmicli，无法QMI拨号"
    return 1
  }

  ip link set "$LTE_IF" down 2>/dev/null || true

  if [ -e "/sys/class/net/$LTE_IF/qmi/raw_ip" ]; then
    echo Y > "/sys/class/net/$LTE_IF/qmi/raw_ip" 2>/dev/null || true
  fi

  ip link set "$LTE_IF" up 2>/dev/null || true

  log "开始4G拨号: apn=$APN"
  qmicli -d "$QMI_DEV" --device-open-proxy \
    --wds-start-network="apn=$APN,ip-type=4" \
    --client-no-release-cid >>"$LOG" 2>&1 || true

  if has_cmd udhcpc; then
    udhcpc -i "$LTE_IF" -q -n -t 5 -T 3 >>"$LOG" 2>&1 || true
  elif has_cmd busybox; then
    busybox udhcpc -i "$LTE_IF" -q -n -t 5 -T 3 >>"$LOG" 2>&1 || true
  else
    log "缺少 udhcpc，无法给4G接口获取IP"
    return 1
  fi

  has_ipv4 "$LTE_IF"
}

probe_if() {
  local iface="$1"

  link_exists "$iface" || return 1
  has_ipv4 "$iface" || return 1
  ping -I "$iface" -c 1 -W 2 "$SERVER" >/dev/null 2>&1
}

choose_once() {
  local old new

  ensure_lte || true
  normalize_default_routes

  old="$(route_dev)"

  if probe_if "$WIFI_IF"; then
    route_server_via "$WIFI_IF"
    new="$(route_dev)"
    if [ "$old" != "$new" ]; then
      log "切换项目服务器路由: ${old:-none} -> $new，WiFi优先"
    fi
    return 0
  fi

  if probe_if "$LTE_IF"; then
    route_server_via "$LTE_IF"
    new="$(route_dev)"
    if [ "$old" != "$new" ]; then
      log "切换项目服务器路由: ${old:-none} -> $new，4G兜底"
    fi
    return 0
  fi

  log "WiFi和4G都无法访问 $SERVER，保持当前路由: ${old:-none}"
  return 1
}

case "${1:-run}" in
  once)
    choose_once
    ;;
  run)
    log "启动网络切换守护: server=$SERVER wifi=$WIFI_IF lte=$LTE_IF apn=$APN"
    while true; do
      choose_once
      sleep "$INTERVAL"
    done
    ;;
  *)
    echo "usage: $0 [run|once]" >&2
    exit 2
    ;;
esac
