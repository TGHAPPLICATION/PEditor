"""P9-08：介面主題（ADR-0029 §7）：配色對比、QSS 套用、工具列分組與圖示。"""

import pytest
from PySide6.QtWidgets import QToolButton

from peditor.ui import theme


@pytest.mark.parametrize(("fg", "bg"), theme.CONTRAST_PAIRS)
def test_contrast_meets_wcag_aa(fg, bg):
    assert theme.contrast(theme.TOKENS[fg], theme.TOKENS[bg]) >= 4.5


def test_stylesheet_uses_tokens():
    qss = theme.stylesheet()
    assert theme.TOKENS["accent"] in qss and "QToolButton#primary" in qss
    assert "{" in qss and "{{" not in qss  # f-string 已展開


def test_icons_render():
    for name in ("open", "save", "undo", "redo", "page_tools", "fit_width"):
        assert not theme.icon(name).isNull()
    assert theme.icon("unknown").isNull()


def test_toolbar_groups_and_primary(qtbot, make_window):
    window = make_window()
    toolbar = window.findChildren(type(window.addToolBar("x")))[0]
    names = [a for a in toolbar.actions()]
    assert window.actions["find"] not in names and window.actions["about"] not in names
    assert names.index(window.actions["page_tools"]) == len(names) - 1  # 最右邊
    assert sum(1 for a in names if a.isSeparator()) == 2
    save = toolbar.widgetForAction(window.actions["save"])
    assert isinstance(save, QToolButton) and save.objectName() == "primary"
    menus = {a.text() for a in window.menuBar().actions()}
    assert {"檔案", "編輯", "檢視", "工具", "說明"} <= menus
