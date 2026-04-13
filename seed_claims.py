#!/usr/bin/env python3
"""Seed Stark Financial Holdings LLC claims ledger.

Logs all outstanding and in-progress claims against crypto exchanges and
financial institutions that have failed to pay obligations owed to the firm.

Usage:
    python seed_claims.py              # uses DB_PATH from .env / default ledger.db
    DB_PATH=custom.db python seed_claims.py
"""

import os
import sqlite3
import sys
from decimal import Decimal
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "ledger.db")

# ---------------------------------------------------------------------------
# Claim definitions
# ---------------------------------------------------------------------------
# amount_owed: enter the specific claim amount once confirmed with counsel.
# Values marked "TBD" should be updated after forensic account reconstruction.
# ---------------------------------------------------------------------------

CLAIMS = [
    # ── Crypto Exchange Bankruptcies ─────────────────────────────────────
    {
        "institution":       "FTX Trading Ltd (in Chapter 11 bankruptcy)",
        "claim_type":        "investment_return",
        "amount_owed":       "0.0000",   # UPDATE: enter confirmed claim amount
        "currency":          "USD",
        "origin_date":       "2022-11-11",   # FTX Chapter 11 filing date
        "last_contact_date": "2026-03-31",   # 4th distribution (Class 5B/6A/6B at 100%; Class 7 at 120%)
        "status":            "judgment_obtained",
        "jurisdiction":      "Federal — SDNY Bankruptcy Court (Case 22-11068)",
        "counsel":           "TBD — retain bankruptcy claims specialist",
        "description":       (
            "FTX Trading Ltd filed Chapter 11 on Nov 11, 2022. "
            "FTX Recovery Trust has distributed $7.1B+ across 4 rounds. "
            "March 31, 2026: 4th distribution of $2.2B. "
            "Class 5B US customers and Classes 6A/6B reached 100% recovery; "
            "Class 7 reached 120% cumulative. "
            "Preferred equity record date: Apr 30, 2026; payment date: May 29, 2026."
        ),
        "notes":             (
            "Distribution partners: BitGo, Kraken, Payoneer. "
            "Valuation controversy: payouts based on Nov 2022 USD value, not current BTC price. "
            "If claim has not been filed, the bar date may have passed — confirm with counsel immediately. "
            "UPDATE amount_owed with actual filed claim amount."
        ),
    },
    {
        "institution":       "Celsius Network LLC (in Chapter 11 bankruptcy)",
        "claim_type":        "investment_return",
        "amount_owed":       "0.0000",   # UPDATE: enter confirmed claim amount
        "currency":          "USD",
        "origin_date":       "2022-07-13",   # Celsius Chapter 11 filing date
        "last_contact_date": "2026-02-01",   # Feb 2026 distribution
        "status":            "judgment_obtained",
        "jurisdiction":      "Federal — SDNY Bankruptcy Court",
        "counsel":           "TBD — retain bankruptcy claims specialist",
        "description":       (
            "Celsius Network filed Chapter 11 on Jul 13, 2022. "
            "Plan confirmed Nov 2023. Distributions commenced 2024. "
            "Feb 2026 distribution ongoing; total creditor recovery ~60%. "
            "Creditors who did not opt out of class claim settlement receive 5% markup. "
            "Mining business spun off to customers as new entity."
        ),
        "notes":             (
            "Recovery ~60% of claim value. Balance (~40%) likely irrecoverable. "
            "Feb 2026 distribution reported on 2026 tax return. "
            "File proof of claim at claimsportal.celsius.network if not already done. "
            "UPDATE amount_owed with actual filed claim amount."
        ),
    },
    {
        "institution":       "BlockFi Inc (in Chapter 11 bankruptcy)",
        "claim_type":        "investment_return",
        "amount_owed":       "0.0000",   # UPDATE: enter confirmed claim amount
        "currency":          "USD",
        "origin_date":       "2022-11-28",   # BlockFi Chapter 11 filing date
        "last_contact_date": "2025-06-01",   # Final distribution completed
        "status":            "settled",
        "jurisdiction":      "Federal — D.NJ Bankruptcy Court",
        "counsel":           "TBD",
        "description":       (
            "BlockFi filed Chapter 11 on Nov 28, 2022. "
            "Plan confirmed Oct 2023. BlockFi sold its FTX claims and "
            "completed final distribution of 100% of eligible customer and "
            "general unsecured creditor claims. Case effectively closed."
        ),
        "notes":             (
            "100% recovery achieved on eligible customer claims. "
            "Confirm that distribution was received. If not received, contact "
            "BlockFi claims agent immediately — distributions may have been forfeited. "
            "UPDATE amount_owed with original claim amount for records."
        ),
    },
    {
        "institution":       "Genesis Global Capital LLC (in Chapter 11 bankruptcy)",
        "claim_type":        "investment_return",
        "amount_owed":       "0.0000",   # UPDATE: enter confirmed claim amount
        "currency":          "USD",
        "origin_date":       "2023-01-19",   # Genesis Chapter 11 filing date
        "last_contact_date": "2024-05-01",   # Plan confirmation
        "status":            "in_negotiation",
        "jurisdiction":      "Federal — SDNY Bankruptcy Court",
        "counsel":           "TBD — retain bankruptcy claims specialist",
        "description":       (
            "Genesis Global Capital filed Chapter 11 on Jan 19, 2023. "
            "Plan confirmed May 2024. Liquidation and wind-down of business. "
            "Claims against parent Digital Currency Group (DCG) preserved "
            "for post-wind-down entity to pursue on behalf of creditors. "
            "Distributions ongoing through wind-down process."
        ),
        "notes":             (
            "Recovery rate uncertain pending DCG claim resolution. "
            "Post-wind-down entity pursuing DCG for additional recovery. "
            "Monitor case docket for distribution notices. "
            "UPDATE amount_owed with actual filed claim amount."
        ),
    },
    {
        "institution":       "Voyager Digital Ltd (in Chapter 11 bankruptcy)",
        "claim_type":        "investment_return",
        "amount_owed":       "0.0000",   # UPDATE: enter confirmed claim amount
        "currency":          "USD",
        "origin_date":       "2022-07-05",   # Voyager Chapter 11 filing date
        "last_contact_date": "2024-06-01",
        "status":            "settled",
        "jurisdiction":      "Federal — SDNY Bankruptcy Court",
        "counsel":           "TBD",
        "description":       (
            "Voyager Digital filed Chapter 11 on Jul 5, 2022. "
            "Plan confirmed May 2024. Customers received a combination of "
            "crypto (in-kind) and cash distributions. "
            "Recovery rate varied by asset class; BTC/ETH claimants "
            "received higher percentage than fiat claimants."
        ),
        "notes":             (
            "Confirm distribution receipt. If crypto was returned in-kind, "
            "the acquisition date for tax purposes is the distribution date. "
            "UPDATE amount_owed with original claim amount for records."
        ),
    },
]

