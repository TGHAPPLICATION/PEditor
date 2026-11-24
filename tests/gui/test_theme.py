"""P9-08：介面主題（ADR-0029 §7）：配色對比、QSS 套用、工具列分組與圖示。"""

import pytest
from PySide6.QtWidgets import QToolButton

from lumicat.ui import theme


@pytest.mark.parametrize(("fg", "bg"), theme.CONTRAST_PAIRS)
def test_contrast_meets_wcag_aa(fg, bg):
    assert theme.contrast(theme.TOKENS[fg], theme.TOKENS[bg]) >= 4.5


def test_stylesheet_uses_tokens():
    qss = theme.stylesheet()
    assert theme.TOKENS["accent"] in qss and "QToolButton#primary" in qss
    assert "{" in qss and "{{" not in qss  # f-string 已展開


def test_icons_render(qtbot):  # QPixmap 需要 QApplication（單獨執行本檔時）
    for name in ("open", "save", "undo", "redo", "page_tools", "text_extract", "fit_width"):
        assert not theme.icon(name).isNull()
    assert theme.icon("unknown").isNull()


def test_toolbar_groups_and_primary(qtbot, make_window):
    window = make_window()
    toolbar = window.findChildren(type(window.addToolBar("x")))[0]
    names = [a for a in toolbar.actions()]
    assert window.actions["find"] not in names and window.actions["about"] not in names
    # 工程師 2026-11-24：「頁面管理」移到「另存新檔」右方，其右為「文字擷取」（ADR-0033）
    save_at = names.index(window.actions["save"])
    assert names[save_at + 1] is window.actions["page_tools"]
    assert names[save_at + 2] is window.actions["text_extract"]
    assert window.actions["page_tools"].text() == "頁面管理…"
    for name in ("page_tools", "text_extract"):
        button = toolbar.widgetForAction(window.actions[name])
        assert isinstance(button, QToolButton) and button.objectName() == "outline"
    tools = next(a.menu() for a in window.menuBar().actions() if a.text() == "工具")
    assert [a.text() for a in tools.actions()] == ["頁面管理…", "文字擷取…"]
    assert sum(1 for a in names if a.isSeparator()) == 2
    save = toolbar.widgetForAction(window.actions["save"])
    assert isinstance(save, QToolButton) and save.objectName() == "primary"
    menus = {a.text() for a in window.menuBar().actions()}
    assert {"檔案", "編輯", "檢視", "工具", "說明"} <= menus
