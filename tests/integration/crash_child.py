"""crash injection 子行程（G3-03）：編輯並另存，在指定階段前以 os._exit 中止整個行程。

用法：python crash_child.py <source> <destination> <stage> <old> <new> <region>
"""

import os
import sys

from peditor.core.service import DocumentService
from peditor.export import transaction


def main() -> None:
    source, destination, stage, old, new, region = sys.argv[1:7]

    def crash(name: str) -> None:
        if name == stage:
            os._exit(17)  # 模擬斷電／被強制結束：不執行任何清理

    with DocumentService() as service:
        doc = service.open_document(source)["document_id"]
        span_id = service.find_text(doc, 0, old)
        plan = service.plan_text_edit(doc, span_id, new, "prefer_a", 0,
                                      [float(v) for v in region.split(",")])  # fmt: skip
        rev = service.apply_edit(doc, plan["plan_id"], 0)["new_revision"]
        token = service.destination_token(destination, overwrite=True)
        transaction.fault = crash
        service.export_document(doc, token, rev)
    sys.exit(0)


if __name__ == "__main__":
    main()
