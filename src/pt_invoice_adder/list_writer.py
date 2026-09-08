"""Append extracted invoice rows to PT INV LIST.xlsx (columns A–F)."""

from __future__ import annotations

import os
import subprocess
import sys
from copy import copy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.worksheet.worksheet import Worksheet


HEADERS = (
    "Invoice Date",
    "Country",
    "Shipment type",
    "GMBH INV.",
    "total (總件數)",
    "gross weight(KG)",
)


def _get_sheet(wb) -> Worksheet:
    if "工作表1" in wb.sheetnames:
        return wb["工作表1"]
    return wb[wb.sheetnames[0]]


def _norm_inv(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    s = str(value).strip()
    if s.endswith(".0"):
        try:
            return str(int(float(s)))
        except ValueError:
            pass
    return s


def existing_inv_set(ws: Worksheet) -> set[str]:
    found: set[str] = set()
    for r in range(2, (ws.max_row or 1) + 1):
        inv = _norm_inv(ws.cell(r, 4).value)
        if inv:
            found.add(inv)
    return found


def _last_data_row(ws: Worksheet) -> int | None:
    """Last row that has a GMBH INV (col D) or any A–F value; skip header row 1."""
    for r in range(ws.max_row or 1, 1, -1):
        if any(ws.cell(r, c).value is not None for c in range(1, 7)):
            return r
    return None


def _copy_style(src: Cell, dst: Cell) -> None:
    """Copy cell formatting like Excel Format Painter (style only, not value)."""
    if src.has_style:
        dst.font = copy(src.font)
        dst.border = copy(src.border)
        dst.fill = copy(src.fill)
        dst.number_format = src.number_format
        dst.protection = copy(src.protection)
        dst.alignment = copy(src.alignment)


def _paint_row_from_template(ws: Worksheet, template_row: int, target_row: int) -> None:
    for c in range(1, 7):
        _copy_style(ws.cell(template_row, c), ws.cell(target_row, c))
    try:
        dim = ws.row_dimensions[template_row]
        if dim.height is not None:
            ws.row_dimensions[target_row].height = dim.height
    except Exception:
        pass


def open_workbook(path: str | Path) -> None:
    """Open the workbook with the OS default app (Excel, etc.)."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(str(path))
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def append_rows(
    list_path: str | Path,
    rows: Sequence[dict[str, Any]],
    *,
    dry_run: bool = False,
    open_after: bool = False,
) -> tuple[int, int]:
    """Append A–F only; skip duplicate GMBH INV in col D. Return (added, skipped).

    New rows copy formatting from the previous data row (format painter).
    If open_after and at least one row was written, open the file for review.
    """
    list_path = Path(list_path)
    if list_path.exists():
        wb = load_workbook(list_path)
        ws = _get_sheet(wb)
    else:
        if dry_run:
            return (len(rows), 0)
        wb = Workbook()
        ws = wb.active
        ws.title = "工作表1"
        for c, h in enumerate(HEADERS, 1):
            ws.cell(1, c, h)

    existing = existing_inv_set(ws)
    added = 0
    skipped = 0
    next_row = (ws.max_row or 1) + 1
    if ws.max_row == 1 and ws.cell(1, 1).value is None:
        for c, h in enumerate(HEADERS, 1):
            ws.cell(1, c, h)
        next_row = 2

    template_row = _last_data_row(ws)

    for row in rows:
        inv = _norm_inv(row.get("invoice_no"))
        if not inv or inv in existing:
            skipped += 1
            continue
        if dry_run:
            added += 1
            existing.add(inv)
            continue

        inv_date = row.get("invoice_date")
        if isinstance(inv_date, date) and not isinstance(inv_date, datetime):
            cell_date: Any = datetime(inv_date.year, inv_date.month, inv_date.day)
        else:
            cell_date = inv_date

        inv_cell: Any = inv
        try:
            inv_cell = int(inv)
        except ValueError:
            pass

        if template_row is not None:
            _paint_row_from_template(ws, template_row, next_row)

        ws.cell(next_row, 1, cell_date)
        ws.cell(next_row, 2, row.get("country"))
        ws.cell(next_row, 3, row.get("shipment_type"))
        ws.cell(next_row, 4, inv_cell)
        ws.cell(next_row, 5, row.get("total_pkg"))
        ws.cell(next_row, 6, row.get("gross_weight"))

        # Keep number formats from template if painted; otherwise sensible defaults
        if template_row is None:
            ws.cell(next_row, 1).number_format = "YYYY-MM-DD"

        existing.add(inv)
        template_row = next_row  # subsequent new rows match the one just written
        next_row += 1
        added += 1

    if not dry_run and added:
        wb.save(list_path)
        if open_after:
            try:
                open_workbook(list_path)
            except Exception:
                pass
    return added, skipped
