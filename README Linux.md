### **🚀 基于 AI YOLOv8 姿态检测的老年人监控系统(Elder Monitor System)**

#### &#x09;			*开发板设备部署方案*



**一、 硬件连接检查**

在开始软件操作前，请确保完成以下物理连接：

&#x09;    摄像头：插入USB接口，并在终端运行ls /dev/video\*确认。
	报警器：后续增加报警功能，插入 USB 转串口线。

&#x09;网络：确保开发板已联网（**用于下载 YOLO 模型和依赖**）。



**二、 环境初始化 (核心步骤)**

Ubuntu 系统通常不带Qt运行环境，必须先安装图形支持库：

\# 1. 更新软件源

sudo apt update \&\& sudo apt upgrade -y

\# 2. 安装图形显示与OpenCV依赖 

sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \\

libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libgl1-mesa-dri \\

libglx-mesa0 v4l-utils -y

\# 3. 授予当前用户硬件访问权限（有管理员权限可忽略）

sudo usermod -aG video $USER

sudo usermod -aG dialout $USER

***执行完权限命令后，必须注销并重新登录或重启***



**三、 代码同步与虚拟环境**

在开发板上建议使用 venv 隔离环境，防止系统 Python 库版本冲突：

\# 1. 克隆gitee仓库代码并切换到master分支

git clone https://gitee.com/r05e/elder\_-monitor\_-system.git

cd elder\_monitor\_system

git checkout master

\# 2. 创建并激活虚拟环境

python3 -m venv .venv

source .venv/bin/activate

\# 3. 安装项目依赖

pip install --upgrade pip

pip install -r requirements.txt



**四、 配置文件微调**

在运行前，请组员打开main.py以下两点：

摄像头索引：Ubuntu 下首个USB摄像头通常是 0。

硬件串口：确认串口路径是否为/dev/ttyUSB0（避免报 Write timeout 错误）。



**五、 启动监控**

\# 在虚拟环境（venv)下启动

python main.py

首次启动：系统会自动下载 yolov8n-pose.pt 模型（约 6.5MB），请保持网络畅通。



