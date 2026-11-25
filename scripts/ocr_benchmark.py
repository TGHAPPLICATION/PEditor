"""作業系統內建 OCR 準確度量測（ADR-0035，P14-04）：把繁中 fixture 畫成純圖片頁（模擬掃描），
以 LUMICAT 的 OCR 辨識，和原本的文字層比對字元正確率與每頁秒數。輸出 Markdown 表格。

只在 Windows／macOS 有意義；用 `uv run python scripts/ocr_benchmark.py`。
測試資料是 repo 內的合成 fixture，不含真實公文。
"""

from __future__ import annotations

import difflib
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import pymupdf

from lumicat.core.service import DocumentService, ServiceError

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "tests" / "fixtures" / "files"
FIXTURES = ("T01", "T02", "T03", "T04", "T05", "F02")
SCAN_DPI = 200  # 一般辦公掃描解析度


def make_scanned(source: Path, target: Path, dpi: int = SCAN_DPI) -> bool:
    """每頁畫成灰階點陣後放進新 PDF：沒有文字層，模擬掃描檔。回傳第 1 頁是否畫得出內容。
    T01、F02 的字型 CID 與字型程式不一致，MuPDF 畫出空白頁（PREVIEW_UNRELIABLE），不計入。"""
    inked = False
    with pymupdf.open(source) as src, pymupdf.open() as out:
        for number, page in enumerate(src):
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
            if number == 0:
                inked = any(value < 128 for value in pix.samples)
            new = out.new_page(width=page.rect.width, height=page.rect.height)
            new.insert_image(new.rect, stream=pix.tobytes("png"))
        out.save(target)
    return inked


def chars(text: str) -> list[str]:
    """比對用：去空白與標點，全形半形統一（NFKC）。"""
    norm = unicodedata.normalize("NFKC", text)
    return [c for c in norm if not c.isspace() and not unicodedata.category(c).startswith("P")]


def accuracy(reference: str, found: str) -> float:
    ref, got = chars(reference), chars(found)
    if not ref:
        return 1.0 if not got else 0.0
    matcher = difflib.SequenceMatcher(None, ref, got, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks()) / len(ref)


def measure(
    name: str, service: DocumentService, work: Path
) -> tuple[str, int, float, float] | None:
    """None＝原檔畫不出內容，無法模擬掃描（不計）。"""
    source = FILES / f"{name}.pdf"
    scanned = work / f"{name}-scan.pdf"
    if not make_scanned(source, scanned):
        return None
    original = service.open_document(source)["document_id"]
    reference = service.extract_text(original, 0)["text"]
    doc = service.open_document(scanned)["document_id"]
    started = time.perf_counter()
    found = service.ocr_page(doc, 0)["text"]
    seconds = time.perf_counter() - started
    return name, len(chars(reference)), accuracy(reference, found), seconds


def main() -> int:
    rows, blank = [], []
    with tempfile.TemporaryDirectory() as tmp, DocumentService() as service:
        for name in FIXTURES:
            try:
                row = measure(name, service, Path(tmp))
            except ServiceError as exc:
                print(f"OCR 無法執行：{exc.code}")
                return 2
            if row is None:
                blank.append(name)
            else:
                rows.append(row)
    print(f"### OCR 準確度（{sys.platform}，合成掃描 {SCAN_DPI} dpi）\n")
    print("| fixture | 參考字數 | 字元正確率 | 秒 |")
    print("| --- | --- | --- | --- |")
    for name, count, acc, seconds in rows:
        print(f"| {name} | {count} | {acc:.1%} | {seconds:.2f} |")
    total = sum(r[1] for r in rows)
    weighted = sum(r[1] * r[2] for r in rows) / total if total else 0.0
    print(f"| 合計 | {total} | {weighted:.1%} | {sum(r[3] for r in rows):.2f} |")
    if blank:
        names = "、".join(blank)
        print(f"\n不計：{names}（原檔字型 CID 與字型程式不一致，畫面空白，無法模擬掃描）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
