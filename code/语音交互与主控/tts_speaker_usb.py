#!/usr/bin/env python3
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

VOICE = os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
DEVICE = os.environ.get("TTS_DEVICE", "dmix:CARD=Audio,DEV=0")
VOLUME = os.environ.get("TTS_VOLUME", "0.45")
CACHE_DIR = Path.home() / "tts_cache_usb"

def run(cmd):
    subprocess.run(cmd, check=True)

def cache_key(text):
    return hashlib.sha1((VOICE + "\n" + text).encode("utf-8")).hexdigest()[:20]

def ensure_wav(text):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = cache_key(text)
    wav = CACHE_DIR / f"{key}.wav"

    if wav.exists() and wav.stat().st_size > 1024:
        return wav

    mp3_tmp = CACHE_DIR / f".{key}.tmp.mp3"
    wav_tmp = CACHE_DIR / f".{key}.tmp.wav"

    print(f"[TTS-USB] 生成缓存: {text}", flush=True)

    run([
        sys.executable, "-m", "edge_tts",
        "--voice", VOICE,
        "--text", text,
        "--write-media", str(mp3_tmp),
    ])

    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(mp3_tmp),
        "-acodec", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(wav_tmp),
    ])

    wav_tmp.replace(wav)
    try:
        mp3_tmp.unlink()
    except FileNotFoundError:
        pass

    return wav

def play_wav(wav):
    print(f"[TTS-USB] play device={DEVICE} volume={VOLUME} file={wav}", flush=True)
    gst = shutil.which("gst-launch-1.0")
    if gst:
        run([
            gst, "-q",
            "filesrc", f"location={wav}",
            "!", "wavparse",
            "!", "audioconvert",
            "!", "audioresample",
            "!", "volume", f"volume={VOLUME}",
            "!", "alsasink", f"device={DEVICE}", "sync=false",
        ])
        return

    tmp = wav.with_suffix(".play_tmp.wav")
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav),
        "-af", f"volume={VOLUME}",
        str(tmp),
    ])
    run(["aplay", "-D", DEVICE, str(tmp)])
    tmp.unlink(missing_ok=True)


def normalize_tts_text(text):
    text = str(text).strip()
    if (
        "已拍照" in text
        or "检测到：" in text
        or "识别到物品" in text
        or "未识别到物品" in text
        or "未检测到" in text
    ):
        return "拍照成功"
    return text

def _speak_impl(text):
    text = normalize_tts_text(text)
    text = str(text).strip()
    if not text:
        return
    wav = ensure_wav(text)
    play_wav(wav)

def main():
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print("usage: tts_speaker_usb.py 文本")
        return 2
    speak(text)
    return 0


def speak(text):
    try:
        return _speak_impl(text)
    except Exception as e:
        print(f"[TTS-USB] 播放失败但不中断主控: {e}", flush=True)
        return None

if __name__ == "__main__":
    raise SystemExit(main())
