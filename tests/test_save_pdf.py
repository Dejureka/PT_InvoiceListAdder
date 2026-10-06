from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from pt_invoice_adder.save_pdf import save_pdfs


def _pdf(path: Path, data: bytes = b"%PDF-1.4 A") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_copies_pdf_and_creates_folder(tmp_path: Path):
    src = _pdf(tmp_path / "in" / "INV 123.pdf")
    dest = tmp_path / "out" / "nested"
    res = save_pdfs([src], dest)
    assert res.saved == [dest / "INV 123.pdf"]
    assert (dest / "INV 123.pdf").read_bytes() == src.read_bytes()
    assert not res.skipped and not res.errors


def test_identical_existing_is_skipped(tmp_path: Path):
    src = _pdf(tmp_path / "in" / "a.pdf")
    dest = tmp_path / "out"
    _pdf(dest / "a.pdf")  # same bytes
    res = save_pdfs([src], dest)
    assert res.saved == [] and res.skipped == [dest / "a.pdf"]
    assert sorted(p.name for p in dest.iterdir()) == ["a.pdf"]


def test_collision_adds_suffix_and_rerun_is_idempotent(tmp_path: Path):
    dest = tmp_path / "out"
    _pdf(dest / "a.pdf", b"old")
    src1 = _pdf(tmp_path / "x" / "a.pdf", b"new 1")
    src2 = _pdf(tmp_path / "y" / "a.pdf", b"new 2")
    res = save_pdfs([src1, src2], dest)
    assert [p.name for p in res.saved] == ["a (1).pdf", "a (2).pdf"]
    assert (dest / "a (1).pdf").read_bytes() == b"new 1"
    assert (dest / "a (2).pdf").read_bytes() == b"new 2"
    assert (dest / "a.pdf").read_bytes() == b"old"

    again = save_pdfs([src1, src2], dest)
    assert again.saved == [] and len(again.skipped) == 2


def test_source_already_in_target_not_copied(tmp_path: Path):
    dest = tmp_path / "out"
    src = _pdf(dest / "a.pdf")
    res = save_pdfs([src], dest)
    assert res.saved == [] and len(res.skipped) == 1
    assert sorted(p.name for p in dest.iterdir()) == ["a.pdf"]


def test_error_is_collected_not_raised(tmp_path: Path):
    missing = tmp_path / "gone.pdf"
    ok = _pdf(tmp_path / "in" / "ok.pdf")
    res = save_pdfs([missing, ok], tmp_path / "out")
    assert len(res.errors) == 1 and res.errors[0][0] == missing
    assert [p.name for p in res.saved] == ["ok.pdf"]


def test_dest_is_a_file_reports_errors(tmp_path: Path):
    blocker = _pdf(tmp_path / "out")  # a file where the folder should be
    src = _pdf(tmp_path / "in" / "a.pdf")
    res = save_pdfs([src], blocker)
    assert len(res.errors) == 1 and not res.saved


class _FakeAtt:
    def __init__(self, name: str, data: bytes):
        self.longFilename = name
        self.data = data


class _FakeMsg:
    def __init__(self, path: str):
        self.attachments = [
            _FakeAtt("Invoice 9001 (copy).pdf", b"%PDF inv"),
            _FakeAtt("logo.png", b"png"),
            _FakeAtt("Invoice 9001 (copy).pdf", b"%PDF other"),
        ]

    def close(self):
        pass


@pytest.fixture
def fake_extract_msg(monkeypatch):
    mod = types.ModuleType("extract_msg")
    mod.Message = _FakeMsg
    monkeypatch.setitem(sys.modules, "extract_msg", mod)
    return mod


def test_msg_attachments_saved_with_original_names(tmp_path: Path, fake_extract_msg):
    from pt_invoice_adder.extract import collect_pdfs

    msg = tmp_path / "mail.msg"
    msg.write_bytes(b"fake")
    pdfs = collect_pdfs([msg])
    assert [p.name for p in pdfs] == ["Invoice 9001 (copy).pdf"] * 2

    dest = tmp_path / "saved"
    res = save_pdfs(pdfs, dest)
    assert [p.name for p in res.saved] == [
        "Invoice 9001 (copy).pdf",
        "Invoice 9001 (copy) (1).pdf",
    ]
    assert (dest / "Invoice 9001 (copy).pdf").read_bytes() == b"%PDF inv"
    assert not (dest / "logo.png").exists()


def test_cli_save_and_dry_run(tmp_path: Path, monkeypatch):
    import pt_invoice_adder.cli as cli
    import pt_invoice_adder.extract as extract
    import pt_invoice_adder.list_writer as list_writer

    src = _pdf(tmp_path / "in" / "inv.pdf")
    monkeypatch.setattr(extract, "rows_from_pdfs", lambda pdfs, lookups=None: [])
    monkeypatch.setattr(list_writer, "append_rows", lambda *a, **k: (0, 0))
    dest = tmp_path / "out"

    base = ["--files", str(src), "--list", str(tmp_path / "l.xlsx"), "--save-pdf-dir", str(dest)]
    assert cli.main(base + ["--dry-run"]) == 0
    assert not dest.exists()

    assert cli.main(base) == 0
    assert (dest / "inv.pdf").read_bytes() == src.read_bytes()
