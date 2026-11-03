"""G4-07：中文字型在頁面與前後對照預覽中實際畫出字形（不是空白，也不是同一個缺字框）。

offscreen 平台沒有系統字型，Qt 介面元件的中文字形無法在此自動驗證，
於 Windows、macOS 實機人工驗收（ADR-0021 §3）。這裡驗證介面拿到的文字未被改碼。
"""

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QGraphicsPixmapItem
from test_e2e import FILES, click_target, open_file, preview


def ink(image: QImage) -> int:
    return sum(QColor(image.pixel(x, y)).lightness() < 128
               for y in range(image.height()) for x in range(image.width()))  # fmt: skip


def after_image(qtbot, window, new_text) -> QImage:
    preview(qtbot, window, new_text)
    assert window.plan["ready"], window.panel.info.text()
    return window.panel.after.pixmap().toImage()


def test_cjk_font_rendering(qtbot, make_window):
    """T05 內嵌 Noto Sans TC，MuPDF 可渲染（不在 ADR-0015 的 7 份例外內）。"""
    window = make_window()
    open_file(qtbot, window, FILES / "T05.pdf")
    target = click_target(qtbot, window, "稽核")
    assert window.panel.selected.text() == target["text"]

    page = next(i for i in window.view.scene().items() if isinstance(i, QGraphicsPixmapItem))
    region = window.view.target_rect(target["target_id"]).toRect()
    assert ink(page.pixmap().copy(region).toImage()) > 0  # 原字形有畫出

    first = after_image(qtbot, window, "資訊安全檢查")
    second = after_image(qtbot, window, "資訊安全演練")
    assert ink(first) > 0 and ink(second) > 0
    assert first != second  # 不同的字畫出不同字形；若都是缺字框則相同
