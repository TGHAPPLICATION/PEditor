"""下載 fixture 與模式 B 用字型（鎖定 commit），並驗證 SHA-256。

只在開發機／CI 執行；產品執行期不下載任何東西（spec §1）。
用法：uv run python scripts/fetch_fonts.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "fonts"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font_paths() -> dict[str, Path]:
    spec = json.loads((FONT_DIR / "fonts.json").read_text(encoding="utf-8"))
    return {f["file"]: FONT_DIR / f["file"] for f in spec["fonts"]}


def fetch() -> None:
    spec = json.loads((FONT_DIR / "fonts.json").read_text(encoding="utf-8"))
    for font in spec["fonts"]:
        path = FONT_DIR / font["file"]
        if path.exists() and _sha256(path) == font["sha256"]:
            print(f"ok      {font['file']}")
            continue
        tmp = path.with_suffix(path.suffix + ".part")
        # URL 來自 fonts.json 的固定 https 位址
        with urllib.request.urlopen(font["url"], timeout=120) as resp:  # noqa: S310
            tmp.write_bytes(resp.read())
        actual = _sha256(tmp)
        if actual != font["sha256"]:
            tmp.unlink()
            raise SystemExit(f"SHA-256 不符：{font['file']} {actual}")
        tmp.replace(path)
        print(f"fetched {font['file']}")


if __name__ == "__main__":
    fetch()
    sys.exit(0)
