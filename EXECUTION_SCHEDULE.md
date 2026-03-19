# Daily Execution Schedule — $100M → $1B Alpha Engine
# Ghost Slicer · VIX Harvest · Clip Sizes · Hourly Timing · Cumulative Alpha

---

## Architecture Summary

```
VIX Long (20%)  →  Harvest 15% of daily PnL  →  TRS margin  →  Phase 1 (VST/GEV/CCJ)
                                                               →  Phase 2 (Tier 1+2)
493 Basket (80%) → Physical Equity (SYMBIOSIS) or TRS (RECYCLE/SHIELD)
```

ADV cap: **3%** regular session | **2%** MOC window (3:50–4:00 PM ET)

---

## $100M Daily Clip Schedule

### Assumptions (adjust for live ADV)

| Ticker | Phase | Weight | Target Notional | Est. ADV | 3% ADV Clip |
|--------|-------|--------|----------------|----------|-------------|
| VST    | 1     | 8%     | $6,400,000     | $60M     | $1,800,000  |
| GEV    | 1     | 7%     | $5,600,000     | $42M     | $1,260,000  |
| CCJ    | 1     | 5%     | $4,000,000     | $30M     | $900,000    |
| MSFT   | 2     | 16%    | $12,800,000    | $350M    | $10,500,000 |
| V      | 2     | 14%    | $11,200,000    | $120M    | $3,600,000  |
| MA     | 2     | 14%    | $11,200,000    | $110M    | $3,300,000  |
| ACN    | 2     | 11%    | $8,800,000     | $24M     | $720,000    |
| UNH    | 2     | 10%    | $8,000,000     | $52M     | $1,560,000  |
| JNJ    | 2     | 10%    | $8,000,000     | $40M     | $1,200,000  |
| ABBV   | 2     | 8%     | $6,400,000     | $36M     | $1,080,000  |
| PG     | 2     | 4%     | $3,200,000     | $30M     | $900,000    |
| COST   | 2     | 4%     | $3,200,000     | $28M     | $840,000    |
| BRK.B  | 2     | 2%     | $1,600,000     | $25M     | $750,000    |

> **Note:** Where Target Notional < 3% ADV Clip, the full target is executable in a
> single Dark Pool order. The clip is limited to MIN(Target, ADV×0.03).

### Harvest-Funded Deployment (today's example: VIX +16.8%)

```
VIX Long ($20M) × 16.8%  = $3,360,000 daily PnL
Harvest (15%)             =   $504,000  ← "Volatility Tax"
Margin rate (15%)         →  $3,360,000 new TRS notional unlocked

Phase 1 deployment from harvest:
  VST:  $3,360,000 × 36% (weight within Phase 1) = $1,210,000
  GEV:  $3,360,000 × 28%                          = $1,010,000
  CCJ:  $3,360,000 × 20%                          =   $730,000
  Residual → Phase 2 Tier 1 (MSFT/V/MA)           =   $410,000
```

---

## Hourly Execution Timeline

All times ET. Regime assumed: RECYCLE (VIX 24–27, Oil > $115).

