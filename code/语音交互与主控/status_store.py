#!/usr/bin/env python3
import json
import os
import time
from pathlib import Path

STATUS_PATH = Path("/home/elf/ai_status.json")


def now_text():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def update_status(**kwargs):
    data = {}

    if STATUS_PATH.exists():
        try:
            data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data.update(kwargs)
    data["updated_at"] = now_text()

    tmp = STATUS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATUS_PATH)


def set_mode(mode, detail=""):
    update_status(mode=mode, detail=detail)
