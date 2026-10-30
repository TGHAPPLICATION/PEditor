"""桌面主視窗（P4、ADR-0021）：開檔、縮圖、預覽、點選文字、替換、前後對照、undo／redo、另存、進度與取消。

UI 只呼叫 DocumentService 的公開 API，不匯入 PDF 程式庫、不組 PDF 指令（spec §9、G1-01）。
所有 DocumentService 呼叫經 JobRunner 在背景執行緒進行，主執行緒不等待 worker（G4-06）。
"""

from __future__ import annotations

import base64
import json
import os
import sys
from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from peditor import __version__
from peditor.core.geometry import PageGeometry, bbox_of
from peditor.core.service import DocumentService, ServiceError
from peditor.ui.jobs import JobRunner
from peditor.ui.messages import NOTICES, reason_text, reasons_text

SMOKE_MARKER = "PEDITOR_SMOKE_OK"
PAGE_DPI = 100
THUMB_DPI = 24
MAX_THUMBS = 200


def _pixmap(rendered: dict) -> QPixmap:
    pix = QPixmap()
    pix.loadFromData(base64.b64decode(rendered["png_base64"]), "PNG")
    return pix


class PageView(QGraphicsView):
    """頁面圖與文字目標框。點選以 bbox 判定命中，回傳的是 target；
    內容由 target_id 定位，不以 bbox 定位（ADR-0021 §2）。"""

    target_clicked = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self._geometry: PageGeometry | None = None
        self._targets: list[dict] = []
        self._selected: QGraphicsRectItem | None = None

    def show_page(self, rendered: dict, page: dict) -> None:
        scene = self.scene()
        scene.clear()
        self._selected = None
        scene.addItem(QGraphicsPixmapItem(_pixmap(rendered)))
        geom = page["page_geometry"]
        self._geometry = PageGeometry(tuple(geom["cropbox"]), geom["rotation"])
        self._targets = [t for t in page["text_targets"] if t.get("bbox")]
        to_view = self._geometry.page_to_view(PAGE_DPI / 72)
        for target in self._targets:
            x0, y0, x1, y1 = bbox_of(to_view, tuple(target["bbox"]))
            color = (
                QColor(0, 120, 215)
                if target["capability"]["status"] == "support"
                else QColor(160, 160, 160)
            )
            item = scene.addRect(QRectF(x0, y0, x1 - x0, y1 - y0), QPen(color, 1))
            item.setData(0, target["target_id"])
        scene.setSceneRect(QRectF(0, 0, rendered["width"], rendered["height"]))

    def target_rect(self, target_id: str) -> QRectF | None:
        for item in self.scene().items():
            if isinstance(item, QGraphicsRectItem) and item.data(0) == target_id:
                return item.sceneBoundingRect()
        return None

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
        target = self.target_at(pos.x(), pos.y())
        if target is not None:
            self.target_clicked.emit(target)
        super().mousePressEvent(event)


class TextInput(QLineEdit):
    """記錄是否在 IME 組字中：Qt 不保證組字中按 Enter 不發出 returnPressed（P4 U7）。"""

    composing = False

    def inputMethodEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        self.composing = bool(event.preeditString())
        super().inputMethodEvent(event)


