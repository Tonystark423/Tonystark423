"""
ledger_sync.py — The Accountant
Appends a timestamped sentiment + VIX snapshot to the financial ledger.
"""

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

LEDGER_CSV = Path(__file__).parent.parent / "ledger_snapshots.csv"

FIELDNAMES = [
    "timestamp",
    "vix",
    "sentiment_score",
    "sentiment_label",
    "headline_count",
    "notes",
]


def _ensure_ledger():
    if not LEDGER_CSV.exists():
        with open(LEDGER_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def append_snapshot(
    vix: float | None,
    sentiment_score: float,
    sentiment_label: str,
    headline_count: int,
    notes: str = "",
) -> None:
    """
    Write one row to the ledger CSV.

    Args:
        vix:              Current VIX level (or None if unavailable).
        sentiment_score:  VADER compound score.
        sentiment_label:  Human-readable label (e.g. "FEAR").
        headline_count:   Number of headlines analyzed.
        notes:            Optional free-text notes for this snapshot.
    """
    _ensure_ledger()

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vix": f"{vix:.2f}" if vix is not None else "N/A",
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label,
        "headline_count": headline_count,
        "notes": notes,
    }

    with open(LEDGER_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(row)


def read_ledger(tail: int = 50) -> list[dict]:
    """
    Read the last `tail` rows from the ledger CSV.

    Returns:
        List of row dicts, most recent last.
    """
    if not LEDGER_CSV.exists():
        return []

    with open(LEDGER_CSV, "r", newline="") as f:
        rows = list(csv.DictReader(f))

    return rows[-tail:]
