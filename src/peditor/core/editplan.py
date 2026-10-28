"""EditPlan 與 span target（spec §7、ADR-0018）。只用標準函式庫，主行程與 worker 共用。

span target：P1 的文字目標（一個文字顯示運算子）一段或多段，加上第一段起始字元與最後一段結束字元。
EditPlan 只由 worker 依解析結果產生；呼叫端只能送 target_id、new_text、policy、editable_region，
不能送任何 PDF 指令或物件（spec §7「禁止由 UI 任意發入原始 PDF 指令」）。
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field

from peditor.core.protocol import ProtocolError

MAX_NEW_TEXT = 200  # 字元；固定框內替換，不做長文排版
POLICIES = frozenset({"prefer_a", "a_only"})  # ADR-0001：預設 A、A 不可行才 B；a_only 為嚴格 A
PLAN_PARAMS = frozenset({"target_id", "new_text", "policy", "editable_region"})

_TARGET_RE = re.compile(
    r"^(?P<kind>[ti]):r(?P<rev>\d+):p(?P<page>\d+):s(?P<num>\d+)\.(?P<gen>\d+)"
    r":o(?P<op>\d+):f(?P<form>[^:+]*):g(?P<geom>[0-9a-f]{12})$"
)
_SPAN_RE = re.compile(r"^span:(?P<parts>.+):c(?P<start>\d+)-(?P<end>\d+)$")


@dataclass(frozen=True)
class TargetRef:
    """P1 target_id 的組成（spec §7）。"""

    kind: str
    revision: int
    page_index: int
    stream: tuple[int, int]
    op_index: int
    form: str
    geometry: str


def parse_target_id(target_id: str) -> TargetRef:
    match = _TARGET_RE.match(target_id) if isinstance(target_id, str) else None
    if match is None:
        raise ProtocolError("INVALID_REQUEST", "target_id 格式錯誤")
    return TargetRef(match["kind"], int(match["rev"]), int(match["page"]),
                     (int(match["num"]), int(match["gen"])), int(match["op"]), match["form"],
                     match["geom"])  # fmt: skip


@dataclass(frozen=True)
class SpanTarget:
    """選取範圍：連續的文字目標，起始字元在 parts[0]、結束字元（不含）在 parts[-1]。"""

    parts: tuple[str, ...]
    start: int
    end: int

    def __post_init__(self) -> None:
        refs = [parse_target_id(p) for p in self.parts]
        if not refs or any(r.kind != "t" for r in refs):
            raise ProtocolError("INVALID_REQUEST", "選取範圍必須是文字目標")
        same_page = len({(r.revision, r.page_index) for r in refs}) == 1
        if not same_page or len(set(self.parts)) != len(refs):
            raise ProtocolError("INVALID_REQUEST", "選取範圍必須在同一頁且不重複")
        if self.start < 0 or self.end < 0 or (len(refs) == 1 and self.start >= self.end):
            raise ProtocolError("INVALID_REQUEST", "字元範圍錯誤")

    @property
    def revision(self) -> int:
        return parse_target_id(self.parts[0]).revision

    @property
    def page_index(self) -> int:
        return parse_target_id(self.parts[0]).page_index

    @property
    def span_id(self) -> str:
        return f"span:{'+'.join(self.parts)}:c{self.start}-{self.end}"

    @classmethod
    def parse(cls, span_id: str) -> SpanTarget:
        match = _SPAN_RE.match(span_id) if isinstance(span_id, str) else None
        if match is None:
            raise ProtocolError("INVALID_REQUEST", "span target 格式錯誤")
        return cls(tuple(match["parts"].split("+")), int(match["start"]), int(match["end"]))


def common_affixes(old: str, new: str) -> tuple[int, int]:
    """相同開頭與結尾的字元數（ADR-0018 §1 實際改動範圍）；兩者不重疊。"""
    limit = min(len(old), len(new))
    prefix = 0
    while prefix < limit and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    while suffix < limit - prefix and old[-1 - suffix] == new[-1 - suffix]:
        suffix += 1
    return prefix, suffix


def validate_plan_params(params: dict) -> dict:
    """plan_text_edit 的參數白名單與型別；回傳正規化後的參數。"""
    unknown = set(params) - PLAN_PARAMS
    if unknown:
        raise ProtocolError("INVALID_REQUEST", "不支援的參數")
    new_text = params.get("new_text")
    if not isinstance(new_text, str) or not 0 < len(new_text) <= MAX_NEW_TEXT:
        raise ProtocolError("INVALID_REQUEST", "new_text 長度錯誤")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn") for ch in new_text):
        raise ProtocolError("INVALID_REQUEST", "new_text 含控制或未定義字元")
    policy = params.get("policy", "prefer_a")
    if policy not in POLICIES:
        raise ProtocolError("INVALID_REQUEST", "未知 policy")
    target_id = params.get("target_id")
    if not isinstance(target_id, str):
        raise ProtocolError("INVALID_REQUEST", "缺少 target_id")
    region = params.get("editable_region")
    if region is not None:
        if (not isinstance(region, list) or len(region) != 4
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                           and math.isfinite(v) for v in region)
                or region[0] >= region[2] or region[1] >= region[3]):  # fmt: skip
            raise ProtocolError("INVALID_REQUEST", "editable_region 格式錯誤")
        region = [float(v) for v in region]
    return {
        "target_id": target_id,
        "new_text": new_text,
        "policy": policy,
        "editable_region": region,
    }


@dataclass
class EditPlan:
    """spec §7 EditPlan；unsupported_reasons 非空即為拒絕的計畫（不可套用）。"""

    plan_id: str
    document_id: str
    preconditions: dict  # {"sha256", "revision"}
    target: dict  # span_id、page_index、selected_text、change（實際改動範圍）
    new_text: str
    policy: str
    mode: str | None  # "A"、"B"；拒絕時為 None
    font_policy: str
    allowed_change_mask: list[float] | None  # 可改動區域（頁面座標 pt）
    geometry: dict = field(default_factory=dict)
    resource_changes: list = field(default_factory=list)
    font_changes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    unsupported_reasons: list = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.unsupported_reasons and self.mode in ("A", "B")

    def to_dict(self) -> dict:
        return {**asdict(self), "ready": self.ready}
