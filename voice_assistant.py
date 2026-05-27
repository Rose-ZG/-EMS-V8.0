import os
import torch
import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
from modules.logger import Logger
from modules._resource import resource_path


def _vlog(fn):
    """Logger 未初始化时静默，已初始化则调用"""
    log = Logger.instance()
    if log:
        fn(log)


class VoiceAssistant:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = resource_path("models/whisper-small")
        _vlog(lambda log: log.info("正在初始化本地语音引擎..."))

        # Whisper - 初始化语音识别模型
        self.has_cuda = torch.cuda.is_available()
        device = "cuda" if self.has_cuda else "cpu"
        compute_type = "float16" if self.has_cuda else "int8"
        try:
            self.model = WhisperModel(model_path, device=device, compute_type=compute_type)
            _vlog(lambda log: log.info(f"Whisper 语音识别加载成功 (Device: {device})"))
        except Exception as e:
            _vlog(lambda log: log.error(f"Whisper 加载失败: {e}"))
            self.model = None

    def speak(self, text):
        """文字转语音 - 完美解决 Windows 多线程 COM 组件崩溃问题"""
        _vlog(lambda log: log.voice(f"🔊 语音合成: {text}"))
        try:
            import pyttsx3
            import pythoncom  # 导入Windows底层COM库

            #调用系统语音组件！
            pythoncom.CoInitialize()

            engine = pyttsx3.init()
            # 设置语速
            engine.setProperty('rate', 160)
            engine.say(text)
            engine.runAndWait()

        except Exception as e:
            _vlog(lambda log: log.error(f"语音播报失败: {e}"))

    def record_and_transcribe(self, duration=5, filename="temp/temp_ask.wav"):
        """录音并转写"""
        if not self.model:
            _vlog(lambda log: log.error("Whisper 模型未加载，无法进行语音识别"))
            return ""
        fs = 16000
        frames = int(duration * fs)
        _vlog(lambda log: log.voice(f"🎙️ 开始录音 ({duration} 秒)..."))
        try:
            recording = sd.rec(frames, samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            sd.stop()
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            write(filename, fs, recording)

            _vlog(lambda log: log.voice("🔄 语音识别中..."))
            segments, _ = self.model.transcribe(
                filename, language="zh", beam_size=5,
                vad_filter=False  # 短录音无需 VAD，且避免 numpy >= 1.24 的 float32 索引兼容性问题
            )
            text = "".join([s.text for s in segments])
            _vlog(lambda log: log.voice(f"📝 识别结果: {text}"))
            return text.strip()
        except Exception as e:
            _vlog(lambda log: log.error(f"录音/识别失败: {e}"))
            return ""

    def ask_and_listen(self, prompt, duration=5):
        """合成语音提问 -> 录音 -> 识别"""
        self.speak(prompt)
        return self.record_and_transcribe(duration=duration)

    def test_microphone(self, duration=3):
        """
        试音功能：循环测试麦克风与识别准确率。
        说出“停止”、“退出”或“结束”即可退出测试。
        """
        print("\n" + "=" * 40)
        print("🎙️ 麦克风试音模式已开启 🎙️")
        print("请对准麦克风说话。每次录音 {} 秒。".format(duration))
        print("想要退出测试，请说出：'停止'、'退出' 或 '结束'。")
        print("=" * 40 + "\n")

        # 播报提示音
        self.speak("试音模式已开启，请对准麦克风说话。")

        while True:
            # 调用已有的录音并转写函数
            result = self.record_and_transcribe(duration=duration)

            # 检查是否有结果
            if result:
                print(f"👉 【试音结果】: {result}")

                # 检查退出关键词
                if any(word in result for word in ["停止", "退出", "结束"]):
                    print("\n[试音结束] 退出试音模式。")
                    self.speak("试音结束，已退出。")
                    break
            else:
                print("👉 【试音结果】: (未听到声音或识别为空)")

if __name__ == "__main__":
        assistant = VoiceAssistant()
        # 启动试音，每次录音 3 秒
        assistant.test_microphone(duration=3)
