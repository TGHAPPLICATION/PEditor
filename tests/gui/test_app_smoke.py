"""G0：空白 Qt app 可啟動（offscreen）。"""

import subprocess
import sys

from peditor.ui.app import SMOKE_MARKER, MainWindow


def test_main_window_shows(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.isVisible()
    assert window.windowTitle().startswith("PEditor")


def test_cli_smoke_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "peditor", "--smoke"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert SMOKE_MARKER in result.stdout
