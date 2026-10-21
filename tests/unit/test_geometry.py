"""G1-04、G1-05：座標轉換。以 PyMuPDF 的頁面矩陣與 PDFium 的實際渲染結果作為獨立對照。

L02 的 CFF 子集字型在 MuPDF 1.28.2 渲染為空白（P1 報告 §9），渲染對照因此用 PDFium。
"""

import random
from pathlib import Path

import pymupdf
import pypdfium2
import pytest

from peditor.core.geometry import PageGeometry, apply, contains, invert

FILES = Path(__file__).resolve().parents[1] / "fixtures" / "files"


def _geometry(page: pymupdf.Page) -> PageGeometry:
    # PyMuPDF 的 cropbox 以未旋轉頁面左上為原點；換回 PDF 空間
    mediabox = page.mediabox
    crop = page.cropbox
    return PageGeometry(
        (crop.x0, mediabox.y1 - crop.y1, crop.x1, mediabox.y1 - crop.y0), page.rotation
    )


def _bbox(row):
    return [float(v) for v in row["bbox_pt"].split(",")]


@pytest.mark.parametrize("fid", ["T01", "L01", "L02"])
def test_pdf_to_page_matches_pymupdf(fid):
    with pymupdf.open(FILES / f"{fid}.pdf") as doc:
        page = doc[0]
        ours = _geometry(page).pdf_to_page()
        assert all(
            abs(a - b) < 1e-6 for a, b in zip(ours, tuple(page.transformation_matrix), strict=True)
        )


def test_coordinate_round_trip_within_half_point():
    rng = random.Random(20261021)  # noqa: S311 — 固定種子的測試座標，非密碼用途
    for rotation in (0, 90, 180, 270):
        geom = PageGeometry((50.0, 50.0, 545.28, 791.89), rotation)
        for zoom in (0.5, 1.0, 2.0, 3.3):
            to_view = geom.pdf_to_view(zoom)
            back = invert(to_view)
            for _ in range(200):
                x, y = rng.uniform(50, 545), rng.uniform(50, 791)
                vx, vy = apply(to_view, x, y)
                rx, ry = apply(back, vx, vy)
                assert abs(rx - x) <= 0.5 and abs(ry - y) <= 0.5
                px, py = apply(geom.pdf_to_page(), x, y)
                qx, qy = geom.view_to_page(vx, vy, zoom)
                assert abs(qx - px) <= 0.5 and abs(qy - py) <= 0.5


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("zoom", [1.0, 2.0])
def test_hit_test_zoom_and_rotation(available_rows, rotation, zoom):
    row = next(r for r in available_rows if r["fixture_id"] == "L02")
    bbox = _bbox(row)
    with pymupdf.open(FILES / "L02.pdf") as doc:
        page = doc[0]
        page.set_rotation(rotation)
        geom = _geometry(page)
        to_view = geom.page_to_view(zoom)
        # 1) 與 PyMuPDF 的旋轉＋縮放矩陣一致
        mu = page.rotation_matrix * pymupdf.Matrix(zoom, zoom)
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        vx, vy = apply(to_view, cx, cy)
        p = pymupdf.Point(cx, cy) * mu
        assert abs(vx - p.x) <= 0.5 and abs(vy - p.y) <= 0.5
        assert geom.view_size(zoom) == pytest.approx(
            (page.rect.width * zoom, page.rect.height * zoom)
        )
        # 2) 點選該處反算回頁面空間，落在目標框內
        hx, hy = geom.view_to_page(vx, vy, zoom)
        assert contains(bbox, hx, hy)
        # 3) 實際渲染（PDFium）：換算出的檢視框內確實有文字像素（深色）
        rotated = pypdfium2.PdfDocument(doc.tobytes())
        image = rotated[0].render(scale=zoom).to_pil().convert("L")
        rotated.close()
        vw, vh = geom.view_size(zoom)
        assert abs(image.size[0] - vw) <= 1 and abs(image.size[1] - vh) <= 1  # PDFium 無條件進位

        def dark_in(box):
            pts = [apply(to_view, x, y) for x, y in ((box[0], box[1]), (box[2], box[3]))]
            x0, x1 = sorted(int(c[0]) for c in pts)
            y0, y1 = sorted(int(c[1]) for c in pts)
            return sum(image.crop((x0, y0, x1, y1)).histogram()[:128])

        assert dark_in(bbox) > 20, (rotation, zoom)
        # 對照：同一頁面空間框往下移 300 pt（L02 該處空白）應無文字像素
        assert dark_in([bbox[0], bbox[1] + 300, bbox[2], bbox[3] + 300]) == 0, (rotation, zoom)
