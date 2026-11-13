"""P9-01、P9-03：頁碼範圍解析與四種組頁計畫（ADR-0029）。"""

import pytest

from peditor.core import pages
from peditor.core.limits import MAX_COMPOSE_SOURCES, MAX_PAGES


@pytest.mark.parametrize(("text", "expected"), [
    ("1-3,5", [0, 1, 2, 4]),
    ("5, 1-2", [0, 1, 4]),  # 排序
    ("2，3、3", [1, 2]),  # 全形逗號、頓號；去重
    ("7-9", [6, 7, 8]),
    ("4－5", [3, 4]),  # 全形連字號
    ("  10  ", [9]),
])  # fmt: skip
def test_parse_ranges(text, expected):
    assert pages.parse_ranges(text, 10) == expected


@pytest.mark.parametrize(("text", "message"), [
    ("", "請輸入頁碼"),
    ("0", "不正確"),
    ("3-1", "不正確"),
    ("11", "超出頁數"),
    ("1-a", "無法辨識"),
    ("1..3", "無法辨識"),
])  # fmt: skip
def test_parse_ranges_errors(text, message):
    with pytest.raises(pages.RangeError, match=message):
        pages.parse_ranges(text, 10)


def test_delete_and_keep_plans():
    assert pages.delete_plan(4, [1, 3]) == [(0, 0), (0, 2)]
    assert pages.keep_plan(4, [3, 1, 1]) == [(0, 1), (0, 3)]
    with pytest.raises(pages.RangeError, match="全部"):
        pages.delete_plan(2, [0, 1])
    with pytest.raises(pages.RangeError):
        pages.keep_plan(2, [])


def test_merge_plan():
    assert pages.merge_plan([2, 1]) == [(0, 0), (0, 1), (1, 0)]
    with pytest.raises(pages.RangeError, match="兩份"):
        pages.merge_plan([3])
    with pytest.raises(pages.RangeError, match="最多"):
        pages.merge_plan([1] * (MAX_COMPOSE_SOURCES + 1))
    with pytest.raises(pages.RangeError, match="超過上限"):
        pages.merge_plan([MAX_PAGES, 1])


@pytest.mark.parametrize(("position", "expected"), [
    (0, [(1, 0), (1, 1), (0, 0), (0, 1), (0, 2)]),  # 最前面
    (1, [(0, 0), (1, 0), (1, 1), (0, 1), (0, 2)]),
    (3, [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]),  # 最後面
])  # fmt: skip
def test_insert_plan(position, expected):
    assert pages.insert_plan(3, 2, position) == expected


def test_insert_plan_bad_position():
    with pytest.raises(pages.RangeError, match="0 到 3"):
        pages.insert_plan(3, 1, 4)
