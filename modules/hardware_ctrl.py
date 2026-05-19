import serial
import serial.tools.list_ports
import os
import platform

class HardwareManager:
    def __init__(self, port=None, baudrate=9600):
        self.available = False
        self.ser = None
        self.os_type = platform.system()

        # 自动检测并连接可用串口
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

    def alert_with_voice(self, active=True):
        # 声音已完全交由主程序的 TTS (Piper) 处理
        # 本模块仅保留物理串口硬件报警器的触发逻辑
        serial_ok = self.send_alarm(active)
        print(f"[HW] 物理报警触发: 串口={serial_ok}, 状态={active}")

    def call_emergency(self, to_number):
        print(f"[HW] 已触发本地求救指令，等待主模块发送邮件至目标地址")
        return True

    def close(self):
        # 仅需关闭串口，无需再处理 pygame 释放
        if self.ser:
            self.ser.close()