"""圖片替換（G5；spec P5、ADR-0009、ADR-0022）：單一出現位置、copy-on-write、外框與其他頁不變。

真修改證據（比照 spec §8.1）：內容串流只有選定的 `Do` 改名；頁面資源新增新圖；
新圖解碼後就是使用者給的圖；MuPDF 與 PDFium 各自渲染，可改動區域（manifest 事前宣告）
+2 pt 外差異 ≤0.01%，區內顯示新圖；
完整另存後，沒有其他地方使用的原圖不再保留。
"""

import base64
import hashlib
import io
import secrets

import pikepdf
import pytest
import visual
from PIL import Image

from peditor.worker import analyzer, edit, export, image

SUPPORTED = ("I01", "I02", "I03", "I04", "I05", "I06", "I07")
MAGENTA = (255, 0, 255)


def png(size, color=MAGENTA, mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, "PNG")
    return buf.getvalue()


def jpeg(size, color=(0, 0, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG", quality=95)
    return buf.getvalue()


def _row(fid):
    return visual.manifest()[fid]


def _floats(text):
    return [float(v) for v in text.split(",")]


def _target_index(row) -> int:
    return int(row["target"].split("#")[1])


def _frame_png(target, color=MAGENTA) -> bytes:
    """與目標外框（未剪裁的放置範圍）同比例的單色 PNG。"""
    x0, y0, x1, y1 = target["bbox"]
    return png((max(1, round((x1 - x0) * 2)), max(1, round((y1 - y0) * 2))), color)


def _replace(fid, tmp_path, data=None, index=None, page_index=0):
    """以 worker 函式替換一次並另存；回傳（原檔位元組, 輸出位元組, 計畫, 原目標, 驗證報告）。"""
    row = _row(fid)
    document = analyzer.open_document(str(visual.FILES / f"{fid}.pdf"))
    try:
        targets = analyzer.inspect_page(document, page_index)["image_targets"]
        target = targets[_target_index(row) if index is None else index]
        payload = base64.b64encode(data or _frame_png(target)).decode()
        asset = image.register_asset(document, {"data": payload})
        plan = image.plan_image_edit(document, {"target_id": target["target_id"],
                                                "asset_id": asset["asset_id"]})  # fmt: skip
        assert plan["ready"], plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], document.revision)
        dest = tmp_path / f"{fid}-{secrets.token_hex(4)}.pdf"
        report = export.export_document(document, str(dest))["validation_report"]
        return document.original, dest.read_bytes(), plan, target, report
    finally:
        document.close()


def _xobject_raw(data: bytes, page_index: int, name: str) -> bytes:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        return pdf.pages[page_index].obj.Resources.XObject[name].read_raw_bytes()


def _all_stream_raw(data: bytes) -> list[bytes]:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        return [o.read_raw_bytes() for o in pdf.objects if isinstance(o, pikepdf.Stream)]


def _image_targets(data: bytes, page_index: int, tmp_path) -> list[dict]:
    path = tmp_path / f"inspect-{hashlib.sha256(data).hexdigest()[:12]}.pdf"
    path.write_bytes(data)
    document = analyzer.open_document(str(path))
    try:
        return analyzer.inspect_page(document, page_index)["image_targets"]
    finally:
        document.close()


def _output_target(data: bytes, page_index: int, op_index: int, stream_order: int, tmp_path):
    """輸出檔同一位置（同一 content stream 順序、同一運算子索引）的圖片目標。"""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        contents = pdf.pages[page_index].obj.Contents
        stream = (list(contents) if isinstance(contents, pikepdf.Array) else [contents])[
            stream_order
        ].objgen
    return next(t for t in _image_targets(data, page_index, tmp_path)
                if tuple(t["stream"]) == stream and t["op_index"] == op_index)  # fmt: skip


def _stream_order(data: bytes, page_index: int, objgen) -> int:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        contents = pdf.pages[page_index].obj.Contents
        items = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
        return [s.objgen for s in items].index(tuple(objgen))


def _center_pixel(img, data, page_index, box_pt):
    x0, y0, x1, y1 = visual.mask_pixels(data, page_index, box_pt)
    return img.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))


