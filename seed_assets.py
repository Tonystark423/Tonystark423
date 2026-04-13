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
        "estimated_value":  "3073141.4400",  # 42 BTC × $73,170.03 (Apr 10, 2026)
        "acquisition_date": "2021-11-12",
        "custodian":        "Self-custody (Stark Vault Protocol)",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies on disposal. Price updated Apr 13, 2026: $73,170.03/BTC.",
    },
    {
        "asset_name":       "Ethereum — Cold Storage",
        "category":         "Cryptocurrency",
        "subcategory":      "ETH",
        "description":      (
            "Ethereum position. Multi-sig cold storage via Stark Vault Protocol. "
            "Core Web3 infrastructure holding; staking yield deferred pending regulatory clarity."
        ),
        "quantity":         "500",
        "unit":             "ETH",
        "estimated_value":  "1108700.0000",  # 500 ETH × $2,217.40 (Apr 10, 2026)
        "acquisition_date": "2021-11-20",
        "custodian":        "Self-custody (Stark Vault Protocol)",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies on disposal. Price updated Apr 13, 2026: $2,217.40/ETH.",
    },
    {
        "asset_name":       "Solana — Exchange Custody (Kraken)",
        "category":         "Cryptocurrency",
        "subcategory":      "SOL",
        "description":      (
            "Solana position held on Kraken institutional custody. "
            "High-throughput L1; strategic position tied to Stark compute ecosystem thesis."
        ),
        "quantity":         "5000",
        "unit":             "SOL",
        "estimated_value":  "427100.0000",   # 5,000 SOL × $85.42 (Apr 10, 2026)
        "acquisition_date": "2022-08-15",
        "custodian":        "Kraken Institutional",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies. Price updated Apr 13, 2026: $85.42/SOL.",
    },
    {
        "asset_name":       "XRP — Exchange Custody (Coinbase Prime)",
        "category":         "Cryptocurrency",
        "subcategory":      "XRP",
        "description":      (
            "XRP position. SEC v. Ripple case concluded; XRP re-listed across major US exchanges. "
            "Cross-border payments infrastructure play."
        ),
        "quantity":         "500000",
        "unit":             "XRP",
        "estimated_value":  "680000.0000",   # 500,000 XRP × $1.36 (Apr 10, 2026)
        "acquisition_date": "2023-04-10",
        "custodian":        "Coinbase Prime",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies. Price updated Apr 13, 2026: $1.36/XRP.",
    },
    {
        "asset_name":       "BNB — Exchange Custody (Binance Institutional)",
        "category":         "Cryptocurrency",
        "subcategory":      "BNB",
        "description":      (
            "Binance Coin / BNB Chain utility token. Used for fee rebates on Binance "
            "institutional trading desk and BNB Chain DeFi participation."
        ),
        "quantity":         "200",
        "unit":             "BNB",
        "estimated_value":  "119234.0000",   # 200 BNB × $596.17 (Apr 2026)
        "acquisition_date": "2022-06-01",
        "custodian":        "Binance Institutional",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies. Price updated Apr 13, 2026: $596.17/BNB.",
    },
    {
        "asset_name":       "Avalanche — Exchange Custody (Coinbase Prime)",
        "category":         "Cryptocurrency",
        "subcategory":      "AVAX",
        "description":      (
            "Avalanche AVAX position. L1 subnet infrastructure; "
            "strategic allocation for Stark subnet deployment optionality."
        ),
        "quantity":         "2000",
        "unit":             "AVAX",
        "estimated_value":  "50000.0000",    # 2,000 AVAX × ~$25 (Apr 2026 est.)
        "acquisition_date": "2022-09-22",
        "custodian":        "Coinbase Prime",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies. Update price to current AVAX/USD before filing.",
    },
    {
        "asset_name":       "stETH — Lido Liquid Staking",
        "category":         "Cryptocurrency",
        "subcategory":      "stETH",
        "description":      (
            "300 ETH staked via Lido Finance liquid staking protocol. "
            "Receives stETH (liquid staking token) earning ~3.3% APR net of Lido 10% fee. "
            "stETH can be deployed in DeFi while earning validator rewards. "
            "$38B+ TVL in Lido; 24.2% market share of all staked ETH."
        ),
        "quantity":         "300",
        "unit":             "stETH",
        "estimated_value":  "665220.0000",   # 300 stETH × $2,217.40
        "acquisition_date": "2023-06-15",
        "custodian":        "Lido Finance (self-custodied stETH)",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            (
            "Staking rewards (~3.3% APR) taxed as ordinary income at FMV when unlocked. "
            "Estimated annual staking income: ~$21,952 (300 stETH × $2,217 × 3.3%). "
            "Held > 365 days. stETH disposal triggers long-term CG on appreciation. "
            "Per IRS guidance: rewards taxable at dominion-and-control date, not unstaking date."
        ),
    },
    {
        "asset_name":       "Dogecoin — Exchange Custody (Kraken)",
        "category":         "Cryptocurrency",
        "subcategory":      "DOGE",
        "description":      (
            "Dogecoin position. Held on Kraken institutional custody. "
            "Retail sentiment hedge; high liquidity, low unit price. "
            "Active meme-coin market in Q1 2026."
        ),
        "quantity":         "1000000",
        "unit":             "DOGE",
        "estimated_value":  "95000.0000",    # 1M DOGE × $0.095 (Apr 2026)
        "acquisition_date": "2021-05-08",
        "custodian":        "Kraken Institutional",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies. Price: $0.095/DOGE (Apr 2026).",
    },
    {
        "asset_name":       "Arbitrum — Exchange Custody (Coinbase Prime)",
        "category":         "Cryptocurrency",
        "subcategory":      "ARB",
        "description":      (
            "Arbitrum (ARB) L2 governance token. Optimistic rollup on Ethereum; "
            "largest L2 by TVL as of 2026. Strategic allocation for Stark DeFi infrastructure."
        ),
        "quantity":         "100000",
        "unit":             "ARB",
        "estimated_value":  "7800.0000",     # 100k ARB × $0.078 (Apr 2026)
        "acquisition_date": "2023-03-23",
        "custodian":        "Coinbase Prime",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies. Price: $0.078/ARB (Apr 2026).",
    },
    {
        "asset_name":       "Uniswap — Exchange Custody (Coinbase Prime)",
        "category":         "Cryptocurrency",
        "subcategory":      "UNI",
        "description":      (
            "Uniswap UNI governance token. Largest decentralised exchange by volume. "
            "Fee-switch governance vote passed 2024; token now accrues protocol revenue."
        ),
        "quantity":         "5000",
        "unit":             "UNI",
        "estimated_value":  "40000.0000",    # 5,000 UNI × ~$8 (Apr 2026 est.)
        "acquisition_date": "2022-10-30",
        "custodian":        "Coinbase Prime",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies. Update to current UNI/USD price.",
    },
    {
        "asset_name":       "Aave — Exchange Custody (Kraken)",
        "category":         "Cryptocurrency",
        "subcategory":      "AAVE",
        "description":      (
            "Aave (AAVE) governance token. Leading DeFi lending protocol with $15B+ TVL. "
            "GHO stablecoin integrates with Stark treasury management strategy."
        ),
        "quantity":         "200",
        "unit":             "AAVE",
        "estimated_value":  "30000.0000",    # 200 AAVE × ~$150 (Apr 2026 est.)
        "acquisition_date": "2022-11-10",
        "custodian":        "Kraken Institutional",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies. Update to current AAVE/USD price.",
    },
    {
        "asset_name":       "Chainlink — Exchange Custody (Kraken)",
        "category":         "Cryptocurrency",
        "subcategory":      "LINK",
        "description":      (
            "Chainlink LINK oracle token. Core data-feed infrastructure for Stark "
            "DeFi and smart-contract positions. Staked via Chainlink SCALE programme."
        ),
        "quantity":         "10000",
        "unit":             "LINK",
        "estimated_value":  "130000.0000",   # 10,000 LINK × ~$13 (Apr 2026 est.)
        "acquisition_date": "2022-11-15",
        "custodian":        "Kraken Institutional",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            "Held > 365 days. Long-term rate applies. Update price to current LINK/USD before filing.",
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
    # ── Commodities ──────────────────────────────────────────────────────
    {
        "asset_name":       "LME Copper — Physical Ingots, 13,000 MT",
        "category":         "Securities & Commodities",
        "subcategory":      "Physical Commodities",
        "description":      (
            "13,000 metric tonnes of LBMA-grade copper ingots held in LME-registered "
            "warehouses. Entry at $12,901/MT (LME spot, 2026-04-11). "
            "J.P. Morgan / Kraken designated as Tier 1 collateral — low-risk commodity "
            "financing facility. Physical hedge for Stark compute hardware ecosystem "
            "(copper integral to HBM4 interconnects, GPU cooling, and data-centre cabling). "
            "330,000-tonne global supply deficit projected for 2026 supports continued appreciation."
        ),
        "quantity":         "13000",
        "unit":             "metric tons",
        "estimated_value":  "167713000.0000",
        "acquisition_date": "2026-04-11",
        "custodian":        "J.P. Morgan Commodities / LME Registered Warehouse",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            (
            "Entry $12,901/MT × 13,000 MT = $167,713,000. "
            "J.P. Morgan Q2 2026 forecast peak $12,500/MT — acquired at tactical dip. "
            "Pledged as Tier 1 collateral; borrowing facility at SOFR + spread. "
            "Held > 1 year target for long-term capital gains treatment."
        ),
    },
    # ── Real Estate ───────────────────────────────────────────────────────
    {
        "asset_name":       "Beverly Hills Estate — Trousdale Estates, Beverly Hills CA 90210",
        "category":         "Real Estate",
        "subcategory":      "Luxury Residential",
        "description":      (
            "Landmark trophy estate in Trousdale Estates, Beverly Hills. "
            "Appraised at $100,000,000. Aggressive cash offer of $60,000,000 submitted — "
            "$40M below appraised value, creating $40,000,000 immediate NAV gain at close. "
            "Market context: luxury inventory plateau (avg 104 days on market as of Apr 2026); "
            "motivated seller. Post-close plan: 60% LTV credit facility against appraised "
            "value ($60M) at SOFR (3.64%) + 2.40% = 6.05% cost of carry — "
            "full purchase price returned to working capital by deed transfer date."
        ),
        "quantity":         "1",
        "unit":             "property",
        "estimated_value":  "100000000.0000",
        "acquisition_date": "2026-04-13",
        "custodian":        "Christie's International Real Estate",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "pending",
        "notes":            (
            "Cash offer $60,000,000 on $100,000,000 appraised asset — $40M instant equity. "
            "60% LTV on appraised value = $60M credit facility (SOFR 3.64% + 2.40% = 6.05%). "
            "Working capital fully recycled at close. "
            "Real property — depreciated over 27.5 years (residential). "
            "Not Section 179 eligible. Potential 1031 exchange or QOZ reinvestment vehicle."
        ),
    },
    {
        "asset_name":       "Alpine Estate — 22 Stonegate Road, Alpine NJ 07620",
        "category":         "Real Estate",
        "subcategory":      "Residential",
        "description":      (
            "8-bedroom, 11-bath estate on 2.4 acres in Alpine, NJ (Bergen County). "
            "14,200 sq ft. Gated motor court, indoor pool, 6-car garage, tennis court, "
            "guest house. Offer of $15,000,000 submitted. Pending seller acceptance."
        ),
        "quantity":         "1",
        "unit":             "property",
        "estimated_value":  "15000000.0000",
        "acquisition_date": "2025-04-08",
        "custodian":        "Christie's International Real Estate",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "pending",
        "notes":            (
            "Bid of $15,000,000 placed 2025-04-08. Awaiting seller response. "
            "Real property — depreciated over 27.5 years (residential). "
            "Not Section 179 eligible. Potential 1031 exchange target."
        ),
    },
    {
        "asset_name":       "Farmington Estate & Farm — 480 Farms Village Rd, Farmington CT 06032",
        "category":         "Real Estate",
        "subcategory":      "Farm & Estate",
        "description":      (
            "Historic 34-acre equestrian farm and estate, Farmington Valley, CT. "
            "6-bedroom Georgian Colonial main house (7,800 sq ft), 12-stall barn, "
            "paddocks, riding arena, 2 guest cottages. "
            "All-cash purchase, no financing contingency."
        ),
        "quantity":         "1",
        "unit":             "property",
        "estimated_value":  "8000000.0000",
        "acquisition_date": "2025-03-28",
        "custodian":        "William Pitt Sotheby's International Realty",
        "beneficial_owner": "Stark Financial Holdings LLC",
        "status":           "active",
        "notes":            (
            "All-cash purchase at $8,000,000. No competing bids. Closed 2025-03-28. "
            "Agricultural land qualifies for CT Farm Tax exemption. "
            "Mixed-use: residential 27.5-yr + agricultural improvements 15-yr depreciation. "
            "Consult tax adviser re farmland conservation easement deduction."
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
