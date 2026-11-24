"""介面主題（ADR-0029 §7，P9-08）：配色 token、QSS、平台內建字型與自繪線條圖示。

依工程師確認的視覺稿（配色與字級）。圖示為本檔自繪的 SVG 路徑，不引入第三方圖示包；
字型用系統內建（Windows「Microsoft JhengHei UI」、macOS「PingFang TC」），不另打包。
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

TOKENS = {
    "accent": "#1F6F5C",
    "accent_hover": "#185A4B",
    "accent_soft": "#E3EFEB",
    "ground": "#F6F7F5",
    "surface": "#FFFFFF",
    "text": "#1D2421",
    "muted": "#5D6963",
    "line": "#D9DFDB",
    "disabled": "#8C9792",
    "notice_bg": "#FFF6DF",
    "notice_line": "#E8D59A",
    "notice_text": "#5C4A12",
    "error": "#B3261E",
}

# 須達 WCAG 4.5:1 的前景／背景組合（tests/gui/test_theme.py 檢查）
CONTRAST_PAIRS = [
    ("text", "surface"), ("text", "ground"), ("muted", "surface"), ("muted", "ground"),
    ("surface", "accent"), ("accent", "surface"), ("accent", "accent_soft"),
    ("notice_text", "notice_bg"), ("error", "surface"),
]  # fmt: skip

FONT_FAMILIES = {"win32": "Microsoft JhengHei UI", "darwin": "PingFang TC"}


def stylesheet(t: dict[str, str] = TOKENS) -> str:
    return f"""
QMainWindow, QDialog {{ background: {t["ground"]}; color: {t["text"]}; }}
QWidget {{ font-size: 14px; }}
QMenuBar {{ background: {t["surface"]}; border-bottom: 1px solid {t["line"]}; }}
QMenuBar::item {{ padding: 6px 10px; border-radius: 6px; }}
QMenuBar::item:selected {{ background: {t["accent_soft"]}; color: {t["accent"]}; }}
QMenu {{ background: {t["surface"]}; border: 1px solid {t["line"]}; padding: 4px; }}
QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t["accent_soft"]}; color: {t["accent"]}; }}
QToolBar {{ background: {t["surface"]}; border: 0; border-bottom: 1px solid {t["line"]};
           padding: 6px 8px; spacing: 4px; }}
QToolBar::separator {{ background: {t["line"]}; width: 1px; margin: 4px 8px; }}
QToolButton {{ border: 1px solid {t["line"]}; background: {t["surface"]}; color: {t["text"]};
              border-radius: 8px; padding: 6px 10px; min-height: 22px; }}
QToolButton:hover {{ background: {t["ground"]}; }}
QToolButton:checked {{ background: {t["accent_soft"]}; border-color: {t["accent"]};
                      color: {t["accent"]}; }}
QToolButton:disabled {{ color: {t["disabled"]}; }}
QToolButton#primary {{ background: {t["accent"]}; border-color: {t["accent"]};
                      color: {t["surface"]}; font-weight: 500; }}
QToolButton#primary:hover {{ background: {t["accent_hover"]}; }}
QToolButton#primary:disabled {{ background: {t["line"]}; border-color: {t["line"]};
                               color: {t["muted"]}; }}
QToolButton#outline {{ border-color: {t["accent"]}; color: {t["accent"]}; font-weight: 500; }}
QPushButton {{ border: 1px solid {t["line"]}; background: {t["surface"]}; color: {t["text"]};
              border-radius: 8px; padding: 8px 16px; min-height: 22px; }}
QPushButton:hover {{ background: {t["ground"]}; }}
QPushButton:disabled {{ color: {t["disabled"]}; }}
QPushButton#primary, QPushButton:default {{ background: {t["accent"]}; border-color: {t["accent"]};
                                           color: {t["surface"]}; font-weight: 500; }}
QPushButton#primary:hover, QPushButton:default:hover {{ background: {t["accent_hover"]}; }}
QPushButton#primary:disabled {{ background: {t["line"]}; border-color: {t["line"]};
                               color: {t["muted"]}; }}
