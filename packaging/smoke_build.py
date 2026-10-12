"""G0 smoke build：以 PyInstaller 打包 onedir，並執行打包結果的 --smoke。

只證明「相依可被凍結並在目標平台啟動」；正式打包（DMG、簽章、SBOM）在 P8。
用法：uv run python packaging/smoke_build.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "build" / "smoke" / "dist"
WORK = ROOT / "build" / "smoke" / "work"
MARKER = "PEDITOR_SMOKE_OK"


def main() -> int:
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean", "--onedir", "--console",
            "--name", "peditor",
            "--distpath", str(DIST),
            "--workpath", str(WORK),
            "--specpath", str(WORK),
            "--paths", str(ROOT / "src"),
            str(ROOT / "packaging" / "pyinstaller_entry.py"),
        ],
        check=True,
    )  # fmt: skip
    exe = DIST / "peditor" / ("peditor.exe" if os.name == "nt" else "peditor")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [str(exe), "--smoke"], capture_output=True, text=True, env=env, timeout=120, check=False
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode != 0 or MARKER not in result.stdout:
        print(f"smoke build FAILED (exit {result.returncode})", file=sys.stderr)
        return 1
    files = (DIST / "peditor").rglob("*")
    size = sum(f.stat().st_size for f in files if f.is_file() and not f.is_symlink())
    print(f"smoke build OK, onedir size = {size / 1_048_576:.1f} MiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
