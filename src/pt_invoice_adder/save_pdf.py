"""Copy processed invoice PDFs into a user-chosen "save as" folder."""

from __future__ import annotations

import filecmp
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class SaveResult:
    saved: list[Path] = field(default_factory=list)  # new files written in dest
    skipped: list[Path] = field(default_factory=list)  # identical file already there
    errors: list[tuple[Path, str]] = field(default_factory=list)  # (source, message)


def _same_bytes(a: Path, b: Path) -> bool:
    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def _same_location(src: Path, dest_dir: Path) -> bool:
    try:
        return src.resolve().parent == dest_dir.resolve()
    except OSError:
        return False


def save_pdfs(pdfs: Iterable[str | Path], dest_dir: str | Path) -> SaveResult:
    """Copy each PDF into *dest_dir* (created if missing) under its own file name.

    - Same name + identical bytes already in dest → skipped.
    - Same name, different bytes → ``name (1).pdf``, ``name (2).pdf`` …
      (an identical ``(n)`` copy found along the way also counts as skipped).
    - A source already located in dest is never copied onto itself (skipped).
    - Errors are collected per file; this function does not raise for I/O errors.
    """
    result = SaveResult()
    dest = Path(dest_dir).expanduser()
    pdf_list = [Path(p) for p in pdfs]
    if not pdf_list:
        return result
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        for src in pdf_list:
            result.errors.append((src, f"無法建立資料夾 {dest}：{exc}"))
        return result

    for src in pdf_list:
        try:
            if _same_location(src, dest):
                result.skipped.append(dest / src.name)
                continue
            stem, suffix = Path(src.name).stem, Path(src.name).suffix
            n = 0
            while True:
                name = src.name if n == 0 else f"{stem} ({n}){suffix}"
                target = dest / name
                if not target.exists():
                    shutil.copy2(src, target)
                    result.saved.append(target)
                    break
                if target.is_file() and _same_bytes(src, target):
                    result.skipped.append(target)
                    break
                n += 1
        except Exception as exc:  # keep going; list write must not be blocked
            result.errors.append((src, str(exc)))
    return result
