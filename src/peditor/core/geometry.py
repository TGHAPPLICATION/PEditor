"""座標轉換：PDF 使用者空間 ↔ 頁面空間 ↔ 檢視像素（spec §7「UI 座標與 PDF 座標在單一模組轉換」）。

三種座標（單位皆為 pt，除檢視像素外）：

- PDF 空間：PDF 預設使用者空間，原點在左下、y 向上（content stream 經 CTM 後的座標）。
- 頁面空間：以 CropBox 左上為原點、y 向下、**未套用 /Rotate**。與 manifest `bbox_pt`、
  PyMuPDF 擷取座標相同。
- 檢視像素：頁面依 /Rotate 順時針旋轉後，乘上縮放（zoom=1 時 1 px = 1 pt）。

矩陣採 PDF 慣例的列向量形式 [a b c d e f]：x' = a·x + c·y + e、y' = b·x + d·y + f。
本模組只用標準函式庫，主行程與 worker 共用。
"""

from __future__ import annotations

from dataclasses import dataclass

Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def multiply(m1: Matrix, m2: Matrix) -> Matrix:
    """先套 m1 再套 m2（PDF 的 `cm`：CTM' = M × CTM）。"""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def invert(m: Matrix) -> Matrix:
    a, b, c, d, e, f = m
    det = a * d - b * c
    if det == 0:
        raise ValueError("矩陣不可逆")
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(e * ia + f * ic), -(e * ib + f * id_))


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def bbox_of(
    m: Matrix, rect: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    """矩形四角經 m 轉換後的外接矩形。"""
    x0, y0, x1, y1 = rect
    pts = [apply(m, x, y) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


@dataclass(frozen=True)
class PageGeometry:
    """一頁的幾何：CropBox（PDF 空間）與 /Rotate（0／90／180／270）。"""

    cropbox: tuple[float, float, float, float]
    rotation: int = 0

    def __post_init__(self) -> None:
        if self.rotation % 90 != 0:
            raise ValueError("/Rotate 必須是 90 的倍數")
        object.__setattr__(self, "rotation", self.rotation % 360)

    @property
    def width(self) -> float:
        """未旋轉的頁面寬（pt）。"""
        return self.cropbox[2] - self.cropbox[0]

    @property
    def height(self) -> float:
        return self.cropbox[3] - self.cropbox[1]

    def pdf_to_page(self) -> Matrix:
        x0, _, _, y1 = self.cropbox
        return (1.0, 0.0, 0.0, -1.0, -x0, y1)

    def page_to_view(self, zoom: float = 1.0) -> Matrix:
        """頁面空間 → 檢視像素：依 /Rotate 順時針旋轉後縮放。"""
        w, h = self.width, self.height
        rot = {
            0: (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            90: (0.0, 1.0, -1.0, 0.0, h, 0.0),
            180: (-1.0, 0.0, 0.0, -1.0, w, h),
            270: (0.0, -1.0, 1.0, 0.0, 0.0, w),
        }[self.rotation]
        return multiply(rot, (zoom, 0.0, 0.0, zoom, 0.0, 0.0))

    def pdf_to_view(self, zoom: float = 1.0) -> Matrix:
        return multiply(self.pdf_to_page(), self.page_to_view(zoom))

    def view_size(self, zoom: float = 1.0) -> tuple[float, float]:
        if self.rotation in (90, 270):
            return self.height * zoom, self.width * zoom
        return self.width * zoom, self.height * zoom

    def view_to_page(self, x: float, y: float, zoom: float = 1.0) -> tuple[float, float]:
        """點選：檢視像素 → 頁面空間。"""
        return apply(invert(self.page_to_view(zoom)), x, y)


def contains(rect: tuple[float, float, float, float], x: float, y: float, tol: float = 0.0) -> bool:
    x0, y0, x1, y1 = rect
    return x0 - tol <= x <= x1 + tol and y0 - tol <= y <= y1 + tol
