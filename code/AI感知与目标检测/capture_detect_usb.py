#!/usr/bin/env python3
import argparse
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

import cv2
from rknnlite.api import RKNNLite
from func.func_yolov8_optimize import detect_frame, FOCUSED_CLASSES

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "rknnModel" / "best.rknn"
OUTPUT_DIR = Path.home() / "captures"

DEVICE = "/dev/video52"
WIDTH = 1280
HEIGHT = 720
FPS = 30


def build_camera_pipeline():
    return (
        f"v4l2src device={DEVICE} ! "
        f"image/jpeg,width={WIDTH},height={HEIGHT},framerate={FPS}/1 ! "
        "jpegdec ! "
        "videoconvert ! video/x-raw,format=BGR ! "
        "appsink drop=true sync=false max-buffers=1"
    )

def read_camera_frame():
    cap = cv2.VideoCapture(build_camera_pipeline(), cv2.CAP_GSTREAMER)
    print("camera opened =", cap.isOpened())
    if not cap.isOpened():
        raise SystemExit("camera open failed")

    frame = None
    for _ in range(5):
        ok, frame = cap.read()
        if not ok:
            cap.release()
            raise SystemExit("camera read failed")

    cap.release()
    return frame


def read_image_frame(path):
    path = Path(path)
    for _ in range(20):
        frame = cv2.imread(str(path))
        if frame is not None:
            print("image input =", path)
            print("image shape =", frame.shape)
            return frame
        time.sleep(0.1)

    raise SystemExit(f"image read failed: {path}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="use an existing image instead of opening the camera")
    return parser.parse_args()


def main():
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = OUTPUT_DIR / f"{ts}_raw.jpg"
    detect_path = OUTPUT_DIR / f"{ts}_detect.jpg"
    json_path = OUTPUT_DIR / f"{ts}_detect.json"

    latest_raw = OUTPUT_DIR / "latest_raw.jpg"
    latest_detect = OUTPUT_DIR / "latest_detect.jpg"
    latest_json = OUTPUT_DIR / "latest_detect.json"

    rknn = RKNNLite()
    ret = rknn.load_rknn(str(MODEL_PATH))
    print("load_rknn ret =", ret)
    if ret != 0:
        raise SystemExit("load_rknn failed")

    ret = rknn.init_runtime()
    print("init_runtime ret =", ret)
    if ret != 0:
        rknn.release()
        raise SystemExit("init_runtime failed")

    if not args.image:
        subprocess.run([str(Path.home() / "set_usb_camera_controls.sh")], check=False)

    if args.image:
        frame = read_image_frame(args.image)
        source = str(Path(args.image))
    else:
        frame = read_camera_frame()
        source = DEVICE

    cv2.imwrite(str(raw_path), frame)
    cv2.imwrite(str(latest_raw), frame)

    start = time.time()
    result, detections = detect_frame(rknn, frame)
    infer_time = time.time() - start

    cv2.imwrite(str(detect_path), result)
    cv2.imwrite(str(latest_detect), result)

    report = {
        "timestamp": ts,
        "infer_time_sec": infer_time,
        "source": source,
        "focused_classes": sorted(FOCUSED_CLASSES),
        "raw": str(raw_path),
        "detect": str(detect_path),
        "detections": detections,
    }

    json_text = json.dumps(report, ensure_ascii=False, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")

    rknn.release()

    print("raw =", raw_path)
    print("detect =", detect_path)
    print("json =", json_path)
    print("latest_raw =", latest_raw)
    print("latest_detect =", latest_detect)
    print("latest_json =", latest_json)
    print("infer_time_sec =", infer_time)
    print("detections =", len(detections))

    for item in detections:
        print(f"{item['class']} {item['score']} box={item['box']}")

    print("status = ok")


if __name__ == "__main__":
    main()
