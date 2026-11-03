"""測試內合成的表格樣本（P6、ADR-0023）：Helvetica（WinAnsi）文字與描邊格線，不需外部字型。"""

from __future__ import annotations

import pikepdf

ORIGIN_X, TOP_Y, COL_W, ROW_H = 50.0, 250.0, 100.0, 30.0  # PDF 空間；頁高 300 pt


def table_pdf(path, rows: list[list[str | None]], vertical: bool = True) -> None:
    """rows[r][c] 為格內文字（None 為空白格）；vertical=False 時只畫水平線（無框線表格）。"""
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(400, 300))
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica,
        Encoding=pikepdf.Name.WinAnsiEncoding))  # fmt: skip
    page = pdf.pages[0]
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    n_rows, n_cols = len(rows), len(rows[0])
    right = ORIGIN_X + COL_W * n_cols
    bottom = TOP_Y - ROW_H * n_rows
    ops = ["0 G 1 w"]
    for r in range(n_rows + 1):
        y = TOP_Y - ROW_H * r
        ops.append(f"{ORIGIN_X} {y} m {right} {y} l S")
    if vertical:
        for c in range(n_cols + 1):
            x = ORIGIN_X + COL_W * c
            ops.append(f"{x} {TOP_Y} m {x} {bottom} l S")
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text is not None:
                x, y = ORIGIN_X + COL_W * c + 6, TOP_Y - ROW_H * r - 20
                ops.append(f"BT /F1 12 Tf {x} {y} Td ({text}) Tj ET")
    page.Contents = pdf.make_stream("\n".join(ops).encode("ascii"))
    pdf.save(path)


def cell_box(row: int, col: int) -> list[float]:
    """第 row 列第 col 欄的格範圍（頁面空間，左上原點）。"""
    top = 300 - TOP_Y + ROW_H * row
    left = ORIGIN_X + COL_W * col
    return [left, top, left + COL_W, top + ROW_H]
