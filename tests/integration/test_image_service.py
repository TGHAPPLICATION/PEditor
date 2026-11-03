"""圖片替換經 DocumentService（G5-06；ADR-0022）。

新圖登記、預覽不提交、undo／redo、worker 重啟與復原草稿。
"""

import shutil
from pathlib import Path

import pytest
from PIL import Image

from peditor.core import drafts
from peditor.core import service as service_module
from peditor.core.service import DocumentService, ServiceError

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _png_file(path: Path, size=(100, 100), color=(255, 0, 255)) -> Path:
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _names(service, doc, revision=None) -> list[str]:
    return [t["name"] for t in service.inspect_page(doc, 0, revision)["image_targets"]]


def _replace(service, doc, index, image_path, revision):
    target = service.inspect_page(doc, 0, revision)["image_targets"][index]
    asset = service.register_image(doc, image_path)
    plan = service.plan_image_edit(doc, target["target_id"], asset["asset_id"], revision)
    assert plan["ready"], plan["unsupported_reasons"]
    return plan


def test_image_preview_undo_redo_and_restart(tmp_path):
    """預覽不提交；套用、撤銷、重做、worker 重啟後重播都正確（I03 同頁共用，只改第 2 次出現）。"""
    image_path = _png_file(tmp_path / "new.png")
    with DocumentService() as service:
        doc = service.open_document(FILES / "I03.pdf")["document_id"]
        original = _names(service, doc)
        plan = _replace(service, doc, 1, image_path, 0)
        preview = service.preview_edit(doc, plan["plan_id"], 0)
        assert preview["mode"] == "image" and preview["before"] != preview["after"]
        assert _names(service, doc, 0) == original  # 預覽不提交
        rev = service.apply_edit(doc, plan["plan_id"], 0)["new_revision"]
        replaced = [original[0], "/PEditorI1"]
        assert _names(service, doc, rev) == replaced
        rev = service.undo(doc, rev)["new_revision"]
        assert _names(service, doc, rev) == original
        rev = service.redo(doc, rev)["new_revision"]
        assert _names(service, doc, rev) == replaced
        service._restart()  # 新圖隨 worker 消失：主行程重新登記後重播
        assert _names(service, doc, rev) == replaced
        rev = service.undo(doc, rev)["new_revision"]
        rev = service.redo(doc, rev)["new_revision"]
        token = service.destination_token(tmp_path / "out.pdf")
        report = service.export_document(doc, token, rev)["validation_report"]
        assert report["ok"], report["failures"]


def test_image_draft_recovery(tmp_path):
    """草稿含新圖檔（0600）；異常結束後可復原，正常關閉時新圖檔一併刪除；新圖檔遺失的草稿視為損壞。"""
    source = tmp_path / "src.pdf"
    shutil.copyfile(FILES / "I01.pdf", source)
    image_path = _png_file(tmp_path / "new.png", (200, 100))
    store_dir = tmp_path / "drafts"
    service = DocumentService(drafts=drafts.DraftStore(store_dir))
    try:
        doc = service.open_document(source)["document_id"]
        plan = _replace(service, doc, 0, image_path, 0)
        service.apply_edit(doc, plan["plan_id"], 0)
        assets = list(store_dir.glob("*.img"))
        assert len(assets) == 1 and assets[0].read_bytes() == image_path.read_bytes()
    finally:
        service.close()  # 未 close_document：模擬異常結束

    with DocumentService(drafts=drafts.DraftStore(store_dir)) as service:
        draft_id = service.list_drafts()[0]["draft_id"]
        doc = service.recover_draft(draft_id)["document_id"]
        assert _names(service, doc) == ["/PEditorI1"]
        rev = service.history(doc)["revision"]
        assert _names(service, doc, service.undo(doc, rev)["new_revision"]) == ["/fzImg0"]
        service.close_document(doc)
    assert list(store_dir.iterdir()) == []

    service = DocumentService(drafts=drafts.DraftStore(store_dir))
    try:
        doc = service.open_document(source)["document_id"]
        plan = _replace(service, doc, 0, image_path, 0)
        service.apply_edit(doc, plan["plan_id"], 0)
    finally:
        service.close()
    next(store_dir.glob("*.img")).unlink()
    store = drafts.DraftStore(store_dir)
    assert store.list() == [] and list(store_dir.iterdir()) == []


def test_register_image_errors_and_release(tmp_path, monkeypatch):
    """讀不到的檔案、過大、不支援的格式都受控失敗且訊息不含路徑；未使用的新圖兩端一起釋放。"""
    secret_dir = tmp_path / "機密資料夾"
    secret_dir.mkdir()
    with DocumentService() as service:
        doc = service.open_document(FILES / "I01.pdf")["document_id"]
        with pytest.raises(ServiceError) as info:
            service.register_image(doc, secret_dir / "不存在.png")
        assert info.value.code == "INVALID_REQUEST" and "機密" not in info.value.message
        gif = secret_dir / "x.gif"
        Image.new("P", (4, 4)).save(gif, "GIF")
        with pytest.raises(ServiceError) as info:
            service.register_image(doc, gif)
        assert info.value.code == "UNSUPPORTED_FEATURE" and "機密" not in info.value.message
        first = service.register_image(doc, _png_file(secret_dir / "a.png"))["asset_id"]
        second = service.register_image(doc, _png_file(secret_dir / "b.png", color=(1, 2, 3)))
        assert list(service._docs[doc].assets) == [second["asset_id"]] != [first]
        monkeypatch.setattr(service_module, "MAX_IMAGE_BYTES", 16)
        with pytest.raises(ServiceError) as info:
            service.register_image(doc, secret_dir / "a.png")
        assert info.value.code == "RESOURCE_LIMIT"


def test_image_and_text_edits_share_log(tmp_path):
    """同一份文件先改字、再換圖：兩種計畫共用 command log，撤銷依序回復。"""
    image_path = _png_file(tmp_path / "new.png", (150, 75))
    with DocumentService() as service:
        doc = service.open_document(FILES / "I06.pdf")["document_id"]
        page = service.inspect_page(doc, 0, 0)
        text = next(t for t in page["text_targets"] if t["capability"]["status"] == "support")
        plan = service.plan_text_edit(doc, text["target_id"], text["text"][:1], "prefer_a", 0)
        assert plan["ready"], plan["unsupported_reasons"]
        rev = service.apply_edit(doc, plan["plan_id"], 0)["new_revision"]
        image_plan = _replace(service, doc, 0, image_path, rev)
        rev = service.apply_edit(doc, image_plan["plan_id"], rev)["new_revision"]
        assert service.history(doc) == {"revision": rev, "undo": 2, "redo": 0}
        rev = service.undo(doc, rev)["new_revision"]
        assert _names(service, doc, rev) == ["/Image14"]
        rev = service.undo(doc, rev)["new_revision"]
        assert service.history(doc) == {"revision": rev, "undo": 0, "redo": 2}
