"""`peditor analyze`：輸出 JSON 能力報告與頁面 PNG（spec P1 輸出、G1-07）。
`peditor edit-text`：以內容尋找文字、產生 EditPlan、套用並另存，輸出計畫與驗證報告（spec P2 輸出）。

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


def _region(text: str) -> list[float]:
    values = [float(v) for v in text.split(",")]
    if len(values) != 4:
        raise argparse.ArgumentTypeError("region 需為 x0,y0,x1,y1")
    return values


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def edit_text(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="peditor edit-text", description="替換 PDF 中的指定文字")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--find", required=True, help="要替換的原文（以內容尋找，不用 bbox）")
    parser.add_argument("--new", required=True, help="新文字")
    parser.add_argument("--page", type=int, default=0, help="頁碼（0 起算）")
    parser.add_argument("--occurrence", type=int, default=0, help="同頁第幾次出現（0 起算）")
    parser.add_argument("--region", type=_region, help="可改動區域 x0,y0,x1,y1（頁面座標 pt）")
    parser.add_argument("--policy", choices=["prefer_a", "a_only"], default="prefer_a")
    parser.add_argument(
        "--out", type=Path, required=True, help="輸出資料夾（output.pdf 不得已存在）"
    )
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    with DocumentService() as service:
        try:
            token = service.destination_token(args.out / "output.pdf")  # 已存在即 SAVE_FAILED
            opened = service.open_document(args.pdf)
            document_id = opened["document_id"]
            span_id = service.find_text(document_id, args.page, args.find, args.occurrence)
            plan = service.plan_text_edit(document_id, span_id, args.new, args.policy, 0,
                                          args.region)  # fmt: skip
            _write_json(args.out / "plan.json", plan)
            if not plan["ready"]:
                print("無法編輯：" + ",".join(plan["unsupported_reasons"]), file=sys.stderr)
                return 3
            applied = service.apply_edit(document_id, plan["plan_id"], 0)
            exported = service.export_document(document_id, token, applied["new_revision"])
        except ServiceError as exc:
            print(f"編輯失敗：{exc.code}", file=sys.stderr)
            return 2
    _write_json(args.out / "validation.json", {
        "tool": "peditor", "version": __version__, "source_sha256": opened["sha256"],
        "mode": plan["mode"], **exported,
    })  # fmt: skip
    print(json.dumps({"mode": plan["mode"], "output_hash": exported["output_hash"]}))
    return 0
