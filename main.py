import sys, os, time, cv2, subprocess
import platform

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

from modules.ai_engine import VideoWorker
from modules.hardware_ctrl import HardwareManager
from modules.logger import Logger
from ui.dashboard import MainDashboard
from dotenv import load_dotenv
load_dotenv()

from modules.email_notifier import EmailNotifier

class Controller(QMainWindow):
    def __init__(self):
        self.os_type = platform.system()
        super().__init__()
        self.setWindowTitle("居家康复监测系统[EMS] v8.0")
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
        self.ui.cam_selector.currentIndexChanged.connect(self.change_camera)
        self.ui.t_slider.valueChanged.connect(self.sync_params)
        self.ui.c_slider.valueChanged.connect(self.sync_params)
        self.ui.reset_btn.clicked.connect(self.reset_system)
        self.ui.snap_btn.clicked.connect(lambda: self.save_snapshot("MANUAL"))
        self.ui.open_btn.clicked.connect(self.open_folder)
        self.ui.call_btn.clicked.connect(self.call_for_help)
        self.ui.save_phone_btn.clicked.connect(self.save_phone_number)

        self.sync_params()
        self.worker.start()
        self.refresh_cameras()

        self.smtp_config = {
            "server": "smtp.qq.com",
            "port": 465,
            "user": "2047103550@qq.com",
            "password": os.environ.get("SMTP_PASSWORD", "")
        }
        self.email_notifier = EmailNotifier(self.smtp_config)

        self.contacts = [
            {"name": "家属A", "email": "2047103550@qq.com", "phone": "", "enabled": True}
        ]

    def sync_params(self):
        slider_val = self.ui.t_slider.value()
        self.worker.threshold = 2.0 - (slider_val / 100.0)
        self.worker.angle_threshold = 95 - slider_val
        self.worker.conf_val = self.ui.c_slider.value() / 100.0

    def update_ui(self, img, is_fall, fps):
        self.ui.video_label.setPixmap(QPixmap.fromImage(img))
        self.ui.fps_label.setText(f"FPS: {fps:.1f}")

        # 管理报警状态（与语音交互联动）
        if not self.worker.is_interacting and not self.worker.is_alarming:
            fall_ratio = self.worker.get_fall_ratio()

    def process_emergency_alert(self, frame):
        """阶段二：语音确认危险，发送急救邮件"""
        self.ui.status_label.setText("🚨 紧急求救！已发送通知")
        self.log.alert("CRITICAL: 语音确认异常！触发终极报警闭环")

        for contact in self.contacts:
            if contact.get("enabled") and contact.get("email"):
                self.email_notifier.send_fall_alert(
                    contact["email"], frame, location="居家环境监控点A")
                self.log.alert(f"告警邮件已发送至 {contact['name']}({contact['email']})")

    def trigger_local_alarm(self):
        """阶段一：视觉发现跌倒，瞬间让 UI 变红并开启物理警报灯"""
        self.ui.status_label.setText("🚨 发现跌倒！语音核实中...")
        self.ui.status_label.setStyleSheet(
            "font-size:20pt; color:white; background:#d9534f; font-weight:bold; border-radius:14px; padding:14px;")
        self.hw.alert_with_voice(active=True)
        self.log.alert("WARN: 视觉检测到跌倒，正在进行语音核实...")
    def call_for_help(self):
        # 【追加防护】：如果 AI 正在交互中，忽略手动点击
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
        for contact in self.contacts:
            if contact.get("enabled") and contact.get("email"):
                success = self.email_notifier.send_fall_alert(contact["email"], fall_frame, location="老人卧室")
                if success:
                    self.log.success(f"告警邮件已发送至 {contact['name']}({contact['email']})")
                else:
                    self.log.error(f"发送至 {contact['name']}({contact['email']}) 失败")

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

    def save_phone_number(self):
        email = self.ui.phone_edit.text().strip()
        if email and "@" in email and "." in email.split("@")[-1]:
            self.log.success(f"紧急联系人邮箱已设置: {email}")
        else:
            self.log.error("请输入有效的邮箱地址")

    def closeEvent(self, event):
        self.worker.stop()
        self.hw.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = Controller()
    window.show()
    sys.exit(app.exec())