@pytest.mark.parametrize("fid", SUPPORTED)
def test_all_supported_image_cases(fid, tmp_path):
    """G5-01：宣告支援的 I01–I07 都能替換，並交付真修改證據。"""
    row = _row(fid)
    assert row["expected"] == "support"
    original, output, plan, target, report = _replace(fid, tmp_path)
    assert report["ok"], report["failures"]
    assert not report["incremental"] and report["unreachable_objects"] == 0
    added = plan["resource_changes"][0]["added"]
    # 1. 內容差異：只有選定的 Do 改名
    assert [(c["page_index"], c["before"], c["after"]) for c in report["content_changes"]] == [
        (0, [f"{target['name']} Do"], [f"{added} Do"])
    ]
    xobjects = [r for r in report["resource_changes"] if r["kind"] == "XObject"]
    assert xobjects and all(added in r["added"] for r in xobjects)
    # 2. 新圖就是使用者給的圖：尺寸與像素
    with pikepdf.open(io.BytesIO(output)) as pdf:
        new = pdf.pages[0].obj.Resources.XObject[added]
        width, height = int(new.Width), int(new.Height)
        pixels = new.read_bytes()
    assert [width, height] == plan["geometry"]["canvas"]
    assert pixels[:3] == bytes(MAGENTA)
    # 3. 雙引擎：可改動區域 +2 pt 外差異不超標，區內（可見範圍中心）顯示新圖
    region = _floats(row["editable_region_pt"])
    mask = visual.mask_pixels(original, 0, region)
    for engine in visual.engines(fid):
        before, after = visual.render(engine, original), visual.render(engine, output)
        stats = visual.diff_stats(before, after, mask)
        assert stats["outside_fraction"] <= visual.OUTSIDE_LIMIT, (engine, stats)
        r, g, b = _center_pixel(after, output, 0, target["visible_bbox"])
        assert r > 200 and g < 60 and b > 200, (engine, (r, g, b))
    # 4. 沒有其他地方使用的原圖不再保留在輸出中
    old_raw = _xobject_raw(original, 0, target["name"])
    shared = fid in ("I02", "I03")
    assert (old_raw in _all_stream_raw(output)) is shared


@pytest.mark.parametrize("fid,index,other", [("I02", 0, (1, 0)), ("I03", 1, (0, 0))])
def test_only_selected_occurrence_changed(fid, index, other, tmp_path):
    """G5-02：同一 xref 跨頁（I02）或同頁（I03）重用時，只有選定的出現位置改用新圖。"""
    original, output, plan, target, report = _replace(fid, tmp_path, index=index)
    assert report["ok"], report["failures"]
    other_page, other_index = other
    before_other = _image_targets(original, other_page, tmp_path)[other_index]
    assert before_other["xobject"] == target["xobject"]  # 原本確實共用同一個圖片物件
    with pikepdf.open(io.BytesIO(original)) as pdf:
        old_raw = pdf.get_object(tuple(target["xobject"])).read_raw_bytes()
    order = _stream_order(original, other_page, before_other["stream"])
    after_other = _output_target(output, other_page, before_other["op_index"], order, tmp_path)
    assert _xobject_raw(output, other_page, after_other["name"]) == old_raw
    order = _stream_order(original, 0, target["stream"])
    after_selected = _output_target(output, 0, target["op_index"], order, tmp_path)
    assert after_selected["name"] == plan["resource_changes"][0]["added"]
    assert _xobject_raw(output, 0, after_selected["name"]) != old_raw


def test_other_pages_unchanged_and_bbox(tmp_path):
    """G5-03：I02 第 2 頁內容與雙引擎像素完全相同；替換後外框與可見範圍誤差 ≤0.5 pt。"""
    original, output, plan, target, report = _replace("I02", tmp_path)
    assert report["ok"], report["failures"]
    assert all(c["page_index"] == 0 for c in report["content_changes"])
    for engine in visual.engines("I02"):
        before, after = visual.render(engine, original, 1), visual.render(engine, output, 1)
        assert visual.diff_stats(before, after)["over_total"] == 0, engine
    for fid in SUPPORTED:
        original, output, plan, target, _ = _replace(fid, tmp_path)
        order = _stream_order(original, 0, target["stream"])
        new = _output_target(output, 0, target["op_index"], order, tmp_path)
        for key in ("bbox", "visible_bbox"):
            assert max(abs(u - v) for u, v in zip(new[key], target[key], strict=True)) <= (
                visual.POSITION_TOL
            ), (fid, key)
        assert new["capability"]["status"] == "support"


