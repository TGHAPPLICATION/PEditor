"""P2 視覺基準實測（spec §8.2「門檻在 P0/P2 用基準實測後鎖定」、G2-21）。

對每個可套用的文字編輯案例，以同引擎（MuPDF、PDFium；ADR-0015 例外只用 PDFium）比較原／新渲染，
記錄改動區 +2 pt 外的超標像素比例、最大通道差、新文字原點與計畫的偏差，輸出 JSON 供報告引用。

  uv run python scripts/p2_visual_baseline.py reports/P2/visual_baseline.json
"""

from __future__ import annotations

import csv
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "integration"))

import pymupdf  # noqa: E402
import pypdfium2.version  # noqa: E402
import visual  # noqa: E402


def cases():
    rows = visual.manifest()
    out = [(fid, r["original_text"], r["new_text"], r["editable_region_pt"])
           for fid, r in rows.items()
           if r["expected"] == "support" and r["new_text"] and fid[0] in "TFL"
           and r["status"] == "available"]  # fmt: skip
    with open(visual.FIXTURES / "edit_cases.csv", encoding="utf-8", newline="") as fh:
        out += [(c["fixture_id"], c["original_text"], c["new_text"], c["editable_region_pt"])
                for c in csv.DictReader(fh) if not c["after_case"]]  # fmt: skip
    return out


def measure(fid, old, new, region_text):
    region = [float(v) for v in region_text.split(",")]
    original, result, plan = visual.apply_manifest_edit(fid, old, new, region)
    entry = {"fixture_id": fid, "mode": plan["mode"], "ready": plan["ready"],
             "reasons": plan["unsupported_reasons"]}  # fmt: skip
    if result is None:
        return entry
    mask = visual.mask_pixels(original, 0, region)
    start = plan["geometry"]["baseline_start"]
    residual = plan["geometry"]["pdfium_width_residual_pt"]
    entry["pdfium_width_residual_pt"] = residual
    entry["adr0019"] = bool(residual) and fid not in visual.MUPDF_BLANK
    entry["engines"] = {}
    for engine in ("mupdf", "pdfium"):
        before, after = visual.render(engine, original), visual.render(engine, result)
        stats = visual.diff_stats(before, after, mask)
        stats["used_for_gate"] = engine in visual.engines(fid)
        changed = plan["target"]["change"]["new_text"]
        found = visual.char_origins(engine, result, changed)
        offsets = [max(abs(o[0][0] - start[0]), abs(o[0][1] - start[1])) for o in found]
        stats["start_offset_pt"] = round(min(offsets), 4) if offsets else None
        entry["engines"][engine] = stats
    return entry


def main(out: Path) -> int:
    results = [measure(*case) for case in cases()]
    report = {
        "dpi": visual.DPI,
        "channel_tol": visual.CHANNEL_TOL,
        "mask_margin_pt": visual.MARGIN_PT,
        "platform": f"{platform.system()} {platform.machine()}",
        "pymupdf": pymupdf.VersionBind,
        "pypdfium2": str(pypdfium2.version.PYPDFIUM_INFO),
        "pdfium": str(pypdfium2.version.PDFIUM_INFO),
        "cases": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for entry in results:
        cells = []
        for engine, s in entry.get("engines", {}).items():
            flag = "*" if s["used_for_gate"] else " "
            cells.append(
                f"{engine}{flag} out={s['over_outside']:>4} frac={s['outside_fraction']:.6f} "
                f"max={s['max_channel_diff']:>3} start={s['start_offset_pt']}"
            )
        note = " ADR-0019" if entry.get("adr0019") else ""
        print(entry["fixture_id"], entry["mode"], " | ".join(cells) or entry["reasons"], note)
    return 0


if __name__ == "__main__":
    sys.exit(
        main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports/P2/visual_baseline.json")
    )