# ---------------------------------------------------------------------------
# Column list (must match schema)
# ---------------------------------------------------------------------------
COLUMNS = [
    "institution", "claim_type", "amount_owed", "currency",
    "origin_date", "last_contact_date", "status", "jurisdiction",
    "counsel", "description", "notes", "created_at", "updated_at",
]


def seed(db_path: str = DB_PATH) -> int:
    if not os.path.exists(db_path):
        print(f"Error: database not found at {db_path}. Run init_db.py first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    inserted = 0
    skipped  = 0

    for claim in CLAIMS:
        existing = conn.execute(
            "SELECT id FROM claims WHERE institution = ? AND origin_date = ?",
            (claim["institution"], claim["origin_date"]),
        ).fetchone()
        if existing:
            print(f"  skip  {claim['institution'][:60]} (already exists, id={existing['id']})")
            skipped += 1
            continue

        row = {k: claim.get(k) for k in COLUMNS if k not in ("created_at", "updated_at")}
        row["created_at"] = now
        row["updated_at"] = now

        cols         = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        conn.execute(f"INSERT INTO claims ({cols}) VALUES ({placeholders})", list(row.values()))
        inserted += 1
        status_tag = claim["status"].upper()
        print(f"  added [{status_tag}] {claim['institution'][:70]}")

    conn.commit()
    conn.close()

    total_owed = sum(Decimal(c["amount_owed"]) for c in CLAIMS)
    print(f"\nDone. {inserted} inserted, {skipped} skipped.")
    print(f"Total amount_owed logged: ${total_owed:,.2f}  (update each record with actual claim amounts)")
    return inserted


if __name__ == "__main__":
    print(f"Seeding claims into {DB_PATH} …\n")
    seed()
