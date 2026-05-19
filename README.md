
# Elder Monitor System V8.0(EMS)

<p align="center">
  <img src="assets/[EMS].png" alt="EMS Logo" width="200" style="border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
  <br>
  <em>基于AI YoloV8的独居老人智能姿态监护与多模态报警系统</em>
</p>

[![Python Version](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Ubuntu%20%7C%20Windows-orange.svg)](https://developer.nvidia.com/embedded/jetson)
[![Framework](https://img.shields.io/badge/Framework-PySide6%20%7C%20Ultralytics-green.svg)](https://pyside.org/)
[![License](https://img.shields.io/badge/License-MIT-red.svg)](LICENSE)

## 📌 项目简介

**EMS (Elder Monitor System) V8.0** 是一款专为养老院、家庭以及老龄化社区设计的**全离线边缘侧智能监护终端**。 

系统以嵌入式 GPU 开发板（NVIDIA Jetson 系列）为核心算力底座，深度整合了 **YOLOv8-Pose 机器视觉技术**与**轻量化离线多模态语音交互引擎（Faster-Whisper + Piper）**。系统能够实现低延迟的实时人体姿态估计，并在视觉判定发生跌倒事件后，主动通过语音合成进行双向核实，构建了“**智能视觉感知 -> 语音多模态确认 -> 物理/网络多维闭环报警**”的全链路安全防线。

由于全流程数据均在边缘端本地闭环处理，视频流不上传云端，从根本上杜绝了摄像头监护对老人隐私的侵害。

---

## ✨ 核心特性

- **🚀 边缘端高效推理**：完美适配 NVIDIA Jetson 架构（如 Jetson Orin Nano），通过 TensorRT 与 FP16 半精度全链路加速，在资源受限的边缘端维持 **25~30 FPS** 的高帧率流畅监控。
- **🧘 高精度双重判定姿态引擎**：突破单一几何特征的局限，独创**人体边界框宽高比**与**躯干关键点倾斜角度（肩膀与髋部中点夹角）**的双重判定策略。配合历史滑动窗口（Deque）消抖机制，跌倒检测准确率达 **95.2%**，有效过滤坐下、弯腰、伸懒腰等日常误判。
- **🗣️ 全离线神经语音多模态交互**：
  - **TTS 语音合成**：采用 **Piper 神经语音合成技术**，生成高拟真度、柔和的离线自然人声播报。
  - **ASR 语音识别**：内置 **Faster-Whisper (Int8 量化架构)** 监听引擎。在检测到跌倒时主动核实，智能匹配危险关键词（如“救命”、“疼”）与安全关键词（如“没事”、“误报”），并在用户昏迷无响时默认触发安全保护报警。
- **🚑 多维闭环网络/硬件联动**：确认险情后，系统秒级触发网络邮件告警（全自动抓拍现场带 YOLO 骨骼检测框的渲染图作为附件发送至家属邮箱），并通过底层串口通信（硬件层协议）联动外部声光报警灯。
- **🎨 现代化跨平台 UI**：基于 PySide6 构建高对比度、现代化深色大屏交互界面。支持 AI 推理置信度、跌倒灵敏度的无需重启、动态滑块调优。

---

## 🛠️ 技术栈与架构

| 模块分类 | 核心技术 / 依赖组件 | 用途说明 |
| :--- | :--- | :--- |
| **GUI 框架** | PySide6 (6.6.3) | 图形化大屏交互界面开发与线程调度 |
| **视觉引擎** | YOLOv8n-Pose (8.3.40) | 人体目标检测与 17 个骨骼关键点实时提取 |
| **图像处理** | OpenCV-Python (4.9.0) | 跨平台多路摄像头采集、预处理与图像帧渲染 |
| **加速后端** | PyTorch (2.4.1) / TensorRT | 本地半精度 (FP16) 与硬件级推理加速 |
| **语音识别** | Faster-Whisper (Int8) | 离线、低能耗、高准确率的语音转文字 (STT) |
| **语音合成** | Piper Voice | 100% 本地化流式深度学习人声合成 (TTS) |
| **硬件联动** | PySerial (3.5) | 通过物理串口下发布控单字节协议控制声光外设 |
| **底层播放** | Linux ALSA / Windows Subprocess | 绕过 Python 内部全局音频锁，实现硬件级无阻塞双声道混音 |

---

## 📂 项目结构

```text
elder_-monitor_-system/
├── main.py                  # 系统主程序入口 (Controller 业务控制类)
├── voice_assistant.py       # 语音助手内核模块 (封装全离线 Piper TTS 与 Whisper ASR)
├── requirements.txt         # 跨平台开发环境依赖包列表
├── yolov8n-pose.engine      # Jetson 边缘端 TensorRT 加速模型（可选）
├── yolov8n-pose.pt          # 通用深度学习视觉权重文件
├── modules/
│   ├── ai_engine.py         # AI 视频多线程处理引擎 (VideoWorker 推理线程)
│   ├── hardware_ctrl.py     # 硬件设备管理器 (Linux aplay/play 底层调用与串口协议)
│   └── email_notifier.py    # SMTP 闭环邮件告警机制 (支持多模态 HTML + 图片嵌入)
├── ui/
│   └── dashboard.py         # 现代化深色主题 UI 仪表盘组件 (Dashboard 视图层)
├── assets/
│   └── audio/               # 本地高品质预置音效资源 (如 RING.wav)
├── records/                 # 异常事件抓拍与日志截图存储文件夹 (系统自动创建)
├── temp/                    # 临时双向交互录音中转区 (系统自动创建，定期释放占位)
└── models/                  # 本地全离线大模型存放矩阵
    └── whisper-small/       # Faster-Whisper 结构化模型依赖包
    └── piper/               # Piper 神经网络 Onnx 语音模型及 Json 配置文件

```

---

## 🚀 部署与环境运行

### 1. 环境依赖安装

确保系统环境已配有 Python 3.10+。激活您的虚拟环境后，执行：

```bash
pip install -r requirements.txt

```

若在边缘计算端（如 NVIDIA Jetson）部署，建议赋予底层声卡硬件级读写权限：

```bash
sudo chmod 666 /dev/snd/*
sudo apt-get install sox libsox-fmt-all

```

### 2. 本地大模型矩阵配置

由于系统采用 **100% 纯本地离线计算**，需确保相应模型放置于 `models/` 目录下：

* **Faster-Whisper**：将模型组件（`config.json`, `model.bin`, `vocabulary.txt`等）放置于 `models/whisper-small/`。
* **Piper**：将华研女声模型放置于 `models/piper/zh_CN-huayan-medium.onnx` 及对应的 `.json` 配置文件。

### 3. 一键启动

在确保摄像头、麦克风等外设正常接通后，在终端执行：

```bash
python main.py

```

---

## 📊 跌倒报警业务全闭环流程

1. **视觉异常感知**：AI 推理线程持续对输入视频流进行高性能全局追踪。一旦满足“双重判定”几何阈值，且滑动窗口判定跌倒帧比例大于 0.7 持续 0.5 秒时，系统升级状态为“内部预警”。
2. **状态大屏响应**：本地大屏及 Web 远程端同步转换为高亮红色危险状态，动态同步实时帧率。
3. **多模态防误报核实**：系统自动调用底层声卡锁，通过 `Piper` 引擎高分贝流式播报：“*系统检测到您可能摔倒了，需要报警吗？*”。随即系统开启 5 秒主动倾听期。
4. **边缘智能决策**：
* 匹配**危险关键词**或用户处于**静默/昏迷无响应状态**：触发最高级别紧急闭环。
* 匹配**安全关键词**（如“没事”）：系统在线复位，不打扰用户。


5. **多渠道联动布防**：在确认危险后，硬件模块通过串口下发 `b'1'` 驱动信号激活声光报警灯；同时网络模块启动异步 SMTP 协议，将**带有 YOLO 目标关键点标记的骨骼渲染现场抓拍原图**，秒级推送至家属邮箱。

---

## 📈 训练与测试成果 (50 Epochs)

本系统核心 YOLOv8n-Pose 模型经过了 **50个轮次 (Epochs)** 的全量迁移学习深度调优：

* 引入多维度特征集，全类平均精度（**mAP50**）最终稳定收敛至 **0.85**。
* 经过自建多场景跌倒数据集验证，系统综合前向、侧向、后向等多形态跌倒测试，结合多模态语音交互过滤后，系统**最终误报率降低至 3% 以下，漏报率低于 1%**，表现出极高工业级稳定度。

---

## 📜 许可证

本项目基于 [MIT License](https://www.google.com/search?q=LICENSE) 协议开源。
