"""Load Supabase-style audit CSV exports (; or , delimited)."""

from __future__ import annotations

import csv
from pathlib import Path


def detect_delimiter(sample: str) -> str:
    first = sample.splitlines()[0] if sample else ""
    if first.count(";") >= first.count(","):
        return ";"
    return ","


def load_csv(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    delim = detect_delimiter(text)
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            rows.append({k.strip(): (v or "").strip() for k, v in row.items() if k})
    return rows
