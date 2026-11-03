"""G5-07：桌面圖片替換流程 E2E（pytest-qt、offscreen、真的 DocumentService 與 worker）。"""

from pathlib import Path

import pikepdf
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from test_e2e import apply, open_file, wait

from peditor.ui.messages import reason_text

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def click_image(qtbot, window, index):
    target = window.page["image_targets"][index]
    rect = window.view.target_rect(target["target_id"])
    pos = window.view.mapFromScene(rect.center())
    qtbot.mouseClick(window.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(pos))
    assert window.selection is not None and window.selection["target_id"] == target["target_id"]
    assert window.selection["kind"] == "image"
    return target


def test_flow_replace_image_preview_apply_undo_save(qtbot, make_window, tmp_path):
    """I03：點第 2 個圖片 → 選新圖 → 前後對照 → 套用 → 復原、重做 → 另存；第 1 個不變。"""
    new_image = tmp_path / "新圖 🖼.png"
    Image.new("RGB", (100, 100), (255, 0, 255)).save(new_image, "PNG")
    window = make_window(ask_image=lambda: str(new_image))
    open_file(qtbot, window, FILES / "I03.pdf")
    first = window.page["image_targets"][0]["name"]
    click_image(qtbot, window, 1)
    assert window.panel.image_button.isEnabled()
    assert not window.panel.new_text.isEnabled() and not window.panel.preview_button.isEnabled()
    qtbot.mouseClick(window.panel.image_button, Qt.MouseButton.LeftButton)
    wait(qtbot, window)
    assert window.plan is not None and window.plan["mode"] == "image"
    assert window.panel.info.text().startswith("替換圖片")
    assert not window.panel.after.pixmap().isNull()
    assert window.revision == 0  # 預覽不提交
    apply(qtbot, window)
    assert window.revision == 1
    assert [t["name"] for t in window.page["image_targets"]] == [first, "/PEditorI1"]
    window.actions["undo"].trigger()
    wait(qtbot, window)
    assert [t["name"] for t in window.page["image_targets"]] == [first, "/fzImg1"]
    window.actions["redo"].trigger()
    wait(qtbot, window)
    out = tmp_path / "輸出 結果.pdf"
    window.save_as(str(out))
    wait(qtbot, window)
    assert window.last_error is None and out.exists()
    with pikepdf.open(out) as pdf:
        assert "/PEditorI1" in pdf.pages[0].Resources.XObject


def test_flow_unsupported_image_shows_reason(qtbot, make_window, tmp_path):
    """I09（非矩形剪裁）：點選後顯示原因、不能選新圖；不支援的圖片格式也顯示原因。"""
    window = make_window(ask_image=lambda: None)
    open_file(qtbot, window, FILES / "I09.pdf")
    click_image(qtbot, window, 0)
    assert window.panel.info.text() == "無法編輯：" + reason_text("UNSUPPORTED_LAYOUT")
    assert not window.panel.image_button.isEnabled()

    gif = tmp_path / "x.gif"
    Image.new("P", (4, 4)).save(gif, "GIF")
    window = make_window(ask_image=lambda: str(gif))
    open_file(qtbot, window, FILES / "I01.pdf")
    click_image(qtbot, window, 0)
    qtbot.mouseClick(window.panel.image_button, Qt.MouseButton.LeftButton)
    wait(qtbot, window)
    assert window.last_error is not None and window.last_error.code == "UNSUPPORTED_FEATURE"
    assert window.panel.info.text() == reason_text("UNSUPPORTED_FEATURE")
    assert window.revision == 0
