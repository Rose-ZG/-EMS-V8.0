import os
import platform

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None


class HardwareManager:
    def __init__(self, port=None, baudrate=9600):
        self.available = False
        self.ser = None
        self.os_type = platform.system()

        if serial is None:
            print("[HW] pyserial is not installed, serial alarm output is disabled.")
            return

        detected_port = port or self._auto_detect_serial()
        if not detected_port:
            print("[HW] No usable serial device detected.")
            return

        try:
            self.ser = serial.Serial(detected_port, baudrate, timeout=0.1, write_timeout=0.1)
            self.available = True
            print(f"[HW] Connected to serial device: {detected_port}")
        except Exception as exc:
            print(f"[HW] Failed to open serial device: {exc}")

    def _auto_detect_serial(self):
        if serial is None:
            return None

        for port in serial.tools.list_ports.comports():
            if "Bluetooth" not in port.description:
                return port.device

        if self.os_type == "Linux":
            for device in ("/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyS0"):
                if os.path.exists(device):
                    return device
        return None

    def send_alarm(self, active=True):
        if not (self.ser and self.available):
            return False
        try:
            self.ser.write(b"1" if active else b"0")
            return True
        except Exception as exc:
            print(f"[HW] Failed to write serial alarm state: {exc}")
            return False

    def alert_with_voice(self, active=True):
        serial_ok = self.send_alarm(active)
        print(f"[HW] Alarm state changed. serial_ok={serial_ok}, active={active}")

    def call_emergency(self, _to_number):
        print("[HW] Emergency call trigger requested.")
        return True

    def close(self):
        if self.ser:
            self.ser.close()
