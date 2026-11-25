"""桌面主視窗（P4、ADR-0021）：開檔、縮圖、預覽、點選文字、替換、undo／redo、另存、進度與取消。
P5（ADR-0022）：點選圖片、選擇新圖片（PNG／JPEG）後套用。
P11（ADR-0032）：點選後在頁面上開半透明編輯框，只有「套用」；有提醒時先在框內顯示、再按一次才寫回。
P6（ADR-0023）：點到表格格內文字時改以儲存格編輯（一次一行）；「手動選格」拉框選格，仍經能力判定。

UI 只呼叫 DocumentService 的公開 API，不匯入 PDF 程式庫、不組 PDF 指令（spec §9、G1-01）。
所有 DocumentService 呼叫經 JobRunner 在背景執行緒進行，主執行緒不等待 worker（G4-06）；
關閉視窗時例外（ADR-0021 §2，P4 U11）。
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QDateTime, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from lumicat import __version__
from lumicat.core.geometry import PageGeometry, bbox_of
from lumicat.core.limits import MAX_RENDER_DPI
from lumicat.core.service import DocumentService, ServiceError
from lumicat.ui import theme
from lumicat.ui.jobs import JobRunner
from lumicat.ui.messages import NOTICES, reason_text, reasons_text
from lumicat.ui.page_tools import PageToolsDialog, Request, Source, probe_error_text
from lumicat.ui.screen import FittedDialog, fit_size, keep_inside
from lumicat.ui.text_extract import TextExtractDialog

SMOKE_MARKER = "LUMICAT_SMOKE_OK"
PAGE_DPI = 100
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.25, 4.0, 1.25  # 頁面縮放（P8 工程師要求）
THUMB_DPI = 24
MAX_THUMBS = 200
OVERLAY_WIDTH = 380  # 編輯框寬度（px；視窗較窄時縮小）
# 只是告知、不需確認的計畫訊息（其他提醒套用前先在編輯框顯示，ADR-0032 §3）
INFO_ONLY_WARNINGS = ("已同步更新結構樹",)


def _pixmap(rendered: dict) -> QPixmap:
    pix = QPixmap()
    pix.loadFromData(base64.b64decode(rendered["png_base64"]), "PNG")
    return pix


class PageView(QGraphicsView):
    """頁面圖與文字、圖片目標框。點選以 bbox 判定命中（圖片用可見範圍），回傳的是 target；
    內容由 target_id 定位，不以 bbox 定位（ADR-0021 §2）。重疊時取面積最小者（圖片上的文字）。"""

    target_clicked = Signal(dict)
    box_selected = Signal(list)  # 手動選格：拉出的範圍（頁面空間 pt）

    zoom_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.zoom = 1.0  # 檢視縮放；場景座標固定為 PAGE_DPI，點選判定不受影響
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._geometry: PageGeometry | None = None
        self._targets: list[dict] = []
        self._selected: QGraphicsRectItem | None = None
        self.box_mode = False
        self._drag_start = None
        self._drag_item: QGraphicsRectItem | None = None

    def show_page(self, rendered: dict, page: dict) -> None:
        scene = self.scene()
        scene.clear()
        self._selected = None
        self._drag_item = None
        self._pixmap_item = QGraphicsPixmapItem(_pixmap(rendered))
        scene.addItem(self._pixmap_item)
        geom = page["page_geometry"]
        self._geometry = PageGeometry(tuple(geom["cropbox"]), geom["rotation"])
        self._targets = [{**t, "kind": "text"} for t in page["text_targets"] if t.get("bbox")]
        self._targets += [{**t, "kind": "image", "bbox": t["visible_bbox"]}
                          for t in page.get("image_targets", [])]  # fmt: skip
        to_view = self._geometry.page_to_view(PAGE_DPI / 72)
        for target in self._targets:
            x0, y0, x1, y1 = bbox_of(to_view, tuple(target["bbox"]))
            if target["capability"]["status"] != "support":
                color = QColor(160, 160, 160)
            else:
                color = QColor(0, 120, 215) if target["kind"] == "text" else QColor(230, 120, 0)
            item = scene.addRect(QRectF(x0, y0, x1 - x0, y1 - y0), QPen(color, 1))
            item.setData(0, target["target_id"])
        scene.setSceneRect(QRectF(0, 0, rendered["width"], rendered["height"]))

    def set_zoom(self, zoom: float) -> None:
        """檢視縮放（25%–400%）：只改檢視轉換，場景與目標框座標不變。"""
        zoom = min(ZOOM_MAX, max(ZOOM_MIN, zoom))
        if abs(zoom - self.zoom) < 1e-6:
            return
        self.zoom = zoom
        self.setTransform(QTransform.fromScale(zoom, zoom))
        self.zoom_changed.emit(zoom)

    def fit_width(self) -> None:
        if self._pixmap_item is not None:
            width = self.scene().sceneRect().width()
            if width > 0:
                self.set_zoom((self.viewport().width() - 4) / width)

    def set_sharper(self, rendered: dict, dpi: int) -> None:
        """放大時以較高 DPI 重新渲染的頁面圖取代原圖（縮回場景的 PAGE_DPI 大小），字不糊。"""
        if self._pixmap_item is not None:
            self._pixmap_item.setPixmap(_pixmap(rendered))
            self._pixmap_item.setScale(PAGE_DPI / dpi)
            self._pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    def wheelEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:  # Ctrl＋滾輪縮放
            step = ZOOM_STEP if event.angleDelta().y() > 0 else 1 / ZOOM_STEP
            self.set_zoom(self.zoom * step)
            event.accept()
            return
        super().wheelEvent(event)

    def clear(self) -> None:
        """清空頁面與目標框（開啟沒有頁面的文件時，不留下前一份文件；P4 U13）。"""
        self.scene().clear()
        self._pixmap_item = None
        self._selected = None
        self._drag_item = None
        self._geometry = None
        self._targets = []

    def target_rect(self, target_id: str) -> QRectF | None:
        for item in self.scene().items():
            if isinstance(item, QGraphicsRectItem) and item.data(0) == target_id:
                return item.sceneBoundingRect()
        return None

    def page_rect(self, box: list) -> QRectF | None:
        """頁面座標（pt）的範圍轉成場景矩形（手動選格的編輯框定位用）。"""
        if self._geometry is None:
            return None
        x0, y0, x1, y1 = bbox_of(self._geometry.page_to_view(PAGE_DPI / 72), tuple(box))
        return QRectF(x0, y0, x1 - x0, y1 - y0)

    def highlight(self, target_id: str | None) -> None:
        for item in self.scene().items():
            if isinstance(item, QGraphicsRectItem):
                width = 3 if item.data(0) == target_id else 1
                pen = item.pen()
                pen.setWidth(width)
                item.setPen(pen)

    def target_at(self, x: float, y: float) -> dict | None:
        if self._geometry is None:
            return None
        px, py = self._geometry.view_to_page(x, y, PAGE_DPI / 72)
        hits = [t for t in self._targets if t["bbox"][0] <= px <= t["bbox"][2]
                and t["bbox"][1] <= py <= t["bbox"][3]]  # fmt: skip

        def area(t: dict) -> float:
            x0, y0, x1, y1 = t["bbox"]
            return (x1 - x0) * (y1 - y0)

        return min(hits, key=area, default=None)

    def mousePressEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        pos = self.mapToScene(event.position().toPoint())
        if self.box_mode and self._geometry is not None:
            self._drag_start = pos
            if self._drag_item is not None:
                self.scene().removeItem(self._drag_item)
            pen = QPen(QColor(0, 150, 0), 1, Qt.PenStyle.DashLine)
            self._drag_item = self.scene().addRect(QRectF(pos, pos), pen)
            return
        target = self.target_at(pos.x(), pos.y())
        if target is not None:
            self.target_clicked.emit(target)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        if self._drag_start is not None and self._drag_item is not None:
            pos = self.mapToScene(event.position().toPoint())
            self._drag_item.setRect(QRectF(self._drag_start, pos).normalized())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        if self._drag_start is not None:
            start, end = self._drag_start, self.mapToScene(event.position().toPoint())
            self._drag_start = None
            zoom = PAGE_DPI / 72
            corners = [self._geometry.view_to_page(p.x(), p.y(), zoom) for p in (start, end)]
            xs, ys = [c[0] for c in corners], [c[1] for c in corners]
            if max(xs) - min(xs) > 1 and max(ys) - min(ys) > 1:
                self.box_selected.emit([min(xs), min(ys), max(xs), max(ys)])
            return
        super().mouseReleaseEvent(event)


BUILD_FILE = Path(__file__).resolve().parents[1] / "resources" / "BUILD"
ICON_DIR = Path(__file__).resolve().parents[1] / "resources" / "icons"  # 品牌圖示（ADR-0034）


def app_icon() -> QIcon:
    """視窗與工作列圖示：多種尺寸的 PNG，由系統依顯示大小挑選。"""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        path = ICON_DIR / f"lumicat-{size}.png"
        if path.is_file():
            icon.addFile(str(path))
    return icon


COPYRIGHT = "Copyright (C) 2026 Mipaliw"
SOURCE_URL = "https://github.com/TGHAPPLICATION/LUMICAT"


def about_text(commit: str = "") -> str:
    """AGPL-3.0 §5(d) 的適當法律聲明（P8 授權核對 F2、F3）；純文字、不開啟網路連結（離線產品）。"""
    source = f"{SOURCE_URL}/tree/{commit}" if commit else SOURCE_URL
    return "\n".join([
        f"LUMICAT {__version__}" + (f"（建置 {commit}）" if commit else ""),
        COPYRIGHT,
        "",
        "本程式為自由軟體，依 GNU Affero 通用公共授權條款第 3 版（AGPL-3.0-only）散布；",
        "您可以依該授權重新散布或修改本程式。",
        "本程式不提供任何擔保，亦無適售性或特定目的適用性之默示擔保。",
        "詳見授權全文（安裝目錄的 LICENSE）。",
        "",
        f"對應原始碼：{source}",
        "第三方元件與授權：安裝目錄的 THIRD_PARTY_NOTICES.md 與 licenses 資料夾。",
    ])  # fmt: skip


def _build_suffix(path: Path = BUILD_FILE) -> str:
    """打包時寫入的建置 commit（P8 實機驗收辨認安裝包）；開發環境沒有此檔則不顯示。"""
    try:
        commit = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return ""
    return f"（{commit}）" if commit.isalnum() and len(commit) <= 12 else ""


class TextInput(QLineEdit):
    """記錄是否在 IME 組字中：Qt 不保證組字中按 Enter 不發出 returnPressed（P4 U7）。"""

    composing = False

    def inputMethodEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        self.composing = bool(event.preeditString())
        super().inputMethodEvent(event)


class EditOverlay(QFrame):
    """頁面上的半透明編輯框（ADR-0032）：選取內容、新文字（或選擇新圖片）、「套用」與關閉。
    點選後焦點自動到輸入欄；Enter 或「套用」送出（IME 組字中不送出）；Esc 或「×」關閉不修改。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("edit_overlay")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)
        head = QHBoxLayout()
        self.selected = QLabel("")
        self.selected.setObjectName("caption")
        self.selected.setWordWrap(True)
        self.close_button = QToolButton()
        self.close_button.setObjectName("overlay_close")
        self.close_button.setText("×")
        self.close_button.setToolTip("關閉（Esc），不修改")
        head.addWidget(self.selected, 1)
        head.addWidget(self.close_button)
        layout.addLayout(head)
        self.line_choice = QComboBox()  # 儲存格的第幾行（ADR-0023：一次改一行）
        self.line_choice.setObjectName("cell_line")
        self.line_choice.setVisible(False)
        layout.addWidget(self.line_choice)
        row = QHBoxLayout()
        self.new_text = TextInput()
        self.new_text.setObjectName("new_text")
        self.new_text.setPlaceholderText("輸入新文字")
        self.image_button = QPushButton("選擇新圖片…")
        self.image_button.setObjectName("replace_image")
        self.image_label = QLabel("")
        self.image_label.setObjectName("caption")
        self.apply_button = QPushButton("套用")
        self.apply_button.setObjectName("primary")
        for widget in (self.new_text, self.image_button, self.image_label):
            row.addWidget(widget, 1 if widget is not self.image_button else 0)
        row.addWidget(self.apply_button)
        layout.addLayout(row)
        self.info = QLabel("")
        self.info.setObjectName("overlay_info")
        self.info.setWordWrap(True)
        self.info.setVisible(False)
        layout.addWidget(self.info)
        self.escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.hide()

    def set_info(self, text: str) -> None:
        self.info.setText(text)
        self.info.setVisible(bool(text))
        self.adjustSize()

    def set_image_mode(self, image: bool) -> None:
        self.new_text.setVisible(not image)
        self.image_button.setVisible(image)
        self.image_label.setVisible(image)


