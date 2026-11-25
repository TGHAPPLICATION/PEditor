"""ADR-0035：OCR 輔助函式（與平台無關的部分）。"""

from pathlib import Path

import pymupdf

from lumicat.core.limits import MAX_RENDER_DPI, OCR_MAX_SIDE_PX
from lumicat.worker import ocr

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def test_join_words_no_space_between_chinese():
    # Windows OCR 的中文以單字為「詞」；line.text 會變成「臺 北 市」
    assert ocr.join_words(["臺", "北", "市", "政", "府"]) == "臺北市政府"
    assert ocr.join_words(["COVID", "19", "疫", "苗"]) == "COVID 19疫苗"
    assert ocr.join_words(["第", "3", "條"]) == "第3條"
    assert ocr.join_words([]) == ""


def test_order_lines_top_to_bottom_left_to_right():
    items = [("第二列右", 0.6, 0.30), ("第一列", 0.1, 0.10), ("第二列左", 0.1, 0.302)]
    assert ocr.order_lines(items) == ["第一列", "第二列左 第二列右"]


def test_page_image_is_gray_and_bounded():
    with pymupdf.open(FILES / "T05.pdf") as doc:
        pix = ocr.page_image(doc[0])
        assert pix.n == 1 and not pix.alpha  # 灰階、不透明（Windows GRAY8）
        assert max(pix.width, pix.height) <= OCR_MAX_SIDE_PX
        assert len(pix.samples) == pix.width * pix.height
        big = pymupdf.open()
        page = big.new_page(width=14400, height=14400)  # PDF 最大頁面
        pix = ocr.page_image(page)
        assert max(pix.width, pix.height) <= OCR_MAX_SIDE_PX * 1.01
        assert MAX_RENDER_DPI == 300
