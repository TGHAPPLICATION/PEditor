"""P8 盲測工具 `peditor blind-run`：結果只含判定與結果碼，不含文件文字、新文字或路徑（G8-03）。"""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_blind_run_outputs_codes_only(tmp_path):
    folder = tmp_path / "blind-secret-folder"
    folder.mkdir()
    for fid in ("T01", "F03", "U02"):
        shutil.copy(FILES / f"{fid}.pdf", folder / f"{fid}.pdf")
    cases = tmp_path / "cases.csv"
    with open(cases, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["fixture_id", "original_text", "new_text", "page_index",
                         "editable_region_pt"])  # fmt: skip
        writer.writerow(["T01", "衛生局", "測試局", "0", ""])
        writer.writerow(["F03", "吉田", "𠮷田", "0", ""])
    out = tmp_path / "result.json"
    run = subprocess.run(
        [sys.executable, "-P", "-m", "peditor", "blind-run", str(folder), "--cases", str(cases),
         "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8", timeout=300,
    )  # fmt: skip
    assert run.returncode == 0, run.stderr
    text = out.read_text(encoding="utf-8")
    for secret in ("衛生局", "測試局", "吉田", "𠮷", str(tmp_path), "blind-secret-folder"):
        assert secret not in text, secret
    results = {r["fixture_id"]: r for r in json.loads(text)["results"]}
    assert results["T01"]["edit"]["ready"] and results["T01"]["edit"]["validation_ok"]
    assert results["F03"]["edit"]["reasons"] == ["GLYPH_MISSING"]
    assert results["U02"]["document"] == {"status": "reject", "reasons": ["ENCRYPTED_DOCUMENT"]}
    assert not (tmp_path / ".result-work").exists()  # 暫存的另存結果不保留
    rerun = subprocess.run([sys.executable, "-P", "-m", "peditor", "blind-run", str(folder),
                            "--out", str(out)], capture_output=True, timeout=120)  # fmt: skip
    assert rerun.returncode == 2  # 不覆寫既有結果