```
09:30 AM  ─ OPEN ─────────────────────────────────────────────────────────────
  Action:   Confirm engine mode (run B4 formula).
  If RECYCLE: Enable Ghost Slicer at 3% ADV. Load Phase 1 orders.
  If SHIELD:  No deployment. Monitor harvest only.
  If BLACK SWAN: Kill TRS. Halt all execution.

09:30–10:30 AM  ─ FIRST HOUR ─────────────────────────────────────────────────
  ADV Cap:   3%
  Focus:     Phase 1 only — VST / GEV / CCJ
  VST:       VWAP  $840k clip  (14% of $6.4M target)
  GEV:       VWAP  $630k clip  (11% of $5.6M target)
  CCJ:       VWAP  $450k clip  (11% of $4.0M target)
  Algo:      VWAP — aligns to opening volume surge
  Expected impact: ~5 bps each (noise band)

10:30–12:00 PM  ─ MID-MORNING ────────────────────────────────────────────────
  ADV Cap:   3%
  Focus:     Finish Phase 1 + begin Phase 2 Tier 1
  VST:       VWAP  $840k clip  (2nd of 4 daily clips)
  GEV:       VWAP  $630k clip
  CCJ:       VWAP  $450k clip
  MSFT:      Dark Pool  $3,200k  (MSFT ADV >> target — sub-3% easily)
  V:         Dark Pool  $2,800k
  MA:        Dark Pool  $2,800k

12:00–1:30 PM  ─ LUNCH LULL ─────────────────────────────────────────────────
  ADV Cap:   3%  (volume thins — reduce clip frequency, not size)
  Focus:     Phase 2 Tier 1 continuation
  ACN:       TWAP  $360k clip  (ACN ADV tight — 2hr spread)
  UNH:       VWAP  $780k clip
  JNJ:       VWAP  $600k clip
  ABBV:      VWAP  $540k clip
  Note: Watch M10. If negative, pause until 2:00 PM.

1:30–3:00 PM  ─ AFTERNOON ────────────────────────────────────────────────────
  ADV Cap:   3%
  Focus:     Phase 2 Tier 2 + remaining Phase 1 residual
  PG:        Dark Pool  $900k  (single clip — sub-3% ADV)
  COST:      Dark Pool  $840k
  BRK.B:     Dark Pool  $750k
  VST:       VWAP  $840k clip  (3rd of 4)
  GEV:       VWAP  $630k clip  (3rd of 4)
  CCJ:       VWAP  $450k clip  (3rd of 4)

3:00–3:50 PM  ─ PRE-CLOSE ───────────────────────────────────────────────────
  ADV Cap:   3%  (still standard — last chance before tightening)
  Focus:     Final VWAP clips. Reconcile M10.
  Check:     Is M10 > 0? If yes → hold cap. If no → flag for 2% tomorrow.
  VST:       VWAP  $840k clip  (4th / final)
  GEV:       VWAP  $630k clip  (4th / final)
  ACN:       TWAP  $360k clip  (2nd of 2)
  Unfilled:  Log in MOC queue for Closing Cross check.

3:50–4:00 PM  ─ MOC WINDOW (CLOSING CROSS) ──────────────────────────────────
  ADV Cap:   ⚠️ TIGHTEN TO 2%  ← MOC Protector activates
  Action:    Run protectClosingCross() for all unfilled positions.
             Any notional > 2% ADV limit → defer to tomorrow's VWAP open.
  HFT risk:  Maximum — do NOT exceed 2% ADV regardless of remaining target.
  VST MOC limit:  $60M × 2% = $1,200,000  (if unfilled < $1.2M → execute)
  GEV MOC limit:  $42M × 2% = $840,000
  CCJ MOC limit:  $30M × 2% = $600,000
  ACN MOC limit:  $24M × 2% = $480,000  ← tight — likely defers

4:00 PM  ─ CLOSE ─────────────────────────────────────────────────────────────
  Action:   Reconcile M10. Log deferred notional. Update cumulative P1 (LENS tab).
  If any names deferred: load as tomorrow's first VWAP clips (9:30 AM open).
  Commit:   systemicAlpha P1 += today's (493 TRS gain + VIX roll - financing)
```

---

## $1B Daily Clip Schedule

### Scale-Up from $100M

At $1B the ADV cap stays at 5% (Guardian mode) but notionals are 10× larger.
MSFT and V/MA are easily absorbed (ADV >> position). Tighter names are ACN, CCJ, VST.

| Ticker | Phase | Target Notional | Est. ADV | 5% ADV Clip | Days to full position |
|--------|-------|----------------|----------|-------------|----------------------|
| VST    | 1     | $80,000,000    | $120M    | $6,000,000  | ~13 trading days     |
| GEV    | 1     | $70,000,000    | $85M     | $4,250,000  | ~16 trading days     |
| CCJ    | 1     | $50,000,000    | $60M     | $3,000,000  | ~17 trading days     |
| MSFT   | 2     | $160,000,000   | $3,500M  | $175,000,000| 1 day (Dark Pool)    |
| V      | 2     | $140,000,000   | $900M    | $45,000,000 | 3–4 days             |
| MA     | 2     | $140,000,000   | $850M    | $42,500,000 | 3–4 days             |
| ACN    | 2     | $110,000,000   | $180M    | $9,000,000  | ~12 trading days     |
| UNH    | 2     | $100,000,000   | $400M    | $20,000,000 | 5 days               |
| JNJ    | 2     | $100,000,000   | $320M    | $16,000,000 | 6–7 days             |
| ABBV   | 2     | $80,000,000    | $280M    | $14,000,000 | 6 days               |
| PG     | 2     | $40,000,000    | $240M    | $12,000,000 | 3–4 days             |
| COST   | 2     | $40,000,000    | $220M    | $11,000,000 | 3–4 days             |
| BRK.B  | 2     | $20,000,000    | $200M    | $10,000,000 | 2 days               |

> At $1B, VST/GEV/CCJ require 13–17 days to fully size — **stealth is the schedule**.
> Guardian mode means the position builds gradually over multiple weeks.
> To the market, it looks like systematic index rebalancing, not directional accumulation.

### $1B Multi-Day Schedule (Phase 1 focus)

```
Day 1–3:   VST $18M / GEV $12.75M / CCJ $9M per day
           MSFT complete (Dark Pool, 1 day)
           BRK.B complete (2 days)

Day 4–6:   VST $18M / GEV $12.75M / CCJ $9M (continuing)
           V $45M/day → complete by day 7
           MA $42.5M/day → complete by day 7
           PG/COST complete

Day 7–12:  VST $18M / GEV $12.75M / CCJ $9M (continuing)
           UNH $20M/day → complete by day 12
           JNJ $16M/day → complete by day 13

Day 12–17: ACN $9M/day → complete
           ABBV $14M/day → complete
           Final VST/GEV/CCJ clips → full positions

Total deployment window: ~17 trading days (~3.5 weeks)
```

