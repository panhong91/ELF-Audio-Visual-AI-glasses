#!/usr/bin/env bash
set -e

source "$HOME/venv/bin/activate"

export WAKE_GAIN="${WAKE_GAIN:-4.0}"
export COMMAND_GAIN=4.0
export STREAM_VOLUME="${STREAM_VOLUME:-4.0}"
export AUDIO_DEVICE="plughw:CARD=Audio,DEV=0"
export TTS_DEVICE="dmix:CARD=Audio,DEV=0"
export TTS_VOLUME="0.45"

bash "$HOME/set_usb_camera_controls.sh"

if [ -x "$HOME/setup_buttons_gpio.sh" ]; then
  sudo -n "$HOME/setup_buttons_gpio.sh" 2>/tmp/elf_buttons_gpio_setup.err || \
    echo "[WARN] 按钮GPIO未初始化；如按钮无效，请运行: sudo $HOME/setup_buttons_gpio.sh"
fi

python "$HOME/audio_module/elf_glasses_controller_usb.py"
