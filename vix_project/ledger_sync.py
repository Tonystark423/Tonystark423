"""
ledger_sync.py — The Accountant
Manages two CSV files:
  - ledger_snapshots.csv : timestamped VIX + sentiment history
  - holdings.csv         : current position tracker (shares, cost basis)
"""

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

LEDGER_CSV   = Path(__file__).parent.parent / "ledger_snapshots.csv"
HOLDINGS_CSV = Path(__file__).parent.parent / "holdings.csv"

HOLDINGS_FIELDNAMES = ["Ticker", "Shares", "Avg_Price", "Notes"]

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


def _ensure_holdings():
    if not HOLDINGS_CSV.exists():
        with open(HOLDINGS_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HOLDINGS_FIELDNAMES)
            writer.writeheader()


def read_holdings() -> list[dict]:
    """Return all rows from holdings.csv."""
    if not HOLDINGS_CSV.exists():
        return []
    with open(HOLDINGS_CSV, "r", newline="") as f:
        return list(csv.DictReader(f))


def add_holding(ticker: str, shares: float, avg_price: float, notes: str = "") -> None:
    """
    Add a new position to holdings.csv.
    Raises ValueError if the ticker already exists (use process_derisking_sale to update).
    """
    _ensure_holdings()
    existing = read_holdings()
    if any(r["Ticker"] == ticker for r in existing):
        raise ValueError(f"{ticker} already exists in holdings. Use process_derisking_sale to update.")

    with open(HOLDINGS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HOLDINGS_FIELDNAMES)
        writer.writerow({"Ticker": ticker, "Shares": shares, "Avg_Price": avg_price, "Notes": notes})


def process_derisking_sale(
    ticker: str,
    shares_sold: float,
    current_price: float,
) -> str:
    """
    Record a principal-recovery sale against holdings.csv.

    - Deducts `shares_sold` from the position.
    - Sets the remaining shares' Avg_Price to $0.00 (House Money).
    - Appends a timestamped entry to ledger_snapshots.csv for audit trail.

    Args:
        ticker:        Position identifier (e.g. "VIXY", "VOO").
        shares_sold:   Number of shares being sold to recover principal.
        current_price: Price per share at time of sale.

    Returns:
        Human-readable status string.

    Raises:
        ValueError: If ticker is not found or shares_sold exceeds position size.
    """
    import pandas as pd

    _ensure_holdings()

    df = pd.read_csv(HOLDINGS_CSV)

    if ticker not in df["Ticker"].values:
        raise ValueError(f"Ticker '{ticker}' not found in holdings.")

    idx = df.index[df["Ticker"] == ticker][0]
    current_shares = float(df.at[idx, "Shares"])

    if shares_sold > current_shares:
        raise ValueError(
            f"Cannot sell {shares_sold:.4f} shares — position only holds {current_shares:.4f}."
        )

    realized_gain    = shares_sold * current_price
    remaining_shares = current_shares - shares_sold

    df.at[idx, "Shares"]    = round(remaining_shares, 6)
    df.at[idx, "Avg_Price"] = 0.00  # Remaining shares are House Money
    df.at[idx, "Notes"]     = f"De-risked {datetime.now(timezone.utc).date()} — cost basis zeroed."

    df.to_csv(HOLDINGS_CSV, index=False)

    # Audit entry in the main ledger
    _ensure_ledger()
    audit_note = (
        f"SALE | {ticker} | {shares_sold:.4f} shares @ ${current_price:.2f} "
        f"| Realized: ${realized_gain:,.2f} | Remaining: {remaining_shares:.4f} @ $0.00 (House Money)"
    )
    with open(LEDGER_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow({
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "vix":             "N/A",
            "sentiment_score": "",
            "sentiment_label": "SALE",
            "headline_count":  0,
            "notes":           audit_note,
        })

    return (
        f"Sold {shares_sold:.4f} shares of {ticker} @ ${current_price:.2f}. "
        f"Realized: ${realized_gain:,.2f}. "
        f"Remaining {remaining_shares:.4f} shares are now HOUSE MONEY ($0.00 cost basis)."
    )


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
