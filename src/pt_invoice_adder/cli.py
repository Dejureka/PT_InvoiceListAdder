"""CLI entry: python -m pt_invoice_adder --files ... --list path [--dry-run]"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from typing import Any


def _json_default(o: Any) -> Any:
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return str(o)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pt_invoice_adder",
        description="Extract Bosch PT GmbH invoice fields and append to PT INV LIST.xlsx",
    )
    p.add_argument(
        "--files",
        nargs="+",
        help="PDF / MSG files or folders containing them",
    )
    p.add_argument(
        "--list",
        dest="list_path",
        help="Path to PT INV LIST.xlsx",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and print rows; do not write the workbook",
    )
    p.add_argument(
        "--lookups",
        default=None,
        help="Optional path to lookups.json",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Launch GUI",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # No args or explicit --gui → GUI
    if not argv or argv == ["--gui"] or argv == ["gui"]:
        from pt_invoice_adder.gui import run_gui

        run_gui()
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        from pt_invoice_adder.gui import run_gui

        run_gui()
        return 0

    if not args.files or not args.list_path:
        parser.error("--files and --list are required for CLI mode (or use --gui)")

    from pt_invoice_adder.extract import collect_pdfs, rows_from_pdfs
    from pt_invoice_adder.list_writer import append_rows
    from pt_invoice_adder.lookups import load_lookups

    lookups = load_lookups(args.lookups) if args.lookups else load_lookups()
    pdfs = collect_pdfs(args.files)
    if not pdfs:
        print("No PDF files found.", file=sys.stderr)
        return 1

    rows = rows_from_pdfs(pdfs, lookups)
    print(json.dumps(rows, ensure_ascii=False, indent=2, default=_json_default))

    added, skipped = append_rows(args.list_path, rows, dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "write"
    print(f"[{mode}] added={added} skipped={skipped} pdfs={len(pdfs)} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
