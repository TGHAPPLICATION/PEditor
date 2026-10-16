"""離線原則的靜態護欄：產品原始碼不得匯入網路模組（P7 再以實機監測驗證）。"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN = {
    "socket",
    "ssl",
    "http",
    "urllib",
    "ftplib",
    "smtplib",
    "requests",
    "httpx",
    "aiohttp",
    "PySide6.QtNetwork",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
}


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
            yield from (f"{node.module}.{a.name}" for a in node.names)


def test_no_network_imports_in_product_code():
    violations = []
    for path in (ROOT / "src").rglob("*.py"):
        for name in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            if any(name == f or name.startswith(f + ".") for f in FORBIDDEN):
                violations.append(f"{path.relative_to(ROOT)}: {name}")
    assert not violations, violations
