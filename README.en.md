# Elder Monitor System v8.0

An AI YOLOv8 Pose-Based Elderly Monitoring System with Voice Interaction

## Project Overview

Elder Monitor System is an intelligent monitoring solution designed for nursing homes and home care scenarios, utilizing YOLOv8 pose estimation technology to detect falls. The system features voice interaction capability - upon detecting a fall, it actively asks the elderly person for confirmation, and only sends email alerts when help is confirmed, thus avoiding false alarms.

## Key Features

- **AI Fall Detection**: Real-time human pose analysis using the YOLOv8 Pose model to accurately identify fall events
- **Voice Interaction Confirmation**: Upon fall detection, uses TTS (Text-to-Speech) to ask the elderly, and Whisper for speech recognition to understand responses
- **Email Alerts**: After confirming help is needed, automatically sends an email with fall scene screenshot to emergency contacts
- **Real-Time Video Monitoring**: Supports multi-camera switching and displays live video feeds with frame rate information
- **Screenshot Capture**: Unified storage in `images/` folder for post-event review and analysis
- **Log Recording**: Comprehensive logging of system status and alert events
- **Hardware Integration**: Support for serial port control of external alert devices

## Technology Stack

- **GUI Framework**: PySide6
- **AI Models**: YOLOv8 Pose (Ultralytics) + Faster Whisper (Speech Recognition)
- **Text-to-Speech**: pyttsx3
- **Image Processing**: OpenCV
- **Hardware Communication**: PySerial
- **Email Sending**: smtplib

## Project Structure

```
elder_-monitor_-system/
├── main.py                 # Main entry point, controller class
├── voice_assistant.py      # Voice assistant module (TTS + Whisper)
├── modules/
│   ├── ai_engine.py        # AI video processing module
│   ├── hardware_ctrl.py    # Hardware control module
│   └── email_notifier.py   # Email notification module
├── ui/
│   └── dashboard.py        # UI dashboard component
├── assets/
│   └── audio/              # Audio resources
├── images/                 # Screenshot folder (auto-created)
├── temp/                   # Temp recording folder (auto-created)
├── models/                 # Whisper model folder (needs manual setup)
├── ffmpeg.exe              # FFmpeg executable
├── ffprobe.exe
├── ffplay.exe
└── requirements.txt        # Dependency list
```

## System Requirements

- Python 3.8+
- Windows/Linux operating system
- Camera device

## Install Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install PySide6 opencv-python ultralytics pyserial pyttsx3 sounddevice scipy faster-whisper
```

## Whisper Model Setup

1. Copy Faster Whisper model files to `models/whisper-small/` folder
2. Required files:
   - `config.json`
   - `model.bin`
   - `tokenizer.json`
   - `vocabulary.txt`
3. If no model is found, system automatically uses simplified mode (TTS only, speech recognition returns default value)

## How to Use

1. Ensure your camera device is connected
2. If hardware integration is needed, connect the alert device to the designated serial port (default: COM3)
3. Set emergency contact email in the UI
4. Run the main program:

```bash
python main.py
```

## Function Operations

- **Switch Camera**: Select from the camera list
- **Save Screenshot**: Click the save button, screenshots are saved to `images/` folder
- **Open Folder**: View saved screenshots
- **Repeat Call**: Manually trigger voice interaction confirmation
- **Reset System**: Clear current alert status
- **Refresh Cameras**: Re-detect available camera devices

## Fall Alert Process

1. **Detect Fall**: AI model continuously monitors, triggers after 0.5 seconds of confirmation
2. **Trigger Alert**: UI shows red alert status, plays alert sound
3. **Voice Query**: "系统检测到您可能摔倒了，需要报警吗？请回答需要或不需要。" (System detected you may have fallen, need help? Please answer yes or no)
4. **User Response**: Record for 5 seconds, recognize with Whisper
5. **Decision Handling**:
   - Danger keywords (need, help, alarm, etc.) → Send email alert
   - Safety keywords (fine, no need, etc.) → Cancel alert
   - No response after 2 confirmations → Send email alert

## Configuration Guide

### AI Model

Default model is `yolov8n-pose.pt`. Modify the model path in `modules/ai_engine.py` if needed.

### Email Configuration

- Default sender: `2047103550@qq.com`
- Default authorization code: Pre-configured
- Can be modified in `modules/email_notifier.py`

### Serial Port Configuration

Default settings: `PORT=COM3`, `BAUDRATE=9600`. Adjust these values in `modules/hardware_ctrl.py` as required.

### Audio Path

Audio resources are stored in `assets/audio/` folder.

## License

MIT License
