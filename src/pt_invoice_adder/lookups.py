"""Load COO / incoterms / ship_type lookup tables."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _candidate_paths() -> list[Path]:
    here = Path(__file__).resolve()
    return [
        here.parents[2] / "data" / "lookups.json",  # project root (editable / src layout)
        here.parents[1] / "data" / "lookups.json",
        Path.cwd() / "data" / "lookups.json",
        Path.cwd() / "lookups.json",
    ]


@dataclass
class Lookups:
    incoterms: list[str] = field(default_factory=list)
    coo_map: dict[str, str] = field(default_factory=dict)
    ship_types: list[tuple[str, float]] = field(default_factory=list)  # (type, weight_kg)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lookups":
        coo_map: dict[str, str] = {}
        for row in data.get("coo") or []:
            full = str(row.get("full", "")).strip()
            code = str(row.get("code", "")).strip()
            if full:
                coo_map[full] = code
        ship: list[tuple[str, float]] = []
        for row in data.get("ship_type") or []:
            t = str(row.get("type", "")).strip()
            try:
                w = float(row.get("weight_kg", 0) or 0)
            except (TypeError, ValueError):
                w = 0.0
            if t:
                ship.append((t, w))
        return cls(
            incoterms=[str(x).strip() for x in (data.get("incoterms") or []) if str(x).strip()],
            coo_map=coo_map,
            ship_types=ship,
        )

    def map_coo(self, city: str) -> str:
        if not city:
            return "please check invoice directly"
        return self.coo_map.get(city, "please check invoice directly")

    def ship_by_weight(self, gw: float) -> str:
        """XLOOKUP-style: largest weight_kg ≤ gw."""
        best_w: float | None = None
        best_t = ""
        for t, w in self.ship_types:
            if w <= gw and (best_w is None or w > best_w):
                best_w = w
                best_t = t
        return best_t


def load_lookups(path: Path | str | None = None) -> Lookups:
    if path is not None:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        return Lookups.from_dict(data)
    for cand in _candidate_paths():
        if cand.is_file():
            data = json.loads(cand.read_text(encoding="utf-8"))
            return Lookups.from_dict(data)
    raise FileNotFoundError(
        "lookups.json not found; tried: " + ", ".join(str(c) for c in _candidate_paths())
    )
