"""「工具 → 頁面工具…」對話框（ADR-0029，P9-06）：刪除、保留／擷取、合併、插入。

只收集使用者的選擇並組成計畫；實際組頁與另存由主視窗經 DocumentService 在 worker 執行。
畫面只顯示檔名，不顯示完整路徑。
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from peditor.core import pages
from peditor.core.limits import MAX_COMPOSE_SOURCES, MAX_PAGES
from peditor.ui.messages import reasons_text

LIMITS_TEXT = (
    "結果保留每頁內容、註解、頁面大小與旋轉；不保留書籤。"
    "含表單欄位、加密、簽章或主動內容的檔案無法使用。"
    "結果一律另存新檔，不覆寫原檔。"
)
TABS = ("delete", "keep", "merge", "insert")


@dataclass
class Source:
    path: str
    page_count: int

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


@dataclass
class Request:
    kind: str
    sources: list[str]
    plan: pages.Plan
    open_after: bool


class PageToolsDialog(QDialog):
    """probe(path) → Source 或丟出 ValueError（訊息可直接顯示）；
    ask_files／ask_file 為選檔對話框。"""

    def __init__(self, current: Source | None, probe: Callable[[str], Source],
                 ask_files: Callable[[], list[str]], ask_file: Callable[[], str | None],
                 parent: QWidget | None = None) -> None:  # fmt: skip
        super().__init__(parent)
        self.setWindowTitle("頁面工具")
        self.resize(640, 560)
        self.current, self._probe = current, probe
        self._ask_files, self._ask_file = ask_files, ask_file
        self.request: Request | None = None
        self.inserted: Source | None = None

        self.tabs = QTabWidget()
        self.delete_range, self.delete_info = QLineEdit(), QLabel()
        self.keep_range, self.keep_info = QLineEdit(), QLabel()
        self.tabs.addTab(
            self._range_tab(self.delete_range, self.delete_info, "要刪除的頁碼"), "刪除頁面"
        )
        self.tabs.addTab(self._range_tab(self.keep_range, self.keep_info, "要保留的頁碼"),
                         "保留／擷取頁面")  # fmt: skip
        self.tabs.addTab(self._merge_tab(), "合併 PDF")
        self.tabs.addTab(self._insert_tab(), "插入 PDF")

        self.error = QLabel("")
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        limits = QLabel(LIMITS_TEXT)
        limits.setObjectName("limits")
        limits.setWordWrap(True)
        self.open_after = QCheckBox("完成後開啟新檔")
        self.open_after.setChecked(True)
        self.cancel_button = QPushButton("取消")
        self.ok_button = QPushButton("另存新檔…")
        self.ok_button.setObjectName("primary")
        self.ok_button.setDefault(True)
        self.cancel_button.clicked.connect(self.reject)
        self.ok_button.clicked.connect(self.submit)
        buttons = QHBoxLayout()
        buttons.addWidget(self.open_after)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.ok_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(limits)
        layout.addWidget(self.error)
        layout.addLayout(buttons)
        self.delete_range.textChanged.connect(self._update)
        self.keep_range.textChanged.connect(self._update)
        self.tabs.currentChanged.connect(self._update)
        if current is not None:
            self._add_source(current)
        self._update()

    # --- 分頁 -------------------------------------------------------------
    def _source_label(self) -> QLabel:
        text = (f"目前檔案：{self.current.name}（共 {self.current.page_count} 頁）"
                if self.current else "請先開啟要處理的 PDF")  # fmt: skip
        label = QLabel(text)
        label.setWordWrap(True)
        return label

    def _range_tab(self, field: QLineEdit, info: QLabel, caption: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._source_label())
        label = QLabel(f"{caption}（例如 1-3,5）")
        label.setObjectName("caption")
        layout.addWidget(label)
        field.setPlaceholderText("1-3,5")
        field.setEnabled(self.current is not None)
        layout.addWidget(field)
        info.setObjectName("caption")
        layout.addWidget(info)
        layout.addStretch(1)
        return tab

    def _merge_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        caption = QLabel(
            f"依下列順序接成一份新 PDF（最多 {MAX_COMPOSE_SOURCES} 份、合計 {MAX_PAGES} 頁）。"
        )
        caption.setWordWrap(True)
        layout.addWidget(caption)
        self.merge_list = QListWidget()
        self.merge_list.setObjectName("merge_list")
        layout.addWidget(self.merge_list, 1)
        row = QHBoxLayout()
        self.add_button = QPushButton("加入檔案…")
        self.up_button, self.down_button = QPushButton("上移"), QPushButton("下移")
        self.remove_button = QPushButton("移除")
        for button in (self.add_button, self.up_button, self.down_button, self.remove_button):
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        self.merge_info = QLabel("")
        self.merge_info.setObjectName("caption")
        layout.addWidget(self.merge_info)
        self.add_button.clicked.connect(self.add_files)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(1))
        self.remove_button.clicked.connect(self._remove)
        self.merge_list.currentRowChanged.connect(self._update)
        return tab

    def _insert_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._source_label())
        row = QHBoxLayout()
        self.insert_button = QPushButton("選擇要插入的檔案…")
        self.insert_button.setEnabled(self.current is not None)
        self.insert_label = QLabel("尚未選擇")
        row.addWidget(self.insert_button)
        row.addWidget(self.insert_label, 1)
        layout.addLayout(row)
        caption = QLabel("插入在第幾頁之後（0＝最前面）")
        caption.setObjectName("caption")
        layout.addWidget(caption)
        self.position = QSpinBox()
        self.position.setRange(0, self.current.page_count if self.current else 0)
        self.position.setValue(self.current.page_count if self.current else 0)
        layout.addWidget(self.position)
        layout.addStretch(1)
        self.insert_button.clicked.connect(self.choose_insert)
        return tab

    # --- 合併清單 ---------------------------------------------------------
    def sources(self) -> list[Source]:
        return [self.merge_list.item(i).data(256) for i in range(self.merge_list.count())]

    def add_files(self) -> None:
        errors = []
        for path in self._ask_files():
            if self.merge_list.count() >= MAX_COMPOSE_SOURCES:
                errors.append(f"最多 {MAX_COMPOSE_SOURCES} 份檔案")
                break
            try:
                self._add_source(self._probe(path))
            except ValueError as exc:
                errors.append(f"{os.path.basename(path)}：{exc}")
        self._update()
        self.error.setText("\n".join(errors))

    def _add_source(self, source: Source) -> None:
        item = QListWidgetItem(f"{source.name}（{source.page_count} 頁）")
        item.setData(256, source)
        self.merge_list.addItem(item)

    def _move(self, step: int) -> None:
        row = self.merge_list.currentRow()
        target = row + step
        if row < 0 or not 0 <= target < self.merge_list.count():
            return
        item = self.merge_list.takeItem(row)
        self.merge_list.insertItem(target, item)
        self.merge_list.setCurrentRow(target)

    def _remove(self) -> None:
        row = self.merge_list.currentRow()
        if row >= 0:
            self.merge_list.takeItem(row)
        self._update()

    def choose_insert(self) -> None:
        path = self._ask_file()
        if not path:
            return
        try:
            self.inserted = self._probe(path)
        except ValueError as exc:
            self.error.setText(f"{os.path.basename(path)}：{exc}")
            return
        self.insert_label.setText(f"{self.inserted.name}（{self.inserted.page_count} 頁）")
        self._update()

    # --- 計畫 -------------------------------------------------------------
    @property
    def kind(self) -> str:
        return TABS[self.tabs.currentIndex()]

    def build(self) -> Request:
        """依目前分頁組成計畫；不合法時丟出 pages.RangeError（訊息可直接顯示）。"""
        kind, current = self.kind, self.current
        if kind in ("delete", "keep", "insert") and current is None:
            raise pages.RangeError("請先開啟要處理的 PDF")
        if kind in ("delete", "keep"):
            field = self.delete_range if kind == "delete" else self.keep_range
            chosen = pages.parse_ranges(field.text(), current.page_count)
            make = pages.delete_plan if kind == "delete" else pages.keep_plan
            plan = make(current.page_count, chosen)
            sources = [current.path]
        elif kind == "merge":
            items = self.sources()
            plan = pages.merge_plan([s.page_count for s in items])
            sources = [s.path for s in items]
        else:
            if self.inserted is None:
                raise pages.RangeError("請選擇要插入的檔案")
            plan = pages.insert_plan(current.page_count, self.inserted.page_count,
                                     self.position.value())  # fmt: skip
            sources = [current.path, self.inserted.path]
        return Request(kind, sources, plan, self.open_after.isChecked())

    def _update(self, *_args) -> None:
        self.error.setText("")
        if self.current is not None:
            for field, info, verb in ((self.delete_range, self.delete_info, "刪除"),
                                      (self.keep_range, self.keep_info, "保留")):  # fmt: skip
                if not field.text().strip():
                    info.setText("")
                    continue
                try:
                    chosen = pages.parse_ranges(field.text(), self.current.page_count)
                except pages.RangeError as exc:
                    info.setText(str(exc))
                    continue
                left = (self.current.page_count - len(chosen)) if verb == "刪除" else len(chosen)
                info.setText(f"將{verb} {len(chosen)} 頁，新檔共 {left} 頁")
        total = sum(s.page_count for s in self.sources())
        self.merge_info.setText(f"{self.merge_list.count()} 份檔案，合計 {total} 頁")
        row, count = self.merge_list.currentRow(), self.merge_list.count()
        self.up_button.setEnabled(row > 0)
        self.down_button.setEnabled(0 <= row < count - 1)
        self.remove_button.setEnabled(row >= 0)
        self.ok_button.setText("另存合併檔…" if self.kind == "merge" else "另存新檔…")

    def submit(self) -> None:
        try:
            self.request = self.build()
        except pages.RangeError as exc:
            self.error.setText(str(exc))
            return
        self.accept()


def probe_error_text(reasons: list[str]) -> str:
    return "無法使用：" + reasons_text(reasons)
