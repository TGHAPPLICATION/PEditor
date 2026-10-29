"""P3 儲存交易、撤銷與復原（G3-01、G3-02、G3-04、G3-05、G3-08；ADR-0020）。"""

import hashlib
import io
import shutil
from pathlib import Path

import pikepdf
import pymupdf
import pytest
import visual

from peditor.core.service import DocumentService, ServiceError
from peditor.export import transaction
from peditor.worker import analyzer, edit, export, span

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _row(manifest_rows, fixture_id):
    return next(r for r in manifest_rows if r["fixture_id"] == fixture_id)


def _region(text: str) -> list[float]:
    return [float(v) for v in text.split(",")]


def _fingerprint(document) -> str:
    """工作文件內容指紋：/ID 固定後的完整重寫（/ID 每次儲存不同，ADR-0020 U3）。"""
    buf = io.BytesIO()
    document.pike.save(buf, static_id=True, compress_streams=True,
                       object_stream_mode=pikepdf.ObjectStreamMode.preserve)  # fmt: skip
    return hashlib.sha256(buf.getvalue()).hexdigest()


def _numbers_sample(tmp_path) -> Path:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(400, 200))
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica,
        Encoding=pikepdf.Name.WinAnsiEncoding))  # fmt: skip
    pdf.pages[0].Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    pdf.pages[0].Contents = pdf.make_stream(b"BT /F1 24 Tf 72 100 Td (Count 00 done) Tj ET")
    path = tmp_path / "numbers.pdf"
    pdf.save(path)
    return path


def _apply(document, old: str, new: str) -> dict:
    target = span.find(document, 0, old)
    params = {"target_id": target.span_id, "new_text": new, "policy": "prefer_a"}
    plan = edit.plan_text_edit(document, params)
    assert plan["ready"], plan["unsupported_reasons"]
    base = document.revision
    edit.apply_edit(document, plan["plan_id"], base)
    return {"params": params, "base_revision": base}


def test_50_undo_redo_equivalent(tmp_path):
    """G3-01：50 次操作後逐步撤銷到原檔、再逐步重做，每一步內容都與當時相同。"""
    document = analyzer.open_document(str(_numbers_sample(tmp_path)))
    try:
        prints, log = [_fingerprint(document)], []
        for i in range(50):
            log.append(_apply(document, f"{i:02d}", f"{i + 1:02d}"))
            prints.append(_fingerprint(document))
        assert len(set(prints)) == 51  # 每一步都是不同的內容
        revision = document.revision
        for n in range(49, -1, -1):
            edit.replay(document, log[:n], revision + 1, True)
            revision += 1
            assert document.revision == revision
            assert _fingerprint(document) == prints[n], n
        for n in range(50):
            edit.replay(document, [log[n]], revision + 1, False)
            revision += 1
            assert _fingerprint(document) == prints[n + 1], n
        assert "Count 50 done" in document.mu[0].get_text()
    finally:
        document.close()


def test_replay_failure_restores_state(tmp_path):
    document = analyzer.open_document(str(_numbers_sample(tmp_path)))
    try:
        log = [_apply(document, "00", "01")]
        before, revision = _fingerprint(document), document.revision
        bad = {"params": {**log[0]["params"], "new_text": "€" * 40}, "base_revision": 0}
        with pytest.raises(Exception):  # noqa: B017,PT011 — 溢出或其他拒絕皆可，重點是復原
            edit.replay(document, [log[0], bad], revision + 1, True)
        assert document.revision == revision and _fingerprint(document) == before
    finally:
        document.close()


def test_service_undo_redo_and_truncation(manifest_rows):
    row = _row(manifest_rows, "T01")
    region = _region(row["editable_region_pt"])
    with DocumentService() as service:
        doc = service.open_document(FILES / "T01.pdf")["document_id"]
        with pytest.raises(ServiceError) as exc:
            service.undo(doc, 0)
        assert exc.value.code == "INVALID_REQUEST"
        span_id = service.find_text(doc, 0, row["original_text"])
        plan = service.plan_text_edit(doc, span_id, row["new_text"], "prefer_a", 0, region)
        rev = service.apply_edit(doc, plan["plan_id"], 0)["new_revision"]
        assert service.history(doc) == {"revision": rev, "undo": 1, "redo": 0}
        service.find_text(doc, 0, row["new_text"])

        with pytest.raises(ServiceError) as exc:
            service.undo(doc, rev - 1)
        assert exc.value.code == "REVISION_CONFLICT"
        rev = service.undo(doc, rev)["new_revision"]
        assert rev == 2 and service.history(doc) == {"revision": 2, "undo": 0, "redo": 1}
        service.find_text(doc, 0, row["original_text"])
        rev = service.redo(doc, rev)["new_revision"]
        assert rev == 3
        service.find_text(doc, 0, row["new_text"])

        rev = service.undo(doc, rev)["new_revision"]
        span_id = service.find_text(doc, 0, row["original_text"])
        plan = service.plan_text_edit(doc, span_id, "測試", "prefer_a", rev, region)
        rev = service.apply_edit(doc, plan["plan_id"], rev)["new_revision"]
        assert service.history(doc) == {"revision": rev, "undo": 1, "redo": 0}  # 重做被截斷
        with pytest.raises(ServiceError) as exc:
            service.redo(doc, rev)
        assert exc.value.code == "INVALID_REQUEST"


