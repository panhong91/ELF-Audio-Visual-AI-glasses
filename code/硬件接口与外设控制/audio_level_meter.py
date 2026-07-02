#!/usr/bin/env python3
import audioop
import math
import signal
import subprocess
import time

DEVICE = "hw:0,0"
RATE = 44100
CHANNELS = 2
SAMPLE_WIDTH = 2
CHUNK_FRAMES = 2048
BYTES_PER_READ = CHUNK_FRAMES * CHANNELS * SAMPLE_WIDTH
PRINT_INTERVAL_SEC = 0.5
WARMUP_SEC = 0.5


def dbfs_from_pcm(raw_data):
    mono = audioop.tomono(raw_data, SAMPLE_WIDTH, 0.5, 0.5)
    rms = audioop.rms(mono, SAMPLE_WIDTH)
    peak = audioop.max(mono, SAMPLE_WIDTH)

    rms_db = -120.0 if rms <= 0 else 20.0 * math.log10(rms / 32768.0)
    peak_db = -120.0 if peak <= 0 else 20.0 * math.log10(peak / 32768.0)

    return rms_db, peak_db


def main():
    cmd = [
        "arecord",
        "-D", DEVICE,
        "-f", "S16_LE",
        "-r", str(RATE),
        "-c", str(CHANNELS),
        "-t", "raw",
    ]

    print(f"device={DEVICE}, format=S16_LE, rate={RATE}, channels={CHANNELS}")
    print("前 0.5 秒丢弃，避免声卡启动脉冲。按 Ctrl+C 停止。")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    start = time.monotonic()
    last_print = start
    rms_values = []
    peak_values = []

    try:
        while True:
            raw_data = proc.stdout.read(BYTES_PER_READ)
            if not raw_data:
                print("没有读到音频数据")
                break

            now = time.monotonic()
            if now - start < WARMUP_SEC:
                continue

            rms_db, peak_db = dbfs_from_pcm(raw_data)
            rms_values.append(rms_db)
            peak_values.append(peak_db)

            if now - last_print >= PRINT_INTERVAL_SEC:
                if rms_values:
                    avg_rms = sum(rms_values) / len(rms_values)
                    max_peak = max(peak_values)
                    min_rms = min(rms_values)
                    max_rms = max(rms_values)

                    print(
                        f"rms_avg={avg_rms:6.1f} dBFS, "
                        f"rms_range={min_rms:6.1f}..{max_rms:6.1f}, "
                        f"peak_max={max_peak:6.1f} dBFS",
                        flush=True,
                    )

                rms_values.clear()
                peak_values.clear()
                last_print = now

    except KeyboardInterrupt:
        print("\n停止")
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    main()
