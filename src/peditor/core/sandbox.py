"""worker 子行程的作業系統層級限制（spec P7、ADR-0024）。只用標準函式庫，主行程與 worker 共用。

- Windows：worker 以暫停狀態建立，主行程以 Job Object 包住後才恢復執行（沒有未受限的時間窗）——
  行程記憶體上限、不得再建立子行程、不得使用剪貼簿等 UI 資源、主行程的 job handle 關閉
  （含主行程異常結束）時 worker 一併終止。
- macOS 等 POSIX：worker 啟動時（讀任何 PDF 之前）自行設 RLIMIT_AS 與 RLIMIT_CORE；
  macOS 核心不強制 RLIMIT_AS，記憶體上限在 macOS 只是宣告（ADR-0024 缺口）。

這不是 OS 沙箱：worker 仍以使用者權限執行，可讀寫使用者可存取的檔案（ADR-0024）。
"""

from __future__ import annotations

import sys

from peditor.core.limits import WORKER_MEMORY_BYTES

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x0008
    _JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100
    _JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x0400
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    _JOB_OBJECT_UILIMIT_ALL = (
        0x00FF  # 桌面、顯示設定、登出、全域 atom、USER handle、剪貼簿、系統參數
    )
    _JOB_BASIC_UI_RESTRICTIONS = 4
    _JOB_EXTENDED_LIMIT_INFORMATION = 9
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_TERMINATE = 0x0001
    _TH32CS_SNAPTHREAD = 0x0004
    _THREAD_SUSPEND_RESUME = 0x0002
    _INVALID_HANDLE = wintypes.HANDLE(-1).value
    CREATE_SUSPENDED = 0x0004

    class _ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    class _BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimit),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    )  # fmt: skip
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _kernel32.Thread32First.restype = wintypes.BOOL
    _kernel32.Thread32First.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    _kernel32.Thread32Next.restype = wintypes.BOOL
    _kernel32.Thread32Next.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    _kernel32.OpenThread.restype = wintypes.HANDLE
    _kernel32.OpenThread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.ResumeThread.restype = wintypes.DWORD
    _kernel32.ResumeThread.argtypes = (wintypes.HANDLE,)
else:
    CREATE_SUSPENDED = 0


class SandboxError(Exception):
    """無法對 worker 套用限制；呼叫端應終止 worker，不得在沒有限制下繼續（fail closed）。"""


class WorkerJob:
    """Windows：包住一個 worker 的 Job Object；close() 時 worker 一併終止。其他平台不做事。

    worker 須以 CREATE_SUSPENDED 建立；套用限制後由本類別恢復執行。processes 為 job 內允許的
    行程數：1；開發環境的 venv `python.exe` 是轉介程式、會再啟動真正的直譯器，需要 2
    （仍不能再多建立任何子行程）。"""

    def __init__(
        self, pid: int, processes: int = 1, memory_bytes: int = WORKER_MEMORY_BYTES
    ) -> None:
        self._handle = None
        if sys.platform != "win32":
            return
        job = _kernel32.CreateJobObjectW(None, None)
        if not job:
            raise SandboxError("CreateJobObject")
        self._handle = job
        try:
            info = _ExtendedLimit()
            info.BasicLimitInformation.LimitFlags = (
                _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | _JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | _JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
                | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            info.BasicLimitInformation.ActiveProcessLimit = processes  # 不得再建立子行程
            info.ProcessMemoryLimit = memory_bytes
            if not _kernel32.SetInformationJobObject(
                job, _JOB_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)
            ):
                raise SandboxError("SetInformationJobObject")
            ui = wintypes.DWORD(_JOB_OBJECT_UILIMIT_ALL)
            if not _kernel32.SetInformationJobObject(
                job, _JOB_BASIC_UI_RESTRICTIONS, ctypes.byref(ui), ctypes.sizeof(ui)
            ):
                raise SandboxError("SetInformationJobObject(UI)")
            process = _kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
            if not process:
                raise SandboxError("OpenProcess")
            try:
                if not _kernel32.AssignProcessToJobObject(job, process):
                    raise SandboxError("AssignProcessToJobObject")
            finally:
                _kernel32.CloseHandle(process)
            _resume(pid)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle:
            _kernel32.CloseHandle(handle)


def _resume(pid: int) -> None:
    """恢復以 CREATE_SUSPENDED 建立的行程（主執行緒；Toolhelp 列舉該行程的執行緒）。"""
    snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPTHREAD, 0)
    if not snapshot or snapshot == _INVALID_HANDLE:
        raise SandboxError("CreateToolhelp32Snapshot")
    resumed = 0
    try:
        entry = _ThreadEntry()
        entry.dwSize = ctypes.sizeof(entry)
        more = _kernel32.Thread32First(snapshot, ctypes.byref(entry))
        while more:
            if entry.th32OwnerProcessID == pid:
                thread = _kernel32.OpenThread(_THREAD_SUSPEND_RESUME, False, entry.th32ThreadID)
                if not thread:
                    raise SandboxError("OpenThread")
                try:
                    if _kernel32.ResumeThread(thread) == 0xFFFFFFFF:
                        raise SandboxError("ResumeThread")
                    resumed += 1
                finally:
                    _kernel32.CloseHandle(thread)
            more = _kernel32.Thread32Next(snapshot, ctypes.byref(entry))
    finally:
        _kernel32.CloseHandle(snapshot)
    if not resumed:
        raise SandboxError("no thread")


def limit_self(memory_bytes: int = WORKER_MEMORY_BYTES) -> None:
    """POSIX worker 啟動時呼叫：位址空間上限與不寫 core dump（hard limit 一併設定，之後無法調高）。
    macOS 核心不強制 RLIMIT_AS；設定失敗不中止（記憶體上限在 macOS 本來就只是宣告，ADR-0024）。"""
    if sys.platform == "win32":
        return
    import resource

    for limit, value in ((resource.RLIMIT_AS, memory_bytes), (resource.RLIMIT_CORE, 0)):
        try:
            resource.setrlimit(limit, (value, value))
        except (ValueError, OSError):
            pass
