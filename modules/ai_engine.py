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
        self.is_interacting = False
        self.is_alarming = False
        self.threshold = 1.4
        self.angle_threshold = 35
        self.conf_val = 0.5
        self.inference_size = 192

        self.fall_history = deque(maxlen=15)
        self.prev_states = {}               # track_id -> (cx, cy) 帧间速度计算
        self.camera_id = 0
        self.cap = None
        self._camera_request = None

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

        # 阈值配置
        kp_conf_thresh = getattr(self, 'kp_conf_threshold', 0.5)
        kp_ratio_thresh = getattr(self, 'kp_ratio_threshold', 1.0)
        angle_thresh = getattr(self, 'angle_threshold', 45)

        # COCO 关键点索引
        LSHO, RSHO = 5, 6
        LHIP, RHIP = 11, 12
        LKNE, RKNE = 13, 14
        LANK, RANK = 15, 16

        for r in results:
            if r.boxes is None or r.keypoints is None:
                continue
            frame_h = r.orig_shape[0]

            for i, box in enumerate(r.boxes):
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                w, h = x2 - x1, y2 - y1
                if h < 10 or w < 10:
                    continue
                box_ratio = w / h

                track_id = int(box.id[0]) if box.id is not None else None
                kps = r.keypoints.data[i].cpu().numpy()
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

                # ── 关键点不足 → 回退到检测框宽高比 ──
                if len(kps) < 17:
                    if box_ratio > 1.8:
                        score = max(score, 0.50)
                    continue

                # ── 仅头部可见时跳过（无法判断姿态）──
                body_kp_visible = int((kps[5:17, 2] > kp_conf_thresh).sum())
                if body_kp_visible < 3:
                    continue

                # ── 提取关键点置信度 ──
                lsho_c = kps[LSHO][2] > kp_conf_thresh
                rsho_c = kps[RSHO][2] > kp_conf_thresh
                sho_ok = lsho_c and rsho_c
                shoulder_mid = (
                    np.array([(kps[LSHO][0] + kps[RSHO][0]) / 2,
                              (kps[LSHO][1] + kps[RSHO][1]) / 2])
                    if sho_ok else None
                )

                lhip_c = kps[LHIP][2] > kp_conf_thresh
                rhip_c = kps[RHIP][2] > kp_conf_thresh
                hip_ok = lhip_c and rhip_c
                hip_mid = (
                    np.array([(kps[LHIP][0] + kps[RHIP][0]) / 2,
                              (kps[LHIP][1] + kps[RHIP][1]) / 2])
                    if hip_ok else None
                )

                lkne_c = kps[LKNE][2] > kp_conf_thresh
                rkne_c = kps[RKNE][2] > kp_conf_thresh
                lank_c = kps[LANK][2] > kp_conf_thresh
                rank_c = kps[RANK][2] > kp_conf_thresh

                # ── 阶段1: 初步判断 ──
                # 规则3: 肩在脚下方 (shoulder_y > ankle_y)
                rule3 = False
                if lsho_c and lank_c and kps[LSHO][1] > kps[LANK][1]:
                    rule3 = True
                elif rsho_c and rank_c and kps[RSHO][1] > kps[RANK][1]:
                    rule3 = True
                if not rule3 and sho_ok and lank_c and rank_c:
                    ankle_mid_y = (kps[LANK][1] + kps[RANK][1]) / 2
                    if shoulder_mid[1] > ankle_mid_y:
                        rule3 = True

                # 规则4: 膝盖在肩上方 (knee_y < shoulder_y)
                rule4 = False
                if lsho_c and lkne_c and kps[LKNE][1] < kps[LSHO][1]:
                    rule4 = True
                elif rsho_c and rkne_c and kps[RKNE][1] < kps[RSHO][1]:
                    rule4 = True

                suspected = rule3 or rule4

                if not suspected:
                    if box_ratio > 1.8:
                        score = max(score, 0.45)
                    continue

                # ── 阶段2: 关键点外接矩形宽高比验证 ──
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

                # ── 阶段3: 角度规则确认 ──
                person_score = 0.50  # 通过阶段1+2的基础分

                # 6.1 大腿与水平面夹角
                def _thigh_horizontal(hip_i, knee_i):
                    if not (kps[hip_i][2] > kp_conf_thresh and kps[knee_i][2] > kp_conf_thresh):
                        return False
                    vec = kps[knee_i][:2] - kps[hip_i][:2]
                    norm_v = np.linalg.norm(vec)
                    if norm_v == 0:
                        return False
                    cos_a = abs(vec[0]) / norm_v
                    return np.degrees(np.arccos(np.clip(cos_a, -1, 1))) < angle_thresh

                # 6.2 躯干-大腿夹角（髋部折叠）
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

                # 6.3 大腿-小腿夹角（膝部折叠）
                def _thigh_shin(hip_i, knee_i, ankle_i):
                    if not (kps[hip_i][2] > kp_conf_thresh
                            and kps[knee_i][2] > kp_conf_thresh
                            and kps[ankle_i][2] > kp_conf_thresh):
                        return False
                    thigh = kps[knee_i][:2] - kps[hip_i][:2]
                    shin = kps[ankle_i][:2] - kps[knee_i][:2]
                    nt, ns = np.linalg.norm(thigh), np.linalg.norm(shin)
                    if nt == 0 or ns == 0:
                        return False
                    cos_a = np.dot(thigh, shin) / (nt * ns)
                    return np.degrees(np.arccos(np.clip(cos_a, -1, 1))) < angle_thresh

                angle_count = 0
                if _thigh_horizontal(LHIP, LKNE) or _thigh_horizontal(RHIP, RKNE):
                    angle_count += 1
                if _torso_thigh(LHIP, LKNE) or _torso_thigh(RHIP, RKNE):
                    angle_count += 1
                if _thigh_shin(LHIP, LKNE, LANK) or _thigh_shin(RHIP, RKNE, RANK):
                    angle_count += 1

                person_score += angle_count * 0.15

                # ── 阶段4: 帧间速度加成 ──
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

    def handle_emergency(self,current_frame):
        """在独立线程中运行，通过信号与主界面交互"""
        self.is_interacting = True
        print("\n--- 🚨 进入语音核实流程 ---")
        self.assistant.speak("系统检测到您可能摔倒了，需要报警吗？")
        reply = self.assistant.record_and_transcribe(duration=3).strip()
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
            fall_score = self._fall_detection_logic(results)
            self.fall_history.append(fall_score)

            # 创建带检测框的标注图像（在紧急处理前）
            annotated_frame = results[0].plot() if results else frame

            # 平滑触发 (最近10帧平均>0.5，且非交互状态)
            if not self.is_interacting and len(self.fall_history) >= 10:
                if sum(self.fall_history) / len(self.fall_history) > 0.5:
                    threading.Thread(target=self.handle_emergency, args=(annotated_frame,), daemon=True).start()

            # 发送图像给 GUI
            curr_time = self._emit_frame(annotated_frame, prev_time, fall_score)
            prev_time = curr_time
            self.msleep(1)

        if self.cap:
            self.cap.release()

    def _emit_frame(self, frame, prev_time, fall_score):
        rgb_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape
        qt_img = QImage(rgb_img.data, w, h, ch * w, QImage.Format_RGB888)
        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        is_fall = fall_score > 0.5 if isinstance(fall_score, float) else fall_score
        self.change_pixmap_signal.emit(qt_img, is_fall, fps)
        return curr_time

    def stop(self):
        self.running = False
        self.wait()