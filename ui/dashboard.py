from PySide6.QtWidgets import *
from PySide6.QtCore import Qt

class MainDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #1a1a2e; color: #e0e0e0; font-family: "Microsoft YaHei", "PingFang SC"; font-size: 14px; }
            QLabel { color: #d1d1e9; background: transparent; }
            QPushButton { background-color: #2d2d44; border: 1px solid #3d3d5c; padding: 10px 18px; border-radius: 8px; min-height: 32px; font-weight: bold; color: #f0f0ff; }
            QPushButton:hover { background-color: #3e3e5e; border-color: #5a5a8a; }
            QPushButton:pressed { background-color: #4a4a6a; }
            QPushButton#action_btn { background-color: #7aa2f7; border: none; color: #1a1a2e; }
            QPushButton#action_btn:hover { background-color: #96b9fc; }
            QComboBox { background: #2d2d44; border: 1px solid #3d3d5c; padding: 6px 10px; border-radius: 6px; min-height: 30px; color: #f0f0ff; }
            QComboBox::drop-down { border: none; }
            QSlider::groove:horizontal { height: 6px; background: #2d2d44; border-radius: 3px; }
            QSlider::handle:horizontal { background: #7aa2f7; border-radius: 8px; width: 18px; margin: -6px 0; }
            QGroupBox { border: 1px solid #3d3d5c; border-radius: 12px; margin-top: 20px; padding-top: 20px; font-weight: bold; color: #c0caf5; background-color: #21213a; }
            QGroupBox::title { subcontrol-origin: margin; left: 18px; padding: 0 10px; color: #9ece6a; font-size: 15px; }
            QTextEdit { background: #16162a; border: 1px solid #3d3d5c; border-radius: 8px; padding: 10px; font-family: "Consolas", monospace; font-size: 12px; color: #c0caf5; }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(28)
        main_layout.setContentsMargins(28, 28, 28, 28)

        # ---------- 左侧视频区 ----------
        left_container = QVBoxLayout()
        left_container.setSpacing(14)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("📹"))
        top_bar.addWidget(QLabel("监控源选择:"))
        self.cam_selector = QComboBox()
        top_bar.addWidget(self.cam_selector, 1)
        self.ref_btn = QPushButton("🔄 刷新设备")
        top_bar.addWidget(self.ref_btn)
        left_container.addLayout(top_bar)

        self.video_label = QLabel("等待摄像头连接...")
        self.video_label.setFixedSize(640, 480)
        self.video_label.setStyleSheet(
            "background-color: #0b0b1a; border: 3px solid #7aa2f7; border-radius: 18px; color: #8b8baa; font-size: 18px; font-weight: bold;")
        self.video_label.setAlignment(Qt.AlignCenter)
        left_container.addWidget(self.video_label, 0, Qt.AlignCenter)

        info_bar = QHBoxLayout()
        self.fps_label = QLabel("FPS: 0.0")
        self.fps_label.setStyleSheet("color: #a3b8cc; font-weight: bold; font-size: 15px;")
        self.snap_btn = QPushButton("📷 抓拍记录")
        self.open_btn = QPushButton("📁 记录回溯")
        info_bar.addWidget(self.fps_label)
        info_bar.addStretch()
        info_bar.addWidget(self.snap_btn)
        info_bar.addWidget(self.open_btn)
        left_container.addLayout(info_bar)

        main_layout.addLayout(left_container, 5)

        # ---------- 右侧控制区 ----------
        right_container = QVBoxLayout()
        right_container.setSpacing(20)

        self.status_label = QLabel("🟢 系统实时监控中")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "font-size: 22pt; font-weight: bold; color: #1a1a2e; background-color: #9ece6a; border-radius: 14px; padding: 16px; margin-bottom: 6px;")
        right_container.addWidget(self.status_label)

        self.cfg_group = QGroupBox("⚙️ AI 参数动态调优")
        cfg_lay = QVBoxLayout(self.cfg_group)

        sens_layout = QHBoxLayout()
        sens_layout.addWidget(QLabel("跌倒判定灵敏度:"))
        self.t_value_label = QLabel("60")
        self.t_value_label.setStyleSheet("color: #7aa2f7; font-weight: bold;")
        sens_layout.addWidget(self.t_value_label)
        cfg_lay.addLayout(sens_layout)

        self.t_slider = QSlider(Qt.Horizontal)
        self.t_slider.setRange(30, 90)
        self.t_slider.setValue(60)
        self.t_slider.valueChanged.connect(lambda v: self.t_value_label.setText(str(v)))
        cfg_lay.addWidget(self.t_slider)

        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("AI 检测置信度阈值:"))
        self.c_value_label = QLabel("50")
        self.c_value_label.setStyleSheet("color: #7aa2f7; font-weight: bold;")
        conf_layout.addWidget(self.c_value_label)
        cfg_lay.addLayout(conf_layout)

        self.c_slider = QSlider(Qt.Horizontal)
        self.c_slider.setRange(10, 90)
        self.c_slider.setValue(50)
        self.c_slider.valueChanged.connect(lambda v: self.c_value_label.setText(str(v)))
        cfg_lay.addWidget(self.c_slider)
        right_container.addWidget(self.cfg_group)

        self.call_btn = QPushButton("🔄 重复呼叫")
        self.call_btn.setObjectName("call_btn")
        self.call_btn.setStyleSheet(
            "QPushButton#call_btn { height: 55px; background-color: #fab387; color: #1a1a2e; font-weight: bold; font-size: 16pt; border-radius: 12px; border: none; } QPushButton#call_btn:hover { background-color: #f9e2af; }")
        right_container.addWidget(self.call_btn)

        log_label = QLabel("📋 系统运行日志:")
        right_container.addWidget(log_label)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(120)
        right_container.addWidget(self.log_box)

        contact_group = QGroupBox("📞 紧急联系人")
        contact_layout = QVBoxLayout(contact_group)
        phone_layout = QHBoxLayout()
        phone_layout.addWidget(QLabel("E-Mail地址:"))
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("输入紧急联系人邮箱地址，如:xxxxxxxxxx@xx.com")
        phone_layout.addWidget(self.phone_edit)
        self.save_phone_btn = QPushButton("保存")
        phone_layout.addWidget(self.save_phone_btn)
        contact_layout.addLayout(phone_layout)
        right_container.addWidget(contact_group)

        self.reset_btn = QPushButton("🚨 警报解除 / 硬件初始化")
        self.reset_btn.setObjectName("reset_btn")
        self.reset_btn.setStyleSheet(
            "QPushButton#reset_btn { height: 60px; background-color: #f7768e; color: #1a1a2e; font-weight: bold; font-size: 16pt; border-radius: 12px; border: none; } QPushButton#reset_btn:hover { background-color: #ff9aa2; }")
        right_container.addWidget(self.reset_btn)

        main_layout.addLayout(right_container, 3)

    def append_log(self, message):
        self.log_box.append(message)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())