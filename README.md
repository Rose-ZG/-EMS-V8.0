

# Elder Monitor System

基于 AI YOLOv8 姿态检测的老年人监控系统

## 项目简介

Elder Monitor System 是一款面向养老院和家庭场景的智能监控系统，采用 YOLOv8 姿态检测技术实现跌倒检测功能。该系统提供实时视频监控、跌倒报警、硬件联动等功能，为老年人的安全监护提供技术保障。

## 主要特性

- **AI 跌倒检测**：基于 YOLOv8 Pose 模型实时分析人体姿态，精准识别跌倒事件
- **实时视频监控**：支持多摄像头切换，实时显示监控画面和帧率
- **智能报警**：检测到跌倒时自动触发声光报警，并可通过串口控制外部硬件设备
- **截图保存**：一键保存监控快照，便于事后回溯分析
- **日志记录**：完整记录系统运行状态和报警事件

## 技术栈

- **GUI 框架**：PyQt5
- **AI 模型**：YOLOv8 Pose (Ultralytics)
- **图像处理**：OpenCV
- **硬件通信**：PySerial

## 项目结构

```
elder_monitor_system/
├── main.py                 # 主程序入口，控制器类
├── modules/
│   ├── ai_engine.py        # AI 视频处理模块
│   └── hardware_ctrl.py    # 硬件控制模块
└── ui/
    └── dashboard.py        # UI 仪表盘组件
```

## 环境要求

- Python 3.8+
- Windows/Linux 操作系统
- 修改测试，gitee上传功能

## 安装依赖

```bash
pip install PyQt5 opencv-python ultralytics pyserial
```

## 使用方法

1. 确保已连接摄像头设备
2. 如需硬件联动，请连接报警设备至指定串口（默认 COM3）
3. 运行主程序：

```bash
python main.py
```

## 功能操作

- **切换摄像头**：从摄像头列表中选择
- **保存截图**：点击保存按钮，截图将保存至本地
- **打开文件夹**：查看保存的截图和日志
- **重置系统**：清除当前报警状态
- **刷新相机**：重新检测可用摄像头

## 配置说明

### AI 模型

默认使用 `yolov8n-pose.pt` 轻量级模型，可在 `modules/ai_engine.py` 中修改模型路径。

### 串口配置

默认配置：`PORT=COM3`, `BAUDRATE=9600`，可在 `modules/hardware_ctrl.py` 中修改。

## 许可证

MIT License