#!/usr/bin/env python3
import os
import time

class ButtonPoller:
    def __init__(self, pins, debounce_sec=0.08, cooldown_sec=0.35):
        self.pins = pins
        self.debounce_sec = debounce_sec
        self.cooldown_sec = cooldown_sec
        self.last_value = {}
        self.last_event = {}

        for name, pin in pins.items():
            if self._ensure_gpio(pin):
                self.last_value[name] = self._read(pin)
                self.last_event[name] = 0.0
            else:
                print(f"[BUTTON] GPIO{pin} 不可用，{name} 按钮禁用", flush=True)

    def _path(self, pin):
        return f"/sys/class/gpio/gpio{pin}"

    def _ensure_gpio(self, pin):
        path = self._path(pin)

        if not os.path.isdir(path):
            try:
                with open("/sys/class/gpio/export", "w") as f:
                    f.write(str(pin))
                time.sleep(0.1)
            except PermissionError:
                print(f"[BUTTON] 无权限导出 GPIO{pin}，请先运行 sudo ~/setup_buttons_gpio.sh", flush=True)
                return False
            except OSError as e:
                print(f"[BUTTON] 导出 GPIO{pin} 失败: {e}", flush=True)
                return False

        try:
            with open(f"{path}/direction", "w") as f:
                f.write("in")
        except PermissionError:
            pass
        except OSError:
            pass

        try:
            self._read(pin)
            return True
        except OSError as e:
            print(f"[BUTTON] 读取 GPIO{pin} 失败: {e}", flush=True)
            return False

    def _read(self, pin):
        with open(f"{self._path(pin)}/value", "r") as f:
            return int(f.read().strip())

    def poll(self):
        actions = []
        now = time.monotonic()

        for name, pin in self.pins.items():
            if name not in self.last_value:
                continue

            try:
                value = self._read(pin)
            except OSError:
                continue

            if self.last_value[name] == 1 and value == 0:
                if now - self.last_event[name] >= self.cooldown_sec:
                    time.sleep(self.debounce_sec)
                    try:
                        if self._read(pin) == 0:
                            actions.append(name)
                            self.last_event[name] = time.monotonic()
                    except OSError:
                        pass

            self.last_value[name] = value

        return actions
