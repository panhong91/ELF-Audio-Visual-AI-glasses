#!/usr/bin/env bash
set -u

TALKBACK_URL="${TALKBACK_URL:-rtsp://49.232.181.138:8554/glasses_talkback}"
AUDIO_DEVICE="${TALKBACK_AUDIO_DEVICE:-dmix:CARD=Audio,DEV=0}"
GAIN="${TALKBACK_GAIN:-1.2}"
LOG_FILE="${TALKBACK_LOG_FILE:-/tmp/talkback_player_usb.log}"

echo "[talkback-usb] start: $(date)" >> "$LOG_FILE"
echo "[talkback-usb] url=$TALKBACK_URL device=$AUDIO_DEVICE gain=$GAIN" >> "$LOG_FILE"

while true; do
  gst-launch-1.0 -q \
    rtspsrc location="$TALKBACK_URL" protocols=tcp latency=80 timeout=5000000 ! \
    rtpopusdepay ! opusdec ! audioconvert ! audioresample ! \
    volume volume="$GAIN" ! \
    alsasink device="$AUDIO_DEVICE" sync=false >> "$LOG_FILE" 2>&1

  echo "[talkback-usb] disconnected: $(date), retry in 2s" >> "$LOG_FILE"
  sleep 2
done
