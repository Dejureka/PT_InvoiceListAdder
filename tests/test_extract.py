from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from pt_invoice_adder.extract import (
    extract_from_lines,
    lines_from_text,
    parse_invoice_date,
)
from pt_invoice_adder.lookups import Lookups, load_lookups

FIXTURE = Path(__file__).parent / "fixtures" / "sample_invoice_lines.txt"


@pytest.fixture(scope="module")
def lookups() -> Lookups:
    root = Path(__file__).resolve().parents[1]
    return load_lookups(root / "data" / "lookups.json")


def test_date_regex_bare():
    assert parse_invoice_date("Invoice Date 08.07.2026") == dt.date(2026, 7, 8)


def test_date_regex_prefixed():
    assert parse_invoice_date("Foo bar Invoice Date 08.07.2026") == dt.date(2026, 7, 8)


def test_date_regex_glued():
    assert parse_invoice_date("Invoice Date 08.07.2026Account No. 227026") == dt.date(
        2026, 7, 8
    )


def test_fixture_two_invoices(lookups: Lookups):
    lines = lines_from_text(FIXTURE.read_text(encoding="utf-8"))
    rows = extract_from_lines(lines, lookups, source_file="fixture.txt")
    assert len(rows) == 2

    # bottom-most invoice keys inserted first while scanning bottom→top;
    # output is reverse → document order: 50656407 then 50659999
    r0, r1 = rows
    assert r0["invoice_no"] == "50656407"
    assert r0["invoice_date"] == dt.date(2026, 7, 8)
    assert r0["country"] == "MY"
    assert r0["shipment_type"] == "SEA"
    assert r0["total_pkg"] == 5
    assert r0["gross_weight"] == pytest.approx(437.53)

    assert r1["invoice_no"] == "50659999"
    assert r1["invoice_date"] == dt.date(2026, 7, 9)
    assert r1["country"] == "CN"
    # empty Dispatch type → weight lookup (1319.84 ≥ 100 → Sea)
    assert r1["shipment_type"] == "SEA"
    assert r1["total_pkg"] == 5
    assert r1["gross_weight"] == pytest.approx(1319.84)


def test_coo_unknown(lookups: Lookups):
    # Real PDFs repeat Invoice No. on later pages after packing details.
    lines = [
        "Departure country Atlantis",
        "Invoice Date 01.01.2026",
        "Invoice No. 1",
        "Dispatch type Air",
        "total ______________ ______________",
        "    1.000 kg     2.000 kg",
        "total :   1",
        "Invoice No. 1",
    ]
    rows = extract_from_lines(lines, lookups)
    assert rows[0]["country"] == "please check invoice directly"
    assert rows[0]["shipment_type"] == "AIR"
    assert rows[0]["total_pkg"] == 1
    assert rows[0]["gross_weight"] == pytest.approx(2.0)
