#!/usr/bin/env python3
import json
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8080

CAPTURE_DIR = Path("/home/elf/captures")
LATEST_JSON = CAPTURE_DIR / "latest_detect.json"
LATEST_DETECT = CAPTURE_DIR / "latest_detect.jpg"
LATEST_RAW = CAPTURE_DIR / "latest_raw.jpg"
STATUS_JSON = Path("/home/elf/ai_status.json")

VIDEO_URL = "https://49.232.181.138:8443/glasses_unified"


HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Glasses Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0f1115;
      --panel: #171b22;
      --line: #2b313b;
      --text: #e9edf3;
      --muted: #9aa4b2;
      --accent: #31c48d;
      --warn: #f5b84b;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
      background: #12161d;
    }

    h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 650;
      letter-spacing: 0;
    }

    .status {
      display: flex;
      gap: 12px;
      align-items: center;
      color: var(--muted);
      font-size: 13px;
    }

    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--warn);
      display: inline-block;
    }

    .dot.ok { background: var(--accent); }

    main {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr);
      gap: 14px;
      padding: 14px;
    }

    section {
      min-width: 0;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      overflow: hidden;
    }

    .section-head {
      height: 42px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 12px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
    }

    .video-frame {
      width: 100%;
      height: 48vh;
      min-height: 320px;
      border: 0;
      background: #05070a;
      display: block;
    }

    .detect-img {
      width: 100%;
      display: block;
      background: #05070a;
      object-fit: contain;
      max-height: calc(100vh - 130px);
    }

    .metrics {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      padding: 10px;
    }

    .metric {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #10141a;
    }

    .metric .label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }

    .metric .value {
      font-size: 20px;
      font-weight: 650;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }

    th, td {
      padding: 9px 10px;
      border-top: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }

    th { color: var(--muted); font-weight: 550; }

    pre {
      margin: 0;
      padding: 10px;
      color: #cbd5e1;
      overflow: auto;
      max-height: 260px;
      border-top: 1px solid var(--line);
      background: #0b0e13;
      font-size: 12px;
    }

    a {
      color: #79b8ff;
      text-decoration: none;
    }

    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      .video-frame { height: 38vh; }
    }
  </style>
</head>
<body>
  <header>
    <h1>AI Glasses Dashboard</h1>
    <div class="status">
      <span><span id="dot" class="dot"></span> <span id="state">等待数据</span></span><span id="mode" style="color:#e9edf3;background:#202632;border:1px solid #2b313b;border-radius:6px;padding:3px 8px;">-</span>
      <span id="updated">-</span>
    </div>
  </header>

  <main>
    <div>
      <section>
        <div class="section-head">
          <span>实时视频</span>
<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
  <span id="talkbackState" style="color:#94a3b8;font-size:13px;">对讲未开启</span>
  <button id="talkbackStartBtn" type="button" onclick="startTalkback()" style="background:#2563eb;color:white;border:0;border-radius:6px;padding:6px 10px;cursor:pointer;">开始对讲</button>
  <button id="talkbackStopBtn" type="button" onclick="stopTalkback()" disabled style="background:#374151;color:white;border:0;border-radius:6px;padding:6px 10px;cursor:pointer;">停止对讲</button>
  <a href="https://49.232.181.138:8443/glasses_unified" target="_blank">打开视频页</a>
