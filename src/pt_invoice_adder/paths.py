"""Resolve app / resource paths for source and frozen (PyInstaller) runs."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Folder containing the executable (frozen) or project root (dev)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # .../src/pt_invoice_adder/paths.py → project root
    return Path(__file__).resolve().parents[2]


def resource_dir() -> Path:
    """Bundled read-only resources (PyInstaller _MEIPASS or project root)."""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return app_dir()
