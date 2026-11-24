"""ADR-0030：開新視窗、選單列與標題顯示檔名。"""

import sys

from test_e2e import FILES, apply, click_target, open_file, preview

from peditor.ui import app as app_module


def test_title_and_menu_show_file_name(qtbot, make_window):
    window = make_window()
    assert window.file_label.text() == "" and window.windowTitle().startswith("PEditor")
    open_file(qtbot, window, FILES / "F04.pdf")
    assert window.file_label.text() == "F04.pdf"
    assert window.windowTitle().startswith("F04.pdf — PEditor")
    assert window.menuBar().cornerWidget() is window.file_label
    click_target(qtbot, window, "World")
    preview(qtbot, window, "Earth")
    apply(qtbot, window)
    assert window.windowTitle().startswith("F04.pdf * — ")
    assert "未另存的修改" in window.file_label.text()
    assert str(FILES) not in window.file_label.text()  # 只顯示檔名，不顯示完整路徑


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
