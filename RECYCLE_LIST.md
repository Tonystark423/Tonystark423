# Recycle List — VIX Alpha Deployment Targets

> **When to use:** Shield holds → VIX premium harvested → deploy into these names in order.
> **Filter:** Lowest Energy Sensitivity in the S&P 493 (excludes Mag 7).

---

## Top 10 Low Energy-Sensitivity S&P 493 Names

| # | Ticker | Company | Sector | Energy Sensitivity | Deployment Rationale |
|---|--------|---------|--------|--------------------|----------------------|
| 1 | MSFT | Microsoft | Technology | ⬛ Very Low | Pure software/cloud — no physical input costs |
| 2 | V | Visa | Financials | ⬛ Very Low | Payment network toll-road — 100% transaction margin |
| 3 | MA | Mastercard | Financials | ⬛ Very Low | Identical model to Visa — zero energy exposure |
| 4 | UNH | UnitedHealth | Healthcare | 🟦 Low | Managed care/insurance — revenue driven by premiums not energy |
| 5 | JNJ | Johnson & Johnson | Healthcare | 🟦 Low | Diversified pharma — strong pricing power offsets any input cost |
| 6 | ABBV | AbbVie | Healthcare | 🟦 Low | Biotech royalties + Humira pipeline — no energy input |
| 7 | ACN | Accenture | Technology | ⬛ Very Low | Pure labor/consulting model — margins unaffected by oil |
| 8 | PG | Procter & Gamble | Consumer Staples | 🟨 Low-Moderate | Brand pricing power historically absorbs commodity spikes |
| 9 | COST | Costco | Consumer Staples | 🟨 Low-Moderate | Membership fee model insulates operating margin |
| 10 | BRK.B | Berkshire Hathaway | Financials | 🟦 Low | Energy holdings (BNSF, OXY) internally hedge any oil exposure |

---

## Energy Sensitivity Key

| Symbol | Level | Meaning |
|--------|-------|---------|
| ⬛ | Very Low | Negligible exposure — deploy first |
| 🟦 | Low | Minimal exposure — deploy second tier |
| 🟨 | Low-Moderate | Some input cost risk — deploy after confirmation |
| 🟥 | High | Do not deploy during RECYCLE phase |

---

## Primary Recycle Targets — VST / GEV

When RECYCLE is triggered (VIX > 24 + Oil > 115), lead deployment with:

| Ticker | Company | Why |
|--------|---------|-----|
| VST | Vistra Corp | Power generator — benefits directly from high energy prices |
| GEV | GE Vernova | Grid infrastructure — energy transition play, oil-shock resilient |

These are the **first two positions** to receive VIX alpha in a RECYCLE phase.
Deploy the broader Tier 1/2 list after VST/GEV are sized.

---

## EXEC Tab Integration

```
=IF(B1>27,              "🚨 BLACK SWAN: STOP RECYCLING, MAXIMIZE SHIELD",
 IF(AND(B1>24,B3>115),  "♻️ RECYCLE: MOVE VIX PROFIT TO VST/GEV",
                         "🌊 SYMBIOSIS: MONITOR 493 DECOUPLING"))
```

---

## Deployment Sequence

```
BLACK SWAN (VIX > 27)
  └─▶ Stop all recycling. Maximize VIX shield to full notional.

Shield / Critical (VIX 25–27, GEX < 0)
  └─▶ Hold VIX. Accumulate Tier 1: MSFT → V → MA → ACN

Recycle Triggered (VIX > 24, Oil > 115)
  └─▶ Lead: VST → GEV
  └─▶ Then Tier 1+2: UNH → JNJ → ABBV → PG → COST → BRK.B

Symbiosis (NORMAL)
  └─▶ Hold all. Monitor 493 decoupling from Mag 7.
```
