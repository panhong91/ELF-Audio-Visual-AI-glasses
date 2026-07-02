#!/usr/bin/env bash
set -u

REMOTE_HOST="${REMOTE_HOST:-49.232.181.138}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_PORT="${REMOTE_PORT:-18080}"
LOCAL_HOST="${LOCAL_HOST:-127.0.0.1}"
LOCAL_PORT="${LOCAL_PORT:-8080}"
KEY="${KEY:-/home/elf/.ssh/dashboard_tunnel_ed25519}"
LOG="${LOG:-/tmp/dashboard_tunnel.log}"

log() {
  echo "[tunnel] $*" | tee -a "$LOG"
}

cleanup_remote_port() {
  log "cleanup remote ${REMOTE_HOST}:${REMOTE_PORT}"

  ssh -i "$KEY" \
    -o BatchMode=yes \
    -o ConnectTimeout=8 \
    -o ServerAliveInterval=10 \
    -o ServerAliveCountMax=2 \
    "${REMOTE_USER}@${REMOTE_HOST}" \
    "pids=\$(ss -lntp 2>/dev/null | awk '\$4 ~ /:${REMOTE_PORT}\$/ && \$0 ~ /sshd/ {print}' | sed -n 's/.*pid=\\([0-9][0-9]*\\).*/\\1/p' | sort -u); if [ -n \"\$pids\" ]; then echo \"kill old tunnel pid(s): \$pids\"; kill \$pids; else echo \"no old tunnel on ${REMOTE_PORT}\"; fi" \
    >>"$LOG" 2>&1 || true
}

log "start: $(date)"

while true; do
  cleanup_remote_port
  sleep 1

  log "connecting ${REMOTE_USER}@${REMOTE_HOST}, ${REMOTE_PORT} -> ${LOCAL_HOST}:${LOCAL_PORT} at $(date)"

  ssh -i "$KEY" \
    -N -T \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -R "0.0.0.0:${REMOTE_PORT}:${LOCAL_HOST}:${LOCAL_PORT}" \
    "${REMOTE_USER}@${REMOTE_HOST}" \
    >>"$LOG" 2>&1

  log "disconnected at $(date), retry in 5s"
  sleep 5
done
