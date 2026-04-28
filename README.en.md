# Elder Monitor System

An AI YOLOv8 Pose-Based Elderly Monitoring System

## Project Overview

Elder Monitor System is an intelligent monitoring solution designed for nursing homes and home care scenarios, utilizing YOLOv8 pose estimation technology to detect falls. The system provides real-time video surveillance, fall alerts, and hardware integration to ensure the safety and well-being of the elderly.

## Key Features

- **AI Fall Detection**: Real-time human pose analysis using the YOLOv8 Pose model to accurately identify fall events
- **Real-Time Video Monitoring**: Supports multi-camera switching and displays live video feeds with frame rate information
- **Intelligent Alerts**: Automatically triggers audio-visual alarms upon fall detection; can control external hardware via serial port
- **Screenshot Capture**: One-click screenshot saving for post-event review and analysis
- **Log Recording**: Comprehensive logging of system status and alert events

## Technology Stack

- **GUI Framework**: PySide6
- **AI Model**: YOLOv8 Pose (Ultralytics)
- **Image Processing**: OpenCV
- **Hardware Communication**: PySerial

## Project Structure

```
elder_monitor_system/
├── main.py                 # Main entry point, controller class
├── modules/
│   ├── ai_engine.py        # AI video processing module
│   └── hardware_ctrl.py    # Hardware control module
└── ui/
    └── dashboard.py        # UI dashboard component
```

## System Requirements

- Python 3.8+
- Windows/Linux operating system

## Install Dependencies

```bash
pip install PySide6 opencv-python ultralytics pyserial
```

## How to Use

1. Ensure your camera device is connected
2. If hardware integration is needed, connect the alert device to the designated serial port (default: COM3)
3. Run the main program:

```bash
python main.py
```

## Function Operations

- **Switch Camera**: Select from the camera list
- **Save Screenshot**: Click the save button to capture and store a snapshot locally
- **Open Folder**: View saved screenshots and logs
- **Reset System**: Clear current alert status
- **Refresh Cameras**: Re-detect available camera devices

## Configuration Guide

### AI Model

The default model is `yolov8n-pose.pt`. Modify the model path in `modules/ai_engine.py` if needed.

### Serial Port Configuration

Default settings: `PORT=COM3`, `BAUDRATE=9600`. Adjust these values in `modules/hardware_ctrl.py` as required.

## License

MIT License