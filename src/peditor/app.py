"""空白 Qt 主視窗（P0）。編輯功能自 P4 起實作。"""

from __future__ import annotations

import json
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from peditor import __version__

SMOKE_MARKER = "PEDITOR_SMOKE_OK"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"PEditor {__version__}")
        self.resize(1024, 768)
        placeholder = QLabel("PEditor（P0 空白視窗）")
        placeholder.setObjectName("placeholder")
        self.setCentralWidget(placeholder)


def run(*, smoke: bool = False, versions: dict[str, str] | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("PEditor")
    window = MainWindow()
    window.show()
    if smoke:
        QTimer.singleShot(0, app.quit)
    code = app.exec()
    if smoke and code == 0:
        print(SMOKE_MARKER, json.dumps(versions or {}, ensure_ascii=False), flush=True)
    return code