def test_worker_restart_replays_log(manifest_rows):
    """worker 重啟後重播 command log，已套用的編輯不遺失、revision 不變（ADR-0020 §1）。"""
    row = _row(manifest_rows, "T01")
    with DocumentService() as service:
        doc = service.open_document(FILES / "T01.pdf")["document_id"]
        span_id = service.find_text(doc, 0, row["original_text"])
        plan = service.plan_text_edit(doc, span_id, row["new_text"], "prefer_a", 0,
                                      _region(row["editable_region_pt"]))  # fmt: skip
        rev = service.apply_edit(doc, plan["plan_id"], 0)["new_revision"]
        service._restart()
        page = service.inspect_page(doc, 0, rev)
        assert any(row["new_text"] in t["text"] for t in page["text_targets"])
        assert service.undo(doc, rev)["new_revision"] == rev + 1


def _edit_and_export(service, source, row, destination, overwrite=False, new=None):
    doc = service.open_document(source)["document_id"]
    try:
        span_id = service.find_text(doc, 0, row["original_text"])
        plan = service.plan_text_edit(doc, span_id, new or row["new_text"], "prefer_a", 0,
                                      _region(row["editable_region_pt"]))  # fmt: skip
        rev = service.apply_edit(doc, plan["plan_id"], 0)["new_revision"]
        token = service.destination_token(destination, overwrite)
        return plan, service.export_document(doc, token, rev)
    finally:
        service.close_document(doc)


def _temps(folder: Path) -> list[str]:
    return [p.name for p in folder.iterdir() if transaction.TEMP_PATTERN.match(p.name)]


def test_reopen_after_save(manifest_rows, tmp_path, service):
    """G3-02：另存後重開，新文字在目標位置、舊文字少一次，原檔不變。"""
    row = _row(manifest_rows, "T01")
    out = tmp_path / "out.pdf"
    plan, result = _edit_and_export(service, FILES / "T01.pdf", row, out)
    data = out.read_bytes()
    assert hashlib.sha256(data).hexdigest() == result["output_hash"]
    assert result["validation_report"]["ok"] and not result["validation_report"]["visual_failed"]
    assert _temps(tmp_path) == []
    reopened = service.open_document(out)
    try:
        assert reopened["sha256"] == result["output_hash"]
        service.find_text(reopened["document_id"], 0, row["new_text"])
    finally:
        service.close_document(reopened["document_id"])
    origins = visual.char_origins("pdfium", data, row["new_text"])
    start = plan["geometry"]["baseline_start"]
    assert any(abs(o[0][0] - start[0]) <= 0.5 and abs(o[0][1] - start[1]) <= 0.5 for o in origins)
    with pymupdf.open(stream=data, filetype="pdf") as mu, pymupdf.open(FILES / "T01.pdf") as orig:
        old = row["original_text"]
        assert mu[0].get_text().count(old) == orig[0].get_text().count(old) - 1
    assert hashlib.sha256((FILES / "T01.pdf").read_bytes()).hexdigest() == row["sha256"]


def test_100_save_cycles(manifest_rows, tmp_path, service):
    """G3-04：以上一次的輸出為來源連續另存 100 次（兩個檔案輪替覆寫），每次驗證通過、內容正確。"""
    row = _row(manifest_rows, "T01")
    paths = [tmp_path / "c0.pdf", tmp_path / "c1.pdf"]
    shutil.copyfile(FILES / "T01.pdf", paths[0])
    texts = (row["original_text"], row["new_text"])
    for i in range(100):
        cycle_row = {**row, "original_text": texts[i % 2]}
        source, dest = paths[i % 2], paths[(i + 1) % 2]
        _, result = _edit_and_export(service, source, cycle_row, dest, overwrite=True,
                                     new=texts[(i + 1) % 2])  # fmt: skip
        assert result["validation_report"]["ok"], i
        assert hashlib.sha256(dest.read_bytes()).hexdigest() == result["output_hash"], i
    with pymupdf.open(paths[0]) as mu:  # 偶數次替換後回到原文
        assert row["original_text"] in mu[0].get_text()
        assert mu.page_count == 1 and not mu.is_repaired
    with pymupdf.open(paths[1]) as mu:  # 第 99 次輸出為新文字
        assert row["new_text"] in mu[0].get_text()
        assert mu.page_count == 1 and not mu.is_repaired
    assert _temps(tmp_path) == []