def test_reject_unsupported_mask_clip(tmp_path):
    """G5-04：I09（非矩形剪裁）拒絕；補邊後超過像素上限時拒絕（RESOURCE_LIMIT）。"""
    row = _row("I09")
    document = analyzer.open_document(str(visual.FILES / "I09.pdf"))
    try:
        target = analyzer.inspect_page(document, 0)["image_targets"][_target_index(row)]
        asset = image.register_asset(document, {"data": base64.b64encode(png((10, 10))).decode()})
        plan = image.plan_image_edit(document, {"target_id": target["target_id"],
                                                "asset_id": asset["asset_id"]})  # fmt: skip
        assert not plan["ready"] and plan["unsupported_reasons"] == [row["reason_code"]]
        with pytest.raises(Exception, match="計畫不存在"):
            edit.apply_edit(document, plan["plan_id"], document.revision)
    finally:
        document.close()
    document = analyzer.open_document(str(visual.FILES / "I01.pdf"))
    try:
        target = analyzer.inspect_page(document, 0)["image_targets"][0]  # 外框 2:1
        tall = base64.b64encode(png((1, 6000))).decode()  # 補邊後 12000×6000＝72 MP
        asset = image.register_asset(document, {"data": tall})
        plan = image.plan_image_edit(document, {"target_id": target["target_id"],
                                                "asset_id": asset["asset_id"]})  # fmt: skip
        assert not plan["ready"] and plan["unsupported_reasons"] == ["RESOURCE_LIMIT"]
    finally:
        document.close()


def test_aspect_fit_and_smask(tmp_path):
    """G5-05：比例不同時等比置中、兩側透明；透明遮罩由新圖決定；JPEG 不補邊時原樣嵌入。"""
    # I01 外框 2:1，正方形新圖：畫布 2:1、左右各補 1/4 透明
    original, output, plan, target, report = _replace("I01", tmp_path, data=png((100, 100)))
    assert report["ok"], report["failures"]
    assert plan["geometry"] == {"image_size": [100, 100], "canvas": [200, 100],
                                "offset": [50, 0]}  # fmt: skip
    assert "新圖比例與外框不同：已等比縮放置中，兩側透明" in plan["warnings"]
    added = plan["resource_changes"][0]["added"]
    with pikepdf.open(io.BytesIO(output)) as pdf:
        new = pdf.pages[0].obj.Resources.XObject[added]
        alpha = new.SMask.read_bytes()
        assert list(new.SMask.Matte) == [0, 0, 0]
    assert (
        alpha[:50] == bytes(50) and alpha[50:150] == b"\xff" * 100 and alpha[150:200] == bytes(50)
    )
    x0, y0, x1, y1 = target["bbox"]
    quarter = (x1 - x0) / 4
    for engine in visual.engines("I01"):
        after = visual.render(engine, output)
        left = _center_pixel(after, output, 0, [x0, y0, x0 + quarter, y1])
        middle = _center_pixel(after, output, 0, target["bbox"])
        assert min(left) > 240, (engine, left)  # 透明處露出白色頁面
        assert middle[0] > 200 and middle[1] < 60, (engine, middle)

    # I04 原圖有 SMask：新圖不透明 → 不帶 SMask；新圖半透明 → 新的 SMask，不沿用原圖的
    original, output, plan, target, report = _replace("I04", tmp_path, data=png((300, 150)))
    assert report["ok"] and "原圖的透明遮罩不沿用；新圖沒有透明部分" in plan["warnings"]
    added = plan["resource_changes"][0]["added"]
    with pikepdf.open(io.BytesIO(output)) as pdf:
        assert "/SMask" not in pdf.pages[0].obj.Resources.XObject[added]
    rgba = png((300, 150), (255, 0, 255, 128), "RGBA")
    original, output, plan, target, report = _replace("I04", tmp_path, data=rgba)
    assert report["ok"], report["failures"]
    with pikepdf.open(io.BytesIO(original)) as pdf:
        old_smask = pdf.pages[0].obj.Resources.XObject[target["name"]].SMask.read_raw_bytes()
    with pikepdf.open(io.BytesIO(output)) as pdf:
        smask = pdf.pages[0].obj.Resources.XObject[plan["resource_changes"][0]["added"]].SMask
        assert smask.read_bytes() == bytes([128]) * (300 * 150)
        assert smask.read_raw_bytes() != old_smask

    # I05 JPEG、比例相同：DCTDecode 原樣嵌入，位元組與新圖檔相同
    data = jpeg((640, 480))
    original, output, plan, target, report = _replace("I05", tmp_path, data=data)
    assert report["ok"], report["failures"]
    with pikepdf.open(io.BytesIO(output)) as pdf:
        new = pdf.pages[0].obj.Resources.XObject[plan["resource_changes"][0]["added"]]
        assert new.Filter == "/DCTDecode" and new.read_raw_bytes() == data

    # I06 圖片蓋住的文字：替換後擷取文字與原檔相同（另存驗證 image_text_check）
    original, output, plan, target, report = _replace("I06", tmp_path, data=jpeg((300, 90)))
    assert report["ok"] and report["text_changed"] == []
