import importlib.util
import os

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

from modules._resource import resource_path


class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EMS Setup Check")
        self.resize(560, 360)

        layout = QVBoxLayout(self)

        title = QLabel("Some runtime pieces are missing.")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        body = QLabel(
            "The app can still start in a limited mode, but AI, voice, or hardware features may stay disabled until these items are added."
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        details = QTextEdit()
        details.setReadOnly(True)
        details.setPlainText("\n".join(self.missing_items()))
        layout.addWidget(details)

        buttons = QHBoxLayout()
        buttons.addStretch()

        continue_button = QPushButton("Continue")
        continue_button.clicked.connect(self.accept)
        buttons.addWidget(continue_button)

        exit_button = QPushButton("Exit")
        exit_button.clicked.connect(self.reject)
        buttons.addWidget(exit_button)

        layout.addLayout(buttons)

    @classmethod
    def missing_items(cls):
        items = []

        if not os.path.exists(resource_path(".env")):
            items.append("Missing .env file for SMTP settings.")
        if not os.path.exists(resource_path("models/whisper-small")):
            items.append("Missing local Whisper model directory: models/whisper-small")
        if not os.path.exists(resource_path("models/piper")):
            items.append("Missing local Piper model directory: models/piper")

        for module_name in ("ultralytics", "torch", "faster_whisper", "sounddevice", "serial", "dotenv"):
            if importlib.util.find_spec(module_name) is None:
                items.append(f"Missing Python package: {module_name}")

        return items or ["No setup issues detected."]

    @classmethod
    def needs_setup(cls):
        return cls.missing_items() != ["No setup issues detected."]