</div>
        </div>
        <iframe class="video-frame" src="''' + VIDEO_URL + r'''"></iframe>
      </section>

      <section style="margin-top:14px;">
        <div class="section-head">
          <span id="rawTitle">最新原图</span>
          <span style="display:flex;align-items:center;gap:12px;">
            <button id="showLatestBtn" onclick="showLatestView()" style="display:none;background:#202632;color:#e9edf3;border:1px solid #2b313b;border-radius:6px;padding:3px 8px;cursor:pointer;">返回最新</button>
            <a id="downloadRaw" href="/latest_raw.jpg" download="latest_raw.jpg">保存原图</a>
            <span id="rawImageInfo">-</span>
          </span>
        </div>
        <img id="rawImg" class="detect-img" alt="latest raw">
      </section>

      <section style="margin-top:14px;">
        <div class="section-head">
          <span id="detectTitle">最新 AI 检测结果图</span>
          <span style="display:flex;align-items:center;gap:12px;">
            <a id="downloadLatest" href="/latest_detect.jpg" download="latest_detect.jpg">保存检测图</a>
            <span id="imageInfo">-</span>
          </span>
        </div>
        <img id="detectImg" class="detect-img" alt="latest detection">
      </section>
    </div>

    <section>
      <div class="section-head">
        <span>识别结果</span>
        <span id="timestamp">-</span>
      </div>

      <div style="padding:10px;border-bottom:1px solid var(--line);font-size:18px;font-weight:650;">
        检测到：<span id="summaryText">-</span>
      </div>

      <div class="metrics">
        <div class="metric">
          <div class="label">目标数</div>
          <div id="detCount" class="value">0</div>
        </div>
        <div class="metric">
          <div class="label">推理耗时</div>
          <div id="inferTime" class="value">-</div>
        </div>
        <div class="metric">
          <div class="label">图片状态</div>
          <div id="imgState" class="value">-</div>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th>类别</th>
            <th>置信度</th>
            <th>框坐标</th>
          </tr>
        </thead>
        <tbody id="detBody">
          <tr><td colspan="3">暂无检测结果</td></tr>
        </tbody>
      </table>

      <pre id="jsonView">{}</pre>

      <div class="section-head" style="border-top:1px solid var(--line);">
        <span>最近 10 次识别</span>
        <span id="historyCount">-</span>
      </div>
      <div id="historyList" style="padding:10px;display:grid;gap:8px;"></div>
    </section>
  </main>

  <div id="imageModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.78);z-index:50;align-items:center;justify-content:center;padding:18px;">
    <div style="width:min(1120px,96vw);max-height:94vh;background:#11161d;border:1px solid var(--line);border-radius:8px;overflow:hidden;">
      <div class="section-head">
        <span id="modalTitle">历史检测图</span>
        <span style="display:flex;gap:12px;align-items:center;">
          <a id="modalRaw" href="#" target="_blank">查看原图</a>
          <a id="modalJson" href="#" target="_blank">查看 JSON</a>
          <a id="modalDownload" href="#" download>保存检测图</a>
          <button onclick="closeImageModal()" style="background:#202632;color:#e9edf3;border:1px solid #2b313b;border-radius:6px;padding:4px 10px;cursor:pointer;">关闭</button>
        </span>
      </div>
      <img id="modalImg" style="width:100%;max-height:calc(94vh - 44px);object-fit:contain;background:#05070a;display:block;">
    </div>
  </div>

  <script>
    let lastHistoryKey = "";
    let lastLatestImageMtime = "";
    let currentImageView = "latest";
    let lastStatusData = null;

    const CLASS_ZH = {
      "person": "人",
      "bicycle": "自行车",
      "car": "汽车",
      "motorbike": "摩托车",
      "motorcycle": "摩托车",
      "bus": "公交车",
      "truck": "卡车",
      "cat": "猫",
      "dog": "狗",
      "backpack": "背包",
      "umbrella": "雨伞",
      "handbag": "手提包",
      "bottle": "瓶子",
      "cup": "杯子",
      "bowl": "碗",
      "banana": "香蕉",
      "apple": "苹果",
      "chair": "椅子",
      "sofa": "沙发",
      "book": "书",
      "cell phone": "手机",
      "laptop": "笔记本电脑",
      "keyboard": "键盘",
      "mouse": "鼠标"
    };

    function zhName(name) {
      return CLASS_ZH[name] || name || "未知";
    }

    function detectionSummary(items) {
      if (!items || items.length === 0) return "未检测到目标";

      const counts = {};
      for (const item of items) {
        const name = zhName(item.class);
        counts[name] = (counts[name] || 0) + 1;
      }

      return Object.entries(counts)
        .map(([name, count]) => `${name}${count}个`)
        .join("，");
    }

    function fmtTime(sec) {
      if (typeof sec !== "number") return "-";
      return (sec * 1000).toFixed(1) + " ms";
    }

    function setImageHeader(rawTitle, detectTitle, infoText) {
      const rawTitleEl = document.getElementById("rawTitle");
      const detectTitleEl = document.getElementById("detectTitle");
      const rawInfo = document.getElementById("rawImageInfo");
      const imageInfo = document.getElementById("imageInfo");

      if (rawTitleEl) rawTitleEl.textContent = rawTitle;
      if (detectTitleEl) detectTitleEl.textContent = detectTitle;
      if (rawInfo) rawInfo.textContent = infoText || "-";
      if (imageInfo) imageInfo.textContent = infoText || "-";
    }

    function updateDownloadLinks(rawUrl, detectUrl, timestamp) {
      const rawDownload = document.getElementById("downloadRaw");
      const latestDownload = document.getElementById("downloadLatest");
      const suffix = timestamp || "image";

      if (rawDownload) {
        rawDownload.href = rawUrl;
        rawDownload.download = `raw_${suffix}.jpg`;
      }

      if (latestDownload) {
        latestDownload.href = detectUrl;
        latestDownload.download = `detect_${suffix}.jpg`;
      }
    }

    function showLatestImages(data, force = false) {
      const btn = document.getElementById("showLatestBtn");
      if (btn) btn.style.display = "none";

      setImageHeader("最新原图", "最新 AI 检测结果图", data.image_mtime || "-");

      if (!data.image_exists) return;

      if (force || data.image_mtime !== lastLatestImageMtime) {
        lastLatestImageMtime = data.image_mtime;
        const version = encodeURIComponent(data.report.timestamp || data.image_mtime || Date.now());
        const rawUrl = `/latest_raw.jpg?v=${version}`;
        const detectUrl = `/latest_detect.jpg?v=${version}`;

        document.getElementById("rawImg").src = rawUrl;
        document.getElementById("detectImg").src = detectUrl;
        updateDownloadLinks(rawUrl, detectUrl, data.report.timestamp || "latest");
      }
    }

    function showLatestView() {
      currentImageView = "latest";
      lastLatestImageMtime = "";
      if (lastStatusData) {
        showLatestImages(lastStatusData, true);
      }
    }

    function showHistoryImages(item) {
      currentImageView = "history";

      const btn = document.getElementById("showLatestBtn");
      if (btn) btn.style.display = "inline-block";

      const version = encodeURIComponent(item.timestamp || item.detect_url || "history");
      const rawUrl = `${item.raw_url || item.detect_url}?v=${version}`;
      const detectUrl = `${item.detect_url}?v=${version}`;

      document.getElementById("rawImg").src = rawUrl;
      document.getElementById("detectImg").src = detectUrl;

      setImageHeader("历史原图", "历史 AI 检测结果图", item.time_text || item.timestamp || "-");
      updateDownloadLinks(rawUrl, detectUrl, item.timestamp || "history");
    }


    function renderDetections(items) {
      const body = document.getElementById("detBody");
      body.innerHTML = "";

      if (!items || items.length === 0) {
        body.innerHTML = '<tr><td colspan="3">未检测到目标</td></tr>';
        return;
      }

      for (const item of items) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${zhName(item.class)} <span style="color:#7d8794;">${item.class ?? "unknown"}</span></td>
          <td>${item.score ?? "-"}</td>
          <td>${JSON.stringify(item.box ?? [])}</td>
        `;
        body.appendChild(tr);
      }
    }

    function openHistoryImage(item) {
      const modal = document.getElementById("imageModal");
      const img = document.getElementById("modalImg");
      const title = document.getElementById("modalTitle");
      const raw = document.getElementById("modalRaw");
      const json = document.getElementById("modalJson");
      const download = document.getElementById("modalDownload");

      const version = encodeURIComponent(item.timestamp || item.detect_url || "history");
      img.src = `${item.detect_url}?v=${version}`;
      title.textContent = `${item.time_text || item.timestamp} · ${item.summary}`;
      raw.href = item.raw_url || item.detect_url;
      json.href = item.json_url || "#";
      download.href = `${item.detect_url}?v=${version}`;
      download.download = `detect_${item.timestamp || "history"}.jpg`;

      modal.style.display = "flex";
    }

    function closeImageModal() {
      document.getElementById("imageModal").style.display = "none";
    }


    function renderHistory(items) {
      const list = document.getElementById("historyList");
      const count = document.getElementById("historyCount");
      list.innerHTML = "";
      count.textContent = `${items.length} 条`;

      if (!items || items.length === 0) {
        list.innerHTML = '<div style="color:#9aa4b2;">暂无历史记录</div>';
        return;
      }

      for (const item of items) {
        const row = document.createElement("div");
        row.style.display = "grid";
        row.style.gridTemplateColumns = "86px 1fr";
        row.style.gap = "10px";
        row.style.alignItems = "center";
        row.style.border = "1px solid var(--line)";
        row.style.borderRadius = "6px";
        row.style.background = "#10141a";
        row.style.padding = "8px";
        row.style.cursor = "pointer";

        row.innerHTML = `
          <img src="${item.detect_url}?v=${encodeURIComponent(item.timestamp || item.detect_url)}" style="width:86px;height:54px;object-fit:cover;border-radius:4px;background:#05070a;">
          <div style="min-width:0;">
            <div style="font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${item.summary}</div>
            <div style="color:#9aa4b2;font-size:12px;margin-top:3px;">${item.time_text || item.timestamp}</div>
            <div style="color:#9aa4b2;font-size:12px;margin-top:3px;">${fmtTime(item.infer_time_sec)} · ${item.detection_count} 个目标</div>
            <a href="${item.json_url}" target="_blank" onclick="event.stopPropagation()" style="font-size:12px;">查看 JSON</a>
          </div>
        `;

        row.addEventListener("click", () => showHistoryImages(item));
        list.appendChild(row);
      }
    }


    async function refresh() {
      try {
        const res = await fetch("/api/status?ts=" + Date.now());
        const data = await res.json();
        lastStatusData = data;

        document.getElementById("dot").className = data.ok ? "dot ok" : "dot";
        document.getElementById("state").textContent = data.ok ? "数据正常" : "等待检测";
        document.getElementById("updated").textContent = data.server_time;
        const system = data.system || {};
        document.getElementById("mode").textContent =
          (system.mode || "-") + (system.detail ? " / " + system.detail : "");
        document.getElementById("timestamp").textContent = data.report.timestamp ?? "-";
        document.getElementById("detCount").textContent = data.detection_count;
        document.getElementById("inferTime").textContent = fmtTime(data.report.infer_time_sec);
        document.getElementById("imgState").textContent = data.image_exists ? "OK" : "无";
        if (currentImageView === "latest") {
          document.getElementById("imageInfo").textContent = data.image_mtime ?? "-";
          const rawInfo = document.getElementById("rawImageInfo");
          if (rawInfo) rawInfo.textContent = data.image_mtime ?? "-";
        }
        document.getElementById("jsonView").textContent = JSON.stringify(data.report, null, 2);
        document.getElementById("summaryText").textContent = detectionSummary(data.report.detections || []);


        renderDetections(data.report.detections || []);

        const history = data.history || [];
        const historyKey = JSON.stringify(history.map(item => [
          item.timestamp,
          item.summary,
          item.detect_url,
          item.detection_count,
          item.infer_time_sec
        ]));

        if (historyKey !== lastHistoryKey) {
          lastHistoryKey = historyKey;
          renderHistory(history);
        }

        if (currentImageView === "latest") {
          showLatestImages(data);
        }
      } catch (err) {
        document.getElementById("dot").className = "dot";
        document.getElementById("state").textContent = "连接失败";
      }
    }

    refresh();
    setInterval(refresh, 1200);
  


let talkbackPc = null;
let talkbackStream = null;
let talkbackRawStream = null;
let talkbackAudioContext = null;
let talkbackGainNode = null;

const WHIP_URL = "https://49.232.181.138:8443/glasses_talkback/whip";
const TALKBACK_BROWSER_GAIN = 1.0;
const TALKBACK_UNMUTE_DELAY_MS = 800;

function setTalkbackUi(text, active) {
  const state = document.getElementById("talkbackState");
  const startBtn = document.getElementById("talkbackStartBtn");
  const stopBtn = document.getElementById("talkbackStopBtn");
  if (state) {
    state.textContent = text;
    state.style.color = active ? "#34d399" : "#94a3b8";
  }
  if (startBtn) startBtn.disabled = active;
  if (stopBtn) stopBtn.disabled = !active;
}

function waitIceGatheringComplete(pc) {
  return new Promise((resolve) => {
    if (pc.iceGatheringState === "complete") {
      resolve();
      return;
    }
    const timer = setTimeout(done, 3000);
    function done() {
      clearTimeout(timer);
      pc.removeEventListener("icegatheringstatechange", onChange);
      resolve();
    }
    function onChange() {
      if (pc.iceGatheringState === "complete") done();
    }
    pc.addEventListener("icegatheringstatechange", onChange);
  });
}

async function startTalkback() {
  try {
    if (!window.isSecureContext) {
      alert("浏览器麦克风需要安全上下文，请通过 http://localhost:8080 打开 Dashboard");
      return;
    }

    setTalkbackUi("对讲连接中", true);

    talkbackRawStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: false,
        channelCount: 1,
        sampleRate: 48000
      },
      video: false
    });

    talkbackAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = talkbackAudioContext.createMediaStreamSource(talkbackRawStream);
    talkbackGainNode = talkbackAudioContext.createGain();
    talkbackGainNode.gain.setValueAtTime(0.0, talkbackAudioContext.currentTime);

    const dest = talkbackAudioContext.createMediaStreamDestination();
    source.connect(talkbackGainNode);
    talkbackGainNode.connect(dest);
    talkbackStream = dest.stream;

    talkbackPc = new RTCPeerConnection();
    talkbackStream.getTracks().forEach((track) => {
      track.enabled = false;
      talkbackPc.addTrack(track, talkbackStream);
    });

    talkbackPc.onconnectionstatechange = () => {
      if (!talkbackPc) return;
      if (["failed", "disconnected", "closed"].includes(talkbackPc.connectionState)) {
        stopTalkback();
      }
    };

    const offer = await talkbackPc.createOffer();
    await talkbackPc.setLocalDescription(offer);
    await waitIceGatheringComplete(talkbackPc);

    const resp = await fetch(WHIP_URL, {
      method: "POST",
      headers: { "Content-Type": "application/sdp" },
      body: talkbackPc.localDescription.sdp
    });

    if (!resp.ok) {
      throw new Error("WHIP HTTP " + resp.status + ": " + await resp.text());
    }

    const answer = await resp.text();
    await talkbackPc.setRemoteDescription({ type: "answer", sdp: answer });

    setTimeout(() => {
      if (!talkbackPc || !talkbackStream || !talkbackAudioContext || !talkbackGainNode) return;

      talkbackStream.getAudioTracks().forEach((track) => {
        track.enabled = true;
      });

      const now = talkbackAudioContext.currentTime;
      talkbackGainNode.gain.cancelScheduledValues(now);
      talkbackGainNode.gain.setValueAtTime(0.0, now);
      talkbackGainNode.gain.linearRampToValueAtTime(TALKBACK_BROWSER_GAIN, now + 0.4);

      setTalkbackUi("对讲中", true);
    }, TALKBACK_UNMUTE_DELAY_MS);
  } catch (err) {
    console.error(err);
    alert("对讲开启失败：" + err.message);
    stopTalkback();
  }
}

function stopTalkback() {
  if (talkbackPc) {
    talkbackPc.close();
    talkbackPc = null;
  }
  if (talkbackStream) {
    talkbackStream.getTracks().forEach((track) => track.stop());
    talkbackStream = null;
  }
  if (talkbackRawStream) {
    talkbackRawStream.getTracks().forEach((track) => track.stop());
    talkbackRawStream = null;
  }
  if (talkbackAudioContext) {
    talkbackAudioContext.close();
    talkbackAudioContext = null;
  }
  talkbackGainNode = null;
  setTalkbackUi("对讲未开启", false);
}

window.addEventListener("beforeunload", stopTalkback);

</script>
</body>
</html>
'''



def read_system_status():
    if not STATUS_JSON.exists():
        return {}

    try:
        return json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}



def read_system_status():
    if not STATUS_JSON.exists():
        return {}

    try:
        return json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def summarize_history_detections(detections):
    if not detections:
        return "未检测到目标"

    name_map = {
        "person": "人",
        "bicycle": "自行车",
        "car": "汽车",
        "motorbike": "摩托车",
        "motorcycle": "摩托车",
        "bus": "公交车",
        "truck": "卡车",
        "cat": "猫",
        "dog": "狗",
        "backpack": "背包",
        "umbrella": "雨伞",
        "handbag": "手提包",
        "bottle": "瓶子",
        "cup": "杯子",
        "bowl": "碗",
        "banana": "香蕉",
        "apple": "苹果",
        "chair": "椅子",
        "sofa": "沙发",
        "book": "书",
        "cell phone": "手机",
        "laptop": "笔记本电脑",
        "keyboard": "键盘",
        "mouse": "鼠标",
    }

    counts = {}
    for item in detections:
        name = name_map.get(item.get("class"), item.get("class", "未知"))
        counts[name] = counts.get(name, 0) + 1

    return "，".join(f"{name}{count}个" for name, count in counts.items())


def capture_file_url(path_text):
    if not path_text:
        return ""
    name = Path(path_text).name
    return f"/captures/{name}"


def read_history(limit=10):
    records = []

    for path in CAPTURE_DIR.glob("*_detect.json"):
        if path.name == "latest_detect.json":
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        detections = data.get("detections", [])
        records.append({
            "timestamp": data.get("timestamp", path.stem),
            "time_text": file_mtime(path),
            "infer_time_sec": data.get("infer_time_sec"),
            "detection_count": len(detections),
            "summary": summarize_history_detections(detections),
            "detect_url": capture_file_url(data.get("detect")),
            "raw_url": capture_file_url(data.get("raw")),
            "json_url": capture_file_url(str(path)),
        })

    records.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return records[:limit]


def read_report():
    if not LATEST_JSON.exists():
        return {}

    try:
        return json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def file_mtime(path):
    if not path.exists():
        return None
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_bytes(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_bytes(body, "application/json; charset=utf-8")

    def send_file(self, path, content_type):
        if not path.exists():
            self.send_bytes(b"not found", "text/plain; charset=utf-8", 404)
            return
        self.send_bytes(path.read_bytes(), content_type)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/api/status":
            report = read_report()
            detections = report.get("detections", [])
            self.send_json({
                "ok": bool(report) and "error" not in report,
                "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "video_url": VIDEO_URL,
                "image_exists": LATEST_DETECT.exists(),
                "image_mtime": file_mtime(LATEST_DETECT),
                "json_mtime": file_mtime(LATEST_JSON),
                "detection_count": len(detections),
                "report": report,
                "system": read_system_status(),
                "history": read_history(),
            })
            return

        if path == "/latest_detect.jpg":
            self.send_file(LATEST_DETECT, "image/jpeg")
            return

        if path == "/latest_raw.jpg":
            self.send_file(LATEST_RAW, "image/jpeg")
            return

        if path == "/latest_detect.json":
            self.send_file(LATEST_JSON, "application/json; charset=utf-8")
            return

        if path.startswith("/captures/"):
            name = Path(path).name
            target = CAPTURE_DIR / name

            if name.endswith(".jpg"):
                self.send_file(target, "image/jpeg")
                return

            if name.endswith(".json"):
                self.send_file(target, "application/json; charset=utf-8")
                return

            self.send_bytes(b"not found", "text/plain; charset=utf-8", 404)
            return

        self.send_bytes(b"not found", "text/plain; charset=utf-8", 404)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"AI dashboard: http://10.10.100.82:{PORT}")
    print(f"Video URL: {VIDEO_URL}")
    server.serve_forever()


if __name__ == "__main__":
    main()
