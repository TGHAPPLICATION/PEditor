"""G4-06：Qt 標準快捷鍵（Windows 為 Ctrl、macOS 為 Cmd）。

Qt 在 macOS 把 ControlModifier 對應到 Cmd 鍵，所以兩平台都以 ControlModifier 檢查；
實機按鍵在 Windows、macOS 實機人工驗收（ADR-0021 §3）。
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from test_e2e import FILES, apply, click_target, open_file, preview, wait

STANDARD = {
    "open": QKeySequence.StandardKey.Open,
    "save": QKeySequence.StandardKey.SaveAs,
    "undo": QKeySequence.StandardKey.Undo,
    "redo": QKeySequence.StandardKey.Redo,
}


def press(qtbot, window, name):
    combo = window.actions[name].shortcut()[0]
    qtbot.keyClick(window, combo.key(), combo.keyboardModifiers())
    wait(qtbot, window)


def test_platform_shortcuts(qtbot, make_window):
    window = make_window()
    for name, key in STANDARD.items():
        shortcut = window.actions[name].shortcut()
        assert not shortcut.isEmpty() and shortcut == QKeySequence(key), name
        assert shortcut[0].keyboardModifiers() & Qt.KeyboardModifier.ControlModifier, name
        native = shortcut.toString(QKeySequence.SequenceFormat.NativeText)
        assert ("⌘" in native) if sys.platform == "darwin" else native.startswith("Ctrl+"), native

    open_file(qtbot, window, FILES / "F04.pdf")
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Hello Earth")
    apply(qtbot, window)
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    press(qtbot, window, "undo")
    assert window.revision == 2
    assert any(t["text"] == "Hello World" for t in window.page["text_targets"])
    press(qtbot, window, "redo")
    assert window.revision == 3
    assert any(t["text"] == "Hello Earth" for t in window.page["text_targets"])
