import os
import platform
import threading
import time
from collections import deque

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from modules._resource import resource_path
from modules.logger import Logger
from modules.voice_assistant import VoiceAssistant

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


class VideoWorker(QThread):
    change_pixmap_signal = Signal(QImage, bool, float)
    emergency_call_signal = Signal(np.ndarray)
    pre_alarm_signal = Signal()
    cancel_alarm_signal = Signal()

    def __init__(self, model_path=None, debug=False):
        super().__init__()
        self.debug = debug
        self.running = True
        self.is_interacting = False
        self.is_alarming = False
        self.threshold = 1.4
        self.angle_threshold = 35
        self.conf_val = 0.5
        self.inference_size = 192
        self.fall_history = deque(maxlen=15)
        self.prev_states = {}
        self.camera_id = 0
        self.cap = None
        self._camera_request = None
        self.is_video_file = False
        self.video_path = None
        self.source_fps = None
        self._missing_model_logged = False

        self.assistant = VoiceAssistant()
        self.model = self._load_model(model_path)

    @staticmethod
    def _log(fn):
        logger = Logger.instance()
        if logger:
            fn(logger)

    def _load_model(self, model_path=None):
        if YOLO is None:
            self._log(lambda log: log.warn("ultralytics is not installed. AI detection is disabled."))
            return None

        candidate = model_path or resource_path("yolov8n-pose.pt")
        load_target = candidate if os.path.exists(candidate) else "yolov8n-pose.pt"

        try:
            model = YOLO(load_target)
            self._log(lambda log: log.info(f"YOLO model loaded from {load_target}."))
            return model
        except Exception as exc:
            self._log(lambda log: log.warn(f"YOLO model unavailable: {exc}"))
            return None

    def _open_camera(self, camera_id):
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2
        cap = cv2.VideoCapture(camera_id, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _open_video_file(self, file_path):
        cap = cv2.VideoCapture(file_path)
        if cap.isOpened():
            native_fps = cap.get(cv2.CAP_PROP_FPS)
            self.source_fps = native_fps if 0 < native_fps <= 120 else 30.0
            self.is_video_file = True
            self.video_path = file_path
            self._log(lambda log: log.info(f"Loaded local test video: {os.path.basename(file_path)}"))
        return cap

    def request_camera_switch(self, camera_index):
        self._camera_request = camera_index

    def request_video_file(self, file_path):
        self._camera_request = file_path

    def _perform_camera_switch(self, request):
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.is_video_file = False
        self.source_fps = None
        self.video_path = None

        if isinstance(request, str):
            self.cap = self._open_video_file(request)
        else:
            self.camera_id = request
            self.cap = self._open_camera(request)
        self._camera_request = None

    def get_fall_ratio(self):
        if not self.fall_history:
            return 0.0
        return sum(self.fall_history) / len(self.fall_history)

    def _fall_detection_logic(self, results):
        """
        多级级联摔倒检测（返回 0~1 置信度）:
          1. 初步判断: 肩在脚下方 / 膝盖在肩上方
          2. 关键点外接矩形宽高比验证
          3. 角度规则确认 (大腿水平角 / 躯干-大腿夹角 / 大腿-小腿夹角)
          4. 帧间速度加成
        关键点缺失时回退至检测框宽高比。
        """
        score = 0.0
        if not results or len(results) == 0:
            return 0.0

        kp_conf_thresh = getattr(self, "kp_conf_threshold", 0.5)
        kp_ratio_thresh = getattr(self, "kp_ratio_threshold", 1.0)
        angle_thresh = getattr(self, "angle_threshold", 45)

        lsho, rsho = 5, 6
        lhip, rhip = 11, 12
        lkne, rkne = 13, 14
        lank, rank = 15, 16

        for result in results:
            if result.boxes is None or result.keypoints is None:
                continue
            frame_h = result.orig_shape[0]

            for index, box in enumerate(result.boxes):
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                width, height = x2 - x1, y2 - y1
                if height < 10 or width < 10:
                    continue
                box_ratio = width / height

                track_id = int(box.id[0]) if box.id is not None else None
                kps = result.keypoints.data[index].cpu().numpy()
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

                if len(kps) < 17:
                    if box_ratio > 1.8:
                        score = max(score, 0.50)
                    continue

                body_kp_visible = int((kps[5:17, 2] > kp_conf_thresh).sum())
                if body_kp_visible < 3:
                    continue

                lsho_c = kps[lsho][2] > kp_conf_thresh
                rsho_c = kps[rsho][2] > kp_conf_thresh
                sho_ok = lsho_c and rsho_c
                shoulder_mid = (
                    np.array(
                        [
                            (kps[lsho][0] + kps[rsho][0]) / 2,
                            (kps[lsho][1] + kps[rsho][1]) / 2,
                        ]
                    )
                    if sho_ok
                    else None
                )

                lhip_c = kps[lhip][2] > kp_conf_thresh
                rhip_c = kps[rhip][2] > kp_conf_thresh
                hip_ok = lhip_c and rhip_c
                hip_mid = (
                    np.array(
                        [
                            (kps[lhip][0] + kps[rhip][0]) / 2,
                            (kps[lhip][1] + kps[rhip][1]) / 2,
                        ]
                    )
                    if hip_ok
                    else None
                )

                lkne_c = kps[lkne][2] > kp_conf_thresh
                rkne_c = kps[rkne][2] > kp_conf_thresh
                lank_c = kps[lank][2] > kp_conf_thresh
                rank_c = kps[rank][2] > kp_conf_thresh

                rule3 = False
                if lsho_c and lank_c and kps[lsho][1] > kps[lank][1]:
                    rule3 = True
                elif rsho_c and rank_c and kps[rsho][1] > kps[rank][1]:
                    rule3 = True
                if not rule3 and sho_ok and lank_c and rank_c:
                    ankle_mid_y = (kps[lank][1] + kps[rank][1]) / 2
                    if shoulder_mid[1] > ankle_mid_y:
                        rule3 = True

                rule4 = False
                if lsho_c and lkne_c and kps[lkne][1] < kps[lsho][1]:
                    rule4 = True
                elif rsho_c and rkne_c and kps[rkne][1] < kps[rsho][1]:
                    rule4 = True

                suspected = rule3 or rule4

                if not suspected:
                    if box_ratio > 1.8:
                        score = max(score, 0.45)
                    continue

                valid_mask = kps[:, 2] > 0
                valid_pts = kps[valid_mask]
                if len(valid_pts) >= 2:
                    min_xy = np.min(valid_pts[:, :2], axis=0)
                    max_xy = np.max(valid_pts[:, :2], axis=0)
                    kp_w, kp_h = max_xy - min_xy
                    if kp_h == 0 or (kp_w / kp_h) <= kp_ratio_thresh:
                        score = max(score, 0.35)
                        continue
                else:
                    if box_ratio > kp_ratio_thresh:
                        score = max(score, 0.40)
                    continue

                person_score = 0.50

                def _thigh_horizontal(hip_i, knee_i):
                    if not (kps[hip_i][2] > kp_conf_thresh and kps[knee_i][2] > kp_conf_thresh):
                        return False
                    vec = kps[knee_i][:2] - kps[hip_i][:2]
                    norm_v = np.linalg.norm(vec)
                    if norm_v == 0:
                        return False
                    cos_a = abs(vec[0]) / norm_v
                    return np.degrees(np.arccos(np.clip(cos_a, -1, 1))) < angle_thresh

                def _torso_thigh(hip_i, knee_i):
                    if not (sho_ok and hip_ok and kps[knee_i][2] > kp_conf_thresh):
                        return False
                    torso = hip_mid - shoulder_mid
                    thigh = kps[knee_i][:2] - kps[hip_i][:2]
                    nt, nf = np.linalg.norm(torso), np.linalg.norm(thigh)
                    if nt == 0 or nf == 0:
                        return False
                    cos_a = np.dot(torso, thigh) / (nt * nf)
                    return np.degrees(np.arccos(np.clip(cos_a, -1, 1))) < angle_thresh

                def _thigh_shin(hip_i, knee_i, ankle_i):
                    if not (
                        kps[hip_i][2] > kp_conf_thresh
                        and kps[knee_i][2] > kp_conf_thresh
                        and kps[ankle_i][2] > kp_conf_thresh
                    ):
                        return False
                    thigh = kps[knee_i][:2] - kps[hip_i][:2]
                    shin = kps[ankle_i][:2] - kps[knee_i][:2]
                    nt, ns = np.linalg.norm(thigh), np.linalg.norm(shin)
                    if nt == 0 or ns == 0:
                        return False
                    cos_a = np.dot(thigh, shin) / (nt * ns)
                    return np.degrees(np.arccos(np.clip(cos_a, -1, 1))) < angle_thresh

                angle_count = 0
                if _thigh_horizontal(lhip, lkne) or _thigh_horizontal(rhip, rkne):
                    angle_count += 1
                if _torso_thigh(lhip, lkne) or _torso_thigh(rhip, rkne):
                    angle_count += 1
                if _thigh_shin(lhip, lkne, lank) or _thigh_shin(rhip, rkne, rank):
                    angle_count += 1

                person_score += angle_count * 0.15

                velocity_score = 0.0
                if track_id is not None and track_id in self.prev_states:
                    px, py = self.prev_states[track_id]
                    dy = cy - py
                    if dy > 0:
                        velocity_score = np.clip(dy / frame_h * 10, 0, 1) * 0.10
                if track_id is not None:
                    self.prev_states[track_id] = (cx, cy)

                person_score += velocity_score
                score = max(score, min(person_score, 1.0))

        if len(self.prev_states) > 30:
            self.prev_states.clear()

        return score

    def handle_emergency(self, current_frame):
        try:
            self._handle_emergency_impl(current_frame)
        except Exception as exc:
            self._log(lambda log: log.error(f"Voice confirmation flow failed: {exc}"))
            self.cancel_alarm_signal.emit()
            self.fall_history.clear()
            self.is_interacting = False

    def _handle_emergency_impl(self, current_frame):
        self._log(lambda log: log.voice("Starting voice confirmation."))
        self.assistant.speak("A possible fall was detected. Do you need help?")
        reply = self.assistant.record_and_transcribe(duration=3).strip().lower()
        self._log(lambda log: log.voice(f"Voice reply: {reply or '[empty]'}"))

        danger_keywords = {"help", "emergency", "pain", "yes", "call", "doctor", "救命", "帮我", "摔倒"}
        safe_keywords = {"no", "fine", "cancel", "ok", "不用", "没事", "误报"}

        if len(reply) < 2:
            needs_help = True
        elif any(word in reply for word in safe_keywords):
            self.assistant.speak("Alert cancelled.")
            needs_help = False
        elif any(word in reply for word in danger_keywords):
            needs_help = True
        else:
            self.assistant.speak("I could not confirm safety, sending an alert.")
            needs_help = True

        if needs_help:
            self.assistant.speak("Emergency contacts are being notified.")
            self.emergency_call_signal.emit(current_frame)
        else:
            self.cancel_alarm_signal.emit()

        self.fall_history.clear()
        self.is_interacting = False
        self._log(lambda log: log.info("Voice confirmation complete."))

    def _predict(self, frame):
        if self.model is None:
            if not self._missing_model_logged:
                self._log(lambda log: log.warn("Running in preview-only mode because the AI model is unavailable."))
                self._missing_model_logged = True
            return []
        try:
            return self.model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=self.conf_val,
                iou=0.5,
                classes=[0],
                verbose=False,
            )
        except Exception as exc:
            self._log(lambda log: log.error(f"Model inference failed: {exc}"))
            return []

    def run(self):
        if not self.cap:
            self.cap = self._open_camera(self.camera_id)
        previous_time = time.time()

        while self.running:
            if self._camera_request is not None:
                self._perform_camera_switch(self._camera_request)

            if not self.cap or not self.cap.isOpened():
                self.msleep(30)
                continue

            if self.is_video_file:
                frame_start = time.time()

            ret, frame = self.cap.read()
            if not ret:
                if self.is_video_file and self.cap:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.msleep(5)
                    continue
                self.msleep(5)
                continue

            results = self._predict(frame)
            fall_score = self._fall_detection_logic(results) if results else 0.0
            self.fall_history.append(fall_score)

            try:
                annotated_frame = results[0].plot() if results else frame
            except Exception:
                annotated_frame = frame

            if not self.is_interacting and len(self.fall_history) >= 10:
                if sum(self.fall_history) / len(self.fall_history) > 0.5:
                    self.is_interacting = True
                    self.pre_alarm_signal.emit()
                    threading.Thread(target=self.handle_emergency, args=(annotated_frame,), daemon=True).start()

            current_time = self._emit_frame(annotated_frame, previous_time, fall_score)
            previous_time = current_time

            if self.is_video_file and self.source_fps:
                elapsed = time.time() - frame_start
                sleep_time = (1.0 / self.source_fps) - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            self.msleep(1)

        if self.cap:
            self.cap.release()

    def _emit_frame(self, frame, prev_time, fall_score):
        rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_img.shape
        bytes_per_line = channels * width
        qt_img = QImage(rgb_img.data, width, height, bytes_per_line, QImage.Format_RGB888)
        current_time = time.time()
        fps = 1.0 / (current_time - prev_time) if current_time > prev_time else 0.0
        self.change_pixmap_signal.emit(qt_img, fall_score > 0.5, float(fps))
        return current_time

    def stop(self):
        self.running = False
        self.wait()
