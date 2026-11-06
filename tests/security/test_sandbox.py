"""G7-04、G7-06：worker 的 OS 層級限制（ADR-0024）。

Windows 由 Job Object 強制：記憶體上限受控回 RESOURCE_LIMIT、worker 不得建立子行程、
主行程結束時 worker 一併終止。macOS 核心不強制 RLIMIT_AS，記憶體與子行程限制在 macOS
屬已知缺口（ADR-0024），相關測試只在 Windows 執行，報告記為 NOT RUN。
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from peditor.core.limits import WORKER_MEMORY_BYTES
from peditor.core.service import DocumentService, ServiceError, _processes

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"
WINDOWS_ONLY = pytest.mark.skipif(
    sys.platform != "win32", reason="macOS 不強制 RLIMIT_AS、無 Job Object（ADR-0024 缺口）"
)


@pytest.fixture
def hooked(monkeypatch):
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    with DocumentService(timeout=60.0) as svc:
        yield svc


@WINDOWS_ONLY
def test_memory_limit_controlled(hooked):
    """超過 worker 記憶體上限：受控回 RESOURCE_LIMIT，不是崩潰；之後 worker 仍可用。"""
    doc = hooked.open_document(FILES / "T01.pdf")["document_id"]
    with pytest.raises(ServiceError) as exc:
        hooked._send_raw("_alloc", {"bytes": WORKER_MEMORY_BYTES + 256 * 1024 * 1024})
    assert exc.value.code == "RESOURCE_LIMIT"
    assert hooked._send_raw("_alloc", {"bytes": 64 * 1024 * 1024})["allocated"] > 0
    assert hooked.inspect_page(doc, 0)["text_targets"]


@WINDOWS_ONLY
def test_worker_cannot_spawn_processes(hooked):
    """worker 被攻陷時也不能啟動外部程式（Job Object ActiveProcessLimit=1）。"""
    assert hooked._send_raw("_spawn", {}) == {"spawned": False}


def test_spawn_hook_works_without_job(monkeypatch):
    """對照：沒有 Job Object 時同一個 hook 能建立子行程（確認上一項不是 hook 本身失效）。"""
    from peditor.worker import server

    monkeypatch.setattr(server, "_TEST_HOOKS", True)
    assert server._test_hook("_spawn", {}) == {"spawned": True}


@WINDOWS_ONLY
def test_worker_dies_with_main_process(tmp_path, monkeypatch):
    """主行程異常結束（未呼叫 close）時，worker 隨 Job handle 關閉一併終止，不留孤兒行程。
    worker 正在執行長操作（不會因管線關閉讀到 EOF 而自行結束）。"""
    monkeypatch.setenv("PEDITOR_WORKER_TEST_HOOKS", "1")
    script = tmp_path / "main.py"
    script.write_text(
        "import os, sys, threading, time\n"
        "from peditor.core.service import DocumentService\n"
        "svc = DocumentService(timeout=120)\n"
        f"svc.open_document({str(FILES / 'T01.pdf')!r})\n"
        "args = ('_sleep', {'seconds': 60})\n"
        "threading.Thread(target=svc._send_raw, args=args, daemon=True).start()\n"
        "time.sleep(1)\n"
        f"sys.path.insert(0, {str(Path(__file__).parent)!r})\n"
        "from network import process_tree\n"
        "tree = sorted(process_tree([svc._worker.proc.pid]))\n"
        "print(' '.join(map(str, tree)), flush=True)\n"
        "os._exit(0)\n",
        encoding="utf-8",
    )
    out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                         timeout=120, check=True).stdout  # fmt: skip
    tree = [int(v) for v in out.split()]
    assert len(tree) >= _processes([sys.executable])  # 開發環境：轉介程式與真正的直譯器
    alive = tree
    for _ in range(50):
        listing = subprocess.run(["tasklist", "/NH"], capture_output=True, text=True).stdout
        running = {int(c[1]) for c in (line.split() for line in listing.splitlines())
                   if len(c) > 1 and c[1].isdigit()}  # fmt: skip
        alive = [pid for pid in tree if pid in running]
        if not alive:
            break
        time.sleep(0.1)
    assert not alive  # 整棵行程樹（P7 獨立核對 V5）
