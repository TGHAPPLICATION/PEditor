"""P2 文字編輯：模式 A 就地改寫、模式 B 移除後以 Noto Sans TC 重建
（G2-01、G2-02、G2-04、G2-05、G2-06、G2-19、G2-20）。"""

import csv
import hashlib
import re
from pathlib import Path

import pikepdf
import pypdfium2
import pytest

from peditor.core.protocol import ProtocolError
from peditor.core.service import DocumentService
from peditor.worker import analyzer, edit, span
from peditor.worker.content import interpret

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FILES = FIXTURES / "files"
# 原字型子集含全部新字（fontTools 檢查字形輪廓）→ 模式 A；其餘 support 案例 → 模式 B（ADR-0018 §4）
MODE_A = {"T01", "T02", "T08", "F01", "F04", "L02", "L03"}
MODE_B = {"T03", "T04", "T05", "T06", "T07", "F02", "F06", "F07", "L01", "L04", "L05"}
ORIGIN_TOL = 0.01  # pt


def _without_id(data: bytes) -> bytes:
    """trailer /ID 第二元素每次存檔不同（跨秒時）；比對位元組時排除（P2 U3）。"""
    return re.sub(rb"/ID\s*\[\s*<[0-9A-Fa-f]*>\s*<[0-9A-Fa-f]*>\s*\]", b"", data)


def _manifest():
    with open(FIXTURES / "manifest.csv", encoding="utf-8", newline="") as fh:
        return {r["fixture_id"]: r for r in csv.DictReader(fh)}


