"""儲存格改字經 DocumentService（G6-06；ADR-0023）。

預覽不提交、undo／redo、worker 重啟、復原草稿、人工框選。
"""

import shutil
from pathlib import Path

from cell_samples import cell_box, table_pdf

from peditor.core import drafts
from peditor.core.service import DocumentService

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _cell(service, doc, row, col, revision=None):
    page = service.inspect_page(doc, 0, revision)
    return next(c for c in page["cell_targets"] if (c["row"], c["col"]) == (row, col))


def test_cell_preview_undo_redo_and_restart(tmp_path):
    """B04（MuPDF 可渲染，前後對照有差異；B01 屬 ADR-0015 預覽空白檔）。"""
    with DocumentService() as service:
        doc = service.open_document(FILES / "B04.pdf")["document_id"]
        target = _cell(service, doc, 2, 1)
        plan = service.plan_cell_edit(doc, target["cell_id"], "250", 0, "prefer_a", 0)
        assert plan["ready"]
        preview = service.preview_edit(doc, plan["plan_id"], 0)
        assert preview["before"] != preview["after"]
        assert _cell(service, doc, 2, 1, 0)["lines"][0]["text"] == "300"  # 預覽不提交
        rev = service.apply_edit(doc, plan["plan_id"], 0)["new_revision"]
        assert _cell(service, doc, 2, 1, rev)["lines"][0]["text"] == "250"
        rev = service.undo(doc, rev)["new_revision"]
        assert _cell(service, doc, 2, 1, rev)["lines"][0]["text"] == "300"
        rev = service.redo(doc, rev)["new_revision"]
        service._restart()  # worker 重啟：依 command log（op=cell）重播
        assert _cell(service, doc, 2, 1, rev)["lines"][0]["text"] == "250"
        token = service.destination_token(tmp_path / "out.pdf")
        report = service.export_document(doc, token, rev)["validation_report"]
        assert report["ok"] and report["rules_changed"] == []


def test_cell_draft_recovery(tmp_path):
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "B04.pdf", source)
    store_dir = tmp_path / "drafts"
    service = DocumentService(drafts=drafts.DraftStore(store_dir))
    try:
        doc = service.open_document(source)["document_id"]
        target = _cell(service, doc, 2, 1)
        plan = service.plan_cell_edit(doc, target["cell_id"], "250", 0, "prefer_a", 0)
        service.apply_edit(doc, plan["plan_id"], 0)
    finally:
        service.close()  # 未 close_document：模擬異常結束
    with DocumentService(drafts=drafts.DraftStore(store_dir)) as service:
        draft_id = service.list_drafts()[0]["draft_id"]
        doc = service.recover_draft(draft_id)["document_id"]
        assert _cell(service, doc, 2, 1)["lines"][0]["text"] == "250"
        service.close_document(doc)
    assert list(store_dir.iterdir()) == []


def test_manual_cell_via_service(tmp_path):
    path = tmp_path / "borderless.pdf"
    table_pdf(path, [["Item", "Qty"], ["Pen", "12"]], vertical=False)
    box = cell_box(1, 1)
    inner = [box[0] + 1, box[1] + 1, box[2] - 1, box[3] - 1]
    with DocumentService() as service:
        doc = service.open_document(path)["document_id"]
        assessed = service.assess_cell_box(doc, 0, inner, 0)
        assert assessed["capability"]["status"] == "support"
        plan = service.plan_cell_edit(
            doc, None, "21", 0, "prefer_a", 0, cell_box=inner, page_index=0
        )
        assert plan["ready"]
        rev = service.apply_edit(doc, plan["plan_id"], 0)["new_revision"]
        rev = service.undo(doc, rev)["new_revision"]
        rev = service.redo(doc, rev)["new_revision"]
        assert service.assess_cell_box(doc, 0, inner, rev)["lines"][0]["text"] == "21"
