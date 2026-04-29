import cv2
import time
import os
import platform
import numpy as np
import threading
from collections import deque
from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtGui import QImage
from ultralytics import YOLO

# 导入语音助手
from voice_assistant import VoiceAssistant

class VideoWorker(QThread):
    # 信号：图像、是否跌倒、FPS
    change_pixmap_signal = Signal(QImage, bool, float)
    # 增加 numpy.ndarray 类型用于传递图像数据
    emergency_call_signal = Signal(np.ndarray)

    #测试数据集模型runs/pose/fall_detect4/weights/best.pt
    def __init__(self, model_path='yolov8n-pose.pt', debug=False):
        super().__init__()
        self.debug = debug

        # 1. 加载视觉模型（回退机制）
        if not os.path.exists(model_path):
            print(f"[AI] Model {model_path} not found, falling back to yolov8n-pose.pt")
            model_path = 'yolov8n-pose.pt'
        try:
            self.model = YOLO(model_path)
            print(f"[AI] 视觉模型已加载: {model_path}")
        except Exception as e:
            print(f"[错误] 模型加载失败: {e}")
            self.model = None

        # 2. 初始化语音助手
        self.assistant = VoiceAssistant()

        # 3. 运行参数
        self.running = True
        self.is_interacting = False          # 防止重复触发语音交互
        self.is_alarming = False             # 是否处于报警状态（供主界面判断）
        self.threshold = 1.4
        self.angle_threshold = 35
        self.conf_val = 0.5
        self.inference_size = 192

        self.fall_history = deque(maxlen=15) # 滑动窗口平滑
        self.camera_id = 0
        self.cap = None
        self._camera_request = None          # 摄像头切换请求

    def _open_camera(self, camera_id):
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2
        cap = cv2.VideoCapture(camera_id, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def request_camera_switch(self, camera_index):
        self._camera_request = camera_index

    def _perform_camera_switch(self, new_index):
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.camera_id = new_index
        self.cap = self._open_camera(new_index)
        self._camera_request = None

    def get_fall_ratio(self):
        """返回滑动窗口中跌倒帧的比例"""
        if len(self.fall_history) == 0:
            return 0.0
        return sum(self.fall_history) / len(self.fall_history)

    def _fall_detection_logic(self, results):
        """综合宽高比 + 关键点倾角判断"""
        is_fall = False
        if not results or len(results) == 0:
            return False
        for r in results:
            if r.boxes is None or r.keypoints is None:
                continue
            for i, box in enumerate(r.boxes):
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                w, h = x2 - x1, y2 - y1
                if h < 10 or w < 10:
                    continue
                ratio = w / h
                kps = r.keypoints.data[i].cpu().numpy()

                # 关键点清晰时的组合判断
                if len(kps) >= 13 and all(kps[j][2] > 0.4 for j in [5, 6, 11, 12]):
                    shoulder_mid = np.array([(kps[5][0] + kps[6][0]) / 2,
                                            (kps[5][1] + kps[6][1]) / 2])
                    hip_mid = np.array([(kps[11][0] + kps[12][0]) / 2,
                                       (kps[11][1] + kps[12][1]) / 2])
                    torso_vec = hip_mid - shoulder_mid
                    vert_vec = np.array([0, 1])
                    norm_torso = np.linalg.norm(torso_vec)
                    if norm_torso > 0:
                        cos_ang = np.clip(np.dot(torso_vec, vert_vec) / norm_torso, -1.0, 1.0)
                        angle = np.degrees(np.arccos(cos_ang))
                        if angle > self.angle_threshold and ratio > self.threshold:
                            is_fall = True
                            break
                else:
                    # 关键点缺失时使用更严格的宽高比
                    if ratio > 1.8:
                        is_fall = True
                        break
        return is_fall

    def handle_emergency(self,current_frame):
        """在独立线程中运行，通过信号与主界面交互"""
        self.is_interacting = True
        print("\n--- 🚨 进入语音核实流程 ---")
        self.assistant.speak("系统检测到您可能摔倒了，需要报警吗？")
        reply = self.assistant.record_and_transcribe(duration=5).strip()
        print(f"[语音识别结果]: 「{reply}」")

        danger_keywords = [
            '要', '救命', '报警', '疼', '是的', '好', '帮我', '摔了',
            '起不来', '动不了', '救我', '医生', '快来', '救人', '求救', '紧急'
        ]

        safe_keywords = [
            '没事', '不用', '不需要', '误报', '没摔', '好着呢',
            '走开', '取消', '测试', '我很好', '没有摔', '开玩笑', '自己能起'
        ]

        needs_help = False
        # 1. 首先检查是否完全没有说话（静默判定为危险）
        if len(reply) < 2:
            print("[语音] 无有效回应 -> 判定为昏迷/危险")
            needs_help = True

        # 2. 优先检查“安全关键词”（这样即便说了“不需要报警”，也会先被判定为安全）
        elif any(word in reply for word in safe_keywords):
            print("[语音] 用户确认安全 (命中安全关键词)")
            self.assistant.speak("好的，已为您取消警报。")
            needs_help = False

        # 3. 再检查“危险关键词”
        elif any(word in reply for word in danger_keywords):
            print("[语音] 用户确认需要帮助 (命中危险关键词)")
            needs_help = True

        # 4. 兜底逻辑：如果用户说了一堆话，但既没说没事，也没说救命
        else:
            print("[语音] 语义不明 -> 为了安全起见，默认报警")
            self.assistant.speak("抱歉，我没听清楚，为您启动紧急求助。")
            needs_help = True

        # --- 逻辑优化结束 ---

        if needs_help:
            self.assistant.speak("已收到，正在通知紧急联系人。")
            self.emergency_call_signal.emit(current_frame)

        self.fall_history.clear()
        self.is_interacting = False
        print("--- 预案处理完毕 ---\n")

    def run(self):
        if not self.cap:
            self.cap = self._open_camera(self.camera_id)
        prev_time = time.time()

        while self.running:
            # 处理摄像头切换请求
            if self._camera_request is not None:
                self._perform_camera_switch(self._camera_request)

            if not self.cap or not self.cap.isOpened():
                self.msleep(30)
                continue

            ret, frame = self.cap.read()
            if not ret:
                self.msleep(5)
                continue

            # 推理
            results = self.model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.2)
            is_fall_current = self._fall_detection_logic(results)
            self.fall_history.append(is_fall_current)

            # 创建带检测框的标注图像（在紧急处理前）
            annotated_frame = results[0].plot() if results else frame

            # 平滑触发 (最近10帧中≥7帧为跌倒，且非交互状态)
            if not self.is_interacting and len(self.fall_history) >= 10:
                if sum(self.fall_history) / len(self.fall_history) > 0.7:
                    # 这里的 annotated_frame 是当前带有 YOLO 检测框的标注图像 [cite: 118]
                    threading.Thread(target=self.handle_emergency, args=(annotated_frame,), daemon=True).start()

            # 发送图像给 GUI
            curr_time = self._emit_frame(annotated_frame, prev_time, is_fall_current)
            prev_time = curr_time
            self.msleep(1)

        if self.cap:
            self.cap.release()

    def _emit_frame(self, frame, prev_time, is_fall):
        rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape
        qt_img = QImage(rgb_img.data, w, h, ch * w, QImage.Format_RGB888)
        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        self.change_pixmap_signal.emit(qt_img, is_fall, fps)
        return curr_time

    def stop(self):
        self.running = False
        self.wait()