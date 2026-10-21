"""`peditor analyze`：輸出 JSON 能力報告與頁面 PNG（spec P1 輸出、G1-07）。

PDF 只在 worker 中解析；本模組只透過 DocumentService 取得結果並寫檔。
錯誤訊息只含錯誤碼，不含檔案路徑或文件內容。
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from peditor import __version__
from peditor.core.protocol import PROTOCOL_VERSION
from peditor.core.service import DocumentService, ServiceError


def analyze(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peditor analyze", description="只讀分析 PDF")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="輸出資料夾")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--no-png", action="store_true", help="不輸出頁面 PNG")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    with DocumentService() as service:
        try:
            opened = service.open_document(args.pdf)
            document_id = opened["document_id"]
            assessment = service.assess_editability(document_id)
            pages = []
            for summary in assessment["pages"]:
                index = summary["page_index"]
                pages.append(service.inspect_page(document_id, index))
                if not args.no_png:
                    image = service.render_page(document_id, index, args.dpi)
                    png = base64.b64decode(image["png_base64"])
                    (args.out / f"page-{index + 1:04d}.png").write_bytes(png)
        except ServiceError as exc:
            print(f"分析失敗：{exc.code}", file=sys.stderr)
            return 2
    report = {
        "tool": "peditor",
        "version": __version__,
        "protocol_version": PROTOCOL_VERSION,
        "sha256": opened["sha256"],
        "page_count": opened["page_count"],
        "document_flags": opened["document_flags"],
        "assessment": assessment,
        "pages": pages,
    }
    (args.out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(assessment["document"], ensure_ascii=False))
    return 0
