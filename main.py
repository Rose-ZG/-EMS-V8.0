import sys, os, time, cv2, subprocess

from PyQt5.QtCore import Qt
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

try:
    from modules.ai_engine import VideoWorker
    from modules.hardware_ctrl import HardwareManager
    from ui.dashboard import MainDashboard
except ImportError as e:
    print(f"导入模块失败，请检查文件夹名是否正确: {e}")


class Controller(QMainWindow):
    def __init__(self):
        super().__init__()
        print("[MAIN] 正在初始化窗口...")
        self.setWindowTitle("居家康复监测系统 v3.3")
        self.resize(1200, 850)

        self.available_cams = []
        self.fall_counter = 0

        # 1. 加载UI
        self.ui = MainDashboard()
        self.setCentralWidget(self.ui)
        print("[MAIN] UI 加载完成")

        # 2. 加载硬件
        self.hw = HardwareManager()

        # 3. 加载AI线程
        self.worker = VideoWorker()
        self.worker.change_pixmap_signal.connect(self.update_ui, Qt.QueuedConnection)

        # 4. 绑定事件
        self.ui.ref_btn.clicked.connect(self.refresh_cameras)
        self.ui.cam_selector.currentIndexChanged.connect(self.change_camera)
        self.ui.t_slider.valueChanged.connect(self.sync_params)
        self.ui.c_slider.valueChanged.connect(self.sync_params)
        self.ui.reset_btn.clicked.connect(self.reset_system)
        self.ui.snap_btn.clicked.connect(lambda: self.save_snapshot("MANUAL"))
        self.ui.open_btn.clicked.connect(self.open_folder)

        self.refresh_cameras()
        self.worker.start()
        print("[MAIN] 系统准备就绪")

    def sync_params(self):
        self.worker.threshold = self.ui.t_slider.value() / 100.0
        self.worker.conf_val = self.ui.c_slider.value() / 100.0

    def update_ui(self, img, is_fall, fps):
        self.ui.video_label.setPixmap(QPixmap.fromImage(img))
        self.ui.fps_label.setText(f"FPS: {fps:.1f}")

        if is_fall and not self.worker.is_alarming:
            self.fall_counter += 1
            if self.fall_counter > 12: self.trigger_alarm()
        else:
            self.fall_counter = 0
        self.worker.ui_ready = True

    def trigger_alarm(self):
        if self.worker.is_alarming: return
        self.worker.is_alarming = True
        self.ui.status_label.setText("!!! 紧急报警 !!!")
        self.ui.status_label.setStyleSheet("font-size: 20pt; color: white; background: #d9534f; font-weight: bold;")
        self.hw.send_alarm(True)
        self.add_log("CRITICAL: 检测到跌倒！")

    def reset_system(self):
        self.worker.is_alarming = False
        self.ui.status_label.setText("系统监控中")
        self.ui.status_label.setStyleSheet("font-size: 20pt; color: #2ecc71; font-weight: bold; background: #eee;")
        self.hw.send_alarm(False)
        self.add_log("INFO: 系统已复位")

    def refresh_cameras(self):
        self.ui.cam_selector.blockSignals(True)
        self.ui.cam_selector.clear()
        valid = []
        for i in range(3):
            c = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if c.isOpened():
                valid.append(i)
                c.release()
        self.available_cams = valid
        self.ui.cam_selector.addItems([f"设备 {i}" for i in valid])
        self.ui.cam_selector.blockSignals(False)

    def change_camera(self, index):
        if index >= 0 and self.available_cams:
            self.worker.update_camera(self.available_cams[index])

    def save_snapshot(self, prefix):
        path = os.path.join(os.getcwd(), "records")
        os.makedirs(path, exist_ok=True)
        file_path = os.path.join(path, f"{prefix}_{time.strftime('%H%M%S')}.jpg")
        if self.ui.video_label.pixmap():
            self.ui.video_label.pixmap().save(file_path)
            self.add_log(f"已保存: {os.path.basename(file_path)}")

    def open_folder(self):
        path = os.path.join(os.getcwd(), "records")
        if not os.path.exists(path): os.makedirs(path)
        if sys.platform == 'win32':
            os.startfile(path)
        else:
            subprocess.run(['xdg-open', path])

    def add_log(self, msg):
        self.ui.log_box.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def closeEvent(self, event):
        self.worker.running = False
        self.worker.wait()
        self.hw.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    try:
        window = Controller()
        window.show()
        print("[MAIN] 主循环启动")
        sys.exit(app.exec())
    except Exception as e:
        print(f"[CRASH] 程序发生致命错误: {e}")
        input("按回车键退出...")
