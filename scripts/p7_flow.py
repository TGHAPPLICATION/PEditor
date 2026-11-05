"""P7 實機驗證用的完整流程（G7-01、G7-02、G7-03；由 scripts/p7_offline_check.ps1 呼叫）。

開檔、分析、渲染、規劃、預覽、套用、復原、重做、另存 T01；再開啟 S02–S06 惡意樣本逐頁分析與渲染。
目前資料夾設為輸出資料夾：S06 的 Launch 若被執行會在此建立 sentinel 檔。
重複 rounds 輪（讓連線監測有足夠的取樣次數）。結果寫到 <輸出資料夾>/flow.json
（不含路徑與文件內容），成功時最後一行印出 FLOW-OK。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "tests" / "fixtures" / "files"


def main(out_dir: Path, rounds: int = 1) -> int:
    from peditor.core.service import DocumentService

    out_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(out_dir)
    steps: list[dict] = []
    started = time.monotonic()
    with DocumentService() as svc:
        for _ in range(rounds):
            _round(svc, out_dir, steps)
    sentinel = sorted(p.name for p in out_dir.glob("peditor-sentinel*"))
    result = {"rounds": rounds, "steps": steps[: 1 + 5], "sentinel_files": sentinel,
              "all_saved": all(s.get("saved", True) for s in steps),
              "seconds": round(time.monotonic() - started, 1)}  # fmt: skip
    (out_dir / "flow.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                       encoding="utf-8")  # fmt: skip
    ok = result["all_saved"] and not sentinel
    print("FLOW-OK" if ok else "FLOW-FAILED")
    return 0 if ok else 1


def _round(svc, out_dir: Path, steps: list[dict]) -> None:
    """一輪：T01 完整編輯流程，再開啟 S02–S06。"""
    from peditor.core.service import ServiceError

    opened = svc.open_document(FILES / "T01.pdf")
    doc = opened["document_id"]
    page = svc.inspect_page(doc, 0)
    svc.render_page(doc, 0)
    target = next(t for t in page["text_targets"] if "衛生局" in t["text"])
    new_text = target["text"].replace("衛生局", "測試局")
    plan = svc.plan_text_edit(doc, target["target_id"], new_text)
    svc.preview_edit(doc, plan["plan_id"], opened["revision"])
    revision = svc.apply_edit(doc, plan["plan_id"], opened["revision"])["new_revision"]
    revision = svc.undo(doc, revision)["new_revision"]
    revision = svc.redo(doc, revision)["new_revision"]
    token = svc.destination_token(out_dir / "T01-edited.pdf", overwrite=True)
    report = svc.export_document(doc, token, revision)
    steps.append({"fixture": "T01", "saved": report["validation_report"]["ok"]})
    svc.close_document(doc)
    for fid in ("S02", "S03", "S04", "S05", "S06"):
        opened = svc.open_document(FILES / f"{fid}.pdf")
        doc = opened["document_id"]
        reasons = svc.inspect_page(doc, 0)["capabilities"]["reasons"]
        try:
            svc.render_page(doc, 0)
            rendered = "ok"
        except ServiceError as exc:
            rendered = exc.code
        steps.append({"fixture": fid, "reasons": reasons, "render": rendered})
        svc.close_document(doc)


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 1))
