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


def ops_pdf(path, ops: list[str], form_ops: list[str] | None = None) -> None:
    """自訂內容的樣本：ops 為頁面內容（Helvetica 為 /F1）；
    form_ops 給定時另建 /Fm0（整頁 BBox）。"""
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(400, 300))
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica,
        Encoding=pikepdf.Name.WinAnsiEncoding))  # fmt: skip
    resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    if form_ops is not None:
        form = pdf.make_stream("\n".join(form_ops).encode("ascii"))
        form.Type, form.Subtype = pikepdf.Name.XObject, pikepdf.Name.Form
        form.BBox = [0, 0, 400, 300]
        resources.XObject = pikepdf.Dictionary(Fm0=form)
    page = pdf.pages[0]
    page.Resources = resources
    page.Contents = pdf.make_stream("\n".join(ops).encode("ascii"))
    pdf.save(path)


def text(x: float, y: float, s: str, matrix: str | None = None) -> str:
    """PDF 空間 (x, y) 的 12 pt 文字；matrix 給定時用 Tm（例如旋轉）。"""
    place = f"{matrix} Tm" if matrix else f"{x} {y} Td"
    return f"BT /F1 12 Tf {place} ({s}) Tj ET"


def rich_pdf(path, ops: list[str], shading: bool = False, annots=None, type3: bool = False) -> None:
    """含非路徑畫法的樣本（第三輪核對 S2）：shading /Sh0（全黑）、Square 註解外觀、Type3 字型 /F3
    （字碼 124 的 CharProc 畫一條往上 8000 單位的直線，字形外框很小）。

    annots 每項為 (Rect, 外觀運算子) 或 (Rect, 外觀運算子, 額外設定)；額外設定可給 Subtype、F，
    oc_off（掛在預設關閉的圖層上；第四輪核對 T2）、alpha（外觀串流內 ExtGState 的 CA）、
    indirect_rect（Rect 為間接參照）、direct（註解字典直接寫在 /Annots 裡）、
    bad_rect（以此值取代 Rect；第五輪核對 F1–F4）。"""
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(400, 300))
    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica,
        Encoding=pikepdf.Name.WinAnsiEncoding))  # fmt: skip
    fonts = pikepdf.Dictionary(F1=font)
    resources = pikepdf.Dictionary(Font=fonts)
    if shading:
        function = pdf.make_indirect(pikepdf.Dictionary(FunctionType=2, Domain=[0, 1], C0=[0],
                                                        C1=[0], N=1))  # fmt: skip
        sh = pikepdf.Dictionary(ShadingType=2, ColorSpace=pikepdf.Name.DeviceGray,
                                Coords=[0, 0, 1, 0], Extend=[True, True],
                                Function=function)  # fmt: skip
        resources.Shading = pikepdf.Dictionary(Sh0=pdf.make_indirect(sh))
    if type3:
        proc = pdf.make_stream(b"1 0 0 0 0 0 d0 0 G 2 w 0 0 m 0 8000 l S")
        fonts.F3 = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type3, FontBBox=[0, 0, 1, 1],
            FontMatrix=[0.001, 0, 0, 0.001, 0, 0], CharProcs=pikepdf.Dictionary(bar=proc),
            Encoding=pikepdf.Dictionary(Type=pikepdf.Name.Encoding,
                                        Differences=[124, pikepdf.Name.bar]),
            FirstChar=124, LastChar=124, Widths=[600], Resources=pikepdf.Dictionary()))  # fmt: skip
    page = pdf.pages[0]
    page.Resources = resources
    page.Contents = pdf.make_stream("\n".join(ops).encode("ascii"))
    if annots:
        items = []
        for rect, ap_ops, *rest in annots:
            extra = dict(rest[0]) if rest else {}
            ap = pdf.make_stream(ap_ops.encode("ascii"))
            ap.Type, ap.Subtype, ap.BBox = pikepdf.Name.XObject, pikepdf.Name.Form, rect
            if "alpha" in extra:
                ap.Resources = pikepdf.Dictionary(ExtGState=pikepdf.Dictionary(
                    G0=pikepdf.Dictionary(CA=extra.pop("alpha"))))  # fmt: skip
            value = extra.pop("bad_rect", rect)
            if extra.pop("indirect_rect", False):
                value = pdf.make_indirect(pikepdf.Array(rect))
            annot = pikepdf.Dictionary(
                Type=pikepdf.Name.Annot, Subtype=pikepdf.Name(extra.pop("Subtype", "/Square")),
                Rect=value, F=extra.pop("F", 4), AP=pikepdf.Dictionary(N=ap))  # fmt: skip
            direct = extra.pop("direct", False)
            if extra.pop("oc_off", False):
                ocg = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.OCG, Name="off"))
                annot.OC = ocg
                pdf.Root.OCProperties = pikepdf.Dictionary(
                    OCGs=[ocg], D=pikepdf.Dictionary(OFF=[ocg]))  # fmt: skip
            for key, value in extra.items():
                annot[f"/{key}"] = value
            items.append(annot if direct else pdf.make_indirect(annot))
        page.Annots = pdf.make_indirect(pikepdf.Array(items))
    pdf.save(path)
