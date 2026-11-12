"""P8 授權核對 F1：安裝包的 licenses/ 收齊隨包元件的授權全文（packaging/build_release.py）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packaging"))

import build_release  # noqa: E402


def test_collect_licenses_has_required_texts(tmp_path):
    found = build_release.collect_licenses(tmp_path / "licenses")
    assert set(build_release.REQUIRED_LICENSES) <= set(found)
    qt = {"pyside6-essentials", "shiboken6"}  # wheel 沒附授權檔，由 qt/ 的 LGPL／GPL 全文涵蓋
    for name in set(build_release.LICENSED) - qt:  # 其餘隨包套件都至少有一個授權檔
        assert any(f.startswith(f"{name}/") for f in found), name
    lgpl = (tmp_path / "licenses" / "qt" / "LGPL-3.0-only.txt").read_text(encoding="utf-8")
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in lgpl and "Version 3" in lgpl


def test_release_docs_include_notice():
    assert {"LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"} <= set(build_release.DOCS)
    root = Path(build_release.ROOT)
    notice = (root / "NOTICE").read_text(encoding="utf-8")
    assert "AGPL-3.0-only" in notice and "WITHOUT ANY" in notice
    assert "https://github.com/TGHAPPLICATION/PEditor" in notice
