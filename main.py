import sys, os
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# 抑制 OpenCV / FFmpeg / numpy 向 stderr 输出重复错误
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"

import time, cv2, subprocess, io, platform
import logging
import numpy as np

np.set_printoptions(suppress=True)

# 静默第三方库日志
for _name in ('ultralytics', 'faster_whisper', 'PIL', 'matplotlib'):
    logging.getLogger(_name).setLevel(logging.ERROR)

from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

from modules.ai_engine import VideoWorker
from modules.hardware_ctrl import HardwareManager
from modules.logger import Logger
from ui.dashboard import MainDashboard
from modules._resource import resource_path
from dotenv import load_dotenv

load_dotenv(resource_path('.env'))

from ui.setup_dialog import SetupDialog
from modules.email_notifier import EmailNotifier


class Controller(QMainWindow):
    def __init__(self):
        self.os_type = platform.system()
        super().__init__()
        self.setWindowTitle("居家康复监测系统[EMS] v8.0")
        self.setWindowIcon(QIcon(resource_path("assets/EMS_logo_new.ico")))
        self.resize(1200, 850)

        self.available_cams = []
        self.fall_start_time = None
        self.is_fall_ongoing = False

        self.ui = MainDashboard()
        self.setCentralWidget(self.ui)

        # 初始化统一日志系统
        self.log = Logger()
        self.log.signal.message.connect(self.ui.append_log_html)
        self.log.capture_stdout()

        self.hw = HardwareManager()

        self.worker = VideoWorker(debug=False)
        self.worker.change_pixmap_signal.connect(self.update_ui, Qt.QueuedConnection)
        self.worker.emergency_call_signal.connect(self.process_emergency_alert, Qt.QueuedConnection)
        self.worker.pre_alarm_signal.connect(self.trigger_local_alarm, Qt.QueuedConnection)
        self.worker.cancel_alarm_signal.connect(self.reset_system, Qt.QueuedConnection)

        # 绑定控件
        self.ui.ref_btn.clicked.connect(self.refresh_cameras)
        self.ui.import_video_btn.clicked.connect(self.import_test_video)
        self.ui.cam_selector.currentIndexChanged.connect(self.change_camera)
        self.ui.t_slider.valueChanged.connect(self.sync_params)
        self.ui.c_slider.valueChanged.connect(self.sync_params)
        self.ui.reset_btn.clicked.connect(self.reset_system)
        self.ui.snap_btn.clicked.connect(lambda: self.save_snapshot("MANUAL"))
        self.ui.open_btn.clicked.connect(self.open_folder)
        self.ui.call_btn.clicked.connect(self.call_for_help)
        self.ui.save_phone_btn.clicked.connect(self.save_phone_number)  # 绑定保存按钮
        self.ui.test_email_btn.clicked.connect(self.send_test_email)  # 测试邮件按钮

        self.sync_params()
        self.worker.start()
        self.refresh_cameras()

        self.smtp_config = {
            "server": os.environ.get("SMTP_SERVER", "smtp.qq.com"),
            "port": int(os.environ.get("SMTP_PORT", "465")),
            "user": os.environ.get("SMTP_USER", ""),
            "password": os.environ.get("SMTP_PASSWORD", "")
        }
        self.email_notifier = EmailNotifier(self.smtp_config)

        # 从环境变量读取紧急联系人邮箱（支持逗号分隔多个邮箱）
        default_email_str = os.environ.get("DEFAULT_ALERT_EMAIL", "")
        if default_email_str:
            email_list = [e.strip() for e in default_email_str.split(",") if e.strip()]
        else:
            # 如果未配置紧急联系人，默认使用发件邮箱（向后兼容）
            email_list = [self.smtp_config.get("user", "")]
        email_list = [e for e in email_list if e]  # 过滤空字符串

        self.contacts = []
        for i, email in enumerate(email_list):
            name = f"紧急联系人{i + 1}" if len(email_list) > 1 else "紧急联系人"
            self.contacts.append({"name": name, "email": email, "phone": "", "enabled": True})

        # 回显到 UI 输入框中（显示第一个联系人邮箱）
        if hasattr(self.ui, 'phone_edit') and self.contacts:
            self.ui.phone_edit.setText(self.contacts[0]["email"])

    def sync_params(self):
        slider_val = self.ui.t_slider.value()
        self.worker.threshold = 2.0 - (slider_val / 100.0)
        self.worker.angle_threshold = 95 - slider_val
        self.worker.conf_val = self.ui.c_slider.value() / 100.0

    def update_ui(self, img, is_fall, fps):
        self.ui.video_label.setPixmap(QPixmap.fromImage(img))
        self.ui.fps_label.setText(f"FPS: {fps:.1f}")

        if not self.worker.is_interacting and not self.worker.is_alarming:
            fall_ratio = self.worker.get_fall_ratio()

    def process_emergency_alert(self, frame):
        """阶段二：语音确认危险，发送急救邮件"""
        self.ui.status_label.setText("🚨 紧急求救！已发送通知")
        self.log.alert("CRITICAL: 语音确认异常！触发终极报警闭环")

        # 【修改 2】：统一调用带异常捕获的发送函数
        self.send_alert_email(frame)

    def trigger_local_alarm(self):
        """阶段一：视觉发现跌倒，瞬间让 UI 变红并开启物理警报灯"""
        self.ui.status_label.setText("🚨 发现跌倒！语音核实中...")
        self.ui.status_label.setStyleSheet(
            "font-size:20pt; color:white; background:#d9534f; font-weight:bold; border-radius:14px; padding:14px;")
        self.hw.alert_with_voice(active=True)
        self.log.alert("WARN: 视觉检测到跌倒，正在进行语音核实...")

    def call_for_help(self):
        if self.worker.is_interacting:
            self.log.warn("系统正在语音交互中，请稍后再试")
            return
        self.log.info("用户手动呼叫 - 启动语音确认流程")
        self.worker.assistant.speak("检测到异常情况，是否需要帮助？请在三秒内回答")

    def reset_system(self):
        self.worker.is_alarming = False
        self.worker.is_interacting = False
        self.is_fall_ongoing = False
        self.fall_start_time = None
        self.worker.fall_history.clear()
        self.ui.status_label.setText("🟢 系统监控中")
        self.ui.status_label.setStyleSheet(
            "font-size:20pt; font-weight:bold; color:#11111b; background:#a6e3a1; border-radius:14px; padding:14px;")
        self.hw.alert_with_voice(active=False)
        self.log.success("系统已复位，恢复正常监控")

    def send_alert_email(self, fall_frame):
        """闭环告警：向所有启用的联系人发送邮件"""
        has_enabled_contact = False
        for contact in self.contacts:
            if contact.get("enabled") and contact.get("email"):
                has_enabled_contact = True
                # 执行发送
                success = self.email_notifier.send_fall_alert(
                    contact["email"], fall_frame, location="居家环境监控点A"
                )
                if success:
                    self.log.success(f"📩 告警邮件已成功发送至: {contact['name']}({contact['email']})")
                else:
                    self.log.error(f"❌ 发送至 {contact['name']}({contact['email']}) 失败，请检查邮件配置")

        if not has_enabled_contact:
            self.log.warn("⚠️ 未检测到有效的紧急联系人邮箱，跳过邮件发送。")

    def save_phone_number(self):
        """获取输入框的邮箱，并真正更新到 self.contacts 中"""
        email = self.ui.phone_edit.text().strip()
        if email and "@" in email and "." in email.split("@")[-1]:
            # 支持逗号分隔多个邮箱
            email_list = [e.strip() for e in email.split(",") if e.strip()]
            self.contacts = []
            for i, em in enumerate(email_list):
                name = f"紧急联系人{i + 1}" if len(email_list) > 1 else "紧急联系人"
                self.contacts.append({"name": name, "email": em, "phone": "", "enabled": True})
            self.log.success(f"✅ 紧急联系人邮箱已成功设置为: {email}")
        else:
            self.log.error("❌ 请输入有效的邮箱地址（如: example@qq.com，多个邮箱用逗号分隔）")

    def send_test_email(self):
        """发送测试邮件验证邮箱配置是否正确"""
        # 先确保联系人信息是最新的
        current_email = self.ui.phone_edit.text().strip()
        if current_email and "@" in current_email:
            email_list = [e.strip() for e in current_email.split(",") if e.strip()]
            self.contacts = []
            for i, em in enumerate(email_list):
                name = f"紧急联系人{i + 1}" if len(email_list) > 1 else "紧急联系人"
                self.contacts.append({"name": name, "email": em, "phone": "", "enabled": True})

        if not self.contacts:
            self.log.error("❌ 请先在紧急联系人输入框中输入邮箱地址")
            return

        self.log.info("📧 正在发送测试邮件...")
        has_enabled_contact = False
        all_success = True
        for contact in self.contacts:
            if contact.get("enabled") and contact.get("email"):
                has_enabled_contact = True
                # 创建一个空白测试帧
                test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(test_frame, "EMS Test Email", (120, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
                cv2.putText(test_frame, time.strftime('%Y-%m-%d %H:%M:%S'), (140, 300),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

                success = self.email_notifier.send_fall_alert(
                    contact["email"], test_frame, location="居家环境监控点A [测试]"
                )
                if success:
                    self.log.success(f"✅ 测试邮件已成功发送至: {contact['name']}({contact['email']})")
                else:
                    self.log.error(f"❌ 发送至 {contact['name']}({contact['email']}) 失败，请检查SMTP配置")
                    all_success = False

        if not has_enabled_contact:
            self.log.error("❌ 未检测到有效的紧急联系人邮箱")
        elif all_success:
            self.log.success("🎉 所有测试邮件发送成功！邮件告警系统工作正常")

    def refresh_cameras(self):
        self.ui.cam_selector.blockSignals(True)
        self.ui.cam_selector.clear()
        valid = []
        backend = cv2.CAP_DSHOW if self.os_type == "Windows" else cv2.CAP_V4L2
        for i in range(3):
            cap = cv2.VideoCapture(i, backend)
            if cap.isOpened():
                valid.append(i)
                cap.release()
        self.available_cams = valid
        self.ui.cam_selector.addItems([f"设备 {i}" for i in valid])
        if valid:
            self.ui.cam_selector.setCurrentIndex(0)
            self.worker.request_camera_switch(valid[0])
        self.ui.cam_selector.blockSignals(False)

    def change_camera(self, index):
        if 0 <= index < len(self.available_cams):
            self.worker.request_camera_switch(self.available_cams[index])

    def import_test_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择本地跌倒测试视频", "", "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv)"
        )
        if file_path:
            self.worker.request_video_file(file_path)
            self.log.info(f"📁 已切换至测试视频: {os.path.basename(file_path)}")

    def save_snapshot(self, prefix):
        path = os.path.join(os.getcwd(), "records")
        os.makedirs(path, exist_ok=True)
        file_path = os.path.join(path, f"{prefix}_{time.strftime('%H%M%S')}.jpg")
        if self.ui.video_label.pixmap():
            self.ui.video_label.pixmap().save(file_path)
            self.log.info("截图已保存")

    def open_folder(self):
        path = os.path.join(os.getcwd(), "records")
        os.makedirs(path, exist_ok=True)
        if self.os_type == 'Windows':
            os.startfile(path)
        elif self.os_type == 'Darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])

    def closeEvent(self, event):
        self.worker.stop()
        self.hw.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if SetupDialog.needs_setup():
        dlg = SetupDialog()
        if dlg.exec() == QDialog.Rejected:
            pass

    window = Controller()
    window.show()
    sys.exit(app.exec())