QLineEdit, QSpinBox, QComboBox {{ border: 1px solid {t["line"]}; border-radius: 8px;
                                 padding: 6px 10px; background: {t["surface"]};
                                 selection-background-color: {t["accent_soft"]};
                                 selection-color: {t["text"]}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {t["accent"]}; }}
QListWidget {{ background: {t["surface"]}; border: 0; border-right: 1px solid {t["line"]}; }}
QListWidget::item:selected {{ background: {t["accent_soft"]}; color: {t["accent"]}; }}
QListWidget#merge_list {{ border: 1px solid {t["line"]}; border-radius: 8px; }}
QListWidget#merge_list::item {{ padding: 8px 10px; border-bottom: 1px solid {t["ground"]}; }}
QDockWidget {{ font-weight: 700; }}
QDockWidget > QWidget {{ background: {t["surface"]}; }}
QScrollArea {{ border: 0; background: {t["surface"]}; }}
QLabel#notice {{ background: {t["notice_bg"]}; border: 1px solid {t["notice_line"]};
                color: {t["notice_text"]}; border-radius: 8px; padding: 6px 10px; }}
QLabel#notice[empty="true"] {{ background: transparent; border: 0; padding: 0; }}
QLabel#caption {{ color: {t["muted"]}; font-size: 12px; }}
QLabel#error {{ color: {t["error"]}; }}
QLabel#limits {{ background: {t["surface"]}; border: 1px solid {t["line"]}; border-radius: 8px;
                padding: 10px 12px; color: {t["muted"]}; }}
QTabWidget::pane {{ border: 0; border-top: 1px solid {t["line"]}; }}
QTabBar::tab {{ padding: 10px 14px; border: 0; border-bottom: 2px solid transparent;
               color: {t["muted"]}; background: transparent; }}
QTabBar::tab:selected {{ color: {t["accent"]}; border-bottom-color: {t["accent"]};
                        font-weight: 700; }}
QStatusBar {{ background: {t["surface"]}; border-top: 1px solid {t["line"]}; color: {t["muted"]}; }}
QProgressBar {{ border: 1px solid {t["line"]}; border-radius: 4px; max-height: 8px; }}
QProgressBar::chunk {{ background: {t["accent"]}; }}
"""


def apply(app: QApplication) -> None:
    family = FONT_FAMILIES.get(sys.platform)
    if family:
        font = QFont(family)
        font.setPointSizeF(10.5)
        app.setFont(font)
    app.setStyleSheet(stylesheet())


# 24×24 線條圖示（stroke 為 currentColor 的替代：以 {color} 代入）
_ICONS = {
    "open": '<path d="M3 7h6l2 2h10v10H3z"/>',
    "save": '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v6h8V3"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>',
    "redo": '<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 000 12h3"/>',
    "manual_cell": '<rect x="4" y="4" width="16" height="16" rx="1"/><path d="M4 12h16M12 4v16"/>',
    "zoom_out": '<path d="M5 12h14"/>',
    "zoom_in": '<path d="M5 12h14M12 5v14"/>',
    "zoom_reset": '<rect x="5" y="5" width="14" height="14" rx="1"/><path d="M9 12h6"/>',
    "fit_width": '<path d="M3 12h18M7 8l-4 4 4 4M17 8l4 4-4 4"/>',
    "page_tools": '<rect x="3" y="4" width="8" height="16" rx="1"/>'
    '<rect x="13" y="4" width="8" height="16" rx="1"/>',
    "cancel": '<path d="M6 6l12 12M18 6L6 18"/>',
}


def icon(name: str, color: str = TOKENS["text"]) -> QIcon:
    body = _ICONS.get(name)
    if body is None:
        return QIcon()
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
           f'stroke-linejoin="round">{body}</svg>')  # fmt: skip
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    result = QIcon()
    for size in (18, 36):
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result


def contrast(foreground: str, background: str) -> float:
    """WCAG 2 對比值。"""

    def luminance(hex_color: str) -> float:
        channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    a, b = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (a + 0.05) / (b + 0.05)
