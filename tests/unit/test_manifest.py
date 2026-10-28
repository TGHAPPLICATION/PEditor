"""G0：fixture manifest 結構、群組數量、盲測與 hash 可驗證（spec §5）。"""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
GROUP_COUNTS = {
    "T 基礎文字": 12,
    "F 字型與編碼": 10,
    "L 幾何與背景": 8,
    "I 圖片": 9,
    "B 表格": 8,
    "U 特殊文件": 6,
    "S 損毀與惡意": 8,
}


def test_manifest_rows_match_schema(manifest_rows):
    schema = json.loads((FIXTURES / "manifest.schema.json").read_text(encoding="utf-8"))
    for row in manifest_rows:
        jsonschema.validate(row, schema)


def test_manifest_has_61_fixtures_in_spec_groups(manifest_rows):
    assert len(manifest_rows) == 61
    assert len({r["fixture_id"] for r in manifest_rows}) == 61
    assert Counter(r["group"] for r in manifest_rows) == GROUP_COUNTS
    for row in manifest_rows:
        assert row["group"].startswith(row["fixture_id"][0]), row["fixture_id"]


def test_at_least_12_blind_fixtures_kept_offline(manifest_rows):
    blind = [r for r in manifest_rows if r["blind"] == "true"]
    assert len(blind) >= 12
    for row in blind:
        assert not (FIXTURES / "files" / f"{row['fixture_id']}.pdf").exists(), row["fixture_id"]


def test_first_batch_has_20_reproducible_fixtures_from_two_generators(gen_fixtures):
    reproducible = [f for f in gen_fixtures.SYNTHETIC if f.deterministic]
    assert len(reproducible) >= 20
    assert len({f.generator.split("+")[0] for f in reproducible}) >= 2


def test_committed_fixture_hashes_match_manifest(available_rows):
    for row in available_rows:
        data = (FIXTURES / "files" / f"{row['fixture_id']}.pdf").read_bytes()
        assert hashlib.sha256(data).hexdigest() == row["sha256"], row["fixture_id"]


def test_no_unlisted_files_in_fixture_dir(manifest_rows):
    listed = {f"{r['fixture_id']}.pdf" for r in manifest_rows if r["storage"] == "repo"}
    present = {p.name for p in (FIXTURES / "files").glob("*.pdf")}
    assert present <= listed, present - listed


LOCKED_EDIT_CASES = {  # G2-20：實作前鎖定；修改須在報告說明（不得為通過測試而改）
    "E01": ("T01", "T01", "測試局", "衛生局"),
    "E02": ("F01", "", "臺灣醫衛龜", "醫衛龜臺灣"),
    "E03": ("F04", "", "Hello", "Hi"),
    "E04": ("T02", "", "10 月 31 日", "10 月 13 日"),
}


def test_edit_cases_locked(available_rows):
    import pymupdf

    with open(FIXTURES / "edit_cases.csv", encoding="utf-8", newline="") as fh:
        cases = list(csv.DictReader(fh))
    assert {c["case_id"]: (c["fixture_id"], c["after_case"], c["original_text"], c["new_text"])
            for c in cases} == LOCKED_EDIT_CASES  # fmt: skip
    by_id = {r["fixture_id"]: r for r in available_rows}
    for case in cases:
        row = by_id[case["fixture_id"]]
        assert row["expected"] == "support", case["case_id"]
        if case["after_case"]:  # 接續 manifest 該 fixture 的編輯結果
            assert case["after_case"] == row["fixture_id"]
            assert case["original_text"] == row["new_text"]
        else:
            with pymupdf.open(FIXTURES / "files" / f"{row['fixture_id']}.pdf") as doc:
                text = doc[int(case["page_index"])].get_text()
            assert case["original_text"] in text, case["case_id"]
    manifest_ops = [r for r in available_rows if r["expected"] == "support" and r["new_text"]
                    and r["fixture_id"][0] in "TFL"]  # fmt: skip
    assert len(manifest_ops) + len(cases) >= 20  # spec G2-1


def test_qpdf_warnings_recorded(gen_fixtures, manifest_rows):
    """G2-09：manifest 記錄每份 repo fixture 原有的 qpdf 問題數（spec §8.2）。"""
    for row in manifest_rows:
        path = FIXTURES / "files" / f"{row['fixture_id']}.pdf"
        expected = gen_fixtures.qpdf_warning_count(path) if path.exists() else ""
        assert row["qpdf_warnings"] == expected, row["fixture_id"]


def test_synthetic_rows_are_defined_in_generator(gen_fixtures, available_rows):
    synthetic = {
        r["fixture_id"]
        for r in available_rows
        if r["generator"] in {"pymupdf", "reportlab", "pymupdf+pikepdf"}
    }
    assert synthetic == set(gen_fixtures.BY_ID)
