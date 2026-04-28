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
from ui.dashboard import MainDashboard
from modules.email_notifier import EmailNotifier
from voice_assistant import VoiceAssistant

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

        mp3_path = os.path.join(os.path.dirname(__file__), "assets", "audio", "RING.wav")
        self.hw = HardwareManager(mp3_path=mp3_path)

        self.worker = VideoWorker(debug=False)
        self.worker.change_pixmap_signal.connect(self.update_ui, Qt.QueuedConnection)
        self.worker.emergency_call_signal.connect(self.process_emergency_alert, Qt.QueuedConnection)

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
            "password": "liwkwdbylezpeajg"
        }
        self.email_notifier = EmailNotifier(self.smtp_config)

        self.voice_assistant = VoiceAssistant()

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
            if fall_ratio > 0.7:
                if not self.is_fall_ongoing:
                    self.is_fall_ongoing = True
                    self.fall_start_time = time.time()
                elif time.time() - self.fall_start_time > 0.5:
                    self.trigger_alarm()
            else:
                self.is_fall_ongoing = False
                self.fall_start_time = None

    def process_emergency_alert(self, frame):
        # 1. 更新UI报警状态
        self.ui.status_label.setText("🚨 紧急报警！")
        self.ui.status_label.setStyleSheet(
            "font-size:20pt; color:white; background:#d9534f; font-weight:bold; border-radius:14px; padding:14px;")

        # 2. 自动发送邮件 (带截帧)
        email_addr = "2047103550@qq.com"  # 实际开发可从 UI 获取
        self.email_notifier.send_fall_alert(email_addr, frame, location="居家环境监控点A")

        # 3. 日志记录
        self.add_log(f"ALERT: 自动闭环告警已触发，邮件已发送至 {email_addr}")

    def trigger_alarm(self):
        if self.worker.is_alarming:
            return
        self.worker.is_alarming = True
        self.ui.status_label.setText("🚨 紧急报警！")
        self.ui.status_label.setStyleSheet(
            "font-size:20pt; color:white; background:#d9534f; font-weight:bold; border-radius:14px; padding:14px;")
        self.hw.alert_with_voice(active=True)
        self.add_log("CRITICAL: 检测到跌倒！已触发报警")

    def call_for_help(self):
        self.add_log("USER: 重复呼叫 - 正在使用语音合成进行摔倒确认")
        self.voice_assistant.speak("检测到异常情况，是否需要帮助？请在五秒内回答")

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
        self.add_log("INFO: 系统已复位")

    def send_alert_email(self, fall_frame):
        """闭环告警：接收 AI 引擎传来的截帧并发送邮件"""
        receiver = self.ui.phone_edit.text().strip() # 此时 UI 框应输入邮箱
        if "@" in receiver:
            # 异步发送邮件防止主界面卡死
            success = self.email_notifier.send_fall_alert(receiver, fall_frame, location="老人卧室")
            if success:
                self.add_log(f"SUCCESS: 告警邮件及截帧已发送至 {receiver}")
            else:
                self.add_log("ERROR: 邮件发送失败，请检查网络或授权码")
        else:
            self.add_log("ERROR: 未设置有效的紧急联系人邮箱")

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
            self.add_log(f"已保存截图")

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
            self.add_log(f"INFO: 紧急联系人邮箱已设置: {email}")
        else:
            self.add_log("ERROR: 请输入有效的邮箱地址")

    def add_log(self, msg):
        self.ui.append_log(f"[{time.strftime('%H:%M:%S')}] {msg}")

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