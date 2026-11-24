"""測試用：列出指定行程（含其子孫行程）的 TCP／UDP socket（G7-02、G7-03）。

Windows 以一次 CIM 查詢取得全部行程的父子關係、一次 Get-NetTCPConnection／Get-NetUDPEndpoint
取得 socket；macOS 以一次 `ps` 與 `lsof`。每輪約 1–2 秒（P7 第二輪核對 W2：原本每個 pid 各叫一次
PowerShell，一輪約 5 秒）。列舉失敗一律 RuntimeError，不讓結果變少而假通過。
只在測試中使用，不屬產品程式碼。
"""

from __future__ import annotations

import os
import subprocess
import sys


def _run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError("enumeration failed")
    return result.stdout


def _parents() -> dict[int, tuple[int, int]]:
    """全部行程的 pid → (父 pid, 建立時間)（一次查詢；建立時間只在 Windows 有，其他平台為 0）。"""
    if sys.platform == "win32":
        out = _run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process | ForEach-Object "
                    "{ \"$($_.ProcessId) $($_.ParentProcessId) $(if ($_.CreationDate) "
                    "{ $_.CreationDate.ToFileTimeUtc() } else { 0 })\" }"])  # fmt: skip
    else:
        out = _run(["ps", "-A", "-o", "pid=,ppid="])
    pairs = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) in (2, 3) and all(p.isdigit() for p in parts):
            pairs[int(parts[0])] = (int(parts[1]), int(parts[2]) if len(parts) == 3 else 0)
    if not pairs:
        raise RuntimeError("enumeration failed")
    return pairs


def process_tree(pids: list[int]) -> set[int]:
    """這些行程與其子孫。Windows 不會把孤兒行程改掛到別的父行程，父 pid 可能已被重用
    （例如 wininit、csrss 的父行程 smss 早已結束）：子行程建立時間早於「父」行程者不是它的子行程。
    2026-11-24 CI 曾因此把整串系統服務誤認為測試行程的子孫（run 的 test_no_listening_sockets）。"""
    parents = _parents()
    children: dict[int, list[int]] = {}
    for pid, (ppid, created) in parents.items():
        parent_created = parents.get(ppid, (0, 0))[1]
        if pid != ppid and created >= parent_created:
            children.setdefault(ppid, []).append(pid)
    seen: set[int] = set()
    todo = list(pids)
    while todo:
        pid = todo.pop()
        if pid not in seen:
            seen.add(pid)
            todo.extend(children.get(pid, []))
    return seen


def connections(pids: list[int], include_self: bool = False) -> list[str]:
    """這些行程（含子孫）擁有的 socket，每筆一行原始輸出；沒有即為空清單。"""
    tree = process_tree(pids + ([os.getpid()] if include_self else []))
    if sys.platform == "win32":
        # netstat 的輸出（本地化、編碼）不可靠，改用 NetTCPIP 模組的結構化結果
        ids = ",".join(map(str, sorted(tree)))
        script = (
            f"$ids = @({ids}); "
            "Get-NetTCPConnection | Where-Object { $ids -contains $_.OwningProcess } | "
            "ForEach-Object { 'TCP ' + $_.LocalAddress + ':' + $_.LocalPort + ' ' + "
            "$_.RemoteAddress + ':' + $_.RemotePort + ' ' + $_.State + ' ' + $_.OwningProcess }; "
            "Get-NetUDPEndpoint | Where-Object { $ids -contains $_.OwningProcess } | "
            "ForEach-Object { 'UDP ' + $_.LocalAddress + ':' + $_.LocalPort + ' ' + "
            "$_.OwningProcess }"
        )
        out = _run(["powershell", "-NoProfile", "-Command", script])
        return [line.strip() for line in out.splitlines() if line.strip()]
    # lsof：-p 指定的行程中有任一個沒有符合的檔案即回結束碼 1（其他行程的結果照常輸出）；
    # 結束碼 1 且 stderr 沒有錯誤訊息視為正常，其他情況一律視為列舉失敗（P7 第二輪核對 W5）
    result = subprocess.run(
        ["lsof", "-nP", "-a", "-p", ",".join(map(str, sorted(tree))), "-i"],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    if result.returncode != 0 and not (result.returncode == 1 and not result.stderr.strip()):
        raise RuntimeError("enumeration failed")
    return [line for line in result.stdout.splitlines()[1:] if line.strip()]
