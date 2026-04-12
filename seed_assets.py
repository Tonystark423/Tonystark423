#!/usr/bin/env python3
"""Seed Stark Financial Holdings LLC ledger with initial asset purchases.

Portfolio target: ~$150,000,000 in assets.
Includes aviation (Gulfstream G650ER, Boeing 787-9), proprietary IP,
compute infrastructure, and diversified securities.

Usage:
    python seed_assets.py              # uses DB_PATH from .env / default ledger.db
    DB_PATH=custom.db python seed_assets.py
"""

import os
import sqlite3
import sys
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "ledger.db")

# ---------------------------------------------------------------------------
# Asset definitions
# ---------------------------------------------------------------------------
# All values in USD. estimated_value stored as 4dp TEXT string.

ASSETS = [
    # ── Aviation ──────────────────────────────────────────────────────────
    {
        "asset_name":       "Gulfstream G650ER",
        "category":         "Securities & Commodities",
        "subcategory":      "Private Aviation",
        "description":      (
            "Ultra-long-range business jet. Range 7,500 nmi, capacity 19 passengers. "
            "Registration N650SFH. Based at Teterboro Airport (KTEB)."
        ),
        "quantity":         "1",
        "unit":             "aircraft",
        "estimated_value":  "68000000.0000",
        "acquisition_date": "2024-03-15",
        "custodian":        "Stark Aviation LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "OBBBA Section 179 / 100% bonus depreciation eligible (business use).",
    },
    {
        "asset_name":       "Boeing 787-9 Dreamliner",
        "category":         "Securities & Commodities",
        "subcategory":      "Commercial Aviation",
        "description":      (
            "Wide-body, long-haul commercial aircraft. 296-seat configuration. "
            "Leased to charter operator under 10-year wet-lease agreement. "
            "Registration N789SFH. MSN 65421."
        ),
        "quantity":         "1",
        "unit":             "aircraft",
        "estimated_value":  "50000000.0000",
        "acquisition_date": "2023-11-01",
        "custodian":        "Stark Aviation LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Generates charter lease income. Depreciated over 25 years.",
    },
    # ── Proprietary IP ────────────────────────────────────────────────────
    {
        "asset_name":       "Repulsor Drive Patent Portfolio",
        "category":         "Proprietary IP",
        "subcategory":      "Patent",
        "description":      (
            "47 granted US patents covering arc-reactor propulsion, repulsor beam "
            "collimation, and electromagnetic shielding. Licensing revenue: $4.2M/yr."
        ),
        "quantity":         "47",
        "unit":             "patents",
        "estimated_value":  "12000000.0000",
        "acquisition_date": "2022-06-30",
        "custodian":        "Stark IP Holdings LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Section 179 / OBBBA bonus depreciation eligible.",
    },
    {
        "asset_name":       "JARVIS Neural Architecture — v9 Weights",
        "category":         "Proprietary IP",
        "subcategory":      "Algorithm",
        "description":      (
            "Trained transformer model weights for the J.A.R.V.I.S. reasoning core. "
            "70B parameter dense model. Proprietary architecture with full trade-secret "
            "protection. Commercially licensed to three defence contractors."
        ),
        "quantity":         "1",
        "unit":             "model",
        "estimated_value":  "9500000.0000",
        "acquisition_date": "2025-01-05",
        "custodian":        "Stark AI Research LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "100% bonus depreciation eligible under OBBBA (post-1/19/2025).",
    },
    # ── Computer Resources ────────────────────────────────────────────────
    {
        "asset_name":       "H200 GPU Cluster — Malibu Data Centre",
        "category":         "Computer Resources",
        "subcategory":      "AI Compute",
        "description":      (
            "512-node NVIDIA H200 SXM cluster. 40.96 petaFLOPS BF16. "
            "Liquid-cooled, co-located in Stark Malibu edge DC. "
            "Primary inference workload: JARVIS, weapons-systems simulation."
        ),
        "quantity":         "512",
        "unit":             "nodes",
        "estimated_value":  "6400000.0000",
        "acquisition_date": "2025-02-14",
        "custodian":        "Stark Infrastructure LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "100% bonus depreciation under OBBBA (placed in service post-1/19/2025).",
    },
    {
        "asset_name":       "Quantum Annealing System — DWave Advantage2",
        "category":         "Computer Resources",
        "subcategory":      "Quantum Compute",
        "description":      (
            "On-premise D-Wave Advantage2 annealing processor. "
            "7,000+ qubit topology. Used for route optimisation and "
            "materials-science simulation pipelines."
        ),
        "quantity":         "1",
        "unit":             "system",
        "estimated_value":  "2100000.0000",
        "acquisition_date": "2024-09-20",
        "custodian":        "Stark Infrastructure LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Section 179 eligible. Accelerated depreciation applied.",
    },
    # ── Money Market Funds ────────────────────────────────────────────────
    {
        "asset_name":       "Fidelity Government Money Market — SPAXX",
        "category":         "Money Market Funds",
        "subcategory":      "Government MMF",
        "description":      "Operating cash reserve. 7-day yield ~5.01%. Daily liquidity.",
        "quantity":         "1250000",
        "unit":             "shares",
        "estimated_value":  "1250000.0000",
        "acquisition_date": "2025-04-01",
        "custodian":        "Fidelity Investments",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Sweep account for operating liquidity.",
    },
    # ── Securities & Commodities ──────────────────────────────────────────
    {
        "asset_name":       "NVDA — NVIDIA Corporation Common Stock",
        "category":         "Securities & Commodities",
        "subcategory":      "Equity",
        "description":      "Long position. Core AI infrastructure thesis. Held in taxable account.",
        "quantity":         "5000",
        "unit":             "shares",
        "estimated_value":  "5500000.0000",
        "acquisition_date": "2023-07-18",
        "custodian":        "Morgan Stanley Wealth Management",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Long-term holding. Unrealised gain ~$3.1M.",
    },
    {
        "asset_name":       "Physical Gold — LBMA Bars",
        "category":         "Securities & Commodities",
        "subcategory":      "Precious Metals",
        "description":      (
            "400 troy oz LBMA-certified gold bars. "
            "Held in segregated vault at Brinks Zurich. Serial nos. on file."
        ),
        "quantity":         "400",
        "unit":             "troy oz",
        "estimated_value":  "1200000.0000",
        "acquisition_date": "2024-01-10",
        "custodian":        "Brinks Zurich",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Inflation hedge. Collectibles rate applies (28%) on sale.",
    },
    # ── Cryptocurrency ────────────────────────────────────────────────────
    {
        "asset_name":       "Bitcoin — Cold Storage",
        "category":         "Cryptocurrency",
        "subcategory":      "BTC",
        "description":      (
            "Long-term BTC reserve. Multi-sig cold storage; "
            "keys held across three hardware wallets in geographically separate vaults."
        ),
        "quantity":         "42",
        "unit":             "BTC",
        "estimated_value":  "4200000.0000",
        "acquisition_date": "2021-11-12",
        "custodian":        "Self-custody (Stark Vault Protocol)",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies on disposal.",
    },
    # ── Ground Transportation Fleet ───────────────────────────────────────
    {
        "asset_name":       "Cadillac Escalade ESV Stretch — Fleet #1",
        "category":         "Securities & Commodities",
        "subcategory":      "Ground Transportation",
        "description":      (
            "Custom 6-door stretch Cadillac Escalade ESV. 140-inch stretch. "
            "Seats 14. Airport transfer and executive ground transport service "
            "between Teterboro (KTEB) and Stark Financial HQ, Midtown Manhattan. "
            "GVWR 8,600 lbs — exceeds 6,000 lb threshold; exempt from luxury "
            "auto depreciation caps."
        ),
        "quantity":         "1",
        "unit":             "vehicle",
        "estimated_value":  "95000.0000",
        "acquisition_date": "2024-06-15",
        "custodian":        "Stark Transport LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "GVWR > 6,000 lbs. Section 179 eligible (heavy SUV). 100% business use.",
    },
    {
        "asset_name":       "Cadillac Escalade ESV Super-Stretch Limo — Airport Shuttle",
        "category":         "Securities & Commodities",
        "subcategory":      "Ground Transportation",
        "description":      (
            "Commercial-grade 8-door super-stretch Escalade ESV limousine. "
            "180-inch stretch, seats 20. Dedicated airport shuttle — Teterboro, "
            "JFK, and EWR to Stark Financial HQ. Overweight vehicle: "
            "GVWR 11,200 lbs; requires commercial operator licence. "
            "Exempt from luxury auto depreciation limits under IRC §179(b)(5)."
        ),
        "quantity":         "1",
        "unit":             "vehicle",
        "estimated_value":  "235000.0000",
        "acquisition_date": "2025-03-10",
        "custodian":        "Stark Transport LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            (
            "GVWR 11,200 lbs — over weight limit; full cost expensable under "
            "OBBBA 100% bonus depreciation (placed in service post-1/19/2025). "
            "Commercial vehicle licence on file."
        ),
    },
    {
        "asset_name":       "Cadillac CT6 Stretch Limousine",
        "category":         "Securities & Commodities",
        "subcategory":      "Ground Transportation",
        "description":      (
            "6-door stretch Cadillac CT6 limousine. 120-inch stretch, seats 10. "
            "VIP executive ground transport. Cream interior, privacy partition, "
            "starlight headliner. GVWR 7,100 lbs."
        ),
        "quantity":         "1",
        "unit":             "vehicle",
        "estimated_value":  "185000.0000",
        "acquisition_date": "2025-02-28",
        "custodian":        "Stark Transport LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            (
            "GVWR > 6,000 lbs — exempt from luxury auto caps. "
            "OBBBA 100% bonus depreciation eligible (placed in service post-1/19/2025)."
        ),
    },
    {
        "asset_name":       "Rolls-Royce Spectre",
        "category":         "Securities & Commodities",
        "subcategory":      "Executive Transport",
        "description":      (
            "Rolls-Royce Spectre ultra-luxury electric coupe. "
            "577 hp dual-motor, 0-60 in 4.4 s. Range 260 mi. "
            "Bespoke Commissioners Black exterior, Seashell leather, "
            "starlight headliner with 1,340 fibre-optic stars. "
            "GVWR 6,834 lbs. Personal use of CEO / executive principals."
        ),
        "quantity":         "1",
        "unit":             "vehicle",
        "estimated_value":  "420000.0000",
        "acquisition_date": "2025-01-30",
        "custodian":        "Stark Transport LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            (
            "GVWR 6,834 lbs — exceeds 6,000 lb threshold; qualifies for heavy-vehicle "
            "Section 179 and OBBBA 100% bonus depreciation (placed in service post-1/19/2025). "
            "Mixed business/personal use — apportion depreciation to business-use %."
        ),
    },
    {
        "asset_name":       "Tesla Model S Plaid",
        "category":         "Securities & Commodities",
        "subcategory":      "Executive Transport",
        "description":      (
            "Tesla Model S Plaid. 1,020 hp tri-motor, 0-60 in 1.99 s. "
            "Range 396 mi. Midnight Silver Metallic. Executive daily driver. "
            "GVWR 4,961 lbs — standard passenger vehicle for depreciation purposes."
        ),
        "quantity":         "1",
        "unit":             "vehicle",
        "estimated_value":  "89990.0000",
        "acquisition_date": "2024-11-20",
        "custodian":        "Stark Transport LLC",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            (
            "GVWR < 6,000 lbs — subject to luxury auto depreciation limits (~$12,400 yr-1 "
            "under prior law). OBBBA bonus dep may apply; consult tax adviser re listed-property rules."
        ),
    },
]

# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------

COLUMNS = [
    "asset_name", "category", "subcategory", "description",
    "quantity", "unit", "estimated_value", "acquisition_date",
    "custodian", "beneficial_owner", "status", "notes",
]


def seed(db_path: str = DB_PATH) -> int:
    if not os.path.exists(db_path):
        print(f"Error: database not found at {db_path}. Run init_db.py first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    inserted = 0
    skipped  = 0

    for asset in ASSETS:
        existing = conn.execute(
            "SELECT id FROM assets WHERE asset_name = ?", (asset["asset_name"],)
        ).fetchone()
        if existing:
            print(f"  skip  {asset['asset_name']} (already exists, id={existing['id']})")
            skipped += 1
            continue

        row = {k: asset.get(k) for k in COLUMNS}
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        conn.execute(f"INSERT INTO assets ({cols}) VALUES ({placeholders})", list(row.values()))
        inserted += 1
        print(f"  added {asset['asset_name']}  (${Decimal(asset['estimated_value']):,.2f})")

    conn.commit()
    conn.close()

    total_value = sum(Decimal(a["estimated_value"]) for a in ASSETS)
    print(f"\nDone. {inserted} inserted, {skipped} skipped.")
    print(f"Portfolio total: ${total_value:,.2f}")
    return inserted


if __name__ == "__main__":
    print(f"Seeding {DB_PATH} …\n")
    seed()
