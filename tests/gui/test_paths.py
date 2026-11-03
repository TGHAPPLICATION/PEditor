"""G4-03：中文路徑、空白檔名、emoji 路徑可開啟、編輯、另存並重新開啟。"""

import shutil

import pytest
from test_e2e import FILES, apply, find, open_file, preview, wait


@pytest.mark.parametrize(
    ("folder", "name"),
    [("中文目錄", "衛生局公文.pdf"), ("with space", "file name with spaces.pdf"),
     ("表情😀", "報告📄 v2.pdf")],
)  # fmt: skip
def test_unicode_paths(qtbot, make_window, tmp_path, folder, name):
    source = tmp_path / folder / name
    source.parent.mkdir()
    shutil.copyfile(FILES / "T01.pdf", source)
    out = source.with_name("已修改 " + name)
    window = make_window(ask_save=lambda: str(out))
    open_file(qtbot, window, source)
    find(qtbot, window, "衛生局")
    preview(qtbot, window, "測試局")
    apply(qtbot, window)
    window.actions["save"].trigger()
    wait(qtbot, window)
    assert window.last_error is None and out.is_file()
    open_file(qtbot, window, out)
    assert any("測試局" in t["text"] for t in window.page["text_targets"])
