"""作業系統內建 OCR（ADR-0035；只在 worker 使用）：把頁面畫成灰階點陣，交給
Windows.Media.Ocr（PyWinRT）或 macOS Vision（PyObjC）辨識繁體中文。只讀、不改 PDF。

頁面在 worker 以 MuPDF 渲染（與 render_page 相同的超限頁檢查）；辨識引擎只看到點陣圖，不碰 PDF。
辨識結果與錯誤訊息不寫日誌；錯誤訊息不含路徑或文件內容。
"""

from __future__ import annotations

import sys

import pymupdf

from lumicat.core.limits import MAX_EXTRACT_CHARS, MAX_RENDER_DPI, OCR_MAX_SIDE_PX
from lumicat.core.protocol import ProtocolError
from lumicat.worker import analyzer

# Windows OCR 語言：優先台灣正體，其次其他正體中文
WINDOWS_LANGUAGES = ("zh-hant-tw", "zh-tw", "zh-hant", "zh-hant-hk", "zh-hk")
MAC_LANGUAGES = ["zh-Hant", "en-US"]


def recognize_page(document: analyzer.Document, page_index) -> dict:
    analyzer._require_pages(document)
    page_index = analyzer._check_index(document, page_index)
    analyzer.inspect_page(document, page_index)
    if page_index in document.limited_pages:
        raise ProtocolError("RESOURCE_LIMIT", "頁面內容超過處理上限")
    pix = page_image(document.mu[page_index])
    if sys.platform == "win32":
        lines = _windows(pix)
    elif sys.platform == "darwin":
        lines = _macos(pix)
    else:
        raise ProtocolError("OCR_UNAVAILABLE", "此作業系統沒有內建文字辨識")
    text = "\n".join(line for line in lines if line)
    if len(text) > MAX_EXTRACT_CHARS:
        raise ProtocolError("RESOURCE_LIMIT", "辨識文字超過擷取上限")
    return {"text": text, "lines": len(lines)}


def page_image(page: pymupdf.Page) -> pymupdf.Pixmap:
    """灰階、不透明；長邊不超過 OCR_MAX_SIDE_PX、解析度不超過 MAX_RENDER_DPI。"""
    side = max(page.rect.width, page.rect.height) or 1
    zoom = min(MAX_RENDER_DPI / 72, OCR_MAX_SIDE_PX / side)
    return page.get_pixmap(
        matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False
    )


def join_words(words: list[str]) -> str:
    """Windows OCR 的中文以單字為「詞」，line.text 會在每個字之間加空白；
    只在兩邊都是拉丁字母或數字時保留空白（例如「COVID 19」），中文之間不加。"""
    out = ""
    for word in words:
        if out and word and _latin(out[-1]) and _latin(word[0]):
            out += " "
        out += word
    return out


def _latin(ch: str) -> bool:
    return ch.isascii() and ch.isalnum()


def order_lines(items: list[tuple[str, float, float]]) -> list[str]:
    """(文字, x, 上緣 y；y 由上往下增加) → 由上而下、同一列由左而右的文字。"""
    rows: list[list[tuple[str, float, float]]] = []
    for item in sorted(items, key=lambda i: (i[2], i[1])):
        if rows and abs(rows[-1][0][2] - item[2]) < 0.005:  # 正規化座標：同一列
            rows[-1].append(item)
        else:
            rows.append([item])
    return [" ".join(t for t, _x, _y in sorted(row, key=lambda i: i[1])) for row in rows]


def _windows(pix: pymupdf.Pixmap) -> list[str]:
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.media.ocr import OcrEngine
    except ImportError as exc:
        raise ProtocolError("OCR_UNAVAILABLE", "無法載入系統文字辨識元件") from exc
    available = {
        lang.language_tag.lower(): lang for lang in OcrEngine.available_recognizer_languages
    }
    tag = next((t for t in WINDOWS_LANGUAGES if t in available), None)
    if tag is None:
        raise ProtocolError("OCR_LANGUAGE_MISSING", "系統未安裝繁體中文文字辨識")
    engine = OcrEngine.try_create_from_language(Language(available[tag].language_tag))
    if engine is None:
        raise ProtocolError("OCR_LANGUAGE_MISSING", "系統未安裝繁體中文文字辨識")
    if max(pix.width, pix.height) > OcrEngine.max_image_dimension:
        raise ProtocolError("RESOURCE_LIMIT", "頁面影像超過系統文字辨識的尺寸上限")
    bitmap = SoftwareBitmap.create_copy_from_buffer(
        pix.samples, BitmapPixelFormat.GRAY8, pix.width, pix.height
    )
    try:
        result = engine.recognize_async(bitmap).get()
    except OSError as exc:  # WinRT 錯誤以 OSError 拋出；訊息不轉給使用者
        raise ProtocolError("OCR_UNAVAILABLE", "系統文字辨識失敗") from exc
    return [join_words([w.text for w in line.words]) for line in result.lines]


def _macos(pix: pymupdf.Pixmap) -> list[str]:
    try:
        import Vision
        from Foundation import NSData
    except ImportError as exc:
        raise ProtocolError("OCR_UNAVAILABLE", "無法載入系統文字辨識元件") from exc
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)  # .fast 認不出中文
    if not hasattr(request, "supportedRecognitionLanguagesAndReturnError_"):  # macOS 13 以前
        raise ProtocolError("OCR_UNAVAILABLE", "系統文字辨識版本過舊")
    supported, _error = request.supportedRecognitionLanguagesAndReturnError_(None)
    if not supported or "zh-Hant" not in list(supported):
        raise ProtocolError("OCR_LANGUAGE_MISSING", "系統的文字辨識不支援繁體中文")
    request.setRecognitionLanguages_(MAC_LANGUAGES)
    request.setUsesLanguageCorrection_(True)
    png = pix.tobytes("png")
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
        NSData.dataWithBytes_length_(png, len(png)), {}
    )
    ok, _error = handler.performRequests_error_([request], None)
    if not ok:
        raise ProtocolError("OCR_UNAVAILABLE", "系統文字辨識失敗")
    items = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if not candidates:
            continue
        box = observation.boundingBox()  # 正規化座標，原點在左下
        items.append(
            (str(candidates[0].string()), box.origin.x, 1 - (box.origin.y + box.size.height))
        )
    return order_lines(items)
