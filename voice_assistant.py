import os
import torch
import pyttsx3
import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel

class VoiceAssistant:
    def __init__(self, model_path="./models/whisper-small"):
        """
        初始化本地语音引擎：TTS (播报) + Whisper (识别)
        首次运行请将 Faster-Whisper 的 small 模型放入 ./models/whisper-small
        """
        print("[语音] 正在初始化本地语音引擎...")

        # 1. TTS - 初始化语音合成引擎
        self.engine = None
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 150)
            self.engine.setProperty('volume', 1.0)
            # 获取可用的语音列表
            voices = self.engine.getProperty('voices')
            if voices:
                self.engine.setProperty('voice', voices[0].id)
            print("[语音] TTS初始化成功")
        except Exception as e:
            print(f"[警告] TTS初始化失败: {e}")
            self.engine = None

        # 2. Whisper - 初始化语音识别模型
        self.has_cuda = torch.cuda.is_available()
        device = "cuda" if self.has_cuda else "cpu"
        compute_type = "float16" if self.has_cuda else "int8"
        try:
            self.model = WhisperModel(model_path, device=device, compute_type=compute_type)
            print(f"[语音] Whisper加载成功 (Device: {device})")
        except Exception as e:
            print(f"[错误] Whisper加载失败: {e}")
            self.model = None

    def speak(self, text):
        """文字转语音"""
        print(f"[助手播报] {text}")
        if not self.engine:
            print("[警告] TTS引擎未初始化，跳过语音播报")
            return
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"[错误] 语音播报失败: {e}")
            # 尝试重新初始化
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', 150)
                self.engine.setProperty('volume', 1.0)
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e2:
                print(f"[错误] 重新初始化TTS失败: {e2}")

    def record_and_transcribe(self, duration=5, filename="temp/temp_ask.wav"):
        """录音并转写"""
        if not self.model:
            print("[错误] Whisper模型未加载，无法进行语音识别")
            return ""
        fs = 16000
        print(f"[语音] 🔴 开始录音 ({duration} 秒)...")
        try:
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            write(filename, fs, recording)

            print("[语音] 识别中...")
            segments, _ = self.model.transcribe(filename, language="zh", beam_size=5)
            text = "".join([s.text for s in segments])
            print(f"[语音] 识别结果: {text}")
            return text.strip()
        except Exception as e:
            print(f"[错误] 录音/识别失败: {e}")
            return ""

    def ask_and_listen(self, prompt, duration=5):
        """合成语音提问 -> 录音 -> 识别"""
        self.speak(prompt)
        return self.record_and_transcribe(duration=duration)
