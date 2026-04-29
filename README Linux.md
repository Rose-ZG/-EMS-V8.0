### **🚀 基于 AI YOLOv8 姿态检测的老年人监控系统(Elder Monitor System v8.0)**

#### 			*开发板设备部署方案*

**一、 硬件连接检查**

在开始软件操作前，请确保完成以下物理连接：

    摄像头：插入USB接口，并在终端运行ls /dev/video*确认。
	报警器：后续增加报警功能，插入 USB 转串口线。

	网络：确保开发板已联网（**用于下载 YOLO 模型和依赖**）。

**二、 环境初始化 (核心步骤)**

Ubuntu 系统通常不带Qt运行环境，必须先安装图形支持库：

# 1. 更新软件源

sudo apt update && sudo apt upgrade -y

# 2. 安装图形显示与OpenCV依赖 

sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \

libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libgl1-mesa-dri \

libglx-mesa0 v4l-utils ffmpeg -y

# 3. 授予当前用户硬件访问权限（有管理员权限可忽略）

sudo usermod -aG video $USER

sudo usermod -aG dialout $USER

***执行完权限命令后，必须注销并重新登录或重启***

**三、 代码同步与虚拟环境**

在开发板上建议使用 venv 隔离环境，防止系统 Python 库版本冲突：

# 1. 克隆gitee仓库代码并切换到master分支

git clone https://gitee.com/r05e/elder_-monitor_-system.git

cd elder_-monitor_-system

git checkout master

# 2. 创建并激活虚拟环境

python3 -m venv .venv

source .venv/bin/activate

# 3. 安装项目依赖

pip install --upgrade pip

pip install -r requirements.txt

**四、 Whisper 模型配置（可选）**

v8.0 新增语音交互功能，需要配置 Whisper 模型：

# 1. 创建模型文件夹

mkdir -p models/whisper-small

# 2. 将 Faster Whisper 模型文件复制到该文件夹

需要的文件：
- config.json
- model.bin
- tokenizer.json
- vocabulary.txt

# 3. 如果没有模型，系统会自动使用简化模式（只有TTS）

**五、 配置文件微调**

在运行前，请组员打开以下文件进行配置：

1. 摄像头索引：Ubuntu 下首个USB摄像头通常是 0。
2. 硬件串口：确认串口路径是否为/dev/ttyUSB0（避免报 Write timeout 错误）。
3. 邮件配置：在 modules/email_notifier.py 中配置邮箱地址和授权码。

**六、 启动监控**

# 在虚拟环境（venv)下启动

python main.py

首次启动：系统会自动下载 yolov8n-pose.pt 模型（约 6.5MB），请保持网络畅通。

**七、 v8.0 新功能说明**

1. 语音交互确认：检测到跌倒后，通过TTS询问老人，Whisper识别回复
2. 邮件报警：确认需要帮助后，发送包含截图的邮件
3. 统一文件夹结构：
   - images/：截图保存
   - temp/：临时录音
   - models/：Whisper模型
   - assets/audio/：音频资源
4. 按钮变更："确认呼叫" → "重复呼叫"

**八、 跌倒报警流程**

1. AI检测跌倒（0.5秒确认）
2. UI显示红色报警，播放提醒音
3. 语音询问："系统检测到您可能摔倒了，需要报警吗？请回答需要或不需要。"
4. 录音5秒，Whisper识别
5. 根据关键词判断是否发送邮件
