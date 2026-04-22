import serial

class HardwareManager:
    def __init__(self, port='COM3', baudrate=9600):
        self.available = False
        self.ser = None
        try:
            print(f"[HW] 尝试连接硬件 {port}...")
            self.ser = serial.Serial(port, baudrate, timeout=0.1, write_timeout=0.1)
            self.available = True
            print("[HW] 硬件连接成功")
        except Exception as e:
            print(f"[HW] 硬件未连接或端口占用: {e}")

    def send_alarm(self, active=True):
        if self.ser and self.available:
            try:
                msg = b'1' if active else b'0'
                self.ser.write(msg)
                return True
            except Exception as e:
                print(f"[HW] 信号发送失败: {e}")
                self.available = False
                return False
        return False

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.available = False