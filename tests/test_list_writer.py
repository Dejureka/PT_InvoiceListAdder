from copy import copy
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from pt_invoice_adder.list_writer import append_rows


def _row(inv, **kw):
    base = {
        "invoice_date": date(2026, 7, 8),
        "country": "CN",
        "shipment_type": "SEA",
        "invoice_no": inv,
        "total_pkg": 1,
        "gross_weight": 10.0,
        "source_file": "x.pdf",
    }
    base.update(kw)
    return base


def test_append_and_skip_duplicate(tmp_path: Path):
    path = tmp_path / "list.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "工作表1"
    headers = [
        "Invoice Date",
        "Country",
        "Shipment type",
        "GMBH INV.",
        "total (總件數)",
        "gross weight(KG)",
    ]
    for c, h in enumerate(headers, 1):
        ws.cell(1, c, h)
    ws.cell(2, 4, 111)
    wb.save(path)

    added, skipped = append_rows(path, [_row("111"), _row("222")])
    assert added == 1 and skipped == 1


def test_format_painter_from_previous_row(tmp_path: Path):
    path = tmp_path / "fmt.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "工作表1"
    for c, h in enumerate(
        ["Invoice Date", "Country", "Shipment type", "GMBH INV.", "total (總件數)", "gross weight(KG)"],
        1,
    ):
        ws.cell(1, c, h)
    ws.cell(2, 1, date(2026, 1, 1))
    ws.cell(2, 2, "DE")
    ws.cell(2, 3, "SEA")
    ws.cell(2, 4, 100)
    ws.cell(2, 5, 2)
    ws.cell(2, 6, 3.5)
    blue = Font(name="Calibri", size=11, color="0000FF")
    fill = PatternFill("solid", fgColor="FFFF00")
    for c in range(1, 7):
        ws.cell(2, c).font = blue
        ws.cell(2, c).fill = fill
        if c == 1:
            ws.cell(2, c).number_format = "YYYY-MM-DD"
    wb.save(path)

    append_rows(path, [_row("200")])
    from openpyxl import load_workbook

    ws2 = load_workbook(path)["工作表1"]
    assert ws2.cell(3, 4).value == 200
    assert ws2.cell(3, 2).font.color.rgb.endswith("0000FF") or "0000FF" in str(
        ws2.cell(3, 2).font.color.rgb
    )
    assert ws2.cell(3, 1).number_format == "YYYY-MM-DD"
