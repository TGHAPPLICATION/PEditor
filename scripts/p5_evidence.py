"""P5 圖片替換真修改證據包（spec §8.1 比照、G5；ADR-0022）：每個 I 案例產出一個資料夾。

  uv run python scripts/p5_evidence.py reports/P5/evidence

新圖：與目標外框（未剪裁的放置範圍）同比例的單色洋紅 PNG
（與 tests/integration/test_edit_image.py 相同）。
每案輸出：
- output.pdf：另存驗證通過才寫出；不入庫，SHA-256 記於 summary.json，以本腳本重產
- plan.json：EditPlan（目標、資源變更、幾何、警告）
- validation.json：另存驗證（qpdf、增量歷史、不可達物件、圖片頁文字不變）、解碼後內容差異、資源差異
- visual.json：MuPDF、PDFium 各自原／新渲染：manifest 可改動區域 +2 pt 外的超標像素比例、
  可見範圍中心像素、未改動頁是否逐像素相同、兩引擎擷取文字是否與原檔相同
- compare.png：目標區域放大的原／新渲染（上 PDFium、下 MuPDF）
summary.json 彙整全部案例。原始 PDF 即 tests/fixtures/files/<id>.pdf（manifest 記錄 SHA-256）。
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "integration"))

import pikepdf  # noqa: E402
import pymupdf  # noqa: E402
import pypdfium2  # noqa: E402
import visual  # noqa: E402
from PIL import Image  # noqa: E402

from peditor.worker import analyzer, edit, export, image  # noqa: E402

CASES = ("I01", "I02", "I03", "I04", "I05", "I06", "I07", "I09")
MAGENTA = (255, 0, 255)


def _png(target) -> bytes:
    x0, y0, x1, y1 = target["bbox"]
    buf = io.BytesIO()
    Image.new("RGB", (round((x1 - x0) * 2), round((y1 - y0) * 2)), MAGENTA).save(buf, "PNG")
    return buf.getvalue()


def _texts(data: bytes, page_index: int) -> dict[str, str]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        mu = doc[page_index].get_text()
    pdf = pypdfium2.PdfDocument(data)
    try:
        pd = pdf[page_index].get_textpage().get_text_range()
    finally:
        pdf.close()
    return {"mupdf": mu, "pdfium": pd}


def _compare(original: bytes, result: bytes, region: list[float]) -> Image.Image:
    x0, y0, x1, y1 = visual.mask_pixels(original, 0, region)
    box = (max(0, x0 - 40), max(0, y0 - 20), x1 + 40, y1 + 20)
    tiles = [visual.render(e, d).crop(box) for e in ("pdfium", "mupdf") for d in (original, result)]
    width, height = tiles[0].size
    sheet = Image.new("RGB", (width * 2 + 8, height * 2 + 8), "white")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 2) * (width + 8), (i // 2) * (height + 8)))
    return sheet


def _page_count(data: bytes) -> int:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        return len(pdf.pages)


def run_case(out_dir: Path, fid: str) -> dict:
    row = visual.manifest()[fid]
    case_dir = out_dir / fid
    case_dir.mkdir(parents=True, exist_ok=True)
    index = int(row["target"].split("#")[1])
    document = analyzer.open_document(str(visual.FILES / f"{fid}.pdf"))
    try:
        target = analyzer.inspect_page(document, 0)["image_targets"][index]
        new_image = _png(target)
        asset = image.register_asset(document, {"data": base64.b64encode(new_image).decode()})
        plan = image.plan_image_edit(document, {"target_id": target["target_id"],
                                                "asset_id": asset["asset_id"]})  # fmt: skip
        (case_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")
        if not plan["ready"]:
            return {"case": fid, "expected": row["expected"], "ready": False,
                    "reasons": plan["unsupported_reasons"]}  # fmt: skip
        edit.apply_edit(document, plan["plan_id"], 0)
        output = case_dir / "output.pdf"
        output.unlink(missing_ok=True)
        exported = export.export_document(document, str(output))
        original = document.original
    finally:
        document.close()
    result = output.read_bytes()
    (case_dir / "validation.json").write_text(
        json.dumps(exported, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    region = [float(v) for v in row["editable_region_pt"].split(",")]
    mask = visual.mask_pixels(original, 0, region)
    vx0, vy0, vx1, vy1 = visual.mask_pixels(original, 0, target["visible_bbox"])
    center = ((vx0 + vx1) // 2, (vy0 + vy1) // 2)
    pages = _page_count(original)
    report_visual = {}
    for engine in visual.engines(fid):
        before, after = visual.render(engine, original), visual.render(engine, result)
        stats = visual.diff_stats(before, after, mask)
        others = {p: visual.diff_stats(visual.render(engine, original, p),
                                       visual.render(engine, result, p))["over_total"]
                  for p in range(1, pages)}  # fmt: skip
        report_visual[engine] = {
            "outside_fraction": stats["outside_fraction"],
            "outside_limit": visual.OUTSIDE_LIMIT,
            "center_pixel_after": list(after.getpixel(center)),
            "other_pages_over_total": others,
            "text_unchanged": all(
                _texts(original, p)[engine] == _texts(result, p)[engine] for p in range(pages)
            ),  # fmt: skip
        }
    (case_dir / "visual.json").write_text(
        json.dumps(report_visual, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _compare(original, result, region).save(case_dir / "compare.png", optimize=True)
    report = exported["validation_report"]
    with pikepdf.open(io.BytesIO(original)) as pdf:
        old_raw = pdf.get_object(tuple(target["xobject"])).read_raw_bytes()
    with pikepdf.open(io.BytesIO(result)) as pdf:
        retained = any(isinstance(o, pikepdf.Stream) and o.read_raw_bytes() == old_raw
                       for o in pdf.objects)  # fmt: skip
    return {
        "case": fid, "expected": row["expected"], "ready": True,
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "new_image_sha256": asset["asset_id"], "output_sha256": exported["output_hash"],
        "validation_ok": report["ok"],
        "content_changes": [(c["page_index"], c["before"], c["after"])
                            for c in report["content_changes"]],
        "resource_changes": report["resource_changes"], "geometry": plan["geometry"],
        "warnings": plan["warnings"], "original_image_retained": retained,
        "visual": report_visual,
    }  # fmt: skip


def main(out_dir: Path) -> int:
    summary = [run_case(out_dir, fid) for fid in CASES]
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = True
    for entry in summary:
        expected_ready = entry["expected"] == "support"
        good = entry["ready"] == expected_ready and (not entry["ready"] or entry["validation_ok"])
        ok &= good
        print(entry["case"], entry["ready"], entry.get("validation_ok", entry.get("reasons")), good)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports/P5/evidence"))
