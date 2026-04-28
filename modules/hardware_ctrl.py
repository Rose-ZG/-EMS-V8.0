import serial
import serial.tools.list_ports
import os
import threading
import platform

class HardwareManager:
    def __init__(self, port=None, baudrate=9600, mp3_path="RING.wav",):
        self.available = False
        self.ser = None
        self.mp3_path = mp3_path
        self.os_type = platform.system()

        self.pygame_imported = False
        try:
            import pygame
            pygame.mixer.init()
            self.pygame = pygame
            self.pygame_imported = True
            print("[HW] pygame音频初始化成功")
        except Exception as e:
            print(f"[HW] pygame音频初始化失败: {e}")

        port = port or self._auto_detect_serial()
        if port:
            try:
                self.ser = serial.Serial(port, baudrate, timeout=0.1, write_timeout=0.1)
                self.available = True
                print(f"[HW] 串口连接成功 ({port})")
            except Exception as e:
                print(f"[HW] 串口连接失败: {e}")
        else:
            print("[HW] 未找到可用串口设备")

    def _auto_detect_serial(self):
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if "Bluetooth" not in p.description:
                return p.device
        if self.os_type == "Linux":
            for dev in ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyS0"]:
                if os.path.exists(dev):
                    return dev
        return None

    def send_alarm(self, active=True):
        if self.ser and self.available:
            try:
                self.ser.write(b'1' if active else b'0')
                return True
            except Exception as e:
                print(f"[HW] 串口发送失败: {e}")
        return False

    def _play_audio_async(self, file_path, repeat=1):
        if not self.pygame_imported:
            return
        def play():
            try:
                self.pygame.mixer.music.stop()
                self.pygame.mixer.music.load(file_path)
                for _ in range(repeat):
                    self.pygame.mixer.music.play()
                    while self.pygame.mixer.music.get_busy():
                        self.pygame.time.delay(100)
            except Exception as e:
                print(f"[HW] 音频播放失败: {e}")
        threading.Thread(target=play, daemon=True).start()

    def play_audio(self, file_path, repeat=1):
        if os.path.exists(file_path):
            self._play_audio_async(file_path, repeat)
        else:
            print(f"[HW] Audio file not found: {file_path}")

    def alert_with_voice(self, active=True):
        serial_ok = self.send_alarm(active)
        if active:
            if os.path.exists(self.mp3_path):
                self._play_audio_async(self.mp3_path, repeat=2)
        else:
            if self.pygame_imported:
                self.pygame.mixer.music.stop()
        print(f"[HW] 报警触发: 串口={serial_ok}")

    def call_emergency(self, to_number):
        print(f"[HW] 已触发本地求救指令，等待主模块发送邮件至目标地址")
        return True


    def close(self):
        if self.pygame_imported:
            self.pygame.mixer.quit()
        if self.ser:
            self.ser.close()