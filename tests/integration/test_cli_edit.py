"""`peditor edit-text`：尋找、計畫、套用、驗證後另存（spec P2 輸出）。"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _run(pdf: Path, out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "peditor", "edit-text", str(pdf), "--out", str(out), *extra],
        capture_output=True,
        timeout=120,
    )


def test_edit_text_writes_output_plan_and_validation(available_rows, tmp_path):
    row = next(r for r in available_rows if r["fixture_id"] == "T01")
    src = FILES / "T01.pdf"
    result = _run(src, tmp_path, "--find", row["original_text"], "--new", row["new_text"],
                  "--region", row["editable_region_pt"])  # fmt: skip
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    output = (tmp_path / "output.pdf").read_bytes()
    assert summary == {"mode": "A", "output_hash": hashlib.sha256(output).hexdigest()}
    plan = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    assert plan["ready"] and plan["target"]["change"]["new_text"] == "測試"
    validation = json.loads((tmp_path / "validation.json").read_text(encoding="utf-8"))
    assert validation["source_sha256"] == row["sha256"]
    assert validation["validation_report"]["ok"]
    assert len(validation["validation_report"]["content_changes"]) == 1
    assert hashlib.sha256(src.read_bytes()).hexdigest() == row["sha256"]  # 原檔不變

    again = _run(src, tmp_path, "--find", row["original_text"], "--new", row["new_text"])
    assert again.returncode == 2 and b"SAVE_FAILED" in again.stderr
    assert (tmp_path / "output.pdf").read_bytes() == output  # 不覆寫


def test_unsupported_edit_writes_plan_only(available_rows, tmp_path):
    row = next(r for r in available_rows if r["fixture_id"] == "F03")
    result = _run(FILES / "F03.pdf", tmp_path, "--find", row["original_text"],
                  "--new", row["new_text"], "--policy", "a_only")  # fmt: skip
    assert result.returncode == 3
    assert b"GLYPH_MISSING" in result.stderr
    assert not (tmp_path / "output.pdf").exists()
    assert json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))["ready"] is False
    # 錯誤訊息不含檔案路徑或文件原文（CLAUDE.md）
    assert str(FILES).encode() not in result.stdout + result.stderr
    assert row["original_text"].encode() not in result.stderr
