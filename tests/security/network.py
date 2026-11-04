"""測試用：列出指定行程（含其子孫行程）的 TCP／UDP socket（G7-02、G7-03）。

Windows 以 Get-NetTCPConnection／Get-NetUDPEndpoint 與 CIM 的父子行程關係；
macOS 以 `lsof` 與 `pgrep -P`。
只在測試中使用，不屬產品程式碼。
"""

from __future__ import annotations

import os
import subprocess
import sys


def _children(pid: int) -> list[int]:
    if sys.platform == "win32":
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}').ProcessId"],
            capture_output=True, text=True, timeout=60,
        ).stdout  # fmt: skip
    else:
        out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout
    return [int(v) for v in out.split() if v.isdigit()]


def process_tree(pids: list[int]) -> set[int]:
    seen: set[int] = set()
    todo = list(pids)
    while todo:
        pid = todo.pop()
        if pid not in seen:
            seen.add(pid)
            todo.extend(_children(pid))
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
        command = ["powershell", "-NoProfile", "-Command", script]
        out = subprocess.run(
            command, capture_output=True, text=True, timeout=120, check=True
        ).stdout
        return [line.strip() for line in out.splitlines() if line.strip()]
    out = subprocess.run(
        ["lsof", "-nP", "-a", "-p", ",".join(map(str, sorted(tree))), "-i"],
        capture_output=True, text=True, timeout=60,
    ).stdout  # fmt: skip
    return [line for line in out.splitlines()[1:] if line.strip()]
