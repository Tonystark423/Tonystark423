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

## EXEC Tab Integration

Add a second formula in your **[EXEC]** tab to auto-flag the active deployment tier:

```
=IF(AND(B1>25, B2<0),   "🛡️ SHIELD — Accumulate Tier 1 (MSFT, V, MA)",
 IF(AND(B1>22, B3>115), "♻️ RECYCLE — Deploy Tier 1+2 (add UNH, JNJ, ABBV)",
 "🌊 SYMBIOSIS — Hold All Positions"))
```

---

## Deployment Sequence

```
Shield Active (CRITICAL)
  └─▶ Accumulate Tier 1: MSFT → V → MA → ACN

Shield Holds → Recycle Triggered (ELEVATED)
  └─▶ Add Tier 2:        UNH → JNJ → ABBV → PG → COST → BRK.B

Symbiosis (NORMAL)
  └─▶ Hold all. No new deployment. Maintain 493 alpha long.
```
