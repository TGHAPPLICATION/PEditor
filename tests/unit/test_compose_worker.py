"""P9-02、P9-04：worker compose_pages 的參數驗證與輸出驗證失敗路徑（直接呼叫 worker 模組）。"""

import pymupdf
import pytest

from peditor.core.limits import MAX_COMPOSE_SOURCES
from peditor.core.protocol import ProtocolError
from peditor.worker import pages


def _sample(path, count=2):
    doc = pymupdf.open()
    for i in range(count):
        doc.new_page(width=200, height=200).insert_text((40, 100), f"P{i}")
    doc.save(path)
    doc.close()
    return str(path)


@pytest.mark.parametrize("plan", [
    [[True, 0]], [[0, False]], [[0, 0, 0]], [[0]], ["0,0"], [[0, 0], [0, 0]], [], [[0, 1.0]],
])  # fmt: skip
def test_rejects_bad_plans(tmp_path, plan):
    a = _sample(tmp_path / "a.pdf")
    with pytest.raises(ProtocolError) as info:
        pages.compose_pages({"sources": [a], "plan": plan, "destination": str(tmp_path / "o.pdf")})
    assert info.value.code == "INVALID_REQUEST"
    assert not (tmp_path / "o.pdf").exists()


def test_rejects_too_many_sources(tmp_path):
    a = _sample(tmp_path / "a.pdf", 1)
    params = {"sources": [a] * (MAX_COMPOSE_SOURCES + 1), "plan": [[0, 0]],
              "destination": str(tmp_path / "o.pdf")}  # fmt: skip
    with pytest.raises(ProtocolError, match="來源檔清單"):
        pages.compose_pages(params)


def test_rejects_total_bytes(tmp_path, monkeypatch):
    a = _sample(tmp_path / "a.pdf", 1)
    monkeypatch.setattr(pages, "MAX_COMPOSE_BYTES", 10)
    with pytest.raises(ProtocolError) as info:
        pages.compose_pages(
            {"sources": [a], "plan": [[0, 0]], "destination": str(tmp_path / "o.pdf")}
        )
    assert info.value.code == "RESOURCE_LIMIT"


def test_validation_failure_writes_nothing(tmp_path, monkeypatch):
    a = _sample(tmp_path / "a.pdf")
    calls = iter(range(100))
    monkeypatch.setattr(pages, "_content", lambda page: [next(calls)])  # 每次不同：比對必失敗
    with pytest.raises(ProtocolError) as info:
        pages.compose_pages(
            {"sources": [a], "plan": [[0, 1]], "destination": str(tmp_path / "o.pdf")}
        )
    assert info.value.code == "VALIDATION_FAILED"
    assert not (tmp_path / "o.pdf").exists()
