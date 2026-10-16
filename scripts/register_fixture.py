"""登記人工製作的 fixture：複製到 tests/fixtures/files/，回寫 manifest 的 hash 與幾何欄位。

用法：
  uv run python scripts/register_fixture.py T05 "D:\\fixtures\\T05.pdf"
  # 盲測：只印 hash，不入庫
  uv run python scripts/register_fixture.py B07 "E:\\blind\\B07.pdf" --hash-only

會寫入：sha256、generator_version（取自 PDF 的 Producer／Creator）、
bbox_pt（以 original_text 搜尋）、editable_region_pt（空白時預設 bbox 外 2 pt）、
status=available。expected／reason_code 等欄位不動。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "manifest.csv"
FILES = ROOT / "tests" / "fixtures" / "files"


def _fmt(rect) -> str:
    return ",".join(f"{v:.2f}" for v in rect)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture_id")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--hash-only", action="store_true", help="盲測樣本：只輸出 SHA-256")
    args = parser.parse_args(argv)

    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    with MANIFEST.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)
    row = next((r for r in rows if r["fixture_id"] == args.fixture_id), None)
    if row is None:
        raise SystemExit(f"manifest 沒有 {args.fixture_id}")
    if args.hash_only or row["blind"] == "true":
        print(f"{args.fixture_id} sha256={digest}（盲測樣本不入庫，請記入離線保管清冊）")
        return 0

    with pymupdf.open(args.pdf) as doc:
        meta = doc.metadata or {}
        version = "; ".join(v for v in (meta.get("producer"), meta.get("creator")) if v)
        page = doc[int(row["page_index"] or 0)]
        bbox = ""
        if row["original_text"]:
            hits = page.search_for(row["original_text"])
            if not hits:
                where, text = row["page_index"], row["original_text"]
                print(f"警告：第 {where} 頁找不到原文「{text}」，bbox 留空")
            else:
                bbox = _fmt(hits[0])
        elif row["target"].startswith("image") and page.get_images():
            rects = page.get_image_rects(page.get_images()[0][0])
            bbox = _fmt(rects[0]) if rects else ""

    FILES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.pdf, FILES / f"{args.fixture_id}.pdf")
    if bbox and not row["editable_region_pt"]:
        x0, y0, x1, y1 = (float(v) for v in bbox.split(","))
        row["editable_region_pt"] = _fmt((x0 - 2, y0 - 2, x1 + 2, y1 + 2))
    row.update(sha256=digest, generator_version=version, bbox_pt=bbox, status="available")

    with MANIFEST.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{args.fixture_id} 已登記：sha256={digest[:16]}… bbox={bbox or '（無）'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
