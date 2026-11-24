"""ADR-0034：改名 LUMICAT——圖示、品牌色、安裝程式、舊資料夾與舊暫存檔沿用。"""

import json
import os
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from lumicat.core import drafts
from lumicat.export import transaction
from lumicat.ui import app as app_module
from lumicat.ui import theme

ROOT = Path(__file__).resolve().parents[2]
ISS = ROOT / "packaging" / "windows" / "lumicat.iss"


def test_app_icon_has_all_sizes(qtbot):
    icon = app_module.app_icon()
    sizes = {(s.width(), s.height()) for s in icon.availableSizes()}
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes


def test_window_title_and_app_name(qtbot, make_window):
    window = make_window()
    assert window.windowTitle().startswith("LUMICAT ")
    assert "PEditor" not in window.windowTitle()
    assert app_module.about_text("abc1234").count("LUMICAT") >= 1
    assert "PEditor" not in app_module.about_text("abc1234")
    assert QApplication.instance() is not None


def test_brand_colors():
    assert theme.TOKENS["accent"] == "#00529B" and theme.TOKENS["ground"] == "#F4FAFF"
    brand = json.loads((ROOT / "docs" / "brand" / "colors.json").read_text(encoding="utf-8"))
    assert (
        brand["deepBlue"] == theme.TOKENS["accent"] and brand["offWhite"] == theme.TOKENS["ground"]
    )
    # 光耀藍對白底小字對比不足，不用作文字色（品牌指南）
    assert theme.contrast(brand["primary"], "#FFFFFF") < 4.5
    assert brand["primary"] not in theme.TOKENS.values()


def test_installer_branding():
    text = ISS.read_text(encoding="ascii")
    settings = [line for line in text.splitlines() if not line.startswith(";")]
    assert "AppName=LUMICAT" in settings and not any("PEditor" in line for line in settings)
    # 新 AppId：不覆蓋 PEditor 測試版的安裝
    assert "AppId={{C1D285B1-CE4F-4431-A669-F12FEB8E0D91}" in settings
    assert "SetupIconFile=..\\icons\\lumicat.ico" in text
    assert (ISS.parent / ".." / "icons" / "lumicat.ico").resolve().is_file()
    assert (ROOT / "packaging" / "icons" / "lumicat.icns").is_file()


def test_old_data_folder_is_renamed(tmp_path):
    old = tmp_path / "PEditor" / "drafts"
    old.mkdir(parents=True)
    (old / "keep.json").write_text("{}", encoding="utf-8")
    base = drafts._migrate(tmp_path)
    assert base == tmp_path / "LUMICAT" and (base / "drafts" / "keep.json").is_file()
    assert not (tmp_path / "PEditor").exists()
    assert drafts._migrate(tmp_path) == tmp_path / "LUMICAT"  # 已改過就不再動


def test_old_data_folder_kept_when_rename_fails(tmp_path, monkeypatch):
    (tmp_path / "PEditor").mkdir()

    def fail(*_a):
        raise OSError("in use")

    monkeypatch.setattr(Path, "rename", fail)
    assert drafts._migrate(tmp_path) == tmp_path / "PEditor"  # 不遺失草稿


def test_old_temp_name_still_cleaned(tmp_path, monkeypatch):
    registry = tmp_path / "pending-temps.json"
    monkeypatch.setattr(transaction, "registry", str(registry))
    old_temp = tmp_path / ".~peditor-00000000000000ab.tmp.pdf"  # 改名前留下的
    old_temp.write_bytes(b"x")
    stale = time.time() - transaction.STALE_TEMP_S - 60
    os.utime(old_temp, (stale, stale))
    registry.write_text(json.dumps([str(old_temp)]), encoding="utf-8")
    transaction.cleanup_recorded()
    assert not old_temp.exists()
    assert not transaction.TEMP_PATTERN.match(".~other-00000000000000ab.tmp.pdf")
