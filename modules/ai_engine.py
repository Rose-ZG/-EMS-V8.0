import cv2
import time
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from ultralytics import YOLO


class VideoWorker(QThread):
    change_pixmap_signal = Signal(QImage, bool, float)

    def __init__(self, model_path='yolov8n-pose.pt'):
        super().__init__()
        try:
            print(f"[AI] 正在加载模型: {model_path}...")
            self.model = YOLO(model_path)
            print("[AI] 模型加载成功")
        except Exception as e:
            print(f"[AI] 模型加载失败: {e}")
            self.model = None

        self.running = True
        self.is_alarming = False
        self.threshold = 0.6
        self.conf_val = 0.5
        self.ui_ready = True
        self.camera_index = 0
        self.cap = None

    def update_camera(self, index):
        self.camera_index = index
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

    def run(self):
        if not self.cap:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

        prev_time = 0
        while self.running:
            if self.ui_ready and self.cap and self.cap.isOpened() and self.model:
                ret, frame = self.cap.read()
                if ret:
                    curr_time = time.time()
                    fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
                    prev_time = curr_time

                    results = self.model(frame, imgsz=256, conf=self.conf_val, verbose=False)
                    is_fall = False
                    for r in results:
                        for box in r.boxes:
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            if (y2 - y1) / (x2 - x1) < self.threshold:
                                is_fall = True
                                break

                    annotated_frame = results[0].plot()
                    rgb_img = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_img.shape
                    qt_img = QImage(rgb_img.data, w, h, ch * w, QImage.Format_RGB888)

                    self.ui_ready = False
                    self.change_pixmap_signal.emit(qt_img, is_fall, fps)
            else:
                self.msleep(100)
        if self.cap: self.cap.release()