import logging
import os
import platform
import subprocess
import sys
import time

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QDialog, QMainWindow

from modules._resource import ensure_runtime_dirs, resource_path
from modules.ai_engine import VideoWorker
from modules.email_notifier import EmailNotifier
from modules.hardware_ctrl import HardwareManager
from modules.logger import Logger
from ui.dashboard import MainDashboard
from ui.setup_dialog import SetupDialog

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False


if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"

np.set_printoptions(suppress=True)

for logger_name in ("ultralytics", "faster_whisper", "PIL", "matplotlib"):
    logging.getLogger(logger_name).setLevel(logging.ERROR)

load_dotenv(resource_path(".env"))


class Controller(QMainWindow):
    def __init__(self):
        super().__init__()
        self.os_type = platform.system()
        self.available_cams = []
        self.contacts = []
        self.is_fall_ongoing = False
        self.fall_start_time = None

        self.setWindowTitle("Elder Monitor System [EMS] v8.0")
        self.resize(1200, 850)
        self._apply_window_icon()

        self.ui = MainDashboard()
        self.setCentralWidget(self.ui)

        self.log = Logger()
        self.log.signal.message.connect(self.ui.append_log_html)
        self.log.capture_stdout()

        self.hw = HardwareManager()
        self.worker = VideoWorker(debug=False)
        self.worker.change_pixmap_signal.connect(self.update_ui, Qt.QueuedConnection)
        self.worker.emergency_call_signal.connect(self.process_emergency_alert, Qt.QueuedConnection)
        self.worker.pre_alarm_signal.connect(self.trigger_local_alarm, Qt.QueuedConnection)
        self.worker.cancel_alarm_signal.connect(self.reset_system, Qt.QueuedConnection)

        self._bind_ui()
        self._setup_email_contacts()

        self.sync_params()
        self.worker.start()
        self.refresh_cameras()
        self.log.info("EMS controller started.")

    def _apply_window_icon(self):
        for candidate in ("assets/[EMS].png", "img.png"):
            icon_path = resource_path(candidate)
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                return

    def _bind_ui(self):
        self.ui.ref_btn.clicked.connect(self.refresh_cameras)
        self.ui.import_video_btn.clicked.connect(self.import_test_video)
        self.ui.cam_selector.currentIndexChanged.connect(self.change_camera)
        self.ui.t_slider.valueChanged.connect(self.sync_params)
        self.ui.c_slider.valueChanged.connect(self.sync_params)
        self.ui.reset_btn.clicked.connect(self.reset_system)
        self.ui.snap_btn.clicked.connect(lambda: self.save_snapshot("MANUAL"))
        self.ui.open_btn.clicked.connect(self.open_folder)
        self.ui.call_btn.clicked.connect(self.call_for_help)
        self.ui.save_phone_btn.clicked.connect(self.save_phone_number)
        self.ui.test_email_btn.clicked.connect(self.send_test_email)

    def _setup_email_contacts(self):
        self.smtp_config = {
            "server": os.environ.get("SMTP_SERVER", "smtp.qq.com"),
            "port": int(os.environ.get("SMTP_PORT", "465")),
            "user": os.environ.get("SMTP_USER", ""),
            "password": os.environ.get("SMTP_PASSWORD", ""),
        }
        self.email_notifier = EmailNotifier(self.smtp_config)

        raw_emails = os.environ.get("DEFAULT_ALERT_EMAIL", "") or self.smtp_config.get("user", "")
        self._replace_contacts_from_text(raw_emails)
        if self.contacts:
            self.ui.phone_edit.setText(", ".join(contact["email"] for contact in self.contacts))

    def _replace_contacts_from_text(self, email_text: str):
        self.contacts = []
        email_list = [item.strip() for item in email_text.split(",") if item.strip()]
        for index, email in enumerate(email_list, start=1):
            name = f"Emergency Contact {index}" if len(email_list) > 1 else "Emergency Contact"
            self.contacts.append({"name": name, "email": email, "phone": "", "enabled": True})

    def sync_params(self):
        slider_val = self.ui.t_slider.value()
        self.worker.threshold = 2.0 - (slider_val / 100.0)
        self.worker.angle_threshold = 95 - slider_val
        self.worker.conf_val = self.ui.c_slider.value() / 100.0

    def update_ui(self, img, is_fall, fps):
        self.ui.video_label.setPixmap(QPixmap.fromImage(img))
        self.ui.fps_label.setText(f"FPS: {fps:.1f}")
        if not self.worker.is_interacting and not self.worker.is_alarming:
            self.ui.status_label.setText("Monitoring" if not is_fall else "Possible fall detected")

    def process_emergency_alert(self, frame):
        self.ui.status_label.setText("Emergency alert sent")
        self.log.alert("Voice confirmation marked this event as an emergency.")
        self.send_alert_email(frame)

    def trigger_local_alarm(self):
        self.ui.status_label.setText("Possible fall detected, confirming by voice...")
        self.ui.status_label.setStyleSheet(
            "font-size:20pt; color:white; background:#d9534f; font-weight:bold; border-radius:14px; padding:14px;"
        )
        self.hw.alert_with_voice(active=True)
        self.log.alert("Visual fall detection triggered local alarm.")

    def call_for_help(self):
        if self.worker.is_interacting:
            self.log.warn("Voice interaction is already in progress.")
            return
        self.log.info("Manual help check started.")
        self.worker.assistant.speak("We detected something unusual. Do you need help?")

    def reset_system(self):
        self.worker.is_alarming = False
        self.worker.is_interacting = False
        self.is_fall_ongoing = False
        self.fall_start_time = None
        self.worker.fall_history.clear()
        self.ui.status_label.setText("Monitoring")
        self.ui.status_label.setStyleSheet(
            "font-size:20pt; font-weight:bold; color:#11111b; background:#a6e3a1; border-radius:14px; padding:14px;"
        )
        self.hw.alert_with_voice(active=False)
        self.log.success("System reset complete.")

    def send_alert_email(self, fall_frame):
        has_enabled_contact = False
        for contact in self.contacts:
            if contact.get("enabled") and contact.get("email"):
                has_enabled_contact = True
                success = self.email_notifier.send_fall_alert(contact["email"], fall_frame, location="EMS device")
                if success:
                    self.log.success(f"Alert email sent to {contact['name']} ({contact['email']}).")
                else:
                    self.log.error(f"Failed to send alert email to {contact['name']} ({contact['email']}).")

        if not has_enabled_contact:
            self.log.warn("No valid emergency email address is configured.")

    def save_phone_number(self):
        email_text = self.ui.phone_edit.text().strip()
        if email_text and "@" in email_text:
            self._replace_contacts_from_text(email_text)
            self.log.success("Emergency contact email updated.")
        else:
            self.log.error("Please enter at least one valid email address.")

    def send_test_email(self):
        current_email = self.ui.phone_edit.text().strip()
        if current_email:
            self._replace_contacts_from_text(current_email)

        if not self.contacts:
            self.log.error("Please add an emergency contact email first.")
            return

        self.log.info("Sending test email...")
        has_enabled_contact = False
        all_success = True
        for contact in self.contacts:
            if contact.get("enabled") and contact.get("email"):
                has_enabled_contact = True
                test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(test_frame, "EMS Test Email", (120, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
                cv2.putText(
                    test_frame,
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    (140, 300),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (200, 200, 200),
                    2,
                )
                success = self.email_notifier.send_fall_alert(contact["email"], test_frame, location="EMS device [test]")
                if success:
                    self.log.success(f"Test email sent to {contact['name']} ({contact['email']}).")
                else:
                    self.log.error(f"Failed to send test email to {contact['name']} ({contact['email']}).")
                    all_success = False

        if not has_enabled_contact:
            self.log.error("No valid emergency email address is configured.")
        elif all_success:
            self.log.success("All test emails were sent successfully.")

    def refresh_cameras(self):
        self.ui.cam_selector.blockSignals(True)
        self.ui.cam_selector.clear()
        valid = []
        backend = cv2.CAP_DSHOW if self.os_type == "Windows" else cv2.CAP_V4L2
        for index in range(3):
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                valid.append(index)
            cap.release()

        self.available_cams = valid
        self.ui.cam_selector.addItems([f"Device {index}" for index in valid])
        if valid:
            self.ui.cam_selector.setCurrentIndex(0)
            self.worker.request_camera_switch(valid[0])
            self.log.info(f"Detected {len(valid)} camera(s).")
        else:
            self.log.warn("No camera detected. You can still import a local test video.")
        self.ui.cam_selector.blockSignals(False)

    def change_camera(self, index):
        if 0 <= index < len(self.available_cams):
            self.worker.request_camera_switch(self.available_cams[index])

    def import_test_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select local test video",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.flv *.wmv)",
        )
        if file_path:
            self.worker.request_video_file(file_path)
            self.log.info(f"Switched to local video: {os.path.basename(file_path)}")

    def save_snapshot(self, prefix):
        folder = resource_path("records")
        os.makedirs(folder, exist_ok=True)
        file_path = os.path.join(folder, f"{prefix}_{time.strftime('%H%M%S')}.jpg")
        if self.ui.video_label.pixmap():
            self.ui.video_label.pixmap().save(file_path)
            self.log.info(f"Snapshot saved: {os.path.basename(file_path)}")

    def open_folder(self):
        folder = resource_path("records")
        os.makedirs(folder, exist_ok=True)
        if self.os_type == "Windows":
            os.startfile(folder)
        elif self.os_type == "Darwin":
            subprocess.run(["open", folder], check=False)
        else:
            subprocess.run(["xdg-open", folder], check=False)

    def closeEvent(self, event):
        self.worker.stop()
        self.hw.close()
        event.accept()


if __name__ == "__main__":
    ensure_runtime_dirs("records", "temp", "models")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    if SetupDialog.needs_setup():
        dialog = SetupDialog()
        if dialog.exec() == QDialog.Rejected:
            sys.exit(0)

    window = Controller()
    window.show()
    sys.exit(app.exec())
