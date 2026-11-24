"""視窗與對話框不超出螢幕可用範圍。

2026-11-24 實機：高 DPI 縮放時對話框下方按鈕超出畫面下緣、文字被遮住。

以螢幕「可用範圍」（扣除工作列）為準：預設大小超過時縮小，顯示時整個框（含標題列）移回範圍內。
對話框內容須能縮小（文字區、清單可捲動），按鈕維持原尺寸、不被壓縮。
"""

from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QWidget

MARGIN = 8  # 與可用範圍邊緣保留的距離（px）


def available_area(widget: QWidget) -> QRect:
    """視窗所在螢幕扣除工作列後的範圍；測試可替換此函式模擬小螢幕。"""
    screen = widget.screen() or QGuiApplication.primaryScreen()
    return screen.availableGeometry()


def fit_size(widget: QWidget, width: int, height: int) -> None:
    """預設大小，但不超過可用範圍（扣除標題列約 40 px 與邊距）。"""
    area = available_area(widget)
    widget.resize(min(width, area.width() - 2 * MARGIN),
                  min(height, area.height() - 40 - 2 * MARGIN))  # fmt: skip


def keep_inside(widget: QWidget) -> None:
    """含標題列的整個框移回可用範圍；仍放不下時縮小內容區（不低於最小尺寸）。"""
    area = available_area(widget).adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)
    frame = widget.frameGeometry()
    extra_w = frame.width() - widget.width()  # 標題列與邊框
    extra_h = frame.height() - widget.height()
    width = min(widget.width(), area.width() - extra_w)
    height = min(widget.height(), area.height() - extra_h)
    if (width, height) != (widget.width(), widget.height()):
        widget.resize(max(width, widget.minimumWidth()), max(height, widget.minimumHeight()))
        frame = widget.frameGeometry()
    x = min(max(frame.x(), area.left()), area.right() - frame.width() + 1)
    y = min(max(frame.y(), area.top()), area.bottom() - frame.height() + 1)
    widget.move(max(x, area.left()), max(y, area.top()))


class FittedDialog(QDialog):
    """顯示時不超出螢幕可用範圍的對話框。"""

    def showEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        super().showEvent(event)
        keep_inside(self)
