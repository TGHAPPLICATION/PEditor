"""ADR-0030：開新視窗、視窗標題顯示檔名。"""

import sys

from test_e2e import FILES, apply, click_target, open_file, preview

from peditor.ui import app as app_module


def test_title_shows_file_name(qtbot, make_window):
    window = make_window()
    assert window.windowTitle().startswith("PEditor")
    open_file(qtbot, window, FILES / "F04.pdf")
    assert window.windowTitle().startswith("F04.pdf — PEditor")
    assert window.menuBar().cornerWidget() is None  # 檔名只在標題，不在選單列重複
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Earth")
    apply(qtbot, window)
    assert window.windowTitle().startswith("F04.pdf * — ")
    assert str(FILES) not in window.windowTitle()  # 只顯示檔名，不顯示完整路徑


def test_new_window_spawns_process(qtbot, make_window, monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.subprocess, "Popen", lambda cmd, **kw: calls.append((cmd, kw)))
    window = make_window()
    menus = {a.text(): a.menu() for a in window.menuBar().actions()}
    assert window.actions["new_window"] in menus["檔案"].actions()
    window.actions["new_window"].trigger()
    cmd, kw = calls[0]
    assert cmd == [sys.executable, "-m", "peditor"] and "shell" not in kw
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert app_module._self_command() == [sys.executable]


def test_new_window_failure_reported(qtbot, make_window, monkeypatch):
    def fail(*_a, **_k):
        raise OSError("no")

    monkeypatch.setattr(app_module.subprocess, "Popen", fail)
    window = make_window()
    window.new_window()
    assert window.statusBar().currentMessage() == "無法開啟新視窗"