class EditPanel(QWidget):
    """側欄：選取內容、新文字輸入、計畫資訊、前後對照。
    只在按「預覽」或 Enter 時規劃（IME 組字中不送出）。"""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.selected = QLabel("尚未選取文字")
        self.selected.setObjectName("selected")
        self.selected.setWordWrap(True)
        self.new_text = TextInput()
        self.new_text.setObjectName("new_text")
        self.new_text.setPlaceholderText("輸入新文字")
        self.preview_button = QPushButton("預覽")
        self.preview_button.setObjectName("preview")
        self.apply_button = QPushButton("套用")
        self.apply_button.setObjectName("apply")
        self.info = QLabel("")
        self.info.setObjectName("info")
        self.info.setWordWrap(True)
        self.before = QLabel()
        self.before.setObjectName("before")
        self.after = QLabel()
        self.after.setObjectName("after")
        self.find_text = QLineEdit()
        self.find_text.setObjectName("find_text")
        self.find_text.setPlaceholderText("尋找文字（可跨段落選取）")
        self.find_button = QPushButton("尋找")
        self.find_button.setObjectName("find")
        for widget in (QLabel("選取的文字"), self.selected, QLabel("新文字"), self.new_text,
                       self.preview_button, self.info, QLabel("修改前"), self.before,
                       QLabel("修改後"), self.after, self.apply_button, self.find_text,
                       self.find_button):  # fmt: skip
            layout.addWidget(widget)
        layout.addStretch(1)


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: DocumentService | None = None,
        ask_open: Callable[[], str | None] | None = None,
        ask_save: Callable[[], str | None] | None = None,
        ask_draft: Callable[[list[dict]], tuple[str, str] | None] | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"PEditor {__version__}")
        self.resize(1280, 860)
        self.service = service
        self.jobs = JobRunner()
        self._ask_open = ask_open or self._dialog_open
        self._ask_save = ask_save or self._dialog_save
        self._ask_draft = ask_draft or self._dialog_draft
        self.document_id: str | None = None
        self.revision = 0
        self.page_count = 0
        self.page_index = 0
        self.page: dict | None = None
        self.selection: dict | None = None  # {"target_id", "text", "capability"}
        self.plan: dict | None = None
        self.last_error: ServiceError | None = None

        self.thumbs = QListWidget()
        self.thumbs.setObjectName("thumbs")
        self.thumbs.setIconSize(QPixmap(96, 128).size())
        self.thumbs.setMaximumWidth(150)
        self.thumbs.currentRowChanged.connect(self._thumb_selected)
        self.view = PageView()
        self.view.target_clicked.connect(self.select_target)
        self.panel = EditPanel()
        self.panel.setMaximumWidth(380)
        self.panel.preview_button.clicked.connect(self.request_preview)
        self.panel.new_text.returnPressed.connect(self.request_preview)
        self.panel.apply_button.clicked.connect(self.apply_plan)
        self.panel.find_button.clicked.connect(self.find)
        self.notice = QLabel("")
        self.notice.setObjectName("notice")
        self.notice.setWordWrap(True)
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.addWidget(self.notice)
        center_layout.addWidget(self.view)
        splitter = QSplitter()
        for widget in (self.thumbs, center, self.panel):
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
            ("open", "開啟", QKeySequence.StandardKey.Open, self.open_dialog),
            ("save", "另存新檔", QKeySequence.StandardKey.SaveAs, self.save_dialog),
            ("undo", "復原", QKeySequence.StandardKey.Undo, self.undo),
            ("redo", "重做", QKeySequence.StandardKey.Redo, self.redo),
            ("cancel", "取消", QKeySequence(Qt.Key.Key_Escape), self.cancel),
        ):
            action = QAction(text, self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(slot)
            toolbar.addAction(action)
            self.actions[name] = action
        self._refresh_actions()

    # --- 狀態 ----------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self.jobs.busy

    def _busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        busy, opened = self.jobs.busy, self.document_id is not None
        history = (self.service.history(self.document_id)
                   if opened and self.service else {"undo": 0, "redo": 0})  # fmt: skip
        self.actions["open"].setEnabled(not busy)
        self.actions["save"].setEnabled(opened and not busy)
        self.actions["undo"].setEnabled(opened and not busy and history["undo"] > 0)
        self.actions["redo"].setEnabled(opened and not busy and history["redo"] > 0)
        self.actions["cancel"].setEnabled(busy)
        editable = (self.selection is not None and not busy
                    and self.selection["capability"]["status"] == "support")  # fmt: skip
        self.panel.preview_button.setEnabled(editable)
        self.panel.new_text.setEnabled(editable)
        self.panel.apply_button.setEnabled(editable and self.plan is not None
                                           and self.plan.get("ready", False))  # fmt: skip
        self.panel.find_button.setEnabled(opened and not busy)

    def _status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _fail(self, error: ServiceError) -> None:
        self.last_error = error
        self._status(reason_text(error.code))
        self.panel.info.setText(reason_text(error.code))
        self._refresh_actions()

    def _run(self, func, on_done) -> None:
        self.last_error = None
        self.jobs.submit(func, on_done, self._fail)
        self._refresh_actions()

    # --- 開檔與頁面 ------------------------------------------------------
    def open_dialog(self) -> None:
        path = self._ask_open()
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        if self.document_id is not None:
            old, self.document_id = self.document_id, None
            self._run(lambda: self.service.close_document(old), lambda _: None)
        self._status("開啟中…")
        self._run(lambda: self.service.open_document(path), self._opened)

    def _opened(self, result: dict) -> None:
        self.document_id = result["document_id"]
        self.revision = result["revision"]
        self.page_count = result["page_count"]
        flags = result["document_flags"]
        self.thumbs.clear()
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
        self.view.show_page(rendered, page)
        notes = [NOTICES[n] for n in page.get("notices", []) if n in NOTICES]
        reasons = page["capabilities"]["reasons"]
        if reasons:
            notes.append("此頁：" + reasons_text(reasons))
        if notes or self.notice.text().startswith("此頁") or not self.notice.text():
            self.notice.setText("\n".join(notes))
        self._clear_selection()

    # --- 選取、預覽、套用 ------------------------------------------------
    def _clear_selection(self) -> None:
        self.selection = None
        self.plan = None
        self.panel.selected.setText("尚未選取文字")
        self.panel.new_text.clear()
        self.panel.info.clear()
        self.panel.before.clear()
        self.panel.after.clear()
        self._refresh_actions()

    def select_target(self, target: dict) -> None:
        if self.busy:
            return
        self.selection = {"target_id": target["target_id"], "text": target["text"],
                          "capability": target["capability"]}  # fmt: skip
        self.plan = None
        self.view.highlight(target["target_id"])
        self.panel.selected.setText(target["text"])
        self.panel.new_text.setText(target["text"])
        if target["capability"]["status"] == "support":
            self.panel.info.setText("")
        else:
            self.panel.info.setText("無法編輯：" + reasons_text(target["capability"]["reasons"]))
        self.panel.before.clear()
        self.panel.after.clear()
        self._refresh_actions()

    def find(self) -> None:
        text = self.panel.find_text.text()
        if not text or self.document_id is None:
            return
        doc, index = self.document_id, self.page_index

        def found(span_id: str) -> None:
            self.select_target({"target_id": span_id, "text": text,
                                "capability": {"status": "support", "reasons": []}})  # fmt: skip

        self._run(lambda: self.service.find_text(doc, index, text), found)

    def request_preview(self) -> None:
        # 只取已確認的文字：組字中（含組字中按 Enter）不規劃；preedit 不在 text() 內（G4-02、P4 U7）
        if self.selection is None or self.busy or self.panel.new_text.composing:
            return
        doc, revision = self.document_id, self.revision
        target_id, new_text = self.selection["target_id"], self.panel.new_text.text()

        def work():
            plan = self.service.plan_text_edit(doc, target_id, new_text, "prefer_a", revision)
            if not plan["ready"]:
                return plan, None
            return plan, self.service.preview_edit(doc, plan["plan_id"], revision)

        self._status("預覽中…")
        self._run(work, lambda result: self._previewed(*result))

    def _previewed(self, plan: dict, preview: dict | None) -> None:
        self.plan = plan
        if preview is None:
            self.panel.info.setText("無法修改：" + reasons_text(plan["unsupported_reasons"]))
            self._status("無法修改")
        else:
            lines = [
                f"模式 {plan['mode']}"
                + ("（沿用原字型）" if plan["mode"] == "A" else "（字型替換）")
            ]
            lines += plan.get("warnings", [])
            self.panel.info.setText("\n".join(lines))
            x0, y0, x1, y1 = preview["box"]
            m = 12  # 改動區域外留邊，看得到鄰近內容
            for label, key in ((self.panel.before, "before"), (self.panel.after, "after")):
                pix = _pixmap(preview[key]).copy(x0 - m, y0 - m, x1 - x0 + 2 * m, y1 - y0 + 2 * m)
                label.setPixmap(pix.scaledToWidth(min(340, max(1, pix.width()))))
            self._status("預覽完成，按「套用」提交")
        self._refresh_actions()

    def apply_plan(self) -> None:
        if not self.plan or not self.plan.get("ready") or self.busy:
            return
        doc, revision, plan_id = self.document_id, self.revision, self.plan["plan_id"]
        self._status("套用中…")
        self._run(lambda: self.service.apply_edit(doc, plan_id, revision), self._changed)

    def _changed(self, result: dict) -> None:
        self.revision = result["new_revision"]
        warnings = result.get("warnings") or []
        self._status("；".join(["已更新", *warnings]))
        self.load_page(self.page_index)

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

    def save_as(self, path: str) -> None:
        if self.document_id is None or self.busy:
            return
        doc, revision = self.document_id, self.revision

        def work():
            token = self.service.destination_token(path, overwrite=os.path.exists(path))
            return self.service.export_document(doc, token, revision)

        self._status("另存中…")
        self._run(work, self._saved)

    def _saved(self, result: dict) -> None:
        warnings = result.get("warnings") or []
        self._status("；".join(["已另存", *warnings]))

    # --- 復原草稿 ----------------------------------------------------------
    def offer_drafts(self) -> None:
        """使用者選擇後才復原（ADR-0020 §5）。"""
        if self.service is None or self.service.drafts is None:
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
        if action == "discard":
            self._run(lambda: self.service.discard_draft(draft_id), lambda _: None)
        elif action == "recover":
            self._run(lambda: self.service.recover_draft(draft_id), self._recovered)

    def _recovered(self, result: dict) -> None:
        flags = result.get("document_flags") or {"status": "support", "reasons": []}
        self._opened({**result, "document_flags": flags})

    # --- 對話框（測試以參數替換） -------------------------------------------
    def _dialog_open(self) -> str | None:
        path, _ = QFileDialog.getOpenFileName(self, "開啟 PDF", "", "PDF (*.pdf)")
        return path or None

    def _dialog_save(self) -> str | None:
        path, _ = QFileDialog.getSaveFileName(self, "另存新檔", "", "PDF (*.pdf)")
        return path or None

    def _dialog_draft(self, drafts: list[dict]) -> tuple[str, str] | None:
        draft = drafts[0]
        name = os.path.basename(draft["path"])
        text = (f"找到「{name}」未儲存的 {draft['operations']} 項編輯，要復原嗎？\n"
                "（選「否」會捨棄草稿）")  # fmt: skip
        answer = QMessageBox.question(self, "復原草稿", text)
        return ("recover" if answer == QMessageBox.StandardButton.Yes else "discard",
                draft["draft_id"])  # fmt: skip

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt 介面
        self.jobs.shutdown()
        super().closeEvent(event)


def prepare_storage():
    """啟動時的本機儲存接線（ADR-0021 §2 例外：不經 DocumentService）：建立復原草稿區、
    設定暫存檔紀錄位置並清除上次中斷留下的另存暫存檔（P3 U9）。回傳 DraftStore，不可用時回 None。"""
    from peditor.core.drafts import DraftStore, default_dir
    from peditor.export import transaction

    try:
        drafts = DraftStore()  # 同時建立本機資料目錄
    except Exception:  # noqa: BLE001 — 草稿區不可用時照常編輯，只是不保存草稿
        drafts = None
    transaction.registry = str(default_dir().parent / "pending-temps.json")
    transaction.cleanup_recorded()
    return drafts


def run(*, smoke: bool = False, versions: dict[str, str] | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("PEditor")
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
        QTimer.singleShot(0, window.offer_drafts)
        return app.exec()
