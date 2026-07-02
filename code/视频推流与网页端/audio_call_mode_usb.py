#!/usr/bin/env python3
import json
import math
import os
import queue
import signal
import subprocess
import threading
import time
import wave
from collections import deque
from pathlib import Path

import numpy as np
import pvporcupine
from vosk import Model, KaldiRecognizer, SetLogLevel

import sys
sys.path.insert(0, "/home/elf/audio_module")
from status_store import update_status, set_mode

sys.path.insert(0, "/home/elf/audio_module")
try:
    from tts_speaker_usb import speak as tts_speak
except Exception as exc:
    tts_speak = None
    print(f"[TTS] 加载失败: {exc}")

RTSP_URL = "rtsp://49.232.181.138:8554/glasses_voice_call"
WEB_URL = "http://49.232.181.138:8889/glasses_voice_call"

MODEL_PATH = "/home/elf/models/vosk-model-small-cn-0.22"
DEBUG_WAV = "/tmp/video_mode_command_usb.wav"
LATEST_FRAME_PATH = Path("/tmp/elf_glasses_usb_latest_frame.jpg")
CAPTURE_PYTHON = "/home/elf/rknn_venv/bin/python"
CAPTURE_SCRIPT = Path("/home/elf/rknn_demo/capture_detect_usb.py")
CAPTURE_JSON = Path("/home/elf/captures/latest_detect.json")

RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
FRAMES_PER_READ = 512
BYTES_PER_READ = FRAMES_PER_READ * CHANNELS * SAMPLE_WIDTH

WAKE_GAIN = float(os.environ.get("WAKE_GAIN", "4.0"))
COMMAND_GAIN = float(os.environ.get("COMMAND_GAIN", "6.0"))
STREAM_VOLUME = float(os.environ.get("STREAM_VOLUME", "4.0"))

START_TIMEOUT_SEC = 5.0
MAX_RECORD_SEC = 6.0
END_SILENCE_SEC = 1.0
PRE_ROLL_SEC = 0.8
WARMUP_SEC = 0.3
TAIL_SILENCE_SEC = 0.45
START_HOLD_CHUNKS = 3

VAD_START_RMS_DB = float(os.environ.get("VAD_START_RMS_DB", "-65"))
VAD_START_PEAK_DB = float(os.environ.get("VAD_START_PEAK_DB", "-54"))
VAD_CONTINUE_RMS_DB = float(os.environ.get("VAD_CONTINUE_RMS_DB", "-68"))
VAD_CONTINUE_PEAK_DB = float(os.environ.get("VAD_CONTINUE_PEAK_DB", "-56"))

COMMAND_GRAMMAR = [
    "拍照",
    "牌照",
    "照相",
    "拍 一 张",
    "截图",
    "停止 视频",
    "关闭 视频",
    "结束 视频",
    "退出",
    "退 出",
    "没事",
    "没 什么",
    "没什么",
    "闭嘴",
    "别 说话",
    "别说话",
    "不用了",
    "取消",
    "退出",
    "退 出",
    "[unk]",
]

CLASS_ZH = {
    "person": "人",
    "bicycle": "自行车",
    "car": "汽车",
    "motorcycle": "摩托车",
    "motorbike": "摩托车",
    "bus": "公交车",
    "truck": "卡车",
    "cat": "猫",
    "dog": "狗",
}






# USB_STREAM_READY_BEGIN
STREAM_RTSP_URL = os.environ.get("STREAM_RTSP_URL", "rtsp://49.232.181.138:8554/glasses_voice_call")

def _wait_stream_ready_async(timeout=20):
    deadline = time.time() + timeout
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-rtsp_transport", "tcp",
        "-i", STREAM_RTSP_URL,
        "-frames:v", "1",
        "-f", "null", "-",
    ]
    while time.time() < deadline:
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=6)
            out = (r.stdout or "") + "\n" + (r.stderr or "")
            if r.returncode == 0:
                print("[stream-ready] OK: decoded first video frame", flush=True)
                return True
            if out.strip():
                print("[stream-ready] not ready: " + out.strip().replace("\n", " "), flush=True)
        except Exception as e:
            print(f"[stream-ready] probe failed: {e}", flush=True)
        time.sleep(1)
    return False

def _stream_ready_worker():
    if _wait_stream_ready_async():
        say("语音通话已接通")
    else:
        print("[stream-ready] 视频流未就绪，暂不播报成功", flush=True)
        say("语音通话打开失败，请重试")
        print("[stream-ready] ready failed, exit video mode", flush=True)
        os._exit(2)

def start_stream_ready_notifier():
    threading.Thread(target=_stream_ready_worker, daemon=True).start()
# USB_STREAM_READY_END

def say(text):
    print(f"[回复] {text}", flush=True)
    if os.environ.get("ENABLE_TTS", "1") != "0" and tts_speak is not None:
        tts_speak(text)


