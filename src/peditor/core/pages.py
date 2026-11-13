"""頁面工具的頁碼範圍與組頁計畫（ADR-0029）；純函式，主行程與測試共用。

計畫是 [(來源索引, 頁索引)] 的清單（頁索引從 0 起），由 worker 的 compose_pages 依序組成新檔。
"""

from __future__ import annotations

import re

from peditor.core.limits import MAX_COMPOSE_SOURCES, MAX_PAGES

Plan = list[tuple[int, int]]
_PART = re.compile(r"^(\d{1,5})(?:\s*[-－~～]\s*(\d{1,5}))?$")


class RangeError(ValueError):
    """頁碼範圍格式錯誤或超出頁數；訊息可直接顯示給使用者（不含文件內容）。"""


def parse_ranges(text: str, page_count: int) -> list[int]:
    """「1-3,5,7-9」（1 起算；全形逗號、頓號、空白可分隔）→ 由小到大、不重複的頁索引（0 起算）。"""
    if page_count <= 0:
        raise RangeError("文件沒有頁面")
    parts = [p.strip() for p in re.split(r"[,，、;；\s]+", text.strip()) if p.strip()]
    if not parts:
        raise RangeError("請輸入頁碼，例如 1-3,5")
    pages: set[int] = set()
    for part in parts:
        match = _PART.match(part)
        if match is None:
            raise RangeError(f"無法辨識「{part[:20]}」，請用 1-3,5 的格式")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start:
            raise RangeError(f"範圍「{part}」不正確")
        if end > page_count:
            raise RangeError(f"第 {end} 頁超出頁數（共 {page_count} 頁）")
        pages.update(range(start - 1, end))
    return sorted(pages)


def delete_plan(page_count: int, deleted: list[int]) -> Plan:
    """刪除指定頁；全部刪除即錯誤（輸出不能沒有頁面）。"""
    drop = set(deleted)
    plan = [(0, i) for i in range(page_count) if i not in drop]
    if not plan:
        raise RangeError("不能刪除全部頁面")
    return plan


def keep_plan(page_count: int, kept: list[int]) -> Plan:
    """只保留（擷取）指定頁，依原順序。"""
    plan = [(0, i) for i in sorted(set(kept)) if 0 <= i < page_count]
    if not plan:
        raise RangeError("沒有要保留的頁面")
    return plan


def merge_plan(page_counts: list[int]) -> Plan:
    """依序接續每份檔案的全部頁面。"""
    if len(page_counts) < 2:
        raise RangeError("合併至少需要兩份檔案")
    if len(page_counts) > MAX_COMPOSE_SOURCES:
        raise RangeError(f"最多 {MAX_COMPOSE_SOURCES} 份檔案")
    plan = [(s, i) for s, count in enumerate(page_counts) for i in range(count)]
    return _bounded(plan)


def insert_plan(base_count: int, insert_count: int, position: int) -> Plan:
    """在基礎檔第 position 頁之後插入另一份的全部頁面（0＝最前面、base_count＝最後面）。"""
    if not 0 <= position <= base_count:
        raise RangeError(f"插入位置須在 0 到 {base_count} 之間")
    plan = [(0, i) for i in range(position)]
    plan += [(1, i) for i in range(insert_count)]
    plan += [(0, i) for i in range(position, base_count)]
    return _bounded(plan)


def _bounded(plan: Plan) -> Plan:
    if len(plan) > MAX_PAGES:
        raise RangeError(f"合計 {len(plan)} 頁，超過上限 {MAX_PAGES} 頁")
    return plan
