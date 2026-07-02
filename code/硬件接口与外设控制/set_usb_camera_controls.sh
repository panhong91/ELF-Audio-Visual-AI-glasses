#!/usr/bin/env bash
set -u

DEV="${USB_CAMERA_DEVICE:-/dev/video52}"

if [ ! -e "$DEV" ]; then
  echo "[usb-camera] device not found: $DEV"
  exit 0
fi

echo "[usb-camera] apply controls to $DEV"

v4l2-ctl -d "$DEV" --set-ctrl=power_line_frequency=1 || true
v4l2-ctl -d "$DEV" --set-ctrl=auto_exposure=3 || true
v4l2-ctl -d "$DEV" --set-ctrl=exposure_dynamic_framerate=1 || true
v4l2-ctl -d "$DEV" --set-ctrl=backlight_compensation=1 || true
v4l2-ctl -d "$DEV" --set-ctrl=gain=0 || true
v4l2-ctl -d "$DEV" --set-ctrl=sharpness=3 || true

v4l2-ctl -d "$DEV" --get-ctrl=power_line_frequency || true
v4l2-ctl -d "$DEV" --get-ctrl=auto_exposure || true
v4l2-ctl -d "$DEV" --get-ctrl=exposure_dynamic_framerate || true
v4l2-ctl -d "$DEV" --get-ctrl=backlight_compensation || true
v4l2-ctl -d "$DEV" --get-ctrl=gain || true
v4l2-ctl -d "$DEV" --get-ctrl=sharpness || true
