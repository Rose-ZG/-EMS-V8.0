#日志模块
import sys
from datetime import datetime
from PySide6.QtCore import QObject, Signal


class LogSignal(QObject):
    """跨线程安全发送 HTML 日志到 UI"""
    message = Signal(str)


class Logger:
    _instance = None

    def __init__(self):
        if Logger._instance is not None:
            raise RuntimeError("Logger 已初始化，使用 Logger.instance() 获取")
        Logger._instance = self
        self.signal = LogSignal()

    @staticmethod
    def instance():
        return Logger._instance

    COLORS = {
        "VOICE":   "#ff9e64",   # 亮橙 — 语音识别/合成，最醒目
        "ALERT":   "#f7768e",   # 红色 — 告警
        "SUCCESS": "#9ece6a",   # 绿色 — 成功
        "WARN":    "#e0af68",   # 金黄 — 警告
        "INFO":    "#a0d2eb",   # 浅蓝 — 普通信息
        "ERROR":   "#f7768e",   # 红色 — 错误
        "DEBUG":   "#6c7086",   # 灰色 — 调试
    }

    def _emit(self, level: str, msg: str):
        color = self.COLORS.get(level, "#c0caf5")
        ts = datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:#565f89">[{ts}]</span> ' \
               f'<span style="color:{color};font-weight:bold">[{level}]</span> ' \
               f'<span style="color:#c0caf5">{msg}</span>'
        self.signal.message.emit(html)

    def voice(self, msg: str):
        """语音识别/合成专用，最醒目"""
        self._emit("VOICE", msg)

    def alert(self, msg: str):
        self._emit("ALERT", msg)

    def success(self, msg: str):
        self._emit("SUCCESS", msg)

    def warn(self, msg: str):
        self._emit("WARN", msg)

    def info(self, msg: str):
        self._emit("INFO", msg)

    def error(self, msg: str):
        self._emit("ERROR", msg)

    def debug(self, msg: str):
        self._emit("DEBUG", msg)

    def capture_stdout(self):
        """兜底：拦截遗漏的 print，统一转为 INFO"""
        sys.stdout = _Bridge(self, "INFO")
        sys.stderr = _Bridge(self, "ERROR")


class _Bridge:
    _last_msg = None   # 类级别：跨实例去重
    _first_error = True

    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.buf = ""

    def write(self, text):
        self.buf += text
        if "\n" in self.buf:
            lines = self.buf.split("\n")
            self.buf = lines.pop()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line == _Bridge._last_msg:
                    continue
                _Bridge._last_msg = line
                # 首次遇到 TypeError 时打印调用栈辅助定位
                if _Bridge._first_error and "numpy.float32" in line:
                    _Bridge._first_error = False
                    import traceback
                    self.logger._emit(self.level, line)
                    for tb_line in traceback.format_stack(limit=20):
                        for sub in tb_line.strip().split("\n"):
                            sub = sub.strip()
                            if sub:
                                self.logger._emit("DEBUG", f"  [栈] {sub}")
                    return
                self.logger._emit(self.level, line)

    def flush(self):
        if self.buf.strip() and self.buf.strip() != _Bridge._last_msg:
            _Bridge._last_msg = self.buf.strip()
            self.logger._emit(self.level, self.buf.strip())
        self.buf = ""
