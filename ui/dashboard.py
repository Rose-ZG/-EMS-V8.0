from PySide6.QtWidgets import *
from PySide6.QtCore import Qt

class MainDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)

        # 左侧区
        self.left_part = QVBoxLayout()
        self.top_bar = QHBoxLayout()
        self.top_bar.addWidget(QLabel("📹 切换源:"))
        self.cam_selector = QComboBox()
        self.top_bar.addWidget(self.cam_selector, 1)
        self.ref_btn = QPushButton("刷新设备")
        self.left_part.addLayout(self.top_bar)

        self.video_label = QLabel("正在加载监控画面...")
        self.video_label.setFixedSize(640, 480)
        self.video_label.setStyleSheet("background: #000; border: 4px solid #444; border-radius: 8px;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.left_part.addWidget(self.video_label)

        self.info_bar = QHBoxLayout()
        self.fps_label = QLabel("FPS: 0.0")
        self.snap_btn = QPushButton("📷 实时抓拍")
        self.open_btn = QPushButton("📁 浏览存档")
        self.info_bar.addWidget(self.fps_label)
        self.info_bar.addStretch()
        self.info_bar.addWidget(self.snap_btn)
        self.info_bar.addWidget(self.open_btn)
        self.left_part.addLayout(self.info_bar)
        layout.addLayout(self.left_part)

        # 右侧区
        self.right_part = QVBoxLayout()
        self.status_label = QLabel("系统监控中")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 20pt; color: #2ecc71; font-weight: bold; background: #eee; min-height: 60px;")
        self.right_part.addWidget(self.status_label)

        self.cfg_group = QGroupBox("检测参数微调")
        self.cfg_lay = QVBoxLayout(self.cfg_group)
        self.cfg_lay.addWidget(QLabel("跌倒灵敏度 (滑块越小越灵敏):"))
        self.t_slider = QSlider(Qt.Horizontal)
        self.t_slider.setRange(30, 90)
        self.t_slider.setValue(60)
        self.cfg_lay.addWidget(self.t_slider)
        self.cfg_lay.addWidget(QLabel("AI 置信度 (建议 0.5):"))
        self.c_slider = QSlider(Qt.Horizontal)
        self.c_slider.setRange(10, 90)
        self.c_slider.setValue(50)
        self.cfg_lay.addWidget(self.c_slider)
        self.right_part.addWidget(self.cfg_group)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background: #252525; color: #00ff00; font-family: 'Consolas';")
        self.right_part.addWidget(self.log_box)

        self.reset_btn = QPushButton("解除警报 / 复位硬件")
        self.reset_btn.setStyleSheet("height: 60px; background: #d9534f; color: white; font-weight: bold; font-size: 14pt;")
        self.right_part.addWidget(self.reset_btn)
        layout.addLayout(self.right_part)