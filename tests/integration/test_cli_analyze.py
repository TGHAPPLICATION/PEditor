"""G1-07：`peditor analyze` 輸出 JSON 分析報告與頁面 PNG。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _run(pdf: Path, out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "peditor", "analyze", str(pdf), "--out", str(out), *extra],
        capture_output=True,
        timeout=120,
    )


# T07（LibreOffice）另驗渲染非空白：T01 的 CFF 子集字型在 MuPDF 1.28.2 渲染空白（P1 報告 §9）
@pytest.mark.parametrize("fid", ["T01", "T07"])
def test_json_report_and_png(available_rows, tmp_path, fid):
    row = next(r for r in available_rows if r["fixture_id"] == fid)
    result = _run(FILES / f"{fid}.pdf", tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["sha256"] == row["sha256"]
    assert report["assessment"]["document"]["status"] == "support"
    assert len(report["pages"]) == report["page_count"] == 1
    assert report["pages"][0]["text_targets"]

    png = tmp_path / "page-0001.png"
    with Image.open(png) as image:
        assert image.format == "PNG"
        # 150 DPI 的 A4：595.28 pt × 150/72 ≈ 1240 px
        assert abs(image.size[0] - 1240) <= 1 and abs(image.size[1] - 1754) <= 1
        if fid == "T07":
            dark = sum(image.convert("L").histogram()[:128])
            assert dark > 100


def test_rejected_document_reports_reason_without_path(tmp_path):
    result = _run(FILES / "U02.pdf", tmp_path, "--no-png")
    assert result.returncode == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["assessment"]["document"] == {
        "status": "reject",
        "reasons": ["ENCRYPTED_DOCUMENT"],
    }
    assert str(FILES).encode() not in result.stdout + result.stderr
    assert not list(tmp_path.glob("*.png"))