def test_external_modification_detected(tmp_path, service):
    """G3-05：原檔或目的檔在開啟／取得 token 後被修改，回 REVISION_CONFLICT，且不寫出。"""
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "T01.pdf", source)
    dest = tmp_path / "dest.pdf"
    dest.write_bytes(b"existing")

    doc = service.open_document(source)["document_id"]
    try:
        token = service.destination_token(dest, overwrite=True)
        dest.write_bytes(b"changed by someone else")
        with pytest.raises(ServiceError) as exc:
            service.export_document(doc, token, 0)
        assert exc.value.code == "REVISION_CONFLICT"
        assert dest.read_bytes() == b"changed by someone else"

        token = service.destination_token(dest, overwrite=True)
        source.write_bytes(source.read_bytes() + b"\n%tampered\n")
        with pytest.raises(ServiceError) as exc:
            service.export_document(doc, token, 0)
        assert exc.value.code == "REVISION_CONFLICT"
        assert dest.read_bytes() == b"changed by someone else"
        service._restart()  # worker 重啟後重開也要發現原檔已變
        with pytest.raises(ServiceError) as exc:
            service.inspect_page(doc, 0)
        assert exc.value.code == "REVISION_CONFLICT"
    finally:
        service.close_document(doc)
    assert _temps(tmp_path) == []


def test_destination_rules(manifest_rows, tmp_path, service):
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "T01.pdf", source)
    existing = tmp_path / "exists.pdf"
    existing.write_bytes(b"keep")
    with pytest.raises(ServiceError) as exc:
        service.destination_token(existing)  # 預設不覆寫
    assert exc.value.code == "SAVE_FAILED"
    with pytest.raises(ServiceError) as exc:
        service.destination_token(tmp_path / "x.txt")
    assert exc.value.code == "INVALID_REQUEST"
    with pytest.raises(ServiceError) as exc:
        service.destination_token(tmp_path / "missing" / "x.pdf")
    assert exc.value.code == "SAVE_FAILED"
    doc = service.open_document(source)["document_id"]
    try:
        token = service.destination_token(source, overwrite=True)
        with pytest.raises(ServiceError) as exc:  # 原檔唯讀
            service.export_document(doc, token, 0)
        assert exc.value.code == "INVALID_REQUEST"
        with pytest.raises(ServiceError) as exc:
            service.export_document(doc, "not-a-token", 0)
        assert exc.value.code == "INVALID_REQUEST"
    finally:
        service.close_document(doc)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == _row(manifest_rows, "T01")["sha256"]
    assert existing.read_bytes() == b"keep"


def test_failure_no_partial_output(manifest_rows, tmp_path, monkeypatch):
    """G3-08：套用失敗不更新 revision 並完整回滾（f003、R3-1）；
    驗證或寫入失敗不留下輸出（f017）。"""
    row = _row(manifest_rows, "T01")
    document = analyzer.open_document(str(FILES / "T01.pdf"))
    try:
        ids = [t["target_id"] for t in analyzer.inspect_page(document, 0)["text_targets"]]
        before = _fingerprint(document)
        target = span.find(document, 0, row["original_text"])
        plan = edit.plan_text_edit(document, {"target_id": target.span_id,
                                              "new_text": row["new_text"]})  # fmt: skip

        def broken_commit(self):  # 內容串流已改寫後才失敗
            raise RuntimeError("injected")

        monkeypatch.setattr(analyzer.Document, "commit", broken_commit)
        with pytest.raises(RuntimeError):
            edit.apply_edit(document, plan["plan_id"], 0)
        monkeypatch.undo()
        assert document.revision == 0 and document.applied == []
        assert _fingerprint(document) == before
        assert [t["target_id"] for t in analyzer.inspect_page(document, 0)["text_targets"]] == ids

        _apply(document, row["original_text"], row["new_text"])
        out = tmp_path / "v.pdf"
        monkeypatch.setattr(export, "visual_check", lambda *a: [{"page_index": 0}])
        with pytest.raises(Exception) as exc:  # noqa: PT011
            export.export_document(document, str(out))
        assert getattr(exc.value, "code", None) == "VALIDATION_FAILED" and not out.exists()
        monkeypatch.undo()

        def half_write(fh, data):
            fh.write(data[: len(data) // 2])
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(export, "_write", half_write)
        with pytest.raises(Exception) as exc:  # noqa: PT011
            export.export_document(document, str(out))
        assert getattr(exc.value, "code", None) == "SAVE_FAILED" and not out.exists()
    finally:
        document.close()


def test_product_checks_detect_problems(manifest_rows):
    """另存前的文字與視覺驗證（ADR-0020 §4）能抓到可改動區域外的改動與缺少的新文字。"""
    row = _row(manifest_rows, "F04")  # MuPDF 可正常渲染（非 ADR-0015 例外）
    document = analyzer.open_document(str(FILES / "F04.pdf"))
    try:
        _apply(document, row["original_text"], row["new_text"])
        data = document.working_bytes()
        assert export.visual_check(document, data, {0}) == []
        assert export.text_check(document, data) == []
        document.applied[0]["mask"] = [0, 0, 1, 1]  # 宣告的可改動區域不含實際改動
        assert export.visual_check(document, data, {0})
        document.applied[0]["new_text"] = "NotOnPage"
        assert export.text_check(document, data) == [{"page_index": 0, "edit_index": 0}]
    finally:
        document.close()
