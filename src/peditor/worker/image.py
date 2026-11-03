"""圖片替換：單一出現位置（spec P5、§7 plan_image_edit；ADR-0009、ADR-0022；只在 worker 使用）。

- 新圖：主行程把使用者選的 PNG／JPEG 位元組交給 worker 登記（asset_id＝SHA-256）。先讀檔頭檢查
  格式與像素上限，通過才以 PyMuPDF 解碼。
- copy-on-write：新增圖片 XObject 與新資源名稱，只把選定的那一個 `Do` 改成新名稱；原圖物件不動，
  同頁或其他頁的其他出現位置仍指向原圖。頁面 /Resources 先複製一份給這頁。
- 變換矩陣、剪裁、圖形狀態（透明度）都不動：新圖畫進原本的單位正方形。新圖比例與外框不同時，
  等比縮放置中、兩側補透明（ADR-0022 §2）。透明遮罩由新圖自己的透明通道決定，不沿用原圖的 SMask。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import secrets
import struct
import zlib
from dataclasses import dataclass

import pikepdf
import pymupdf

from peditor.core.editplan import EditPlan, parse_target_id, validate_image_params
from peditor.core.limits import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS
from peditor.core.protocol import ProtocolError
from peditor.worker import analyzer, edit

ASPECT_TOL = 0.01  # 新圖與外框長寬比相差 1% 以內視為相同，不補邊
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SOF = frozenset({0xC0, 0xC1, 0xC2})  # 基線、擴充、漸進（Huffman）
# 無損、階層、算術編碼等其他 SOF：PDF 閱讀器支援不一，拒絕
_JPEG_OTHER_SOF = frozenset({0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})


@dataclass
class Asset:
    asset_id: str
    data: bytes
    format: str  # "png"、"jpeg"
    width: int
    height: int
    components: int  # 1＝灰階、3＝RGB（解碼後）
    has_alpha: bool  # 有透明通道且不是全不透明


@dataclass
class ImagePending:
    """待套用的圖片替換（worker 內部）；與 edit._Pending 共用 apply／preview／replay 流程。"""

    plan: EditPlan
    stream: tuple[int, int]
    op_index: int
    name: str  # 原資源名稱
    new_name: str
    remove_old: bool  # 這頁已沒有其他地方用原名稱：移除，完整另存時原圖不再保留
    asset: Asset
    padding: tuple[int, int, int, int] | None  # (寬, 高, x 偏移, y 偏移)；None＝不補邊
    params: dict
    sync: None = None
    op: str = "image"


def register_asset(document: analyzer.Document, params: dict) -> dict:
    """登記新圖。keep 為要保留的其他 asset_id（主行程依 command log 決定）；未給時全部保留。"""
    data, keep = params.get("data"), params.get("keep")
    if not isinstance(data, str):
        raise ProtocolError("INVALID_REQUEST", "缺少圖片資料")
    if keep is not None and not (isinstance(keep, list) and all(isinstance(k, str) for k in keep)):
        raise ProtocolError("INVALID_REQUEST", "keep 格式錯誤")
    if len(data) > (MAX_IMAGE_BYTES + 2) // 3 * 4:
        raise ProtocolError("RESOURCE_LIMIT", "圖片檔超過大小上限")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProtocolError("INVALID_REQUEST", "圖片資料格式錯誤") from exc
    asset = load_asset(raw)
    if keep is not None:
        document.assets = {k: v for k, v in document.assets.items() if k in keep}
    document.assets[asset.asset_id] = asset
    return {"asset_id": asset.asset_id, "format": asset.format, "width": asset.width,
            "height": asset.height, "has_alpha": asset.has_alpha}  # fmt: skip


def probe(data: bytes) -> tuple[str, int, int]:
    """只讀檔頭：格式與像素尺寸。不支援的格式回 UNSUPPORTED_FEATURE，超過上限回 RESOURCE_LIMIT。"""
    if len(data) > MAX_IMAGE_BYTES:
        raise ProtocolError("RESOURCE_LIMIT", "圖片檔超過大小上限")
    if data.startswith(_PNG_SIGNATURE):
        if len(data) < 24 or data[12:16] != b"IHDR" or not _png_complete(data):
            raise ProtocolError("UNSUPPORTED_FEATURE", "圖片檔損壞")
        fmt, (width, height) = "png", struct.unpack(">II", data[16:24])
    elif data.startswith(b"\xff\xd8"):
        fmt, (width, height) = "jpeg", _jpeg_size(data)
    else:
        raise ProtocolError("UNSUPPORTED_FEATURE", "只支援 PNG 與 JPEG 圖片")
    if width < 1 or height < 1:
        raise ProtocolError("UNSUPPORTED_FEATURE", "圖片檔損壞")
    if width * height > MAX_IMAGE_PIXELS:
        raise ProtocolError("RESOURCE_LIMIT", "圖片像素超過上限")
    return fmt, width, height


def _png_complete(data: bytes) -> bool:
    """MuPDF 會把截斷或損壞的 PNG 補成部分影像而不報錯：
    先確認每個區塊 CRC 正確、有 IDAT 且以 IEND 結束。
    """
    pos, seen_data = 8, False
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        end = pos + 12 + length
        if end > len(data):
            return False
        kind = data[pos + 4 : pos + 8]
        if zlib.crc32(data[pos + 4 : end - 4]) != struct.unpack(">I", data[end - 4 : end])[0]:
            return False
        if kind == b"IEND":
            return seen_data
        seen_data |= kind == b"IDAT"
        pos = end
    return False


def _jpeg_size(data: bytes) -> tuple[int, int]:
    """走訪 JPEG 標記到第一個 SOF：只收 8 位元、1 或 3 個色彩成分（灰階、RGB）。"""
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker == 0xFF:  # 填充位元組
            i += 1
            continue
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # 無長度欄位的標記
            i += 2
            continue
        if marker in (0xD9, 0xDA):  # 影像結束或掃描開始之前都沒有 SOF
            break
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if length < 2:
            break
        if marker in _JPEG_OTHER_SOF:
            raise ProtocolError("UNSUPPORTED_FEATURE", "不支援此 JPEG 編碼方式")
        if marker in _JPEG_SOF:
            if i + 10 > len(data):
                break
            precision, height, width, components = struct.unpack(">BHHB", data[i + 4 : i + 10])
            if precision != 8:
                raise ProtocolError("UNSUPPORTED_FEATURE", "只支援 8 位元 JPEG")
            if components not in (1, 3):
                raise ProtocolError("UNSUPPORTED_FEATURE", "不支援 CMYK 等非灰階／RGB 的 JPEG")
            if data.rfind(b"\xff\xd9") < i:  # 沒有影像結束標記：截斷（MuPDF 不會報錯）
                break
            return width, height
        i += 2 + length
    raise ProtocolError("UNSUPPORTED_FEATURE", "圖片檔損壞")


def load_asset(data: bytes) -> Asset:
    fmt, width, height = probe(data)
    pix = _decode(data, width, height)
    has_alpha = bool(pix.alpha) and not _opaque(pix)
    return Asset(hashlib.sha256(data).hexdigest(), data, fmt, width, height, pix.n - pix.alpha,
                 has_alpha)  # fmt: skip


def _decode(data: bytes, width: int, height: int) -> pymupdf.Pixmap:
    try:
        pix = pymupdf.Pixmap(data)
    except Exception as exc:  # noqa: BLE001 — MuPDF 對損壞的圖片拋出多種例外
        raise ProtocolError("UNSUPPORTED_FEATURE", "無法解碼圖片") from exc
    if (pix.width, pix.height) != (width, height):
        raise ProtocolError("UNSUPPORTED_FEATURE", "圖片檔損壞")
    if pix.colorspace is None or pix.colorspace.n not in (1, 3):
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return pix


def _opaque(pix: pymupdf.Pixmap) -> bool:
    alpha = pix.samples[pix.n - 1 :: pix.n]
    return alpha.count(255) == len(alpha)


def padding(width: int, height: int, frame: tuple[float, float]) -> tuple[int, ...] | None:
    """新圖等比放進外框（寬, 高 pt）所需的畫布：(寬, 高, x 偏移, y 偏移)；比例相同回 None。"""
    frame_ratio = frame[0] / frame[1]
    ratio = width / height
    if abs(ratio / frame_ratio - 1) <= ASPECT_TOL:
        return None
    if ratio > frame_ratio:  # 新圖較寬：上下補邊
        canvas_h = max(height, round(width / frame_ratio))
        size = (width, canvas_h, 0, (canvas_h - height) // 2)
    else:
        canvas_w = max(width, round(height * frame_ratio))
        size = (canvas_w, height, (canvas_w - width) // 2, 0)
    if size[0] * size[1] > MAX_IMAGE_PIXELS:
        raise ProtocolError("RESOURCE_LIMIT", "補邊後圖片像素超過上限")
    return size


def plan_image_edit(document: analyzer.Document, params: dict) -> dict:
    params = validate_image_params(params)
    target_id = params["target_id"]
    page_index = parse_target_id(target_id).page_index
    page_result = analyzer.inspect_page(document, page_index)
    target = next((t for t in page_result["image_targets"] if t["target_id"] == target_id), None)
    use = document.images.get(page_index, {}).get(target_id)
    if target is None or use is None:
        raise ProtocolError("INVALID_REQUEST", "目標不存在")
    asset = document.assets.get(params["asset_id"])
    if not isinstance(asset, Asset):
        raise ProtocolError("INVALID_REQUEST", "圖片未登記")
    plan = EditPlan(
        plan_id=secrets.token_hex(8),
        document_id=document.document_id,
        preconditions={"sha256": document.sha256, "revision": document.revision},
        target={
            "target_id": target_id,
            "page_index": page_index,
            "name": use.name,
            "bbox": target["bbox"],
            "visible_bbox": target["visible_bbox"],
        },  # fmt: skip
        new_text="",
        policy="image",
        mode=None,
        font_policy="keep_original",
        allowed_change_mask=list(target["visible_bbox"]),
        unsupported_reasons=list(target["capability"]["reasons"]),
    )
    if plan.unsupported_reasons:
        return edit._store(document, plan, None)
    if edit._references(document.pike, use.stream) > 1:  # 內容串流被其他頁或重複列出共用
        plan.unsupported_reasons.append("SHARED_RESOURCE_UNSAFE")
        return edit._store(document, plan, None)
    a, _, _, d, _, _ = use.ctm
    try:
        pad = padding(asset.width, asset.height, (a, d))
    except ProtocolError as exc:
        plan.unsupported_reasons.append(exc.code)
        plan.warnings.append(exc.message)
        return edit._store(document, plan, None)
    page = document.pike.pages[page_index]
    new_name = _new_name(page)
    others = [u for u in document.images[page_index].values()
              if u is not use and u.name == use.name and not u.form_path]  # fmt: skip
    remove_old = not others and not _has_type3(page)
    plan.mode = "image"
    plan.geometry = {"image_size": [asset.width, asset.height],
                     "canvas": list(pad[:2]) if pad else [asset.width, asset.height],
                     "offset": list(pad[2:]) if pad else [0, 0]}  # fmt: skip
    plan.resource_changes = [{"page_index": page_index, "kind": "XObject", "added": new_name,
                              "removed": use.name if remove_old else None, "format": asset.format,
                              "smask": asset.has_alpha or bool(pad)}]  # fmt: skip
    if pad:
        plan.warnings.append("新圖比例與外框不同：已等比縮放置中，兩側透明")
    if "/SMask" in use.xobject and not asset.has_alpha and not pad:
        plan.warnings.append("原圖的透明遮罩不沿用；新圖沒有透明部分")
    if target["visible_bbox"] != target["bbox"]:
        plan.warnings.append("原圖經剪裁：新圖只顯示原剪裁範圍內的部分")
    pending = ImagePending(plan, use.stream, use.op_index, use.name, new_name, remove_old, asset,
                           pad, params)  # fmt: skip
    return edit._store(document, plan, pending)


def _new_name(page: pikepdf.Page) -> str:
    xobjects = edit._page_resources(page).get("/XObject")
    names = set(map(str, xobjects.keys())) if isinstance(xobjects, pikepdf.Dictionary) else set()
    n = 1
    while f"/PEditorI{n}" in names:
        n += 1
    return f"/PEditorI{n}"


def _has_type3(page: pikepdf.Page) -> bool:
    """Type3 字型沒有自己的 /Resources 時會用頁面資源，可能畫到原圖名稱：此時不移除原名稱。"""
    fonts = edit._page_resources(page).get("/Font")
    if not isinstance(fonts, pikepdf.Dictionary):
        return False
    return any(isinstance(f, pikepdf.Dictionary) and str(f.get("/Subtype", "")) == "/Type3"
               for f in fonts.values())  # fmt: skip


def rewrite(document: analyzer.Document, pending: ImagePending) -> None:
    pdf = document.pike
    stream = pdf.get_object(pending.stream)
    instructions = list(pikepdf.parse_content_stream(stream))
    inst = instructions[pending.op_index] if pending.op_index < len(instructions) else None
    if (not isinstance(inst, pikepdf.ContentStreamInstruction) or str(inst.operator) != "Do"
            or not inst.operands or str(inst.operands[0]) != pending.name):  # fmt: skip
        raise ProtocolError("VALIDATION_FAILED", "內容與計畫不一致")
    page = pdf.pages[pending.plan.target["page_index"]]
    resources = pikepdf.Dictionary(edit._page_resources(page))  # 頁面資源寫時複製
    xobjects = resources.get("/XObject")
    xobjects = pikepdf.Dictionary(xobjects) if isinstance(xobjects, pikepdf.Dictionary) else (
        pikepdf.Dictionary())  # fmt: skip
    new_image = build_xobject(pdf, pending.asset, pending.padding)
    xobjects[pending.new_name] = pdf.make_indirect(new_image)
    if pending.remove_old:
        del xobjects[pending.name]
    resources.XObject = xobjects
    page.obj.Resources = resources
    instructions[pending.op_index] = pikepdf.ContentStreamInstruction(
        [pikepdf.Name(pending.new_name)], pikepdf.Operator("Do")
    )
    stream.write(pikepdf.unparse_content_stream(instructions))


def build_xobject(pdf: pikepdf.Pdf, asset: Asset, pad) -> pikepdf.Stream:
    """新圖的 Image XObject。JPEG 不需補邊時原樣嵌入（DCTDecode），其餘解碼後以 Flate 壓縮。

    MuPDF 解碼的透明通道是預乘過的色彩，SMask 以 /Matte 黑色宣告（PDF 預乘遮罩），不逐點還原。
    """
    if asset.format == "jpeg" and pad is None:
        return _image(pdf, asset.data, asset.width, asset.height, asset.components, "/DCTDecode")
    pix = _decode(asset.data, asset.width, asset.height)
    if pad is not None:
        if not pix.alpha:
            pix = pymupdf.Pixmap(pix, 1)
        width, height, dx, dy = pad
        canvas = pymupdf.Pixmap(pix.colorspace, width, height, bytes(width * height * pix.n), 1)
        pix.set_origin(dx, dy)
        canvas.copy(pix, pix.irect)
        pix = canvas
    components = pix.n - pix.alpha
    alpha = None
    if pix.alpha and not _opaque(pix):
        alpha = pix.samples[pix.n - 1 :: pix.n]
    color = pymupdf.Pixmap(pix, 0).samples if pix.alpha else pix.samples
    image = _image(pdf, zlib.compress(color), pix.width, pix.height, components, "/FlateDecode")
    if alpha is not None:
        smask = _image(pdf, zlib.compress(alpha), pix.width, pix.height, 1, "/FlateDecode")
        smask.Matte = pikepdf.Array([0] * components)
        image.SMask = pdf.make_indirect(smask)
    return image


def _image(pdf, data: bytes, width: int, height: int, components: int, filter_: str):
    return pikepdf.Stream(pdf, data, {
        "/Type": pikepdf.Name.XObject, "/Subtype": pikepdf.Name.Image, "/Width": width,
        "/Height": height, "/BitsPerComponent": 8,
        "/ColorSpace": pikepdf.Name.DeviceRGB if components == 3 else pikepdf.Name.DeviceGray,
        "/Filter": pikepdf.Name(filter_),
    })  # fmt: skip
