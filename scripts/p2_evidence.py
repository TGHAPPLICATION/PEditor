"""P2 真修改證據包（spec §6 P2 輸出、§8.1）：每個宣告支援的文字操作產出一個資料夾。

  uv run python scripts/p2_evidence.py reports/P2/evidence

每案輸出：
- output.pdf：完整重寫後的新檔（另存驗證通過才寫出）；不入庫，SHA-256 記於 summary.json，
  以本腳本重產
- plan.json：EditPlan（模式、實際改動範圍、字型替換、資源變更、警告）
- validation.json：另存驗證（qpdf、增量歷史、不可達物件）、解碼後內容差異、資源差異
- extraction.json：MuPDF、PDFium 改動前後的頁面文字與目標 occurrence 計數
- compare.png：目標區域放大的原／新渲染（上 PDFium、下 MuPDF；ADR-0015 例外的 MuPDF 為空白）
summary.json 彙整全部案例。原始 PDF 即 tests/fixtures/files/<id>.pdf（manifest 記錄 SHA-256）。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "integration"))
os.environ.setdefault(
    "PEDITOR_MODE_B_FONT", str(ROOT / "tests/fixtures/fonts/NotoSansTC-Regular.otf")
)

import pymupdf  # noqa: E402
import pypdfium2  # noqa: E402
import visual  # noqa: E402
from PIL import Image  # noqa: E402

from peditor.worker import analyzer, edit, export, span  # noqa: E402


def cases():
    rows = visual.manifest()
    out = [(fid, fid, r["original_text"], r["new_text"], r["editable_region_pt"])
           for fid, r in rows.items() if r["expected"] == "support" and r["new_text"]
           and fid[0] in "TFL" and r["status"] == "available"]  # fmt: skip
    with open(visual.FIXTURES / "edit_cases.csv", encoding="utf-8", newline="") as fh:
        rows_e = [c for c in csv.DictReader(fh) if not c["after_case"]]
        out += [(c["case_id"], c["fixture_id"], c["original_text"], c["new_text"],
                 c["editable_region_pt"]) for c in rows_e]  # fmt: skip
    return out


def _flat(text: str) -> str:
    """去掉空白與換行：引擎擷取時可能在目標中間斷行（例如 T06 的 MuPDF）。"""
    return "".join(text.split())


def _texts(data: bytes) -> dict[str, str]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        mu = doc[0].get_text()
    pdf = pypdfium2.PdfDocument(data)
    try:
        pd = pdf[0].get_textpage().get_text_range()
    finally:
        pdf.close()
    return {"mupdf": mu, "pdfium": pd.replace("\r\n", "\n")}


def _compare(original: bytes, result: bytes, region: list[float]) -> Image.Image:
    x0, y0, x1, y1 = visual.mask_pixels(original, 0, region)
    box = (max(0, x0 - 40), max(0, y0 - 20), x1 + 40, y1 + 20)
    tiles = []
    for engine in ("pdfium", "mupdf"):
        for data in (original, result):
            tiles.append(visual.render(engine, data).crop(box))
    width, height = tiles[0].size
    sheet = Image.new("RGB", (width * 2 + 8, height * 2 + 8), "white")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 2) * (width + 8), (i // 2) * (height + 8)))
    return sheet


def run_case(out_dir: Path, case_id: str, fid: str, old: str, new: str, region_text: str) -> dict:
    region = [float(v) for v in region_text.split(",")]
    case_dir = out_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    document = analyzer.open_document(str(visual.FILES / f"{fid}.pdf"))
    try:
        target = span.find(document, 0, old)
        plan = edit.plan_text_edit(document, {"target_id": target.span_id, "new_text": new,
                                              "editable_region": region})  # fmt: skip
        (case_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), "utf-8")
        if not plan["ready"]:
            return {"case": case_id, "fixture": fid, "ready": False,
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
    before, after = _texts(original), _texts(result)
    extraction = {
        engine: {
            "new_text_found": _flat(new) in _flat(after[engine]),
            "old_count_before": before[engine].count(old),
            "old_count_after": after[engine].count(old),
            "after_text": after[engine],
        }
        for engine in ("mupdf", "pdfium")
    }
    (case_dir / "extraction.json").write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _compare(original, result, region).save(case_dir / "compare.png", optimize=True)
    report = exported["validation_report"]
    return {
        "case": case_id, "fixture": fid, "ready": True, "mode": plan["mode"],
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "output_sha256": exported["output_hash"],
        "validation_ok": report["ok"], "content_changes": len(report["content_changes"]),
        "resource_changes": report["resource_changes"],
        "font_changes": plan["font_changes"], "warnings": plan["warnings"],
        "extraction_new_found": {e: extraction[e]["new_text_found"] for e in extraction},
    }  # fmt: skip


def main(out_dir: Path) -> int:
    summary = [run_case(out_dir, *case) for case in cases()]
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for entry in summary:
        print(entry["case"], entry.get("mode"), entry.get("validation_ok"),
              entry.get("extraction_new_found", entry.get("reasons")))  # fmt: skip
    return 0 if all(e["ready"] and e["validation_ok"] for e in summary) else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports/P2/evidence"))
