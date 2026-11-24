"""ADR-0031：檔案總管右鍵「用 PEditor 開啟」——命令列檔案參數與安裝程式機碼。"""

import re
from pathlib import Path

from test_e2e import FILES, wait

from peditor import __main__ as entry
from peditor.ui import app as app_module

ISS = Path(__file__).resolve().parents[2] / "packaging" / "windows" / "peditor.iss"


def test_command_line_path_is_passed_to_run(monkeypatch):
    seen = {}
    monkeypatch.setattr(app_module, "run", lambda **kw: seen.update(kw) or 0)
    assert entry.main([r"C:\docs\a b.pdf"]) == 0
    assert seen["path"] == r"C:\docs\a b.pdf" and seen["smoke"] is False
    assert entry.main([]) == 0
    assert seen["path"] is None


def test_startup_opens_given_file_without_draft_prompt(qtbot, make_window, monkeypatch):
    window = make_window()
    asked = []
    monkeypatch.setattr(window, "offer_drafts", lambda: asked.append(True))
    app_module.startup(window, str(FILES / "F04.pdf"))
    wait(qtbot, window)
    assert window.document_id is not None
    assert window.windowTitle().startswith("F04.pdf — ")
    assert asked == []


def test_startup_without_file_offers_drafts(make_window, monkeypatch):
    window = make_window()
    asked = []
    monkeypatch.setattr(window, "offer_drafts", lambda: asked.append(True))
    app_module.startup(window, None)
    assert asked == [True] and window.document_id is None


def test_startup_bad_file_shows_error_without_path(qtbot, make_window, tmp_path):
    window = make_window()
    bad = tmp_path / "secret-folder" / "missing.pdf"  # 右鍵後檔案已被移走
    app_module.startup(window, str(bad))
    wait(qtbot, window)
    assert window.document_id is None
    assert "secret-folder" not in window.statusBar().currentMessage()


def _registry() -> list[str]:
    text = ISS.read_text(encoding="utf-8")
    section = text.split("[Registry]", 1)[1]
    return [line for line in section.splitlines() if line.startswith("Root:")]


def test_installer_registers_per_user_verb_and_open_with():
    lines = _registry()
    assert lines and all(line.startswith("Root: HKCU;") for line in lines)  # 免管理員權限
    verb = r"Software\Classes\SystemFileAssociations\.pdf\shell\PEditor"
    assert any(f'"{verb}";' in line and "用 PEditor 開啟" in line for line in lines)
    commands = [line for line in lines if "command" in line]
    assert len(commands) == 2
    for line in commands:  # 程式與檔案路徑都加引號，含空白的路徑才不會被拆開
        assert '"""{app}\\PEditor.exe"" ""%1"""' in line
    # 只加入「開啟方式」清單，不改預設 PDF 程式（不寫 .pdf 的預設值或 UserChoice）
    assert not any(re.search(r'\\\.pdf"; ValueType: string; ValueName: ""', line) for line in lines)
    assert not any("UserChoice" in line for line in lines)
    # 卸載時移除
    owned = [line for line in lines if "ValueName: \"\"" in line and "command" not in line
             and "DefaultIcon" not in line]  # fmt: skip
    assert all("uninsdeletekey" in line for line in owned)
    assert any("OpenWithProgids" in line and "uninsdeletevalue" in line for line in lines)