def dbfs(value):
    if value <= 0:
        return -120.0
    return 20.0 * math.log10(value / 32768.0)


def apply_gain(raw_data, gain):
    samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
    samples = np.clip(samples * gain, -32768, 32767)
    return np.round(samples).astype(np.int16).tobytes()


def levels_from_pcm(raw_data):
    samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
    if len(samples) == 0:
        return -120.0, -120.0

    rms = float(np.sqrt(np.mean(samples * samples)))
    peak = float(np.max(np.abs(samples)))
    return dbfs(rms), dbfs(peak)


def is_start_voice(rms_db, peak_db):
    paired_voice = rms_db >= VAD_START_RMS_DB and peak_db >= VAD_CONTINUE_PEAK_DB
    strong_peak = peak_db >= VAD_START_PEAK_DB
    return paired_voice or strong_peak


def is_continue_voice(rms_db, peak_db):
    return rms_db >= VAD_CONTINUE_RMS_DB or peak_db >= VAD_CONTINUE_PEAK_DB


def classify_command(text):
    t = text.replace(" ", "")

    if any(k in t for k in ["拍照", "牌照", "照相", "拍一张", "拍张", "截图"]):
        return "capture"

    if any(k in t for k in ["停止通话", "关闭通话", "结束视频", "停止", "关闭"]):
        return "stop_video"

    if any(k in t for k in ["退出", "退下", "不用了", "不用", "取消", "没事", "没什么", "闭嘴", "别说话", "算了"]):
        return "exit"

    return "unknown"


def setup_audio_video_controls():
    subprocess.run(["amixer", "-c", "1", "sset", "Mic", "100"], check=False)
    subprocess.run(["amixer", "-c", "1", "sset", "Headphone", "80"], check=False)
    subprocess.run([str(Path.home() / "set_usb_camera_controls.sh")], check=False)

def start_unified_pipeline():
    try:
        LATEST_FRAME_PATH.unlink()
    except FileNotFoundError:
        pass

    cmd = [
        "gst-launch-1.0", "-q", "-e",
        "rtspclientsink", "name=sink", "location=rtsp://49.232.181.138:8554/glasses_voice_call", "protocols=tcp",

        "alsasrc", "device=plughw:CARD=Audio,DEV=0", "do-timestamp=true",
        "!", "audioconvert",
        "!", "audioresample",
        "!", "audio/x-raw,format=S16LE,rate=48000,channels=1",
        "!", "tee", "name=audio_t",

        "audio_t.", "!", "queue",
        "!", "volume", "volume=4.0",
        "!", "opusenc", "bitrate=64000", "frame-size=20",
        "!", "queue",
        "!", "sink.sink_0",

        "audio_t.", "!", "queue", "leaky=downstream", "max-size-buffers=30", "max-size-time=0",
        "!", "audioconvert",
        "!", "audioresample",
        "!", "audio/x-raw,format=S16LE,rate=16000,channels=1",
        "!", "fdsink", "fd=1", "sync=false",
    ]

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )


def stop_pipeline(proc):
    if proc.poll() is not None:
        return

    try:
        os.killpg(proc.pid, signal.SIGINT)
        proc.wait(timeout=5)
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
            proc.wait()


class AudioReader:
    def __init__(self, proc, chunk_size=BYTES_PER_READ, max_chunks=600):
        self.proc = proc
        self.chunk_size = chunk_size
        self.q = queue.Queue(maxsize=max_chunks)
        self.stop_event = threading.Event()
        self.error = None
        self.min_time = 0.0
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name="audio-reader", daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            raw = self.proc.stdout.read(self.chunk_size)
            if not raw:
                self.error = RuntimeError("音频流结束，GStreamer 可能已退出")
                break

            item = (time.monotonic(), raw)

            try:
                self.q.put(item, timeout=0.1)
            except queue.Full:
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.q.put_nowait(item)
                except queue.Full:
                    pass

    def read(self, timeout=1.0):
        while True:
            if self.error is not None and self.q.empty():
                raise self.error

            if self.proc.poll() is not None and self.q.empty():
                raise RuntimeError("GStreamer 已退出")

            try:
                ts, raw = self.q.get(timeout=timeout)
            except queue.Empty:
                continue

            with self.lock:
                min_time = self.min_time

            if ts < min_time:
                continue

            return raw

    def flush(self):
        with self.lock:
            self.min_time = time.monotonic()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=1.0)


def read_pcm(audio_reader):
    return audio_reader.read()


