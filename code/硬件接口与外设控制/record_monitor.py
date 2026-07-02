#!/usr/bin/env python3
import subprocess
import signal
import sys

subprocess.run(['amixer','-c','rockchiprv1126b','sset','DAC Digital','290'],check=False)

RATE = 44100
CHANNELS = 2
FORMAT = 'S16_LE'
FRAMES_PER_READ = 1024
BYTES_PER_READ = FRAMES_PER_READ * 2 * CHANNELS

record_cmd = [
    'arecord', '-D', 'hw:0,0', '-f', FORMAT, '-r', str(RATE), '-c', str(CHANNELS), '-t', 'raw'
]
play_cmd = [
    'aplay', '-D', 'hw:0,0', '-f', FORMAT, '-r', str(RATE), '-c', str(CHANNELS), '-t', 'raw'
]

rec_proc = subprocess.Popen(record_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
play_proc = subprocess.Popen(play_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

def signal_handler(sig, frame):
    print("\n停止")
    rec_proc.terminate()
    play_proc.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print("实时监听中（麦克风声音实时从喇叭播出），按 Ctrl+C 停止...")
while True:
    data = rec_proc.stdout.read(BYTES_PER_READ)
    if not data:
        break
    play_proc.stdin.write(data)
    play_proc.stdin.flush()
