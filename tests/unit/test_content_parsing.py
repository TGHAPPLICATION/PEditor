"""G1-08 輔助：ToUnicode CMap 解析與 clip 矩形判定的邊界情況。"""

from peditor.worker.content import _make_clip
from peditor.worker.fonts import parse_cmap

CMAP = """
/CIDInit /ProcSet findresource begin
begincmap
1 begincodespacerange <0000> <FFFF> endcodespacerange
2 beginbfchar
<0003> <0020>
<0010> <D842DFB7>
endbfchar
2 beginbfrange
<0020> <0022> <81FA>
<0030> <0031> [<0041> <00660069>]
endbfrange
endcmap
"""


def test_parse_cmap_bfchar_bfrange_and_arrays():
    mapping = parse_cmap(CMAP)
    assert mapping[0x03] == " "
    assert mapping[0x10] == "\U00020bb7"  # 𠮷，UTF-16 代理對
    assert [mapping[c] for c in (0x20, 0x21, 0x22)] == ["臺", "臻", "臼"]
    assert mapping[0x30] == "A" and mapping[0x31] == "fi"
    assert 0x23 not in mapping  # 未對應的字碼不猜測


def test_clip_rect_detection():
    rect = [([(0, 0), (10, 0), (10, 5), (0, 5)], True, False)]
    assert _make_clip(rect).is_rect
    closed_lines = [([(0, 0), (10, 0), (10, 5), (0, 5), (0, 0)], False, False)]
    assert _make_clip(closed_lines).is_rect
    curved = [([(0, 0), (10, 0), (10, 5), (0, 5)], False, True)]
    assert not _make_clip(curved).is_rect
    rotated = [([(5, 0), (10, 5), (5, 10), (0, 5)], False, False)]
    assert not _make_clip(rotated).is_rect
    two_rects = [rect[0], ([(20, 0), (30, 0), (30, 5), (20, 5)], True, False)]
    assert not _make_clip(two_rects).is_rect
