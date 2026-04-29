
# 居家康复监测系统 v8.0

基于 AI YOLOv8 姿态检测和语音交互的老年人智能监控系统

## 项目简介

Elder Monitor System 是一款面向养老院和家庭场景的智能监控系统，采用 YOLOv8 Pose 模型实时分析人体姿态，精准识别跌倒事件。系统配备语音交互功能，检测到跌倒后主动询问老人，确认需要帮助后才会发送邮件报警，避免误报。

## 主要特性

- **AI 跌倒检测**：基于 YOLOv8 Pose 模型实时分析人体姿态，精准识别跌倒事件
- **语音交互确认**：检测到跌倒后，通过语音合成（TTS）询问老人，语音识别（Whisper）理解回复
- **邮件报警**：确认需要帮助后，自动发送包含跌倒现场截图的邮件给紧急联系人
- **实时视频监控**：支持多摄像头切换，实时显示监控画面和帧率
- **截图保存**：统一保存到 `images/` 文件夹，便于事后回溯分析
- **日志记录**：完整记录系统运行状态和报警事件
- **硬件联动**：支持串口控制外部报警设备

## 技术栈

- **GUI 框架**：PySide6
- **AI 模型**：YOLOv8 Pose (Ultralytics) + Faster Whisper（语音识别）
- **语音合成**：pyttsx3
- **图像处理**：OpenCV
- **硬件通信**：PySerial
- **邮件发送**：smtplib

## 项目结构

```
elder_-monitor_-system/
├── main.py                 # 主程序入口，控制器类
├── voice_assistant.py      # 语音助手模块（TTS + Whisper）
├── modules/
│   ├── ai_engine.py        # AI 视频处理模块
│   ├── hardware_ctrl.py    # 硬件控制模块
│   └── email_notifier.py   # 邮件通知模块
├── ui/
│   └── dashboard.py        # UI 仪表盘组件
├── assets/
│   └── audio/              # 音频资源
├── images/                 # 截图保存文件夹（自动创建）
├── temp/                   # 临时录音文件夹（自动创建）
├── models/                 # Whisper 模型文件夹（需要手动添加）
├── ffmpeg.exe              # FFmpeg 可执行文件
├── ffprobe.exe
├── ffplay.exe
└── requirements.txt        # 依赖包列表
```

## 环境要求

- Python 3.8+
- Windows/Linux 操作系统
- 摄像头设备

## 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：
```bash
pip install PySide6 opencv-python ultralytics pyserial pyttsx3 sounddevice scipy faster-whisper
```

## Whisper 模型配置

1. 将 Faster Whisper 模型文件复制到 `models/whisper-small/` 文件夹
2. 需要的文件：
   - `config.json`
   - `model.bin`
   - `tokenizer.json`
   - `vocabulary.txt`
3. 如果没有模型，系统会自动使用简化模式（只有TTS，语音识别返回默认值）

## 使用方法

1. 确保已连接摄像头设备
2. 如需硬件联动，请连接报警设备至指定串口（默认 COM3）
3. 在 UI 界面中设置紧急联系人邮箱
4. 运行主程序：

```bash
python main.py
```

## 功能操作

- **切换摄像头**：从摄像头列表中选择
- **保存截图**：点击保存按钮，截图保存至 `images/` 文件夹
- **打开文件夹**：查看保存的截图
- **重复呼叫**：手动触发语音交互确认
- **重置系统**：清除当前报警状态
- **刷新相机**：重新检测可用摄像头

## 跌倒报警流程

1. **检测跌倒**：AI 模型持续监控，检测到跌倒后（0.5秒确认）
2. **触发报警**：UI 显示红色报警状态，播放提醒音
3. **语音询问**："系统检测到您可能摔倒了，需要报警吗？请回答需要或不需要。"
4. **用户回复**：录音 5 秒，使用 Whisper 识别
5. **判断处理**：
   - 危险关键词（要、救命、报警等）→ 发送邮件报警
   - 安全关键词（没事、不用、不需要等）→ 取消报警
   - 两次确认无回复 → 发送邮件报警

## 配置说明

### AI 模型

默认使用 `yolov8n-pose.pt` 轻量级模型，可在 `modules/ai_engine.py` 中修改模型路径。

### 邮件配置

- 默认发件邮箱：`2047103550@qq.com`
- 默认授权码：已配置
- 可在 `modules/email_notifier.py` 中修改

### 串口配置

默认配置：`PORT=COM3`, `BAUDRATE=9600`，可在 `modules/hardware_ctrl.py` 中修改。

### 音频路径

音频资源保存在 `assets/audio/` 文件夹中。

## 许可证

MIT License
