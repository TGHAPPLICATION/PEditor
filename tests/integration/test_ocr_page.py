"""ADR-0035：worker 操作 ocr_page。Windows／macOS 在 CI 實際以作業系統 OCR 辨識合成掃描頁；
其他平台只驗證「不支援」的回應與參數檢查。
CI 設 LUMICAT_REQUIRE_OCR=1：缺繁中辨識語言時失敗而不是略過。"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

from lumicat.core.service import DocumentService, ServiceError

ROOT = Path(__file__).resolve().parents[2]
FILES = ROOT / "tests" / "fixtures" / "files"
SPEC = importlib.util.spec_from_file_location(
    "ocr_benchmark", ROOT / "scripts" / "ocr_benchmark.py"
)
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)
NATIVE = sys.platform in ("win32", "darwin")


def test_bad_page_index_rejected():
    with DocumentService() as service:
        doc = service.open_document(FILES / "F04.pdf")["document_id"]
        for bad in (-1, 1, "0", True):
            with pytest.raises(ServiceError) as info:
                service.ocr_page(doc, bad)
            assert info.value.code == "INVALID_REQUEST"


@pytest.mark.skipif(NATIVE, reason="此平台有作業系統 OCR，改由下一個測試實際辨識")
def test_unavailable_on_other_platforms():
    with DocumentService() as service:
        doc = service.open_document(FILES / "F04.pdf")["document_id"]
        with pytest.raises(ServiceError) as info:
            service.ocr_page(doc, 0)
        assert info.value.code == "OCR_UNAVAILABLE"


@pytest.mark.skipif(not NATIVE, reason="作業系統 OCR 只在 Windows／macOS")
def test_recognizes_scanned_traditional_chinese(tmp_path):
    with DocumentService() as service:
        try:
            name, count, acc, seconds = bench.measure("T05", service, tmp_path)
        except ServiceError as exc:
            if exc.code == "OCR_LANGUAGE_MISSING" and os.environ.get("LUMICAT_REQUIRE_OCR") != "1":
                pytest.skip("本機未安裝繁體中文辨識語言")
            raise
    print(f"OCR {sys.platform} {name}: {count} 字，正確率 {acc:.1%}，{seconds:.2f} 秒")
    # 乾淨的合成掃描頁（200 dpi）：門檻先訂 80%，實測後由工程師調整（P14 計畫驗收標準）
    assert acc >= 0.8


def test_accuracy_metric():
    assert bench.accuracy("臺北市政府衛生局", "臺北市政府衛生局") == 1.0
    assert bench.accuracy("臺北市政府", "台北市政府") == 0.8  # 一字錯
    assert bench.accuracy("（第１條）", "(第1條)") == 1.0  # 標點、全半形不計
    assert bench.accuracy("", "") == 1.0


def test_blank_render_fixture_not_counted(tmp_path):
    """T01、F02 的原檔在 MuPDF 畫面空白（PREVIEW_UNRELIABLE），不能當掃描樣本
    （CI 量測曾因此得 0%）。"""
    assert not bench.make_scanned(FILES / "T01.pdf", tmp_path / "t01.pdf")
    assert bench.make_scanned(FILES / "T05.pdf", tmp_path / "t05.pdf")
