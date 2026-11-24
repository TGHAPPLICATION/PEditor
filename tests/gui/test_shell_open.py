"""ADR-0031：檔案總管右鍵「用 LUMICAT 開啟」——命令列檔案參數與安裝程式機碼。"""

import re
from pathlib import Path

from test_e2e import FILES, wait

from lumicat import __main__ as entry
from lumicat.ui import app as app_module

ISS = Path(__file__).resolve().parents[2] / "packaging" / "windows" / "lumicat.iss"


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


def _pascal_string(text: str, function: str) -> str:
    """把 [Code] 函式回傳的 Pascal 字串（'...' 與 #$XXXX 串接）還原成實際文字。"""
    body = text.split(f"function {function}(", 1)[1].split("Result :=", 1)[1].split(";", 1)[0]
    parts = re.findall(r"'([^']*)'|#\$([0-9A-Fa-f]{4})", body)
    return "".join(chunk if chunk else chr(int(code, 16)) for chunk, code in parts)


def test_installer_script_is_ascii_and_chinese_labels_decode():
    """實機發現：安裝程式畫面的中文顯示成方框或問號。腳本維持 ASCII，中文以碼位在 [Code] 組成，
    不受腳本檔解碼方式影響；精靈字型改用有中文字形的 Microsoft JhengHei UI（ADR-0031 §5）。"""
    raw = ISS.read_bytes()
    assert raw.isascii()
    text = raw.decode("ascii")
    assert _pascal_string(text, "OpenVerbCaption") == "用 LUMICAT 開啟"
    caption = "設定 LUMICAT 為 PDF 預設程式（開啟 Windows 設定）"
    assert _pascal_string(text, "DefaultAppCaption") == caption
    assert "DialogFontName=Microsoft JhengHei UI" in text.split("[LangOptions]", 1)[1]


def _registry() -> list[str]:
    text = ISS.read_text(encoding="ascii")
    section = text.split("[Registry]", 1)[1].split("\n[", 1)[0]
    return [line for line in section.splitlines() if line.startswith("Root:")]


def test_installer_registers_per_user_verb_and_open_with():
    lines = _registry()
    assert lines and all(line.startswith("Root: HKCU;") for line in lines)  # 免管理員權限
    verb = r"Software\Classes\SystemFileAssociations\.pdf\shell\LUMICAT"
    assert any(f'"{verb}";' in line and "{code:OpenVerbCaption}" in line for line in lines)
    commands = [line for line in lines if "command" in line]
    assert len(commands) == 2
    for line in commands:  # 程式與檔案路徑都加引號，含空白的路徑才不會被拆開
        assert '"""{app}\\LUMICAT.exe"" ""%1"""' in line
    # 只加入「開啟方式」清單，不改預設 PDF 程式（不寫 .pdf 的預設值或 UserChoice）
    assert not any(re.search(r'\\\.pdf"; ValueType: string; ValueName: ""', line) for line in lines)
    assert not any("UserChoice" in line for line in lines)
    # 卸載時移除
    owned = [line for line in lines if "ValueName: \"\"" in line and "command" not in line
             and "DefaultIcon" not in line]  # fmt: skip
    assert all("uninsdeletekey" in line for line in owned)
    assert any("OpenWithProgids" in line and "uninsdeletevalue" in line for line in lines)


def test_installer_default_app_is_opt_in_via_windows_settings():
    text = ISS.read_text(encoding="ascii")
    run = text.split("[Run]", 1)[1].split("[", 1)[0]
    line = next(x for x in run.splitlines() if "ms-settings:defaultapps" in x)
    # 預設不勾；只開 Windows 設定由使用者選，不自行改預設程式
    assert "registeredAppUser=LUMICAT" in line and "unchecked" in line and "shellexec" in line
    assert 'Description: "{code:DefaultAppCaption}"' in line
    lines = _registry()
    assert any(r'"Software\RegisteredApplications"; ValueType: string; ValueName: "LUMICAT"' in x
               and "uninsdeletevalue" in x for x in lines)  # fmt: skip
    assert any(r"Capabilities\FileAssociations" in x and 'ValueData: "LUMICAT.pdf"' in x
               for x in lines)  # fmt: skip