def _edit_cases():
    with open(FIXTURES / "edit_cases.csv", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _region(text: str) -> list[float]:
    return [float(v) for v in text.split(",")]


def _mode_a_cases():
    rows = _manifest()
    cases = [(fid, rows[fid]["original_text"], rows[fid]["new_text"],
              rows[fid]["editable_region_pt"]) for fid in sorted(MODE_A)]  # fmt: skip
    cases += [(c["fixture_id"], c["original_text"], c["new_text"], c["editable_region_pt"])
              for c in _edit_cases() if not c["after_case"]]  # fmt: skip
    return cases


def _plan(document, old, new, region, policy="prefer_a"):
    params = {
        "target_id": span.find(document, 0, old).span_id,
        "new_text": new,
        "policy": policy,
        "editable_region": _region(region),
    }
    return edit.plan_text_edit(document, params)


def _texts(data: bytes) -> tuple[str, str]:
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        mu = doc[0].get_text().replace("\n", "")
    pdf = pypdfium2.PdfDocument(data)
    try:
        pdfium = pdf[0].get_textpage().get_text_range().replace("\r\n", "").replace("\n", "")
    finally:
        pdf.close()
    return mu, pdfium


def _ops(data: bytes) -> list[list[tuple]]:
    """每頁每個 content stream 的解析後運算子（用於差異比對）。"""
    with pikepdf.open(__import__("io").BytesIO(data)) as pdf:
        out = []
        for page in pdf.pages:
            for inst in pikepdf.parse_content_stream(page):
                out.append((str(inst.operator), pikepdf.unparse_content_stream([inst])))
        return out


@pytest.mark.parametrize(("fid", "old", "new", "region"), _mode_a_cases())
def test_target_occurrence_replaced_dual_engine(fid, old, new, region):
    """模式 A：只有目標運算子被改寫；兩引擎都擷取到新文、目標位置不再有舊文。"""
    document = analyzer.open_document(str(FILES / f"{fid}.pdf"))
    try:
        original = document.working_bytes()
        before_count = _texts(original)[0].count(old)
        plan = _plan(document, old, new, region)
        assert plan["ready"] and plan["mode"] == "A", (
            plan["unsupported_reasons"],
            plan["warnings"],
        )
        assert plan["font_changes"] == []  # 模式 A 不換字型（G2-5）
        edit.apply_edit(document, plan["plan_id"], 0)
        assert document.revision == 1
        result = document.working_bytes()
        mu, pdfium = _texts(result)
        assert new in mu and new in pdfium
        assert mu.count(old) == before_count - 1  # 只移除目標 occurrence
        before_ops, after_ops = _ops(original), _ops(result)
        changed = [i for i, (a, b) in enumerate(zip(before_ops, after_ops, strict=True)) if a != b]
        assert len(changed) == 1 and after_ops[changed[0]][0] in ("TJ", "Tj")
    finally:
        document.close()


def _all_cases():
    """宣告支援的全部文字操作：manifest 18 個＋edit_cases（E01 另見 test_chained_edit_e01）。"""
    rows = _manifest()
    cases = [(fid, r["original_text"], r["new_text"], r["editable_region_pt"],
              "A" if fid in MODE_A else "B")
             for fid, r in rows.items() if r["expected"] == "support" and r["new_text"]
             and fid[0] in "TFL" and r["status"] == "available"]  # fmt: skip
    cases += [(c["fixture_id"], c["original_text"], c["new_text"], c["editable_region_pt"],
               c["expected_mode"]) for c in _edit_cases() if not c["after_case"]]  # fmt: skip
    return cases


def test_supported_case_coverage():
    """G2-1：至少 20 次操作、3 種產生來源、2 種繁中字型（含 E01 接續編輯）。"""
    rows = _manifest()
    cases = _all_cases()
    assert set(f for f, *_ in cases) >= MODE_A | MODE_B
    assert len(cases) + 1 >= 20  # ＋E01
    assert len({rows[f]["generator"].split("+")[0] for f, *_ in cases}) >= 3
    fonts = {rows[f]["fonts"] for f, *_ in cases}
    assert any("Noto Sans TC" in f for f in fonts) and any("Noto Serif TC" in f for f in fonts)


@pytest.mark.parametrize(("fid", "old", "new", "region", "mode"), _all_cases())
def test_all_supported_text_cases(fid, old, new, region, mode):
    """G2-01：宣告支援的每個案例都產生可套用的計畫、以預期模式完成、兩引擎擷取到新文。"""
    document = analyzer.open_document(str(FILES / f"{fid}.pdf"))
    try:
        original = document.working_bytes()
        plan = _plan(document, old, new, region)
        assert plan["ready"] and plan["mode"] == mode, (
            plan["unsupported_reasons"],
            plan["warnings"],
        )
        edit.apply_edit(document, plan["plan_id"], 0)
        mu, pdfium = _texts(document.working_bytes())
        before_mu, before_pdfium = _texts(original)
        assert new.replace(" ", "") in mu.replace(" ", "")
        assert new.replace(" ", "") in pdfium.replace(" ", "")
        # 只移除目標 occurrence（新文本身含原文時，例如 T04 的插入，原文仍會出現）；兩引擎各自判定
        assert mu.count(old) == before_mu.count(old) - 1 + new.count(old)
        assert pdfium.count(old) == before_pdfium.count(old) - 1 + new.count(old)
    finally:
        document.close()


@pytest.mark.parametrize("fid", sorted(MODE_B))
def test_mode_a_keeps_font_mode_b_removes_old(fid):
    """G2-05：模式 B 先移除舊字形再以 Noto Sans TC 重建，並明示字型替換；模式 A 見上方測試。"""
    row = _manifest()[fid]
    document = analyzer.open_document(str(FILES / f"{fid}.pdf"))
    try:
        sel = span.resolve(document, span.find(document, 0, row["original_text"]))
        change = span.change(sel, row["new_text"])
        old_font = sel.runs[change.pieces[0].run_index].font.key
        old_glyphs = [g for p in change.pieces for g in sel.runs[p.run_index].glyphs[p.g0 : p.g1]]
        plan = _plan(document, row["original_text"], row["new_text"], row["editable_region_pt"])
        assert plan["mode"] == "B" and plan["font_policy"] == "replace_with_packaged"
        assert plan["font_changes"][0]["to"] == "NotoSansTC-Regular"
        added = [c["added"] for c in plan["resource_changes"] if c["kind"] == "Font"]
        assert added and any("字型已替換" in w for w in plan["warnings"])
        edit.apply_edit(document, plan["plan_id"], 0)
        runs = interpret(document.pike.pages[0]).runs
        # 舊字形（原字型、原位置）已不存在：不只是被蓋住
        for g in old_glyphs:
            assert not any(r.font and r.font.key == old_font and any(
                h.code == g.code and abs(h.origin[0] - g.origin[0]) <= ORIGIN_TOL
                and abs(h.origin[1] - g.origin[1]) <= ORIGIN_TOL for h in r.glyphs)
                for r in runs), g  # fmt: skip
        rebuilt = "".join(g.unicode for r in runs if r.font and r.font.key == added[0]
                          for g in r.glyphs)  # fmt: skip
        assert rebuilt == change.new_text
    finally:
        document.close()


_PAINT_OR_STATE = {"re", "m", "l", "c", "v", "y", "h", "S", "s", "f", "F", "f*", "B", "B*", "b",
                   "b*", "n", "W", "W*", "cm", "q", "Q", "rg", "RG", "g", "G", "k", "K", "w", "Do",
                   "sh", "gs", "cs", "CS", "sc", "SC", "scn", "SCN"}  # fmt: skip


@pytest.mark.parametrize("fid", ["L03", "L04", "L05", "T07", "F07", "T03"])
def test_neighbors_and_lines_untouched(fid):
    """G2-03：密集鄰字、背景、線條不被修改，不靠白底覆蓋：
    線條／填色／影像運算子與其他文字運算子逐一相同；沒有新增任何繪圖運算子（例如白色矩形）。"""
    row = _manifest()[fid]
    document = analyzer.open_document(str(FILES / f"{fid}.pdf"))
    try:
        original = document.working_bytes()
        plan = _plan(document, row["original_text"], row["new_text"], row["editable_region_pt"])
        assert plan["ready"], plan["unsupported_reasons"]
        edit.apply_edit(document, plan["plan_id"], 0)
        before, after = _ops(original), _ops(document.working_bytes())
    finally:
        document.close()
    paint_before = [op for op in before if op[0] in _PAINT_OR_STATE]
    paint_after = [op for op in after if op[0] in _PAINT_OR_STATE]
    assert paint_before == paint_after  # 線條、背景、裁切、色彩完全相同；沒有白底覆蓋
    text_before = [op for op in before if op[0] in ("Tj", "TJ", "'", '"')]
    text_after = [op for op in after if op[0] in ("Tj", "TJ", "'", '"')]
    # 目標以外的文字運算子逐一保留（目標只會被改寫或拆成多段）
    kept = [op for op in text_before if op in text_after]
    assert len(kept) == len(text_before) - 1


def _stream_key(document, run):
    """(頁面 content stream 順序, 運算子索引)；儲存會重編物件號碼，不能用 objgen 比對前後。"""
    contents = document.pike.pages[0].obj.Contents
    streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
    return ([s.objgen for s in streams].index(run.stream), run.op_index)


def _origins(document):
    runs = interpret(document.pike.pages[0]).runs
    return [
        (_stream_key(document, r), i, g.unicode, g.origin)
        for r in runs
        for i, g in enumerate(r.glyphs)
    ]


@pytest.mark.parametrize(("fid", "old", "new"), [
    ("F04", "Hello", "Hi"),  # E03：較短，後續「 World」不得移動
    ("F04", "World", "Earth"),
    ("T02", "10 月 31 日", "11 月 5 日"),
    ("T01", "衛生局", "測試局"),
])  # fmt: skip
def test_following_glyphs_unmoved(fid, old, new):
    """G2-19：字寬不同時以 TJ 位移補償，目標之後的字形原點不變（ADR-0018 §2）。"""
    document = analyzer.open_document(str(FILES / f"{fid}.pdf"))
    try:
        sel = span.resolve(document, span.find(document, 0, old))
        change = span.change(sel, new)
        piece = change.pieces[0]
        run = sel.runs[piece.run_index]
        op = _stream_key(document, run)
        before = [o for o in _origins(document) if o[0] != op or o[1] >= piece.g1]
        plan = _plan(document, old, new, "0,0,999,999")
        edit.apply_edit(document, plan["plan_id"], 0)
        shift = len(change.new_text) - (piece.g1 - piece.g0)
        after = {(o[0], o[1] - shift if o[0] == op else o[1]): o for o in _origins(document)}
        for op_index, index, uni, (x, y) in before:
            if op_index == op and index < piece.g0:
                continue
            _, _, uni2, (x2, y2) = after[(op_index, index)]
            assert uni == uni2
            assert abs(x - x2) <= ORIGIN_TOL and abs(y - y2) <= ORIGIN_TOL, (uni, x, x2)
    finally:
        document.close()


@pytest.mark.parametrize(("fid", "old", "new"), [
    ("T01", "衛生局", "衛生局局局局"),  # 模式 A（新字都在原子集）
    ("F02", "醫事", "藥事人員公會"),  # 模式 B（Noto Sans TC 字寬）
])  # fmt: skip
def test_overflow_rejected(fid, old, new):
    """G2-06：超出可改動區域一律 TEXT_OVERFLOW，不縮字；計畫不可套用、文件不變。"""
    row = _manifest()[fid]
    path = FILES / f"{fid}.pdf"
    document = analyzer.open_document(str(path))
    try:
        before = _ops(document.working_bytes())
        plan = _plan(document, old, new, row["editable_region_pt"])
        assert plan["unsupported_reasons"] == ["TEXT_OVERFLOW"] and not plan["ready"]
        with pytest.raises(ProtocolError) as exc:
            edit.apply_edit(document, plan["plan_id"], 0)
        assert exc.value.code == "INVALID_REQUEST"
        assert document.revision == 0 and _ops(document.working_bytes()) == before
    finally:
        document.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


def test_unsupported_encoding_rejected_on_edit_path():
    """G2-04：ToUnicode 不完整（F05）在編輯路徑回 UNSUPPORTED_ENCODING，計畫不可套用、文件不變。
    F05 無法以內容搜尋定位，改用 P1 的文字目標 ID。"""
    row = _manifest()["F05"]
    path = FILES / "F05.pdf"
    document = analyzer.open_document(str(path))
    try:
        before = _ops(document.working_bytes())
        analyzer.inspect_page(document, 0)
        _, index = document.runs[0]
        assert index
        for target_id in index:
            plan = edit.plan_text_edit(document, {"target_id": target_id, "new_text": "臺灣",
                                                  "editable_region": [0, 0, 999, 999]})  # fmt: skip
            assert plan["unsupported_reasons"] == ["UNSUPPORTED_ENCODING"] and not plan["ready"]
            with pytest.raises(ProtocolError) as exc:
                edit.apply_edit(document, plan["plan_id"], 0)
            assert exc.value.code == "INVALID_REQUEST"
        assert document.revision == 0 and _ops(document.working_bytes()) == before
    finally:
        document.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


@pytest.mark.parametrize(("fid", "policy"), [
    ("F03", "prefer_a"),  # 𠮷：原字型與 Noto Sans TC 都沒有（ADR-0008、ADR-0013）
    ("F08", "prefer_a"),
    ("F03", "a_only"),
    ("F02", "a_only"),  # 嚴格 A：原子集缺字即拒絕，不改走 B
])  # fmt: skip
def test_rejections_leave_files_unchanged(fid, policy):
    """G2-04：缺字回 GLYPH_MISSING，不顯示方框、不換其他字型；拒絕不改磁碟檔與工作文件。"""
    rows = _manifest()
    path = FILES / f"{fid}.pdf"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    document = analyzer.open_document(str(path))
    try:
        working = document.working_bytes()
        plan = _plan(document, rows[fid]["original_text"], rows[fid]["new_text"],
                     rows[fid]["editable_region_pt"], policy=policy)  # fmt: skip
        assert plan["unsupported_reasons"] == ["GLYPH_MISSING"] and plan["mode"] is None
        assert document.revision == 0 and _without_id(document.working_bytes()) == _without_id(
            working
        )
    finally:
        document.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest == rows[fid]["sha256"]


def test_mode_b_font_unavailable(monkeypatch, tmp_path):
    """模式 B 字型不存在或 SHA-256 不符時不改用其他字型，回 GLYPH_MISSING 並說明。"""
    from peditor.worker import fontb

    fake = tmp_path / "NotoSansTC-Regular.otf"
    fake.write_bytes(b"not the pinned font")
    monkeypatch.setenv(fontb.ENV, str(fake))
    monkeypatch.setattr(fontb, "_state", {})
    monkeypatch.setattr(fontb, "_candidates", lambda: [fake])
    row = _manifest()["F02"]
    document = analyzer.open_document(str(FILES / "F02.pdf"))
    try:
        plan = _plan(document, row["original_text"], row["new_text"], row["editable_region_pt"])
        assert plan["unsupported_reasons"] == ["GLYPH_MISSING"]
        assert any("不可用" in w for w in plan["warnings"])
    finally:
        document.close()


def test_stale_plan_and_revision_conflict():
    document = analyzer.open_document(str(FILES / "T01.pdf"))
    try:
        region = _manifest()["T01"]["editable_region_pt"]
        first = _plan(document, "衛生局", "測試局", region)
        second = _plan(document, "衛生局", "測試局", region)
        with pytest.raises(ProtocolError) as exc:
            edit.apply_edit(document, first["plan_id"], 5)
        assert exc.value.code == "REVISION_CONFLICT"
        edit.apply_edit(document, first["plan_id"], 0)
        with pytest.raises(ProtocolError) as exc:  # 套用後舊版本的計畫全部失效
            edit.apply_edit(document, second["plan_id"], 1)
        assert exc.value.code == "INVALID_REQUEST"
    finally:
        document.close()


def test_chained_edit_e01_through_worker():
    """E01（G2-20）：經 worker 連續兩次編輯同一文件；revision 遞增、第二次以第一次結果為基礎。"""
    case = next(c for c in _edit_cases() if c["case_id"] == "E01")
    row = _manifest()["T01"]
    path = FILES / "T01.pdf"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with DocumentService() as svc:
        doc = svc.open_document(path)
        did = doc["document_id"]
        for revision, (old, new, region) in enumerate([
            (row["original_text"], row["new_text"], row["editable_region_pt"]),
            (case["original_text"], case["new_text"], case["editable_region_pt"]),
        ]):  # fmt: skip
            page = svc.inspect_page(did, 0, expected_revision=revision)
            target = next(t for t in page["text_targets"] if old in t["text"])
            start = target["text"].index(old)
            span_id = f"span:{target['target_id']}:c{start}-{start + len(old)}"
            plan = svc.plan_text_edit(did, span_id, new, expected_revision=revision,
                                      editable_region=_region(region))  # fmt: skip
            assert plan["ready"] and plan["mode"] == "A"
            assert svc.apply_edit(did, plan["plan_id"], revision)["new_revision"] == revision + 1
        texts = [t["text"] for t in svc.inspect_page(did, 0, expected_revision=2)["text_targets"]]
        assert any("衛生局" in t for t in texts) and not any("測試局" in t for t in texts)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest  # 原檔不變
