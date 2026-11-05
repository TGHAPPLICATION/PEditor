"""G7-05：日誌與錯誤訊息不洩漏 sentinel、文件原文、密碼或完整路徑（spec P7、CLAUDE.md）。

產品不寫日誌檔（ADR-0024）；會離開 worker 或主行程的文字只有：錯誤訊息（ServiceError，UI 顯示
的就是它）、worker 的 stderr（產品導向 DEVNULL，這裡改接到檔案以便檢查）、CLI 的 stderr。
樣本放在名稱含 sentinel 的資料夾與檔名，文件內容（S02 的 JavaScript）與新文字也含 sentinel，
並刻意觸發各種失敗，之後上述輸出都不得含 sentinel 或暫存資料夾的完整路徑。
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from peditor.core.service import DocumentService, ServiceError

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
SENTINEL = "peditor-sentinel"


def _worker_with_stderr(path: Path) -> list[str]:
    """與產品相同的 worker，只是 stderr 寫到檔案（產品為 DEVNULL）。"""
    script = (
        "import os, sys\n"
        f"fd = os.open({str(path)!r}, os.O_WRONLY | os.O_CREAT | os.O_APPEND)\n"
        "os.dup2(fd, 2)\n"
        "sys.stderr = open(2, 'w', closefd=False)\n"
        "from peditor.worker.server import main\n"
        "sys.exit(main())\n"
    )
    return [sys.executable, "-P", "-c", script]


def test_no_sentinel_in_logs(tmp_path):
    folder = tmp_path / f"{SENTINEL}-folder"
    folder.mkdir()
    for fid in ("T01", "S01", "S02", "S03", "U02"):
        shutil.copy(FILES / f"{fid}.pdf", folder / f"{SENTINEL}-{fid}.pdf")
    stderr = tmp_path / "worker-stderr.txt"
    messages: list[str] = []

    def attempt(func, *args):
        try:
            return func(*args)
        except ServiceError as exc:
            messages.append(f"{exc.code} {exc.message}")
            return None

    with DocumentService(command=_worker_with_stderr(stderr)) as svc:
        attempt(svc.open_document, folder / f"{SENTINEL}-missing.pdf")
        for fid in ("S01", "S02", "S03", "U02"):
            opened = attempt(svc.open_document, folder / f"{SENTINEL}-{fid}.pdf")
            if opened:
                attempt(svc.inspect_page, opened["document_id"], 0)
                attempt(svc.render_page, opened["document_id"], 0)
        opened = svc.open_document(folder / f"{SENTINEL}-T01.pdf")
        doc = opened["document_id"]
        target = svc.inspect_page(doc, 0)["text_targets"][0]["target_id"]
        attempt(svc.find_text, doc, 0, SENTINEL)
        plan = attempt(svc.plan_text_edit, doc, target, f"{SENTINEL} 新文字 𠮷")
        messages += [f"{r}" for r in (plan or {}).get("unsupported_reasons", [])]
        messages += [f"{w}" for w in (plan or {}).get("warnings", [])]
        attempt(svc.plan_text_edit, doc, target, "x", "prefer_a", 0, [0, 0, 1e9, 1e9])
        attempt(svc.register_image, doc, folder / f"{SENTINEL}-T01.pdf")  # 不是圖片
        attempt(svc.register_image, doc, folder / f"{SENTINEL}-missing.png")  # 讀不到
        attempt(svc.destination_token, folder / f"{SENTINEL}-T01.pdf")
        attempt(svc.destination_token, folder / "no-such-dir" / f"{SENTINEL}.pdf")
        attempt(svc.export_document, doc, f"{SENTINEL}-token", opened["revision"])
        attempt(svc.apply_edit, doc, f"{SENTINEL}-plan", opened["revision"])

    assert messages, "應觸發多個錯誤"
    outputs = [*messages, stderr.read_text(encoding="utf-8", errors="replace")]
    for text in outputs:
        assert SENTINEL not in text, text
        assert str(tmp_path) not in text and tmp_path.name not in text, text


@pytest.mark.parametrize(
    "args",
    [
        ["analyze", "{folder}/{s}-S02.pdf", "--out", "{folder}/out"],
        ["analyze", "{folder}/{s}-missing.pdf", "--out", "{folder}/o"],
    ],
)
def test_cli_stderr_has_no_sentinel(args, tmp_path):
    """CLI 的錯誤輸出同樣只有理由碼。"""
    folder = tmp_path / f"{SENTINEL}-folder"
    folder.mkdir()
    shutil.copy(FILES / "S02.pdf", folder / f"{SENTINEL}-S02.pdf")
    argv = [a.format(folder=folder, s=SENTINEL) for a in args]
    result = subprocess.run([sys.executable, "-P", "-m", "peditor", *argv], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120)  # fmt: skip
    assert SENTINEL not in result.stderr and str(tmp_path) not in result.stderr, result.stderr
