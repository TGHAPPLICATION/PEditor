"""PEditor 進入點。

`--smoke`：建立主視窗、跑一次事件迴圈後結束，並輸出相依版本，供 CI 與打包後的
smoke test 使用（G0）。
"""

from __future__ import annotations

import argparse
import json
import sys

from peditor import __version__


def _versions() -> dict[str, str]:
    import pikepdf
    import pymupdf
    import PySide6

    return {
        "peditor": __version__,
        "python": sys.version.split()[0],
        "pyside6": PySide6.__version__,
        "pymupdf": pymupdf.VersionBind,
        "pikepdf": pikepdf.__version__,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peditor")
    parser.add_argument("--smoke", action="store_true", help="啟動後立即結束（CI 用）")
    parser.add_argument("--version", action="store_true", help="輸出版本資訊")
    args = parser.parse_args(argv)

    if args.version:
        print(json.dumps(_versions(), ensure_ascii=False))
        return 0

    from peditor.ui.app import run

    return run(smoke=args.smoke, versions=_versions() if args.smoke else None)


if __name__ == "__main__":
    sys.exit(main())
