"""P6 儲存格改字真修改證據包（spec §8.1、G6；ADR-0023）：每個 B 案例產出一個資料夾。

  uv run python scripts/p6_evidence.py reports/P6/evidence

每案以 manifest 的原文／新文改目標格中含原文的那一行。輸出：
- output.pdf：另存驗證通過才寫出；不入庫，SHA-256 記於 summary.json（trailer /ID 隨機，重產後不同）
- plan.json：EditPlan（模式、儲存格與行、可改動區域、字型替換）
- validation.json：另存驗證（qpdf、增量歷史、不可達物件、格線不變）、解碼後內容差異、資源差異
- cells.json：改前偵測到的全部格（列欄、跨度、範圍、各行文字、能力判定）
- evidence.json：MuPDF、PDFium 擷取目標格與其他格（含同格其他行）的文字前後、格線前後、
  manifest 可改動區域 +2 pt 外的超標像素比例、其他格的超標像素數
- compare.png：目標格附近放大的原／新渲染（上 PDFium、下 MuPDF；ADR-0015 例外的 MuPDF 為空白）
summary.json 彙整全部案例。原始 PDF 即 tests/fixtures/files/<id>.pdf（manifest 記錄 SHA-256）。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "integration"))
os.environ.setdefault(
    "PEDITOR_MODE_B_FONT", str(ROOT / "tests/fixtures/fonts/NotoSansTC-Regular.otf")
)

import pikepdf  # noqa: E402
import pymupdf  # noqa: E402
import pypdfium2  # noqa: E402
import visual  # noqa: E402
from PIL import Image  # noqa: E402

from peditor.worker import analyzer, cell, edit, export, table  # noqa: E402
from peditor.worker.content import interpret  # noqa: E402

CASES = ("B01", "B02", "B03", "B04", "B05", "B06")


def _texts_in(data: bytes, box) -> dict[str, str]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        mu = doc[0].get_text(clip=pymupdf.Rect(*box))
    pdf = pypdfium2.PdfDocument(data)
    try:
        page = pdf[0]
        height = page.get_height()
        pd = page.get_textpage().get_text_bounded(left=box[0], bottom=height - box[3],
                                                  right=box[2], top=height - box[1])  # fmt: skip
    finally:
        pdf.close()
    return {"mupdf": "".join(mu.split()), "pdfium": "".join(pd.split())}


def _rules(data: bytes) -> list:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        page = pdf.pages[0]
        found = table.rules(interpret(page), analyzer.page_geometry(page).pdf_to_page())
        return [[r.horizontal, round(r.pos, 3), round(r.a, 3), round(r.b, 3), round(r.width, 3)]
                for r in found.horizontal + found.vertical]  # fmt: skip


def _compare(original: bytes, result: bytes, region: list[float]) -> Image.Image:
    x0, y0, x1, y1 = visual.mask_pixels(original, 0, region)
    box = (max(0, x0 - 40), max(0, y0 - 20), x1 + 40, y1 + 20)
    tiles = [visual.render(e, d).crop(box) for e in ("pdfium", "mupdf") for d in (original, result)]
    width, height = tiles[0].size
    sheet = Image.new("RGB", (width * 2 + 8, height * 2 + 8), "white")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 2) * (width + 8), (i // 2) * (height + 8)))
    return sheet


def run_case(out_dir: Path, fid: str) -> dict:
    row = visual.manifest()[fid]
    case_dir = out_dir / fid
    case_dir.mkdir(parents=True, exist_ok=True)
    r, c = map(int, row["target"].removeprefix("cell(").removesuffix(")").split(","))
    document = analyzer.open_document(str(visual.FILES / f"{fid}.pdf"))
    try:
        cells = analyzer.inspect_page(document, 0)["cell_targets"]
        (case_dir / "cells.json").write_text(json.dumps(cells, ensure_ascii=False, indent=2),
                                             encoding="utf-8")  # fmt: skip
        target = next(x for x in cells if (x["row"], x["col"]) == (r, c))
        index = next((i for i, ln in enumerate(target["lines"])
                      if row["original_text"] in ln["text"]), 0)  # fmt: skip
        line = target["lines"][index]["text"] if target["lines"] else ""
        new_line = line.replace(row["original_text"], row["new_text"] or "X")
        plan = cell.plan_cell_edit(document, {"cell_id": target["cell_id"], "line_index": index,
                                              "new_text": new_line or "X"})  # fmt: skip
        (case_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")
        if not plan["ready"]:
            spans = [target["row"], target["col"], target["row_span"], target["col_span"]]
            return {"case": fid, "expected": row["expected"], "ready": False,
                    "reasons": plan["unsupported_reasons"], "cell": spans}  # fmt: skip
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
    protected = [x["inner_bbox"] for x in cells if x["cell_id"] != target["cell_id"]]
    protected += [ln["bbox"] for i, ln in enumerate(target["lines"]) if i != index]
    evidence = {
        "target_before": _texts_in(original, target["inner_bbox"]),
        "target_after": _texts_in(result, target["inner_bbox"]),
        "protected_text_unchanged": all(
            _texts_in(original, b) == _texts_in(result, b) for b in protected
        ),  # fmt: skip
        "rules_unchanged": _rules(original) == _rules(result),
        "rules_count": len(_rules(original)),
        "visual": {},
    }
    mask = visual.mask_pixels(original, 0, region)
    for engine in visual.engines(fid):
        before, after = visual.render(engine, original), visual.render(engine, result)
        over = 0
        for box in protected:
            x0, y0, x1, y1 = visual.mask_pixels(original, 0, box)
            crop = (x0 + 3, y0 + 3, x1 - 3, y1 - 3)
            over += visual.diff_stats(before.crop(crop), after.crop(crop))["over_total"]
        evidence["visual"][engine] = {
            "outside_fraction": visual.diff_stats(before, after, mask)["outside_fraction"],
            "outside_limit": visual.OUTSIDE_LIMIT, "protected_over_total": over,
        }  # fmt: skip
    (case_dir / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _compare(original, result, region).save(case_dir / "compare.png", optimize=True)
    report = exported["validation_report"]
    return {
        "case": fid, "expected": row["expected"], "ready": True, "mode": plan["mode"],
        "cell": [target["row"], target["col"], target["row_span"], target["col_span"]],
        "line_index": index, "new_line": new_line,
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "output_sha256": exported["output_hash"], "validation_ok": report["ok"],
        "rules_changed": report["rules_changed"], "content_changes": len(report["content_changes"]),
        "resource_changes": report["resource_changes"], "font_changes": plan["font_changes"],
        "warnings": plan["warnings"], "evidence": {k: v for k, v in evidence.items()
                                                   if k not in ("target_before",)},
    }  # fmt: skip


def main(out_dir: Path) -> int:
    summary = [run_case(out_dir, fid) for fid in CASES]
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = True
    for entry in summary:
        good = entry["ready"] == (entry["expected"] == "support") and (
            not entry["ready"] or entry["validation_ok"])  # fmt: skip
        ok &= good
        print(entry["case"], entry["ready"], entry.get("validation_ok", entry.get("reasons")), good)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports/P6/evidence"))
