"""「工具 → 文字擷取…」對話框（ADR-0033）：
輸入頁碼，把這些頁的文字合併顯示，可選取、搜尋、複製、另存 .txt。

文字由主視窗經 DocumentService 向 worker 取得（目前工作文件，含未另存的修改）；本檔不開啟 PDF。
畫面與錯誤訊息只顯示檔名，不顯示完整路徑；文件文字不寫入日誌。
"""

from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from peditor.core import pages

NO_TEXT = "（此頁沒有可擷取的文字，可能是掃描圖片）"
LIMITED = "（此頁內容超過處理上限，未擷取）"


def page_header(page_number: int) -> str:
    return f"—— 第 {page_number} 頁 ——"


def combine(results: list[tuple[int, dict]], headers: bool = True) -> str:
    """(頁索引, extract_text 結果) → 合併文字；每頁前加「第 N 頁」標題。
    headers=False（「移除頁碼」）：不加標題，也不放無文字頁的說明，只留文件文字，頁與頁之間空一行。"""
    parts = []
    for index, result in results:
        if not headers:
            if result["text"] and not result["limited"]:
                parts.append(result["text"])
            continue
        body = LIMITED if result["limited"] else (result["text"] or NO_TEXT)
        parts.append(f"{page_header(index + 1)}\n{body}")
    return "\n\n".join(parts)


class TextExtractDialog(QDialog):
    """extract(頁索引) → extract_text 結果（失敗時丟出 ValueError，訊息可直接顯示）；
    ask_save() → .txt 路徑或 None。"""

    def __init__(
        self,
        page_count: int,
        current_page: int,
        extract: Callable[[int], dict],
        ask_save: Callable[[], str | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("文字擷取")
        self.resize(680, 600)
        self.page_count, self._extract, self._ask_save = page_count, extract, ask_save

        self.range = QLineEdit(str(current_page + 1))
        self.range.setPlaceholderText("例如 1-3,5")
        # 欄位已預填目前頁、看不到 placeholder：另以說明文字提示可自行輸入（工程師 2026-11-24）
        self.hint = QLabel(f"可自行輸入頁碼，例如「1-3,5」；整份請輸入「1-{page_count}」。"
                           "輸入後按 Enter 或「擷取」。")  # fmt: skip
        self.hint.setObjectName("caption")
        self.hint.setWordWrap(True)
        self.range.setToolTip(self.hint.text())
        self.extract_button = QPushButton("擷取")
        self.extract_button.setObjectName("primary")
        top = QHBoxLayout()
        caption = QLabel(f"頁碼（共 {page_count} 頁）")
        top.addWidget(caption)
        top.addWidget(self.range, 1)
        top.addWidget(self.extract_button)

        self.search = QLineEdit()
        self.search.setPlaceholderText("在擷取結果中搜尋")
        self.find_button = QPushButton("找下一個")
        search_row = QHBoxLayout()
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.find_button)

        self.text = QPlainTextEdit()
        self.text.setObjectName("extracted_text")
        self.text.setReadOnly(True)  # 可選取、可 Ctrl+C，不能改
        self.info = QLabel("")
        self.info.setObjectName("caption")
        self.info.setWordWrap(True)

        self.results: list[tuple[int, dict]] = []
        # 「移除頁碼」（工程師 2026-11-24）：按下後拿掉「第 N 頁」標題，再按一次加回
        self.headers_button = QPushButton("移除頁碼")
        self.headers_button.setCheckable(True)
        self.copy_button = QPushButton("複製全部")
        self.save_button = QPushButton("另存文字檔…")
        self.close_button = QPushButton("關閉")
        buttons = QHBoxLayout()
        buttons.addWidget(self.info, 1)
        buttons.addWidget(self.headers_button)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.hint)
        layout.addLayout(search_row)
        layout.addWidget(self.text, 1)
        layout.addLayout(buttons)

        self.extract_button.clicked.connect(self.run)
        self.range.returnPressed.connect(self.run)
        self.find_button.clicked.connect(self.find_next)
        self.search.returnPressed.connect(self.find_next)
        self.headers_button.toggled.connect(self._show)
        self.copy_button.clicked.connect(self.copy_all)
        self.save_button.clicked.connect(self.save_text)
        self.close_button.clicked.connect(self.accept)
        self._refresh()
        self.run()

    def _refresh(self) -> None:
        has_text = bool(self.text.toPlainText())
        for button in (self.copy_button, self.save_button, self.find_button,
                       self.headers_button):  # fmt: skip
            button.setEnabled(has_text)

    def run(self) -> None:
        try:
            chosen = pages.parse_ranges(self.range.text(), self.page_count)
        except pages.RangeError as exc:
            self.info.setText(str(exc))
            return
        results = []
        try:
            for index in chosen:
                results.append((index, self._extract(index)))
        except ValueError as exc:
            self.info.setText(str(exc))
            return
        self.results = results
        self._show()
        empty = [str(i + 1) for i, r in results if not r["limited"] and not r["text"]]
        note = f"；第 {','.join(empty)} 頁沒有文字（可能是掃描圖片）" if empty else ""
        chars = sum(len(r["text"]) for _, r in results)
        self.info.setText(f"共 {len(results)} 頁、{chars} 字{note}")
        self._refresh()

    def _show(self, *_args) -> None:
        removed = self.headers_button.isChecked()
        self.headers_button.setText("加回頁碼" if removed else "移除頁碼")
        self.text.setPlainText(combine(self.results, headers=not removed))

    def find_next(self) -> None:
        needle = self.search.text()
        if not needle:
            return
        if not self.text.find(needle):  # 到底了從頭找
            cursor = self.text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.text.setTextCursor(cursor)
            if not self.text.find(needle):
                self.info.setText(f"找不到「{needle}」")
                return
        self.text.setFocus()

    def copy_all(self) -> None:
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        self.info.setText("已複製到剪貼簿")

    def save_text(self) -> None:
        path = self._ask_save()
        if not path:
            return
        if not path.lower().endswith(".txt"):  # 只寫 .txt，不會覆寫 PDF
            path += ".txt"
        try:
            # UTF-8 含 BOM：舊版記事本與 Excel 也能正確辨識中文；換行依作業系統
            with open(path, "w", encoding="utf-8-sig") as fh:  # 覆寫已由存檔對話框確認
                fh.write(self.text.toPlainText())
        except OSError:
            self.info.setText("無法寫入文字檔")
            return
        self.info.setText(f"已另存 {os.path.basename(path)}")
