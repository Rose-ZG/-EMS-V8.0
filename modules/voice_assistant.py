import os

from modules._resource import resource_path
from modules.logger import Logger

try:
    import torch
except ImportError:
    torch = None

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    from scipy.io.wavfile import write
except ImportError:
    write = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None


def _vlog(fn):
    logger = Logger.instance()
    if logger:
        fn(logger)


class VoiceAssistant:
    def __init__(self, model_path=None):
        model_path = model_path or resource_path("models/whisper-small")
        self.model = None
        self.has_cuda = bool(torch and torch.cuda.is_available())

        if WhisperModel is None:
            _vlog(lambda log: log.warn("faster-whisper is not installed. Speech recognition is disabled."))
            return

        device = "cuda" if self.has_cuda else "cpu"
        compute_type = "float16" if self.has_cuda else "int8"

        try:
            self.model = WhisperModel(model_path, device=device, compute_type=compute_type)
            _vlog(lambda log: log.info(f"Whisper model loaded on {device}."))
        except Exception as exc:
            _vlog(lambda log: log.warn(f"Whisper model unavailable: {exc}"))

    def speak(self, text):
        _vlog(lambda log: log.voice(f"TTS: {text}"))
        try:
            import pyttsx3
            try:
                import pythoncom
            except ImportError:
                pythoncom = None

            if pythoncom is not None:
                pythoncom.CoInitialize()

            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            _vlog(lambda log: log.warn(f"TTS unavailable: {exc}"))

    def record_and_transcribe(self, duration=5, filename="temp/temp_ask.wav"):
        if self.model is None:
            _vlog(lambda log: log.warn("Speech recognition model is unavailable."))
            return ""
        if sd is None or write is None:
            _vlog(lambda log: log.warn("sounddevice/scipy is missing. Audio capture is disabled."))
            return ""

        sample_rate = 16000
        frames = int(duration * sample_rate)
        target_path = resource_path(filename)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        try:
            _vlog(lambda log: log.voice(f"Recording {duration} seconds of audio..."))
            recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
            sd.wait()
            sd.stop()
            write(target_path, sample_rate, recording)

            _vlog(lambda log: log.voice("Transcribing audio..."))
            segments, _ = self.model.transcribe(target_path, language="zh", beam_size=5, vad_filter=False)
            text = "".join(segment.text for segment in segments).strip()
            _vlog(lambda log: log.voice(f"ASR: {text or '[empty]'}"))
            return text
        except Exception as exc:
            _vlog(lambda log: log.error(f"Audio capture/transcription failed: {exc}"))
            return ""

    def ask_and_listen(self, prompt, duration=5):
        self.speak(prompt)
        return self.record_and_transcribe(duration=duration)

    def test_microphone(self, duration=3):
        print("Microphone test mode started. Say 'stop' to quit.")
        self.speak("Microphone test mode started.")
        while True:
            result = self.record_and_transcribe(duration=duration)
            print(f"Result: {result or '[empty]'}")
            if any(word in result.lower() for word in ("stop", "quit", "结束", "停止")):
                self.speak("Microphone test finished.")
                break
