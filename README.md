# RV1126B 边缘 AI 音视频交互眼镜系统

本仓库为嵌入式芯片与系统设计作品的开源资料仓库，保存 RV1126B 开发板端运行的主体任务代码、作品设计报告和演示视频。作品实现了基于 USB 摄像头、USB 声卡、有线耳麦、GPIO 按钮、4G/WiFi 网络和 Web Dashboard 的边缘 AI 音视频交互系统。

## 作品资料

- 主体任务代码：见 [`code/`](code/)
- 作品设计报告：见 [`docs/作品设计报告.pdf`](docs/作品设计报告.pdf)
- 演示视频：见 [`demo/elf-glasses-demo.mp4`](demo/elf-glasses-demo.mp4)
- 开源协议：见 [`LICENSE`](LICENSE)

## 主要功能

- 唤醒词监听与中文语音命令识别
- USB 声卡 TTS 语音回复
- GPIO 按钮触发拍照识别、视频推流和长按恢复
- USB 摄像头拍照与 RKNN 目标检测
- 音视频推流与网页端 Dashboard 展示
- 网页端语音对讲播放
- WiFi 优先、4G 备用的网络切换
- 4G 低码率视频推流模式
- systemd 开机自启与 watchdog 服务保活

## 目录结构

```text
ELF-Audio-Visual-AI-glasses/
├─ code/
│  ├─ AI感知与目标检测/
│  ├─ 语音交互与主控/
│  ├─ 硬件接口与外设控制/
│  ├─ 视频推流与网页端/
│  ├─ 网络、4G与可靠性/
│  └─ 开机自启与服务保活/
├─ docs/
│  └─ 作品设计报告.pdf
├─ demo/
│  └─ elf-glasses-demo.mp4
├─ README.md
├─ LICENSE
└─ .gitignore
```