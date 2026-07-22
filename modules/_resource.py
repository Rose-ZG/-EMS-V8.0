import os
import sys


def project_root() -> str:
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path: str) -> str:
    return os.path.join(project_root(), relative_path)


def ensure_runtime_dirs(*names: str) -> None:
    for name in names:
        os.makedirs(resource_path(name), exist_ok=True)
