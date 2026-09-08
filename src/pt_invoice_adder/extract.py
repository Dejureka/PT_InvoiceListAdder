"""Extract Bosch PT GmbH invoice fields from PDF / MSG (AddInvFromGloria port)."""

from __future__ import annotations

import datetime as dt
import re
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

from pt_invoice_adder.lookups import Lookups, load_lookups

REG_INV = re.compile(r"^Invoice No\.\s(\d+)")
REG_INV_DATE = re.compile(r"Invoice Date\s*(\d{2}\.\d{2}\.\d{4})")
REG_DEPART = re.compile(r"^Departure country\s([A-Za-z ]+)$")
REG_SHIP = re.compile(r"^Dispatch type(\s*[A-Za-z]*)")
REG_PACK = re.compile(r"^total\s_+\s_+")
REG_NWGW = re.compile(r"^\s*[0-9,.]+\s+kg\s+([0-9,.]+)\s+kg\s*$")
REG_PKG = re.compile(r"^total\s*:\s*(\d+)\s*$")


def lines_from_text(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.splitlines():
        line = line.replace("\xa0", " ").rstrip()
        if line.strip():
            out.append(line)
    return out


def parse_invoice_date(text: str) -> dt.date | None:
    m = REG_INV_DATE.search(text)
    if not m:
        return None
    d, mo, y = m.group(1).split(".")
    return dt.date(int(y), int(mo), int(d))


def _inco_pattern(incoterms: list[str]) -> re.Pattern[str] | None:
    if not incoterms:
        return None
    term_group = "|".join(re.escape(t) for t in incoterms)
    return re.compile(rf"^({term_group})\s([A-Za-z]+|[A-Za-z]+\s[A-Za-z]+)$")


def extract_from_lines(
    lines: list[str],
    lookups: Lookups | None = None,
    *,
    source_file: str = "",
) -> list[dict[str, Any]]:
    """Port of AddInvFromGloria over a list of text lines (1 PDF / paste)."""
    lookups = lookups or load_lookups()
    reg_inco = _inco_pattern(lookups.incoterms)

    # bottom → top; keep first-seen (bottom-most) row per invoice
    dic_inv: OrderedDict[str, int] = OrderedDict()
    for i in range(len(lines), 0, -1):
        s = lines[i - 1]
        m = REG_INV.match(s) or REG_INV.match(s.lstrip())
        if m and m.group(1) not in dic_inv:
            dic_inv[m.group(1)] = i  # 1-based like Excel

    inv_keys = list(dic_inv.keys())
    inv_rows = list(dic_inv.values())
    n = len(inv_keys)
    if n == 0:
        return []

    # output order = reverse of dictionary insertion order
    ordered_keys = list(reversed(inv_keys))
    ordered_rows = list(reversed(inv_rows))

    results: list[dict[str, Any]] = []
    for idx in range(n):
        celval = 1 if idx == 0 else ordered_rows[idx - 1]
        nextcelval = ordered_rows[idx]
        inv_no = ordered_keys[idx]

        inv_date: dt.date | None = None
        for nn in range(celval, nextcelval + 1):
            d = parse_invoice_date(lines[nn - 1])
            if d is not None:
                inv_date = d
                break

        city = ""
        for mrow in range(celval, nextcelval + 1):
            val = lines[mrow - 1].strip()
            m = REG_DEPART.match(val)
            if m:
                city = m.group(1).strip()
                break
            if reg_inco:
                m = reg_inco.match(val)
                if m:
                    city = m.group(2).strip()
                    break
        country = lookups.map_coo(city)

        pkgttl = 0
        gw = 0.0
        found_pack = False
        for o in range(celval, nextcelval + 1):
            if found_pack:
                break
            if REG_PACK.match(lines[o - 1].strip()):
                found_pack = True
                for o1 in range(o, nextcelval + 1):
                    val1 = lines[o1 - 1]
                    m = REG_NWGW.match(val1) or REG_NWGW.match(val1.strip())
                    if m:
                        gw = float(m.group(1).replace(",", ""))
                    else:
                        m = REG_PKG.match(val1.strip())
                        if m:
                            pkgttl = int(m.group(1))

        ship_type = ""
        for nn in range(celval, nextcelval + 1):
            m = REG_SHIP.match(lines[nn - 1].strip())
            if m:
                ship_type = m.group(1)
                if ship_type.strip():
                    ship_type = ship_type.replace(" ", "")
                else:
                    ship_type = lookups.ship_by_weight(gw)
                break
        ship_type = (ship_type or "").upper()

        results.append(
            {
                "invoice_date": inv_date,
                "country": country,
                "shipment_type": ship_type,
                "invoice_no": inv_no,
                "total_pkg": pkgttl,
                "gross_weight": gw,
                "source_file": source_file,
            }
        )
    return results


def text_from_pdf(path: str | Path) -> str:
    path = Path(path)
    # 1) pypdf
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        parts = [(p.extract_text() or "") for p in reader.pages]
        text = "\n".join(parts)
        if text.strip():
            return text
    except Exception:
        text = ""

    # 2) pdfminer fallback
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract

        text = pdfminer_extract(str(path)) or ""
        return text
    except Exception as exc:
        raise RuntimeError(f"Failed to extract text from PDF: {path}") from exc


def pdfs_from_msg(msg_path: str | Path) -> list[Path]:
    """Extract .pdf attachments from a .msg into a temp dir; return paths."""
    import extract_msg

    msg_path = Path(msg_path)
    out_dir = Path(tempfile.mkdtemp(prefix="pt_msg_"))
    pdfs: list[Path] = []
    msg = extract_msg.Message(str(msg_path))
    try:
        for att in msg.attachments:
            name = getattr(att, "longFilename", None) or getattr(att, "shortFilename", None) or ""
            name = str(name)
            if not name.lower().endswith(".pdf"):
                continue
            # save attachment
            data = att.data
            safe = re.sub(r"[^\w.\-]+", "_", name)
            dest = out_dir / safe
            # avoid overwrite collisions
            if dest.exists():
                dest = out_dir / f"{dest.stem}_{len(pdfs)}{dest.suffix}"
            dest.write_bytes(data)
            pdfs.append(dest)
    finally:
        try:
            msg.close()
        except Exception:
            pass
    return pdfs


def collect_pdfs(paths: Iterable[str | Path]) -> list[Path]:
    """Expand files/folders into a flat list of .pdf paths (also .msg → attached pdfs)."""
    result: list[Path] = []
    seen: set[str] = set()

    def add_pdf(p: Path) -> None:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            result.append(p)

    for raw in paths:
        p = Path(raw)
        if not p.exists():
            continue
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lower() == ".pdf":
                    add_pdf(child)
                elif child.is_file() and child.suffix.lower() == ".msg":
                    for pdf in pdfs_from_msg(child):
                        add_pdf(pdf)
        elif p.suffix.lower() == ".pdf":
            add_pdf(p)
        elif p.suffix.lower() == ".msg":
            for pdf in pdfs_from_msg(p):
                add_pdf(pdf)
    return result


def rows_from_pdfs(
    pdf_paths: Iterable[str | Path],
    lookups: Lookups | None = None,
) -> list[dict[str, Any]]:
    lookups = lookups or load_lookups()
    rows: list[dict[str, Any]] = []
    for pdf in pdf_paths:
        pdf = Path(pdf)
        text = text_from_pdf(pdf)
        lines = lines_from_text(text)
        rows.extend(extract_from_lines(lines, lookups, source_file=pdf.name))
    return rows
