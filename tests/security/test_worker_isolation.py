"""G1-01：使用者 PDF 只在 worker 子行程解析；主行程不載入 PDF 程式庫（ADR-0004）。"""

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF_LIBS = {"pymupdf", "fitz", "pikepdf", "pypdfium2"}
# 主行程端的模組：UI、core（DocumentService 等）、CLI。
# __main__.py 不列入：它只在 --version／--smoke 時匯入 pymupdf／pikepdf 讀版本字串，不開使用者 PDF；
# 開檔路徑是否載入 PDF 程式庫由下方執行期測試涵蓋。
MAIN_PROCESS_MODULES = [
    *(ROOT / "src" / "peditor" / "ui").rglob("*.py"),
    *(ROOT / "src" / "peditor" / "core").rglob("*.py"),
    ROOT / "src" / "peditor" / "cli.py",
]


def _imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module.split(".")[0]
            if node.module == "peditor":
                yield from (f"peditor.{a.name}" for a in node.names)
            elif node.module.startswith("peditor."):
                yield node.module


def test_main_process_modules_do_not_import_pdf_libs_or_worker():
    violations = []
    for path in MAIN_PROCESS_MODULES:
        for name in _imports(path):
            if name in PDF_LIBS or name.startswith("peditor.worker"):
                violations.append(f"{path.relative_to(ROOT)}: {name}")
    assert not violations, violations


def test_main_process_never_imports_pdf_libs_for_user_files(tmp_path):
    """實際開檔、分析、渲染後，主行程的 sys.modules 仍沒有任何 PDF 程式庫。"""
    script = tmp_path / "probe.py"
    script.write_text(
        "import json, sys\n"
        "from peditor.core.service import DocumentService\n"
        "with DocumentService() as s:\n"
        "    doc = s.open_document(sys.argv[1])['document_id']\n"
        "    s.assess_editability(doc)\n"
        "    s.inspect_page(doc, 0)\n"
        "    s.render_page(doc, 0, 72)\n"
        "loaded = sorted(m for m in sys.modules if m.split('.')[0] in "
        + repr(sorted(PDF_LIBS))
        + " or m.startswith('peditor.worker'))\n"
        "print(json.dumps(loaded))\n",
        encoding="utf-8",
    )
    pdf = ROOT / "tests" / "fixtures" / "files" / "T05.pdf"
    result = subprocess.run(
        [sys.executable, str(script), str(pdf)], capture_output=True, timeout=120, text=True
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []
