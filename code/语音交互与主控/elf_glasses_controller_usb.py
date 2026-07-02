#!/usr/bin/env python3
import os
import subprocess
import sys

import numpy as np
import pvporcupine
from scipy import signal as scipy_signal
from tts_speaker_usb import speak as tts_speak


from vosk import Model, SetLogLevel

from status_store import update_status, set_mode
from button_monitor import ButtonPoller

sys.path.insert(0, "/home/elf/rknn_demo")

try:
    from command_controller_voice_ns import (
        MODEL_PATH,
        recognize_command,
        classify_command,
        handle_capture,
        say,
    )
except ImportError:
    from command_controller_voice import (
        MODEL_PATH,
        recognize_command,
        classify_command,
        handle_capture,
        say,
    )

RATE_IN = 44100
CHANNELS_IN = 2
FORMAT = "S16_LE"
FRAMES_PER_READ_IN = 2048
BYTES_PER_READ_IN = FRAMES_PER_READ_IN * CHANNELS_IN * 2
RATE_OUT = 16000

WAKE_GAIN = float(os.environ.get("WAKE_GAIN", "4.0"))
MAX_COMMAND_FAILS = 3

VIDEO_SESSION_PYTHON = "/home/elf/venv/bin/python"
VIDEO_SESSION_SCRIPT = "/home/elf/rknn_demo/video_mode_voice_stop_usb.py"
BUTTON_POLLER = ButtonPoller({"capture": 225, "start_video": 228})


def stop_process(proc):
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def listen_wake_once(porcupine):
    cmd = [
        "arecord",
        "-D", "plughw:CARD=Audio,DEV=0",
        "-f", FORMAT,
        "-r", str(RATE_IN),
        "-c", str(CHANNELS_IN),
        "-t", "raw",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    frame_length = porcupine.frame_length
    pcm_buffer = []

    set_mode("待机监听", "等待唤醒词 computer")
    print("开始监听唤醒词 'computer'，按 Ctrl+C 退出程序...")

    try:
        while True:
            for button_action in BUTTON_POLLER.poll():
                print(f"\n[BUTTON] {button_action}", flush=True)
                update_status(last_action=f"button:{button_action}")
                return button_action

            raw = proc.stdout.read(BYTES_PER_READ_IN)
            if not raw:
                return False

            samples = np.frombuffer(raw, dtype=np.int16)
            usable = len(samples) - (len(samples) % CHANNELS_IN)
            if usable <= 0:
                continue

            samples = samples[:usable].reshape(-1, CHANNELS_IN)
            mono = samples.mean(axis=1).astype(np.float32)
            mono = np.clip(mono * WAKE_GAIN, -32768, 32767).astype(np.int16)

            resampled = scipy_signal.resample_poly(
                mono.astype(float),
                RATE_OUT,
                RATE_IN,
            )
            pcm_buffer.extend(np.round(resampled).astype(np.int16).tolist())

            while len(pcm_buffer) >= frame_length:
                frame = pcm_buffer[:frame_length]
                pcm_buffer = pcm_buffer[frame_length:]

                if porcupine.process(frame) >= 0:
                    print("\n检测到唤醒词: computer")
                    update_status(mode="已唤醒", detail="等待语音命令", last_wake="computer")
                    return "wake"
    finally:
        stop_process(proc)


def run_video_session():
    set_mode("视频启动中", "正在启动统一音视频推流")
    say("正在打开视频")
    ret = subprocess.run(
        [VIDEO_SESSION_PYTHON, VIDEO_SESSION_SCRIPT],
        check=False,
    )
    if ret.returncode == 0:
        set_mode("待机监听", "视频已结束")
        say("视频已结束")
    elif ret.returncode == 2:
        subprocess.run(["pkill", "-TERM", "-f", "gst-launch-1.0.*glasses_unified"], check=False)
        set_mode("待机监听", "视频打开失败，已退回普通监听")
        print("[VIDEO] 视频打开失败，已退回普通监听", flush=True)
    else:
        update_status(mode="异常", detail=f"视频会话异常退出：{ret.returncode}")
        say(f"视频会话异常退出：{ret.returncode}")


def execute_action(action):
    if action == "capture":
        handle_capture()
        return True

    if action == "start_video":
        run_video_session()
        return True

    if action == "stop_video":
        say("当前没有正在进行的视频")
        return True

    if action == "exit":
        say("好的")
        return True

    say("没有听懂命令")
    return False


def command_session(model):
    failures = 0

    while failures < MAX_COMMAND_FAILS:
        print(
            f"请在命令窗口内说话...（连续失败 {failures}/{MAX_COMMAND_FAILS}）",
            flush=True,
        )

        try:
            text, _ = recognize_command(model)
        except Exception as e:
            say(f"语音识别失败：{e}")
            failures += 1
            continue

        print(f"[ASR] 识别文本 = {text}")
        update_status(mode="命令识别完成", detail=text, last_command_text=text)
        action = classify_command(text)
        print(f"[命令] {action}")
        update_status(last_action=action)

        ok = execute_action(action)
        if ok:
            return

        failures += 1
        if failures < MAX_COMMAND_FAILS:
            say("请再说一遍")

    say("我先不打扰了")


def main():
    SetLogLevel(-1)

    print("加载 Porcupine...")
    porcupine = pvporcupine.create(keywords=["computer"])
    print(f"Porcupine 帧长: {porcupine.frame_length}")

    print("加载 Vosk 模型...")
    model = Model(MODEL_PATH)

    print("启动完成")
    set_mode("待机监听", "系统启动完成")
    print(f"参数: WAKE_GAIN={WAKE_GAIN}")

    try:
        while True:
            event = listen_wake_once(porcupine)
            if event == "wake":
                say("我在")
                command_session(model)
                print("\n命令处理结束，重新进入唤醒词监听")
            elif event in ("capture", "start_video"):
                execute_action(event)
                print("\n按钮处理结束，重新进入唤醒词监听")
    except KeyboardInterrupt:
        print("\n退出程序")
    finally:
        porcupine.delete()



def say(text):
    print(f"[USB-SAY] {text}", flush=True)
    try:
        tts_speak(text)
    except Exception as e:
        print(f"[TTS-USB] failed: {e}", flush=True)



# USB_CAPTURE_OVERRIDE

def handle_capture():
    import json
    import subprocess
    from pathlib import Path

    say("拍照成功")

    ret = subprocess.run([
        "/home/elf/rknn_venv/bin/python",
        "/home/elf/rknn_demo/capture_detect_usb.py",
    ])

    if ret.returncode != 0:
        say("拍照识别失败")
        return

    result_path = Path("/home/elf/captures/latest_detect.json")
    if not result_path.exists():
        say("拍照完成，但没有找到检测结果")
        return

    data = json.loads(result_path.read_text(encoding="utf-8"))
    detections = data.get("detections", [])
    if not detections:
        print("[CAPTURE] AI识别完成，跳过识别结果语音播报", flush=True)
        return

    counts = {}
    zh = {"person": "人", "cell phone": "手机", "book": "书", "bottle": "瓶子", "cup": "杯子"}
    for item in detections:
        name = item.get("class", "unknown")
        name = zh.get(name, name)
        counts[name] = counts.get(name, 0) + 1

    summary = "，".join(f"{name}{count}个" for name, count in counts.items())
    print("[CAPTURE] AI识别完成，跳过识别结果语音播报", flush=True)


if __name__ == "__main__":
    main()
