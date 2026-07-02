#!/usr/bin/env bash
set -u

TEXT="$*"
[ -n "$TEXT" ] || exit 0

export HOME=/home/elf
export XDG_RUNTIME_DIR=/run/user/1000

PYTHON="/home/elf/venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"

cd /home/elf/audio_module || exit 1

"$PYTHON" - "$TEXT" <<'PY'
import sys
from pathlib import Path

text = sys.argv[1].strip()
if not text:
    raise SystemExit(0)

sys.path.insert(0, "/home/elf/audio_module")

try:
    import elf_glasses_controller_usb as ctl
    ctl.say(text)
except Exception as e:
    print(f"[say_usb] failed: {e}", flush=True)
    raise
PY