def listen_wake(audio_reader, porcupine):
    frame_len = porcupine.frame_length
    pcm_buffer = []

    set_mode("语音通话中", "语音通话中，等待唤醒词 computer")
    print("语音通话中，继续监听唤醒词 'computer'...")

    while True:
        raw = read_pcm(audio_reader)
        wake_raw = apply_gain(raw, WAKE_GAIN)
        samples = np.frombuffer(wake_raw, dtype=np.int16)
        pcm_buffer.extend(samples.tolist())

        while len(pcm_buffer) >= frame_len:
            frame = pcm_buffer[:frame_len]
            pcm_buffer = pcm_buffer[frame_len:]

            if porcupine.process(frame) >= 0:
                print("\n检测到唤醒词: computer")
                update_status(mode="视频中已唤醒", detail="等待视频内命令", last_wake="computer")
                return


def record_command_from_stream(audio_reader):
    chunk_sec = FRAMES_PER_READ / RATE
    pre_roll = deque(maxlen=max(1, int(PRE_ROLL_SEC / chunk_sec)))
    raw_parts = []

    active = False
    start_hold = 0
    voice_start_time = None
    last_voice_time = None
    start_time = time.monotonic()

    max_rms_db = -120.0
    max_peak_db = -120.0

    print(
        "[VIDEO-VAD] 等待语音："
        f"start_rms>={VAD_START_RMS_DB:.1f}, "
        f"start_peak>={VAD_START_PEAK_DB:.1f}, "
        f"timeout={START_TIMEOUT_SEC:.1f}s, "
        f"max={MAX_RECORD_SEC:.1f}s"
    )

    while True:
        raw = read_pcm(audio_reader)
        cmd_raw = apply_gain(raw, COMMAND_GAIN)

        now = time.monotonic()
        elapsed = now - start_time

        if elapsed < WARMUP_SEC:
            continue

        rms_db, peak_db = levels_from_pcm(cmd_raw)
        max_rms_db = max(max_rms_db, rms_db)
        max_peak_db = max(max_peak_db, peak_db)

        if not active:
            pre_roll.append(cmd_raw)

            if is_start_voice(rms_db, peak_db):
                start_hold += 1
            else:
                start_hold = 0

            if start_hold >= START_HOLD_CHUNKS:
                active = True
                voice_start_time = now
                last_voice_time = now
                raw_parts.extend(pre_roll)
                print(f"[VIDEO-VAD] 开始说话：rms={rms_db:.1f} dBFS, peak={peak_db:.1f} dBFS")
                continue

            if elapsed >= START_TIMEOUT_SEC:
                raise RuntimeError("等待 5 秒未检测到语音")

            continue

        raw_parts.append(cmd_raw)

        if is_continue_voice(rms_db, peak_db):
            last_voice_time = now

        if now - last_voice_time >= END_SILENCE_SEC:
            print("[VIDEO-VAD] 检测到结束静音，停止录音")
            break

        if now - voice_start_time >= MAX_RECORD_SEC:
            print("[VIDEO-VAD] 达到最长录音时间，停止录音")
            break

    if not raw_parts:
        raise RuntimeError("没有录到有效语音")

    tail = b"\x00" * int(RATE * CHANNELS * SAMPLE_WIDTH * TAIL_SILENCE_SEC)
    audio_bytes = b"".join(raw_parts) + tail

    with wave.open(DEBUG_WAV, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(RATE)
        wf.writeframes(audio_bytes)

    duration = len(audio_bytes) / (RATE * CHANNELS * SAMPLE_WIDTH)
    print(f"[VIDEO-VAD] 录音时长 {duration:.2f}s，max_rms={max_rms_db:.1f} dBFS，max_peak={max_peak_db:.1f} dBFS")

    return audio_bytes


def recognize_command(model, audio_bytes):
    rec = KaldiRecognizer(
        model,
        RATE,
        json.dumps(COMMAND_GRAMMAR, ensure_ascii=False),
    )
    rec.SetWords(True)

    offset = 0
    step = 4000
    while offset < len(audio_bytes):
        rec.AcceptWaveform(audio_bytes[offset:offset + step])
        offset += step

    result = json.loads(rec.FinalResult())
    text = result.get("text", "").strip()
    return text, result



def wait_latest_frame(timeout_sec=5.0):
    deadline = time.monotonic() + timeout_sec

    while time.monotonic() < deadline:
        try:
            stat1 = LATEST_FRAME_PATH.stat()
            if stat1.st_size <= 4096:
                time.sleep(0.1)
                continue

            time.sleep(0.05)
            stat2 = LATEST_FRAME_PATH.stat()
            if stat2.st_size == stat1.st_size and stat2.st_mtime == stat1.st_mtime:
                return True
        except FileNotFoundError:
            pass

        time.sleep(0.1)

    return False


def summarize_detections(data):
    detections = data.get("detections", [])
    if not detections:
        return "未检测到目标"

    counts = {}
    for item in detections:
        name = item.get("class", "unknown")
        name = CLASS_ZH.get(name, name)
        counts[name] = counts.get(name, 0) + 1

    return "，".join(f"{name}{count}个" for name, count in counts.items())


def handle_video_capture():
    if not CAPTURE_SCRIPT.exists():
        say("拍照识别脚本不存在")
        print(f"[错误] {CAPTURE_SCRIPT}")
        return

    if not wait_latest_frame():
        say("暂时没有可用视频画面")
        print(f"[错误] latest frame not ready: {LATEST_FRAME_PATH}")
        return

    set_mode("拍照识别中", "视频中拍照，RKNN 推理中")
    say("拍照成功")
    ret = subprocess.run([
        CAPTURE_PYTHON,
        str(CAPTURE_SCRIPT),
        "--image",
        str(LATEST_FRAME_PATH),
    ])

    if ret.returncode != 0:
        say("拍照识别失败")
        return

    if not CAPTURE_JSON.exists():
        say("拍照完成，但没有找到检测结果")
        return

    data = json.loads(CAPTURE_JSON.read_text(encoding="utf-8"))
    summary = summarize_detections(data)
    update_status(mode="语音通话中", detail=f"已拍照，检测到：{summary}", last_capture_summary=summary)
    print("[CAPTURE] AI识别完成，跳过识别结果语音播报", flush=True)
    print(f"[结果] {CAPTURE_JSON}")


capture_lock = threading.Lock()
capture_threads = []


def _capture_job():
    try:
        handle_video_capture()
    finally:
        capture_lock.release()


def start_video_capture_job():
    if not capture_lock.acquire(blocking=False):
        say("正在拍照识别，请稍等")
        return

    t = threading.Thread(target=_capture_job, name="capture-worker", daemon=False)
    capture_threads.append(t)
    t.start()


def wait_capture_jobs(timeout=10.0):
    deadline = time.monotonic() + timeout
    for t in list(capture_threads):
        remaining = max(0.0, deadline - time.monotonic())
        t.join(timeout=remaining)


def handle_video_command(audio_reader, model):
    say("我在")
    consecutive_failures = 0

    while consecutive_failures < 3:
        try:
            audio_bytes = record_command_from_stream(audio_reader)
            text, _ = recognize_command(model, audio_bytes)
        except Exception as e:
            consecutive_failures += 1
            say(f"语音识别失败：{e}")
            if consecutive_failures < 3:
                say("请再说一遍")
            continue

        print(f"[VIDEO-ASR] 识别文本 = {text}")
        update_status(mode="视频命令识别完成", detail=text, last_command_text=text)
        action = classify_command(text)
        print(f"[VIDEO-CMD] {action}")
        update_status(last_action=action)

        if action == "capture":
            start_video_capture_job()
            audio_reader.flush()
            print("[VIDEO] 拍照任务已转入后台，忽略旧控制音频，继续监听")
            return "continue"

        if action == "stop_video":
            say("正在停止通话")
            return "stop_video"

        if action == "exit":
            say("语音通话已挂断")
            say("好的")
            return "continue"

        consecutive_failures += 1
        say("没有听懂命令")
        if consecutive_failures < 3:
            say("请再说一遍")

    say("我先不打扰了")
    return "continue"


def main():
    SetLogLevel(-1)

    setup_audio_video_controls()

    print("加载 Porcupine...")
    porcupine = pvporcupine.create(keywords=["computer"], sensitivities=[0.75])
    print(f"Porcupine 帧长: {porcupine.frame_length}")

    print("加载 Vosk 模型...")
    model = Model(MODEL_PATH)

    print("启动统一音频语音通话...")
    set_mode("视频启动中", "启动统一音频语音通话")
    print(f"网页地址: {WEB_URL}")
    print(f"参数: WAKE_GAIN={WAKE_GAIN}, COMMAND_GAIN={COMMAND_GAIN}, STREAM_VOLUME={STREAM_VOLUME}")

    proc = start_unified_pipeline()
    if wait_latest_frame(timeout_sec=5.0):
        start_stream_ready_notifier()
    else:
        say("视频已启动，但暂时没有画面")
    audio_reader = AudioReader(proc)
    audio_reader.start()

    try:
        while proc.poll() is None:
            listen_wake(audio_reader, porcupine)
            result = handle_video_command(audio_reader, model)

            if result == "stop_video":
                stop_pipeline(proc)
                break

        set_mode("待机监听", "语音通话模式结束")
        print("语音通话模式结束")
    except KeyboardInterrupt:
        print("\n退出语音通话模式")
        stop_pipeline(proc)
    finally:
        audio_reader.stop()
        wait_capture_jobs(timeout=10.0)
        porcupine.delete()

        if proc.poll() is not None:
            err = proc.stderr.read().decode("utf-8", errors="ignore")
            if err.strip():
                print("[GStreamer 日志]")
                print(err[-4000:])


if __name__ == "__main__":
    main()
