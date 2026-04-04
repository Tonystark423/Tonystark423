"""Stark Bank → Ledger sync.

Pulls live transactions from the Stark Bank API and upserts them into the
local assets table under category='Bank Transaction'.

Environment variables (all required when using this module):
  STARKBANK_ENVIRONMENT  sandbox | production
  STARKBANK_PROJECT_ID   numeric project ID from Stark Bank Dashboard
  STARKBANK_PRIVATE_KEY  full PEM string with literal \\n newlines, e.g.:
                           -----BEGIN EC PRIVATE KEY-----\\nMHQCA...\\n-----END EC PRIVATE KEY-----

Usage:
  from starkbank_sync import sync_transactions
  inserted, skipped = sync_transactions(db_conn, limit=50)
"""

from __future__ import annotations

import os
import sqlite3
from decimal import Decimal

import starkbank


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _get_project() -> starkbank.Project:
    env   = os.environ["STARKBANK_ENVIRONMENT"]          # sandbox | production
    pid   = os.environ["STARKBANK_PROJECT_ID"]
    pem   = os.environ["STARKBANK_PRIVATE_KEY"].replace("\\n", "\n")
    return starkbank.Project(environment=env, id=pid, private_key=pem)


# ---------------------------------------------------------------------------
# Field mapping  Stark Bank tx → ledger asset row
# ---------------------------------------------------------------------------

def _tx_to_fields(tx) -> dict:
    """Map one starkbank.Transaction to a ledger-compatible dict."""
    # Stark Bank amounts are integer cents; positive = credit, negative = debit
    amount_cents = tx.amount
    amount_dollars = str(Decimal(str(abs(amount_cents))) / Decimal("100"))
    # Quantize to 4dp to match validate_fields() contract
    amount_dollars = str(
        Decimal(amount_dollars).quantize(Decimal("0.0001"))
    )

    direction = "credit" if amount_cents >= 0 else "debit"
    description = (tx.description or "").strip()[:100] or f"Stark Bank {direction} {tx.id}"

    tags = ", ".join(getattr(tx, "tags", None) or [])
    notes = f"starkbank_id={tx.id}"
    if tags:
        notes += f" | tags: {tags}"

    return {
        "asset_name":       description,
        "category":         "Bank Transaction",
        "subcategory":      direction,
        "description":      description,
        "estimated_value":  amount_dollars,
        "quantity":         "1.0000",
        "unit":             "USD",
        "acquisition_date": str(tx.created.date()) if tx.created else None,
        "custodian":        "Stark Bank",
        "beneficial_owner": os.getenv("LEDGER_BENEFICIAL_OWNER", ""),
        "status":           "active",
        "notes":            notes,
    }


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def sync_transactions(
    db: sqlite3.Connection,
    limit: int = 100,
    after: str | None = None,
    before: str | None = None,
) -> tuple[int, int]:
    """Pull up to `limit` transactions and upsert into assets.

    Deduplication key: notes column containing 'starkbank_id=<id>'.
    Returns (inserted_count, skipped_count).
    """
    starkbank.user = _get_project()

    kwargs: dict = {"limit": limit}
    if after:
        kwargs["after"] = after
    if before:
        kwargs["before"] = before

    transactions = list(starkbank.transaction.query(**kwargs))

    inserted = 0
    skipped  = 0

    for tx in transactions:
        marker = f"starkbank_id={tx.id}"
        existing = db.execute(
            "SELECT id FROM assets WHERE notes LIKE ?", (f"%{marker}%",)
        ).fetchone()

        if existing:
            skipped += 1
            continue

        fields = _tx_to_fields(tx)
        cols         = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        db.execute(
            f"INSERT INTO assets ({cols}) VALUES ({placeholders})",
            list(fields.values()),
        )
        inserted += 1

    db.commit()
    return inserted, skipped