def _caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("caption")
    return label


class NoticeLabel(QLabel):
    """頁面上方的提示列；沒有內容時隱藏（P9 視覺稿）。"""

    def setText(self, text: str) -> None:  # noqa: N802 — Qt 命名
        super().setText(text)
        self.setVisible(bool(text))


class FindBar(FittedDialog):
    """尋找（Ctrl+F，選單「編輯 → 尋找…」）：小型浮動視窗，不擋住頁面；Enter 或「尋找」送出。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Tool)
        self.setWindowTitle("尋找")
        layout = QHBoxLayout(self)
        self.find_text = QLineEdit()
        self.find_text.setObjectName("find_text")
        self.find_text.setPlaceholderText("尋找文字（可跨段落選取）")
        self.find_text.setMinimumWidth(260)
        self.find_button = QPushButton("尋找")
        self.find_button.setObjectName("find")
        self.find_button.setDefault(True)
        layout.addWidget(self.find_text)
        layout.addWidget(self.find_button)


class DraftDialog(FittedDialog):
    """列出全部未逾期草稿，由使用者選一份復原或捨棄（ADR-0020 §5、P4 U9）。
    只顯示檔名，不顯示完整路徑。choice：("recover"|"discard", draft_id)，稍後再說為 None。"""

    def __init__(self, drafts: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("復原草稿")
        self.choice: tuple[str, str] | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"找到 {len(drafts)} 份未儲存的編輯草稿，請選擇要復原或捨棄的草稿：")
        )
        self.list = QListWidget()
        self.list.setObjectName("drafts")
        for draft in drafts:
            saved = QDateTime.fromSecsSinceEpoch(int(draft["saved_at"])).toString(
                "yyyy-MM-dd HH:mm"
            )
            item = QListWidgetItem(
                f"{os.path.basename(draft['path'])}　{draft['operations']} 項編輯　{saved}"
            )
            item.setData(Qt.ItemDataRole.UserRole, draft["draft_id"])
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        layout.addWidget(self.list)
        self.buttons: dict[str, QPushButton] = {}
        row = QHBoxLayout()
        for action, text in (("recover", "復原"), ("discard", "捨棄"), ("later", "稍後再說")):
            button = QPushButton(text)
            button.setObjectName(action)
            button.clicked.connect(lambda _=False, a=action: self._choose(a))
            row.addWidget(button)
            self.buttons[action] = button
        layout.addLayout(row)

    def _choose(self, action: str) -> None:
        item = self.list.currentItem()
        if action != "later" and item is not None:
            self.choice = (action, item.data(Qt.ItemDataRole.UserRole))
        self.accept()


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: DocumentService | None = None,
        ask_open: Callable[[], str | None] | None = None,
        ask_save: Callable[[], str | None] | None = None,
        ask_draft: Callable[[list[dict]], tuple[str, str] | None] | None = None,
        ask_image: Callable[[], str | None] | None = None,
        ask_unsaved: Callable[[], str] | None = None,
        ask_page_tool: Callable[[Source | None], Request | None] | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"LUMICAT {__version__}{_build_suffix()}")
        fit_size(self, 1280, 860)  # 小螢幕或高 DPI（例如 150%）時縮小，不超出畫面
        self._placed = False
        self.service = service
        self.jobs = JobRunner()
        self._ask_open = ask_open or self._dialog_open
        self._ask_save = ask_save or self._dialog_save
        self._ask_draft = ask_draft or self._dialog_draft
        self._ask_image = ask_image or self._dialog_image
        self._ask_unsaved = ask_unsaved or self._dialog_unsaved
        self._ask_page_tool = ask_page_tool or self._dialog_page_tool
        self.saved_revision: int | None = None  # 開檔或最後一次另存成功時的版本（ADR-0027）
        self._saved_path: str | None = None  # 最後一次另存的檔案（頁面工具讀它，ADR-0029）
        self.document_id: str | None = None
        self.revision = 0
        self.page_count = 0
        self.page_index = 0
        self.page: dict | None = None
        # {"target_id", "text", "capability", "kind"}；
        # kind 為 cell／manual_cell 時另有 "cell"、"line_index"
        self.selection: dict | None = None
        self.cells_by_target: dict[str, tuple[dict, int]] = {}  # 文字目標 → （格, 行號）
        self.plan: dict | None = None
        self.last_error: ServiceError | None = None

        self.thumbs = QListWidget()
        self.thumbs.setObjectName("thumbs")
        self.thumbs.setIconSize(QPixmap(96, 128).size())
        self.thumbs.setMaximumWidth(150)
        self.thumbs.currentRowChanged.connect(self._thumb_selected)
        self.view = PageView()
        self.view.target_clicked.connect(self.select_target)
        # 編輯框在頁面上（ADR-0032，取代 P8 的浮動編輯面板與前後對照）
        self.panel = EditOverlay(self.view.viewport())
        self.panel.new_text.returnPressed.connect(self.apply_plan)
        self.panel.apply_button.clicked.connect(self.apply_plan)
        self.panel.close_button.clicked.connect(self.close_editor)
        self.panel.escape.activated.connect(self.close_editor)
        self.panel.new_text.textEdited.connect(self._edit_changed)
        self._anchor: QRectF | None = None
        self.image_path: str | None = None
        self._plan_key: tuple | None = None
        self.find_bar = FindBar(self)
        self.find_bar.find_button.clicked.connect(self.find)
        self.find_bar.find_text.returnPressed.connect(self.find)
        self.panel.image_button.clicked.connect(self.replace_image_dialog)
        for bar in (self.view.horizontalScrollBar(), self.view.verticalScrollBar()):
            bar.valueChanged.connect(self._place_editor)  # 捲動、縮放時編輯框跟著選取的內容
        self.panel.line_choice.currentIndexChanged.connect(self._line_chosen)
        self.view.box_selected.connect(self.select_box)
        self.view.zoom_changed.connect(self._zoomed)
        self.view.zoom_changed.connect(self._place_editor)
        self._sharp_timer = QTimer(self)
        self._sharp_timer.setSingleShot(True)
        self._sharp_timer.setInterval(300)
        self._sharp_timer.timeout.connect(self._render_sharper)
        self._sharp_dpi = PAGE_DPI
        self.notice = NoticeLabel("")
        self.notice.setObjectName("notice")
        self.notice.setWordWrap(True)
        self.notice.setVisible(False)
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.addWidget(self.notice)
        center_layout.addWidget(self.view)
        splitter = QSplitter()
        for widget in (self.thumbs, center):
            splitter.addWidget(widget)
        self.setCentralWidget(splitter)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)
        self.jobs.busy_changed.connect(self._busy)

        toolbar = self.addToolBar("檔案")
        self.actions: dict[str, QAction] = {}
        for name, text, key, slot in (
            ("new_window", "開新視窗", QKeySequence.StandardKey.New, self.new_window),
            ("open", "開啟", QKeySequence.StandardKey.Open, self.open_dialog),
            ("save", "另存新檔", QKeySequence.StandardKey.SaveAs, self.save_dialog),
            ("undo", "復原", QKeySequence.StandardKey.Undo, self.undo),
            ("redo", "重做", QKeySequence.StandardKey.Redo, self.redo),
            ("manual_cell", "手動選格", QKeySequence(), self._toggle_box_mode),
            (
                "zoom_out",
                "縮小",
                QKeySequence.StandardKey.ZoomOut,
                lambda: self.view.set_zoom(self.view.zoom / ZOOM_STEP),
            ),
            (
                "zoom_in",
                "放大",
                QKeySequence.StandardKey.ZoomIn,
                lambda: self.view.set_zoom(self.view.zoom * ZOOM_STEP),
            ),
            ("zoom_reset", "實際大小", QKeySequence("Ctrl+0"), lambda: self.view.set_zoom(1.0)),
            ("fit_width", "符合寬度", QKeySequence(), self.view.fit_width),
            ("find", "尋找…", QKeySequence.StandardKey.Find, self.show_find),
            ("cancel", "取消", QKeySequence(Qt.Key.Key_Escape), self.cancel),
            ("about", "關於 LUMICAT", QKeySequence(), self.show_about),
            ("page_tools", "頁面管理…", QKeySequence(), self.page_tools),
            ("text_extract", "文字擷取…", QKeySequence(), self.text_extract),
        ):
            action = QAction(text, self)
            if isinstance(
                key, QKeySequence.StandardKey
            ):  # 平台的全部標準鍵（重做另有 Ctrl+Shift+Z；P4 U12）
                action.setShortcuts(QKeySequence.keyBindings(key))
            else:
                action.setShortcut(key)
            keys = "、".join(s.toString(QKeySequence.SequenceFormat.NativeText)
                            for s in action.shortcuts() if not s.isEmpty())  # fmt: skip
            action.setToolTip(f"{text}（{keys}）" if keys else text)  # 工具列提示顯示快捷鍵（U12）
            action.triggered.connect(slot)
            action.setIcon(theme.icon(name))
            self.actions[name] = action
        # 工具列分組：檔案（開啟、另存、頁面管理、文字擷取，ADR-0033）｜編輯｜檢視；
        # 尋找、關於只放在選單
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.setMovable(False)
        groups = (["open", "save", "page_tools", "text_extract"], ["undo", "redo", "manual_cell"],
                  ["zoom_out", "zoom_in", "zoom_reset", "fit_width", "cancel"])  # fmt: skip
        for index, names in enumerate(groups):
            if index:
                toolbar.addSeparator()
            for name in names:
                toolbar.addAction(self.actions[name])
        for name, style in (("save", "primary"), ("page_tools", "outline"),
                            ("text_extract", "outline")):  # fmt: skip
            button = toolbar.widgetForAction(self.actions[name])
            if isinstance(button, QToolButton):
                button.setObjectName(style)
        for name in ("undo", "redo", "zoom_out", "zoom_in"):  # 只顯示圖示，提示含快捷鍵（U12）
            button = toolbar.widgetForAction(self.actions[name])
            if isinstance(button, QToolButton):
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        menus = (
            ("檔案", ["new_window", None, "open", "save"]),
            ("編輯", ["undo", "redo", None, "find", "manual_cell", "cancel"]),
            ("檢視", ["zoom_in", "zoom_out", "zoom_reset", "fit_width"]),
            ("工具", ["page_tools", "text_extract"]),
            ("說明", ["about"]),
        )
        for title, names in menus:
            menu = self.menuBar().addMenu(title)
            for name in names:
                if name is None:
                    menu.addSeparator()
                else:
                    menu.addAction(self.actions[name])
        self._refresh_actions()

    # --- 狀態 ----------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self.jobs.busy

    def _busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self._refresh_actions()

    def _update_title(self) -> None:
        base = f"LUMICAT {__version__}{_build_suffix()}"
        if self.document_id is None or self.service is None:
            self.setWindowTitle(base)
            return
        # 另存後顯示新檔名（實機回報：另存後標題仍是舊檔名）；「 *」表示新檔之後又有未另存的修改
        try:
            path = self._saved_path or self.service.document_path(self.document_id)
        except ServiceError:
            path = ""
        name = os.path.basename(path)
        mark = " *" if self.unsaved else ""
        # 視窗標題顯示目前檔名，多個視窗時（工作列、Alt+Tab）以資區別（ADR-0030）
        self.setWindowTitle(f"{name}{mark} — {base}")

    def new_window(self) -> None:
        """另開一個 LUMICAT（各自一個行程與 worker，ADR-0030）。"""
        try:
            spawn_window()
        except OSError:
            self._status("無法開啟新視窗")
            return
        self._status("已開啟新視窗")

    def _refresh_actions(self) -> None:
        self._update_title()
        busy, opened = self.jobs.busy, self.document_id is not None
        history = (self.service.history(self.document_id)
                   if opened and self.service else {"undo": 0, "redo": 0})  # fmt: skip
        self.actions["open"].setEnabled(not busy)
        self.actions["save"].setEnabled(opened and not busy)
        self.actions["undo"].setEnabled(opened and not busy and history["undo"] > 0)
        self.actions["redo"].setEnabled(opened and not busy and history["redo"] > 0)
        self.actions["cancel"].setEnabled(busy)
        self.actions["manual_cell"].setCheckable(True)
        self.actions["manual_cell"].setEnabled(opened and not busy)
        editable = (self.selection is not None and not busy
                    and self.selection["capability"]["status"] == "support")  # fmt: skip
        is_image = self.selection is not None and self.selection.get("kind") == "image"
        self.panel.new_text.setEnabled(editable and not is_image)
        self.panel.image_button.setEnabled(editable and is_image)
        self.panel.apply_button.setEnabled(editable and (not is_image or bool(self.image_path)))
        pending = self.plan is not None and self.plan.get("ready") and self._plan_key is not None
        self.panel.apply_button.setText("確認套用" if pending else "套用")
        # 處理中 Esc 交給「取消」：兩個 Esc 快速鍵同時啟用時 Qt 判定衝突、都不執行（獨立核對 P11）
        self.panel.escape.setEnabled(not busy)
        self.find_bar.find_button.setEnabled(opened and not busy)
        self.actions["page_tools"].setEnabled(not busy and self.service is not None)
        self.actions["text_extract"].setEnabled(opened and not busy)
        self.actions["find"].setEnabled(opened)

    def _status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _fail(self, error: ServiceError) -> None:
        self.last_error = error
        self._status(reason_text(error.code))
        self.panel.set_info(reason_text(error.code))
        self._refresh_actions()
        self._focus_editor()

    def _run(self, func, on_done) -> None:
        self.last_error = None
        self.jobs.submit(func, on_done, self._fail)
        self._refresh_actions()

    # --- 開檔與頁面 ------------------------------------------------------
    def open_dialog(self) -> None:
        path = self._ask_open()
        if path:
            self.open_path(path)

    @property
    def unsaved(self) -> bool:
        """有尚未另存的修改（ADR-0027）：版本與開檔或上次另存時不同；改了又全部復原也算。"""
        return self.document_id is not None and self.revision != self.saved_revision

    def _confirm_leave(self, then: Callable[[], None]) -> bool:
        """關閉或換檔前詢問「另存／不儲存／取消」（ADR-0027）。回傳 True 表示可以立即繼續；
        選另存時另存成功後才呼叫 then，取消、另存對話框取消或另存失敗則停在原文件。"""
        if not self.unsaved or self.busy:
            return True
        answer = self._ask_unsaved()
        if answer == "discard":
            return True
        if answer == "save":
            path = self._ask_save()
            if path:
                self.save_as(path, then)
        return False

    def open_path(self, path: str) -> None:
        if not self._confirm_leave(lambda: self.open_path(path)):
            return
        if self.document_id is not None:
            old, self.document_id = self.document_id, None
            self._run(lambda: self.service.close_document(old), lambda _: None)
        self._status("開啟中…")
        self._run(lambda: self.service.open_document(path), self._opened)

    def _opened(self, result: dict) -> None:
        self.document_id = result["document_id"]
        self.revision = result["revision"]
        self.saved_revision = result["revision"]
        self._saved_path: str | None = None
        self.page_count = result["page_count"]
        flags = result["document_flags"]
        self.thumbs.clear()
        self.view.clear()  # 前一份文件的頁面與目標框（P4 U13）
        self.page_index, self.page, self.cells_by_target = 0, None, {}
        self._clear_selection()
        if flags["status"] != "support":
            self.notice.setText("此檔不能編輯：" + reasons_text(flags["reasons"]))
        else:
            self.notice.setText("")
        self._status(f"已開啟，共 {self.page_count} 頁")
        if self.page_count:
            self.load_page(0)
            self._load_thumbs()

    def _load_thumbs(self) -> None:
        doc = self.document_id
        for index in range(min(self.page_count, MAX_THUMBS)):
            item = QListWidgetItem(f"{index + 1}")
            self.thumbs.addItem(item)
            self._run(lambda i=index: self.service.render_page(doc, i, THUMB_DPI),
                      lambda rendered, it=item: it.setIcon(QIcon(_pixmap(rendered))))  # fmt: skip

    def _thumb_selected(self, row: int) -> None:
        if row >= 0 and row != self.page_index and self.document_id is not None:
            self.load_page(row)

    def load_page(self, index: int) -> None:
        doc, revision = self.document_id, self.revision

        def work():
            page = self.service.inspect_page(doc, index, revision)
            return page, self.service.render_page(doc, index, PAGE_DPI)

        self._run(work, lambda result: self._page_loaded(index, *result))

    def _page_loaded(self, index: int, page: dict, rendered: dict) -> None:
        self.page_index, self.page = index, page
        self.cells_by_target = {
            target_id: (cell, i)
            for cell in page.get("cell_targets", [])
            for i, line in enumerate(cell["lines"])
            for target_id in line["target_ids"]
        }
        self.view.show_page(rendered, page)
        self._sharp_dpi = PAGE_DPI
        if self.view.zoom > 1:
            self._sharp_timer.start()
        notes = [NOTICES[n] for n in page.get("notices", []) if n in NOTICES]
        reasons = page["capabilities"]["reasons"]
        if reasons:
            notes.append("此頁：" + reasons_text(reasons))
        if notes or self.notice.text().startswith("此頁") or not self.notice.text():
            self.notice.setText("\n".join(notes))
        self._clear_selection()

    # --- 選取、編輯框、套用（ADR-0032） ---------------------------------
    def _clear_selection(self) -> None:
        self.selection = None
        self.plan = None
        self._plan_key = None
        self.image_path = None
        self._anchor = None
        self.panel.hide()
        self.panel.selected.setText("")
        self.panel.line_choice.setVisible(False)
        self.panel.new_text.clear()
        self.panel.image_label.clear()
        self.panel.set_info("")
        self.view.highlight(None)
        self._refresh_actions()
        if self.view.zoom > 1 and self.page is not None:
            self._sharp_timer.start()  # 編輯中延後的高解析度渲染

    def close_editor(self) -> None:
        """Esc 或「×」：關閉編輯框，不修改；焦點回到頁面。"""
        if self.busy:
            return
        self._clear_selection()
        self.view.setFocus()

    def _open_editor(self, anchor: QRectF | None) -> None:
        self._anchor = anchor
        self.plan, self._plan_key = None, None
        self.panel.show()
        self.panel.raise_()
        self._place_editor()
        self._refresh_actions()
        self._focus_editor(select=True)

    def _focus_editor(self, select: bool = False) -> None:
        """select=True 只在剛開啟時全選原文字；
        失敗或提醒後回到輸入欄不全選，避免下一個按鍵覆蓋整段。"""
        if not self.panel.isVisible():
            return
        if self.panel.new_text.isVisible() and self.panel.new_text.isEnabled():
            self.panel.new_text.setFocus()
            if select:
                self.panel.new_text.selectAll()
        elif self.panel.image_button.isVisible() and self.panel.image_button.isEnabled():
            self.panel.image_button.setFocus()
        else:
            self.panel.close_button.setFocus()  # 不能改：焦點在框內，Esc 可關閉

    def resizeEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        super().resizeEvent(event)
        QTimer.singleShot(0, self._place_editor)  # 視窗大小改變後重新放置編輯框

    def _place_editor(self, *_args) -> None:
        """編輯框放在選取內容的正下方（下方放不下改放上方），不超出頁面可視範圍。"""
        if not self.panel.isVisible():
            return
        viewport = self.view.viewport().rect()
        width = max(240, min(OVERLAY_WIDTH, viewport.width() - 16))
        self.panel.setFixedWidth(width)
        self.panel.adjustSize()
        height = self.panel.height()
        if self._anchor is None:
            x, y = 8, 8
        else:
            rect = self.view.mapFromScene(self._anchor).boundingRect()
            x = rect.left()
            y = rect.bottom() + 6
            if y + height > viewport.bottom() and rect.top() - 6 - height >= 0:
                y = rect.top() - 6 - height
        x = max(8, min(x, viewport.right() - width - 8))
        y = max(8, min(y, viewport.bottom() - height - 8))
        self.panel.move(x, y)

    def _edit_changed(self, *_args) -> None:
        """提醒顯示後又改了內容：回到一般「套用」（重新規劃，不沿用舊計畫）。"""
        if self._plan_key is not None:
            self.plan, self._plan_key = None, None
            self.panel.set_info("")
            self._refresh_actions()

    def select_target(self, target: dict) -> None:
        if self.busy:
            return
        kind = target.get("kind", "text")
        if kind == "text" and target["target_id"] in self.cells_by_target:
            cell, line_index = self.cells_by_target[target["target_id"]]
            self._select_cell(cell, line_index, "cell", target["target_id"])
            return
        self.panel.line_choice.setVisible(False)
        text = target.get("text", "") if kind == "text" else ""
        self.selection = {"target_id": target["target_id"], "text": text,
                          "capability": target["capability"], "kind": kind}  # fmt: skip
        self.image_path = None
        self.panel.image_label.clear()
        self.panel.set_image_mode(kind == "image")
        self.view.highlight(target["target_id"])
        if kind == "image":
            x0, y0, x1, y1 = target["bbox"]
            self.panel.selected.setText(f"圖片（{x1 - x0:.0f} × {y1 - y0:.0f} pt）")
            self.panel.new_text.clear()
        else:
            self.panel.selected.setText(_shown(target.get("display_text", text), text))
            # 不能改的目標不預填（對應不到 Unicode 的字不能當新文字的起點；P8 實機發現）
            supported = target["capability"]["status"] == "support"
            self.panel.new_text.setText(text if supported else "")
        if target["capability"]["status"] == "support":
            self.panel.set_info("")
        else:
            self.panel.set_info("無法編輯：" + reasons_text(target["capability"]["reasons"]))
        self._open_editor(self.view.target_rect(target["target_id"]))

    def _select_cell(self, cell: dict, line_index: int, kind: str, highlight: str | None) -> None:
        """儲存格選取（ADR-0023）：顯示格位置與行；能力判定不支援時顯示原因、不能套用。"""
        lines = cell["lines"]
        text = lines[line_index]["text"] if lines else ""
        # 格本身支援時，以所選這一行的判定為準（行內文字無法對應 Unicode 等；P8 實機發現）
        capability = cell["capability"]
        if capability["status"] == "support" and lines:
            capability = lines[line_index]["capability"]
        self.selection = {"target_id": cell.get("cell_id"), "text": text, "kind": kind,
                          "capability": capability, "cell": cell,
                          "line_index": line_index}  # fmt: skip
        self.image_path = None
        self.panel.set_image_mode(False)
        self.view.highlight(highlight)
        where = ("手動選格" if kind == "manual_cell"
                 else f"表格第 {cell['row'] + 1} 列第 {cell['col'] + 1} 欄")  # fmt: skip
        shown = _shown(lines[line_index].get("display_text", text), text) if lines else ""
        self.panel.selected.setText(f"{where}：{shown}" if text else where)
        choice = self.panel.line_choice
        choice.blockSignals(True)
        choice.clear()
        choice.addItems([f"第 {i + 1} 行：{_shown(line.get('display_text', line['text']))}"
                         for i, line in enumerate(lines)])  # fmt: skip
        choice.setCurrentIndex(line_index if lines else -1)
        choice.blockSignals(False)
        choice.setVisible(len(lines) > 1)
        self.panel.new_text.setText(text if capability["status"] == "support" else "")
        if capability["status"] == "support":
            self.panel.set_info("")
        else:
            self.panel.set_info("無法編輯：" + reasons_text(capability["reasons"]))
        box = cell.get("cell_box") or cell.get("bbox")
        anchor = self.view.target_rect(highlight) if highlight else None
        self._open_editor(anchor or (self.view.page_rect(box) if box else None))

    def _line_chosen(self, index: int) -> None:
        if self.selection is not None and "cell" in self.selection and index >= 0:
            self._select_cell(self.selection["cell"], index, self.selection["kind"], None)

    def _zoomed(self, zoom: float) -> None:
        self._status(f"縮放 {zoom:.0%}")
        self._sharp_timer.start()  # 停止縮放 300 ms 後才重新渲染

    def _render_sharper(self) -> None:
        """放大後以較高 DPI 重新渲染目前頁（上限 MAX_RENDER_DPI）；換頁或文件已變時丟棄結果。"""
        if self.document_id is None or self.page is None or self.busy:
            return
        if self.panel.isVisible():  # 編輯中不跑背景工作（會停用輸入欄、打斷組字）；關閉後再渲染
            return
        dpi = min(MAX_RENDER_DPI, round(PAGE_DPI * self.view.zoom))
        if dpi <= self._sharp_dpi:
            return
        doc, index, revision = self.document_id, self.page_index, self.revision

        def done(rendered: dict) -> None:
            if (doc, index, revision) == (self.document_id, self.page_index, self.revision):
                self.view.set_sharper(rendered, dpi)
                self._sharp_dpi = dpi

        self._run(lambda: self.service.render_page(doc, index, dpi), done)

    def _toggle_box_mode(self) -> None:
        self.view.box_mode = self.actions["manual_cell"].isChecked()
        self._status("在頁面上拉出儲存格範圍" if self.view.box_mode else "")

    def select_box(self, box: list) -> None:
        """手動選格：框選範圍交 worker 判定（不能有線穿過、不能跨格、文字須完整在框內）。"""
        if self.document_id is None or self.busy:
            return
        doc, revision, index = self.document_id, self.revision, self.page_index

        def done(cell: dict) -> None:
            self.actions["manual_cell"].setChecked(False)
            self.view.box_mode = False
            self._select_cell({**cell, "cell_box": box}, 0, "manual_cell", None)

        self._run(lambda: self.service.assess_cell_box(doc, index, box, revision), done)

    def show_find(self) -> None:
        self.find_bar.show()
        self.find_bar.raise_()
        self.find_bar.activateWindow()
        self.find_bar.find_text.setFocus()
        self.find_bar.find_text.selectAll()

    def find(self) -> None:
        text = self.find_bar.find_text.text()
        if not text or self.document_id is None:
            return
        doc, index = self.document_id, self.page_index

        def found(span_id: str) -> None:
            self.select_target({"target_id": span_id, "text": text,
                                "capability": {"status": "support", "reasons": []}})  # fmt: skip

        self._run(lambda: self.service.find_text(doc, index, text), found)

    def _edit_key(self) -> tuple:
        """這次要套用的內容；提醒顯示後若內容變了就重新規劃。"""
        selection = self.selection or {}
        if selection.get("kind") == "image":
            return ("image", self.image_path)
        return (selection.get("kind"), selection.get("line_index"), self.panel.new_text.text())

    def apply_plan(self) -> None:
        """「套用」或 Enter：規劃後直接寫回；計畫有提醒時先在編輯框顯示，再按一次「確認套用」才寫回
        （ADR-0032 §3）。只取已確認的文字：組字中（含組字中按 Enter）不送出（G4-02、P4 U7）。"""
        selection = self.selection
        if (selection is None or self.busy or self.panel.new_text.composing
                or selection["capability"]["status"] != "support"):  # fmt: skip
            return
        key = self._edit_key()
        if self.plan is not None and self.plan.get("ready") and self._plan_key == key:
            self._commit(self.plan["plan_id"])
            return
        if selection["kind"] == "image" and not self.image_path:
            return
        doc, revision, new_text, path = (self.document_id, self.revision,
                                         self.panel.new_text.text(), self.image_path)  # fmt: skip

        def work():
            if selection["kind"] in ("cell", "manual_cell"):
                cell = selection["cell"]
                return self.service.plan_cell_edit(
                    doc, cell.get("cell_id"), new_text, selection["line_index"], "prefer_a",
                    revision, cell_box=cell.get("cell_box"),
                    page_index=self.page_index if cell.get("cell_box") else None,
                )  # fmt: skip
            if selection["kind"] == "image":
                asset = self.service.register_image(doc, path)
                return self.service.plan_image_edit(doc, selection["target_id"],
                                                    asset["asset_id"], revision)  # fmt: skip
            return self.service.plan_text_edit(doc, selection["target_id"], new_text,
                                               "prefer_a", revision)  # fmt: skip

        self._status("套用中…")
        self._run(work, lambda plan: self._planned(plan, key))

    def replace_image_dialog(self) -> None:
        """選擇新圖片（ADR-0022）；按「套用」才登記、規劃與寫回。"""
        if self.selection is None or self.selection.get("kind") != "image" or self.busy:
            return
        path = self._ask_image()
        if not path:
            return
        self.image_path = path
        self.panel.image_label.setText(os.path.basename(path))  # 只顯示檔名
        self._edit_changed()
        self._refresh_actions()
        self.panel.apply_button.setFocus()

    def _planned(self, plan: dict, key: tuple) -> None:
        self.plan = plan
        if not plan["ready"]:
            self._plan_key = None
            self.panel.set_info("無法修改：" + reasons_text(plan["unsupported_reasons"]))
            self._status("無法修改")
            self._refresh_actions()
            self._focus_editor()
            return
        notes = [w for w in plan.get("warnings", []) if not w.startswith(INFO_ONLY_WARNINGS)]
        if not notes:
            self._commit(plan["plan_id"])
            return
        self._plan_key = key
        self.panel.set_info("請確認：\n" + "\n".join(f"・{n}" for n in notes))
        self._status("有提醒，確認後再按「確認套用」")
        self._refresh_actions()
        self._place_editor()
        self.panel.apply_button.setFocus()

    def _commit(self, plan_id: str) -> None:
        doc, revision = self.document_id, self.revision
        self._status("套用中…")
        self._run(lambda: self.service.apply_edit(doc, plan_id, revision), self._changed)

    def _changed(self, result: dict) -> None:
        self.revision = result["new_revision"]
        warnings = result.get("warnings") or []
        self._status("；".join(["已更新", *warnings]))
        self.load_page(self.page_index)
        self.view.setFocus()  # 焦點回到頁面：之後的 Ctrl+Z 是文件復原，不是輸入欄的復原（P4 U12）

    def undo(self) -> None:
        if self.document_id is not None and not self.busy:
            doc, revision = self.document_id, self.revision
            self._run(lambda: self.service.undo(doc, revision), self._changed)

    def redo(self) -> None:
        if self.document_id is not None and not self.busy:
            doc, revision = self.document_id, self.revision
            self._run(lambda: self.service.redo(doc, revision), self._changed)

    def cancel(self) -> None:
        """終止進行中的 worker 請求；未完成的操作不提交（G4-04）。"""
        if self.busy and self.service is not None:
            self.service.cancel()

    # --- 另存 ------------------------------------------------------------
    def save_dialog(self) -> None:
        path = self._ask_save()
        if path:
            self.save_as(path)

    def save_as(self, path: str, then: Callable[[], None] | None = None) -> None:
        """另存；then：另存成功後要繼續的動作（關閉或換檔，ADR-0027）。"""
        if self.document_id is None or self.busy:
            return
        doc, revision = self.document_id, self.revision

        def work():
            token = self.service.destination_token(path, overwrite=os.path.exists(path))
            return self.service.export_document(doc, token, revision)

        def done(result: dict) -> None:
            self._saved(result, doc, revision, path)
            if then is not None:
                then()

        self._status("另存中…")
        self._run(work, done)

    def _saved(self, result: dict, doc: str, revision: int, path: str | None = None) -> None:
        if doc == self.document_id:
            self.saved_revision = revision
            self._saved_path = path
            self._refresh_actions()  # 標題改為新檔名
        warnings = result.get("warnings") or []
        self._status("；".join(["已另存", *warnings]))

    # --- 頁面工具（ADR-0029） ------------------------------------------------
    def page_tools(self) -> None:
        """讀磁碟上的檔案：目前文件有未另存修改時先詢問（ADR-0027）。"""
        if self.busy or self.service is None:
            return
        if not self._confirm_leave(self.page_tools):
            return
        current = None
        if self.document_id is not None:
            # 剛另存且之後沒再改：用另存的新檔（含修改）；否則用磁碟上的原檔（未另存的修改不含在內）
            path = (self._saved_path if self._saved_path and self.saved_revision == self.revision
                    else self.service.document_path(self.document_id))  # fmt: skip
            current = Source(path, self.page_count)
        request = self._ask_page_tool(current)
        if request is not None:
            self.run_page_tool(request)

    def run_page_tool(self, request: Request) -> None:
        path = self._ask_save()
        if not path or self.busy:
            return

        def work():
            token = self.service.destination_token(path, overwrite=os.path.exists(path))
            return self.service.compose_pages(request.sources, request.plan, token)

        def done(result: dict) -> None:
            warnings = result.get("warnings") or []
            self._status("；".join([f"已另存新檔（{len(request.plan)} 頁）", *warnings]))
            if request.open_after:
                self.open_path(path)

        self._status("處理頁面中…")
        self._run(work, done)

    # --- 文字擷取（ADR-0033） ------------------------------------------------
    def text_extract(self) -> None:
        """目前文件（含未另存的修改）指定頁的文字；預設目前頁。
        對話框開啟時沒有其他工作，同步向 worker 取。"""
        if self.busy or self.document_id is None or self.service is None:
            return
        doc = self.document_id

        def extract(page_index: int) -> dict:
            try:
                return self.service.extract_text(doc, page_index)
            except ServiceError as exc:
                raise ValueError(reason_text(exc.code)) from None

        def ocr(page_index: int) -> dict:
            try:
                return self.service.ocr_page(doc, page_index)
            except ServiceError as exc:
                raise ValueError(reason_text(exc.code)) from None

        # 作業系統內建 OCR 只在 Windows、macOS（ADR-0035）
        ocr_call = ocr if sys.platform in ("win32", "darwin") else None
        dialog = TextExtractDialog(self.page_count, self.page_index, extract,
                                   self._dialog_save_text, self, ocr_call)  # fmt: skip
        self._exec_dialog(dialog)

    def _exec_dialog(self, dialog: QDialog) -> None:
        dialog.exec()

    def _dialog_save_text(self) -> str | None:
        path, _ = QFileDialog.getSaveFileName(self, "另存文字檔", "", "文字檔 (*.txt)")
        return path or None

    def probe(self, path: str) -> Source:
        """頁面管理選檔：取頁數與能力判定（UI 執行緒同步呼叫；對話框開啟時沒有其他工作）。"""
        try:
            result = self.service.probe_document(path)
        except ServiceError as exc:
            raise ValueError(reason_text(exc.code)) from None
        if result["reasons"]:
            raise ValueError(probe_error_text(result["reasons"]))
        return Source(path, result["page_count"])

    def _dialog_page_tool(self, current: Source | None) -> Request | None:
        dialog = PageToolsDialog(current, self.probe, self._dialog_open_many, self._dialog_open,
                                 self)  # fmt: skip
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.request
        return None

    def _dialog_open_many(self) -> list[str]:
        paths, _ = QFileDialog.getOpenFileNames(self, "加入 PDF", "", "PDF (*.pdf)")
        return list(paths)

    # --- 復原草稿 ----------------------------------------------------------
    def offer_drafts(self) -> None:
        """使用者選擇後才復原（ADR-0020 §5）。視窗關閉中不再詢問（P4 U11）。"""
        if self.service is None or self.service.drafts is None or self.jobs.closed:
            return
        try:
            drafts = self.service.list_drafts()
        except ServiceError as exc:
            self._fail(exc)
            return
        if not drafts:
            return
        choice = self._ask_draft(drafts)
        if choice is None:
            return
        action, draft_id = choice
        if action == "discard":  # 捨棄後再列出其餘草稿
            self._run(lambda: self.service.discard_draft(draft_id), lambda _: self.offer_drafts())
        elif action == "recover":  # 一次只開一份文件；其餘草稿保留，下次啟動再列出
            self._run(lambda: self.service.recover_draft(draft_id), self._recovered)

    def _recovered(self, result: dict) -> None:
        flags = result.get("document_flags") or {"status": "support", "reasons": []}
        self._opened({**result, "document_flags": flags})
        self.saved_revision = None  # 復原的修改尚未另存（ADR-0027）

    # --- 對話框（測試以參數替換） -------------------------------------------
    def _dialog_open(self) -> str | None:
        path, _ = QFileDialog.getOpenFileName(self, "開啟 PDF", "", "PDF (*.pdf)")
        return path or None

    def _dialog_save(self) -> str | None:
        path, _ = QFileDialog.getSaveFileName(self, "另存新檔", "", "PDF (*.pdf)")
        return path or None

    def _dialog_image(self) -> str | None:
        path, _ = QFileDialog.getOpenFileName(self, "選擇新圖片", "", "圖片 (*.png *.jpg *.jpeg)")
        return path or None

    def show_about(self) -> None:
        commit = _build_suffix().strip("（）")
        QMessageBox.about(self, "關於 LUMICAT", about_text(commit))

    def _dialog_unsaved(self) -> str:
        """回傳 "save"、"discard" 或 "cancel"（ADR-0027）；不顯示路徑。"""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("尚未另存")
        box.setText("這份文件有尚未另存的修改，要先另存嗎？")
        save = box.addButton("另存…", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("不儲存", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.setEscapeButton(cancel)
        box.exec()
        clicked = box.clickedButton()
        return "save" if clicked is save else "discard" if clicked is discard else "cancel"

    def _dialog_draft(self, drafts: list[dict]) -> tuple[str, str] | None:
        dialog = DraftDialog(drafts, self)
        dialog.exec()
        return dialog.choice

    def showEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        super().showEvent(event)
        # 只在第一次顯示時調整；從最小化還原時不動使用者放的位置（P12 獨立核對）
        if not self._placed and not self.isMaximized():
            keep_inside(self)  # 含標題列與狀態列都在螢幕可用範圍內
        self._placed = True

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        """正常關閉：取消進行中的請求、收下已完成的結果，再關閉文件並刪除草稿
        （ADR-0020 §5，P4 U11）。有未另存的修改時先詢問（ADR-0027）；
        進行中的工作照 P4 U11 處理，不詢問。"""
        if not self._confirm_leave(self.close):
            event.ignore()
            return
        service = self.service
        self.jobs.shutdown(service.cancel if service is not None else None,
                           service.close if service is not None else None)  # fmt: skip
        if self.document_id is not None:
            self.service.close_document(self.document_id)
            self.document_id = None
        super().closeEvent(event)


def _shown(text: str, original: str | None = None) -> str:
    """顯示用：對應不到 Unicode 的字（worker 以 U+FFFD 表示）改為「□」，不顯示成亂碼。
    給 original 且 text 與它不同時，text 是 MuPDF 擷取的顯示文字，加註僅供參考。"""
    if original is not None and text != original:
        return text.replace("\ufffd", "□") + "（MuPDF 擷取，僅供參考）"
    return text.replace("\ufffd", "□")


def _self_command() -> list[str]:
    """重新啟動本程式的指令：打包後為執行檔本身，開發環境為 `python -m lumicat`。"""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "lumicat"]


def spawn_window() -> None:
    """開新視窗：另啟一個獨立的 LUMICAT 行程（不帶任何參數或檔案路徑）。"""
    subprocess.Popen(  # noqa: S603 — 固定指令，不經 shell
        _self_command(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def prepare_storage():
    """啟動時的本機儲存接線（ADR-0021 §2 例外：不經 DocumentService）：建立復原草稿區、
    設定暫存檔紀錄位置並清除上次中斷留下的另存暫存檔（P3 U9）。回傳 DraftStore，不可用時回 None。"""
    from lumicat.core.drafts import DraftStore, default_dir
    from lumicat.export import transaction

    try:
        drafts = DraftStore()  # 同時建立本機資料目錄
    except Exception:  # noqa: BLE001 — 草稿區不可用時照常編輯，只是不保存草稿
        drafts = None
    transaction.registry = str(default_dir().parent / "pending-temps.json")
    transaction.cleanup_recorded()
    return drafts


def startup(window: MainWindow, path: str | None) -> None:
    """啟動後的第一個動作：有指定檔案（右鍵「用 LUMICAT 開啟」，ADR-0031）就開該檔，
    此時不詢問復原草稿（留到一般啟動時再列出）；否則詢問復原草稿。"""
    if path:
        window.open_path(path)
    else:
        window.offer_drafts()


def run(*, smoke: bool = False, versions: dict[str, str] | None = None,
        path: str | None = None) -> int:  # fmt: skip
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("LUMICAT")
    app.setWindowIcon(app_icon())
    theme.apply(app)
    if smoke:
        window = MainWindow()
        window.show()
        QTimer.singleShot(0, app.quit)
        code = app.exec()
        if code == 0:
            print(SMOKE_MARKER, json.dumps(versions or {}, ensure_ascii=False), flush=True)
        return code
    with DocumentService(drafts=prepare_storage()) as service:
        window = MainWindow(service)
        window.show()
        QTimer.singleShot(0, lambda: startup(window, path))
        return app.exec()
