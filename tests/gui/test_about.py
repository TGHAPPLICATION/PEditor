"""P8 授權核對 F2、F3：「說明 → 關於 PEditor」顯示 AGPL-3.0 §5(d) 的適當法律聲明
與對應原始碼位置。"""

from PySide6.QtWidgets import QMessageBox

from peditor.ui.app import COPYRIGHT, SOURCE_URL, about_text


def test_about_text_has_legal_notices():
    text = about_text("0b821ff")
    assert COPYRIGHT in text
    assert "AGPL-3.0-only" in text and "不提供任何擔保" in text
    assert f"{SOURCE_URL}/tree/0b821ff" in text  # 該版本的對應原始碼
    assert "licenses" in text and "THIRD_PARTY_NOTICES.md" in text
    assert f"對應原始碼：{SOURCE_URL}\n" in about_text("")  # 開發環境沒有建置 commit


def test_about_menu_shows_dialog(qtbot, make_window, monkeypatch):
    shown = []
    monkeypatch.setattr(
        QMessageBox, "about", lambda parent, title, text: shown.append((title, text))
    )
    window = make_window()
    menus = {a.text(): a.menu() for a in window.menuBar().actions()}
    assert window.actions["about"] in menus["說明"].actions()
    window.actions["about"].trigger()
    assert shown and shown[0][0] == "關於 PEditor" and COPYRIGHT in shown[0][1]