---

## Daily Expected PnL — $100M Scale

```
Scenario: RECYCLE regime, VIX = 25.4, Oil = $118, VIX +16.8%

[ALPHA SOURCES]
VIX position mark-to-market:          +$3,360,000
VIX roll yield (daily theta):         +$    50,000
493 basket daily drift (avg +0.3%):   +$   240,000  (on $80M deployed)
─────────────────────────────────────────────────────
Gross daily alpha:                     $3,650,000

[COSTS]
TRS financing (25bps/365 × $80M):     -$   548
Execution slippage (5bps avg):         -$   168
  VST $840k × 5bps:                   -$    42
  GEV $630k × 5bps:                   -$    31
  CCJ $450k × 5bps:                   -$    22
  Others (Dark Pool, 2bps):           -$    73
─────────────────────────────────────────────────────
Total daily cost:                      -$   716

M10 Net (gross alpha - costs):        +$3,649,284   ✅ YOU ARE THE HOUSE

[HARVEST DEPLOYMENT]
Harvest amount:                        $504,000
New TRS exposure triggered:           $3,360,000
Phase 1 new notional added:           $1,950,000 (VST/GEV/CCJ)
Phase 2 residual:                     $1,410,000 (Tier 1)
```

---

## Cumulative Alpha Tracker (LENS Tab P1)

```
             Day    Cumul. VIX PnL   Cumul. 493 TRS   Cumul. Financing   P1 Systemic Alpha   % AUM
             ────   ──────────────   ──────────────   ────────────────   ─────────────────   ─────
             1      $3,360,000       $240,000         ($548)             $3,599,452          3.6%
             2      $6,720,000       $480,000         ($1,096)           $7,198,904          7.2%  ← DECOUPLED
             3      $8,400,000       $720,000         ($1,644)           $9,118,356          9.1%
             ...
             14     $47,040,000      $3,360,000       ($7,672)           $50,392,328         50.4%
```

> Note: These are illustrative with VIX +16.8% held constant. Real-world VIX mean-reverts.
> The structural edge is the compounding of harvest → TRS margin → more 493 exposure,
> which generates more 493 PnL, which adds to the self-funding loop.

---

## Alert Integration — Execution Decision Tree

```
4:00 AM PRE-OPEN
  Check VIX futures + Oil → set expected regime for the day
        │
  ┌─────┴───────────────────────────────────┐
  │                                         │
VIX > 35 OR Oil > $140            VIX 22–35 AND GEX < 0
  │                                         │
🚨 BLACK SWAN                     🛡️ SHIELD ACTIVE
  │                                         │
Kill all execution.               Continue harvest only.
Move PnL to Cash/VIX.             No new TRS. 3% ADV cap.
Zero deployment today.            Monitor M10.
  │                                         │
  └─────────────────┬───────────────────────┘
                    │
             VIX 24–27 + Oil > $115
                    │
          ♻️ RECYCLE — RUN SCHEDULE ABOVE
                    │
             VIX < 20
                    │
          🌊 SYMBIOSIS
          Exit TRS. Switch to 100% Physical Equity.
          No harvest needed — vol too low for alpha.

9:30 AM OPEN
  Load clips per schedule above.
  Ghost Slicer: MIN(target, ADV × 3%)

DURING SESSION
  Re-check B4 every 30 min. If regime changes:
  → SHIELD: halt new clips immediately
  → BLACK SWAN: send MOC unwind on all open TRS legs

3:50 PM MOC
  protectClosingCross() → defer excess to tomorrow VWAP

4:00 PM CLOSE
  Update M10 reconciliation.
  Update LENS P1 (cumulative systemic alpha).
  If M10 < 0: tomorrow's cap = 2%.
  If P1 > 5% AUM: DECOUPLED status. Log.
```

---

## Scale Transition Checklist ($100M → $1B)

When AUM crosses $500M, the engine auto-switches (G6 formula returns 0.05).
Manually verify:

- [ ] ADV cap updated to 5% in all manual overrides
- [ ] Max leg size raised from $15M to $150M per name
- [ ] TRS termination threshold raised: GEX < -$500M (was -$50M)
- [ ] Phase 1 deployment raised: VST target $80M (was $6.4M)
- [ ] Multi-day schedule loaded: VST/GEV/CCJ require 13–17 days at $1B
- [ ] MOC cap remains 2% at all scales — do not change
- [ ] M10 roll yield component updated to reflect larger VIX position ($200M)
- [ ] LENS P1 thresholds updated: 5% = $50M decoupled (was $5M)
