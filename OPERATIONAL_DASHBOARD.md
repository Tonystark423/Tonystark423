# Operational Dashboard — $1B / $100M Live Alpha vs Risk
# Unified: Engine State · Harvest · Ghost Slicer · TRS Tracker · Alpha/Risk Panel

---

## Dual-Scale Architecture

| Parameter | $100M Ghost Mode | $1B Guardian Mode |
|-----------|-----------------|-------------------|
| VIX allocation | $20M (20% of AUM) | $200M (20% of AUM) |
| 493 basket | $80M (80% of AUM) | $800M (80% of AUM) |
| ADV slicer cap | **3%** (ghost) | **5%** (standard) |
| G10 formula | `MIN(notional, ADV×0.03)` | `MIN(notional, ADV×0.05)` |
| Phase 1 recycle | VST → GEV → CCJ | VST → GEV → CCJ |
| TRS tenor | 90 days rolling | 90 days rolling |

---

## Sheet Layout

```
     A                    B              C           D                    E          F
1  [INPUTS]              VALUE                     [ENGINE STATE]
2  ──────────────────────────────────────────────────────────────────────────────────
3  VIX                   [live]                    ENGINE MODE          ← B4 formula
4  GEX ($)               [live]                    RISK LEVEL           ← B5 formula
5  Oil ($/bbl)           [live]                    ROUTING              ← H4 formula
6  AUM ($)               [live]                    EXEC PATH            ← I4 formula
7  ADV Slicer Cap        ← G6 formula              SCALE                ← J4 formula
8  TRS Spread (bps)      [live]
9  Holding Days          [live]
10
11 ──────────────────────────────────────────────────────────────────────────────────
12 [HARVEST ENGINE]
13 ──────────────────────────────────────────────────────────────────────────────────
14 VIX Position ($)      [live]                    DAILY VIX PnL        ← E14 formula
15 VIX Daily Return %    [live]                    HARVEST AMOUNT (15%) ← E15 formula
16 Harvest Rate          15%                       NEW TRS EXPOSURE     ← E16 formula
17 Margin Rate           15%                       TRS MULTIPLIER       ← E17 formula
18
19 ──────────────────────────────────────────────────────────────────────────────────
20 [ALPHA vs RISK PANEL]
21 ──────────────────────────────────────────────────────────────────────────────────
22 VIX Premium In        [live]                    ALPHA CREATED        ← E22 formula
23 Basket Cost           [live]                    RISK CONSUMED        ← E23 formula
24 Basket Value          [live]                    NET ALPHA            ← E24 formula
25 TRS Net PnL           ← trsTracker              ALPHA EFFICIENCY     ← E25 formula
26 Slippage Estimate     ← G26 formula             ANNLZD YIELD %       ← E26 formula
27                                                 STATUS               ← E27 formula
28
29 ──────────────────────────────────────────────────────────────────────────────────
30 [GHOST SLICER — PHASE 1: PRIMARY RECYCLE — VST / GEV / CCJ]
31 ──────────────────────────────────────────────────────────────────────────────────
32 TICKER  NOTIONAL  ADV(live)  ADV%  CAP%  ALLOWED    ALGO     SLICE    WINDOW  URGENCY   ROUTE
33 VST     [C33]     [D33]      ←E33  ←F33  ←G33      ←H33     ←I33     ←J33    ←K33      ←L33
34 GEV     [C34]     [D34]      ←E34  ←F34  ←G34      ←H34     ←I34     ←J34    ←K34      ←L34
35 CCJ     [C35]     [D35]      ←E35  ←F35  ←G35      ←H35     ←I35     ←J35    ←K35      ←L35
36
37 ──────────────────────────────────────────────────────────────────────────────────
38 [GHOST SLICER — PHASE 2: TIER 1 (Very Low energy sensitivity)]
39 ──────────────────────────────────────────────────────────────────────────────────
40 MSFT    [C40]     [D40]      ←E40  ←F40  ←G40      ←H40     ←I40     ←J40    ←K40      ←L40
41 V       [C41]     [D41]      ←E41  ...
42 MA      [C42]     [D42]      ←E42  ...
43 ACN     [C43]     [D43]      ←E43  ...
44
45 ──────────────────────────────────────────────────────────────────────────────────
46 [GHOST SLICER — PHASE 2: TIER 2 (Low energy sensitivity)]
47 ──────────────────────────────────────────────────────────────────────────────────
48 UNH     [C48]     [D48]      ←E48  ...
49 JNJ     [C49]     ...
50 ABBV    [C50]     ...
51 PG      [C51]     ...
52 COST    [C52]     ...
53 BRK.B   [C53]     ...
54
55 ──────────────────────────────────────────────────────────────────────────────────
56 [ALERTS]
57 ──────────────────────────────────────────────────────────────────────────────────
58 ← O58  Black Swan Alert
59 ← O59  Termination Alert
60 ← O60  Recycle Alert
61 ← O61  Alpha Efficiency Warning
62 ← O62  TRS Drawdown Warning
```

---

## Cell-by-Cell Formula Reference

### Section 1 — Engine State

**B4 (Engine Mode)**
```
=IF(B3>27,              "🚨 BLACK SWAN: STOP RECYCLING, MAXIMIZE SHIELD",
 IF(AND(B3>24,B5>115),  "♻️ RECYCLE: MOVE VIX PROFIT TO VST/GEV/CCJ",
                         "🌊 SYMBIOSIS: MONITOR 493 DECOUPLING"))
```

**B5 (Risk Level)**
```
=IF(B3>27,             "BLACK SWAN",
 IF(AND(B3>25,B4<0),   "CRITICAL",
 IF(AND(B3>25,B4>=0),  "HIGH",
 IF(AND(B3>24,B5>115), "ELEVATED",
 IF(B3>20,             "WARNING", "NORMAL")))))
```

**G6 (ADV Slicer Cap — Ghost Mode vs Guardian Mode)**
```
=IF(B6>=500000000, 0.05, 0.03)
```
> Returns 3% at $100M scale, 5% at $1B scale.

**H4 (Routing Decision)**
```
=IF((B6/B7)>G6, "EXECUTE VIA SWAP", "EXECUTE VIA DARK POOL")
```

**I4 (Execution Path)**
```
=IF(H4="EXECUTE VIA SWAP", "→ TRS Desk", "→ Dark Pool Broker")
```

**J4 (Scale Label)**
```
=IF(B6>=500000000, "🏛️ $1B GUARDIAN MODE", "👻 $100M GHOST MODE")
```

---

### Section 2 — Harvest Engine

**E14 (Daily VIX PnL)**
```
=B14 * (B15/100)
```
> $20M × 16.8% = **$3,360,000**

**E15 (Harvest Amount — Volatility Tax)**
```
=E14 * B16
```
> $3.36M × 15% = **$504,000**

**E16 (New TRS Exposure Unlocked)**
```
=E15 / B17
```
> $504k / 15% = **$3,360,000** new 493 notional — zero cash outlay

**E17 (TRS Multiplier)**
```
=1/B17
```
> 1 / 15% = **6.67×** — every $1 of harvest controls $6.67 of new exposure

---

### Section 3 — Alpha vs Risk Panel

**E22 (Alpha Created)**
```
=B22 + MAX(0, B24-B23) + MAX(0, B25)
```
> VIX premium + basket appreciation + TRS gains

**E23 (Risk Consumed)**
```
=MAX(0, B23-B24) + MAX(0, -B25) + G26
```
> Basket decline + TRS losses + slippage

**E24 (Net Alpha)**
```
=E22 - E23
```

**E25 (Alpha Efficiency)**
```
=IF(E23>0, E24/E23, "NO RISK CONSUMED")
```
> Net alpha per $1 of risk consumed. Target: > 1.5×

**E26 (Annualised Yield %)**
```
=(E24/B6) * (365/B9) * 100
```

**E27 (Status)**
```
=IF(E25>2,   "🚀 COMPOUNDING",
 IF(E25>1,   "✅ POSITIVE",
 IF(E25>0,   "⚠️ MARGINAL",
             "🔴 UNDERWATER")))
```

**G26 (Slippage Estimate — sum across slicer rows)**
```
=SUMPRODUCT(G33:G53 * IFERROR(VLOOKUP(H33:H53,
  {"UNWIND NOW",0.0025;"ICEBERG",0.0015;"TWAP",0.0008;"VWAP",0.0005;"DARK POOL",0.0002;"HOLD",0}, 2, 0), 0))
```

---

### Section 4 — Ghost Slicer (rows 33–53)

**E33:E53 (ADV % — position as % of ADV)**
```
=C33/D33
```

**F33:F53 (Slicer Cap — AUM-adaptive)**
```
=$G$6
```
> Pulls 3% or 5% from the Scale cell.

**G33:G53 (Allowed Notional — Ghost Slicer Limit)**
```
=MIN(C33, D33*$G$6)
```
> The G10 equivalent per name: `=MIN(Required_Notional, Daily_Volume_493 × cap)`

**H33:H53 (Execution Algo)**
```
=IF($B$4="BLACK SWAN",              "UNWIND NOW",
 IF(OR($B$4="CRITICAL",$B$4="HIGH"),"HOLD",
 IF($B$4="ELEVATED",
   IF(E33>$G$6*4, "ICEBERG",
   IF(E33>$G$6*2, "TWAP",
   IF(E33>$G$6,   "VWAP",
                  "DARK POOL"))),
   "VWAP REBALANCE")))
```

**I33:I53 (Slice Size — one child order)**
```
=IF(H33="UNWIND NOW",       G33,
 IF(H33="HOLD",             0,
 IF(H33="ICEBERG",          G33*0.05,
 IF(H33="TWAP",             G33/12,
 IF(H33="VWAP",             G33/4,
 IF(H33="DARK POOL",        G33,
                             G33/4))))))
```

**J33:J53 (Time Window — minutes)**
```
=IF(H33="UNWIND NOW",     0,
 IF(H33="HOLD",           0,
 IF(H33="ICEBERG",        240,
 IF(H33="TWAP",           120,
 IF(H33="VWAP",           60,
 IF(H33="DARK POOL",      15,
                          60))))))
```

**K33:K53 (Urgency)**
```
=IF(H33="UNWIND NOW",       "🚨 CRITICAL — Accept Slippage",
 IF(H33="HOLD",             "🔒 BLOCKED — Shield Active",
 IF(H33="ICEBERG",          "🥷 STEALTH — 4hr Window",
 IF(H33="TWAP",             "⏱️ MODERATE — 2hr Window",
 IF(H33="VWAP",             "📊 VOLUME-TIMED — 1hr",
 IF(H33="DARK POOL",        "⚡ IMMEDIATE — Dark Pool",
                             ""))))))
```

**L33:L53 (Route)**
```
=IF(E33>$G$6, "TRS DESK", "DARK POOL")
```

---

### Section 5 — Alerts

**O58 (Black Swan)**
```
=IF(B3>27, "🚨 BLACK SWAN: Stop recycling. Maximize VIX shield immediately.", "")
```

**O59 (Termination)**
```
=IF(OR(B3>35,B4<-500000000), "🚨 TERMINATE TRS: VIX>35 or GEX<-$500M. Unwind all legs.", "")
```

**O60 (Recycle)**
```
=IF(AND(B3>24,B5>115,B3<=27), "♻️ RECYCLE: Deploy VIX harvest → VST / GEV / CCJ (Phase 1) first.", "")
```

**O61 (Alpha Efficiency Warning)**
```
=IF(AND(ISNUMBER(E25),E25<0), "⚠️ ALPHA UNDERWATER: Review basket vs VIX hedge sizing.", "")
```

**O62 (TRS Drawdown)**
```
=IF(B25/SUMPRODUCT(C33:C53)<-0.02, "🔴 TRS DRAWDOWN >2%: Check termination event thresholds.", "")
```

---

## Conditional Formatting Rules

| Range | Condition | Fill Color |
|-------|-----------|------------|
| B4 | contains "BLACK SWAN" | Dark Red `#880000` |
| B4 | contains "SHIELD" | Red `#FF0000` |
| B4 | contains "RECYCLE" | Orange `#FF6600` |
| B4 | contains "SYMBIOSIS" | Green `#00AA44` |
| J4 | contains "GHOST" | Purple `#6600CC` |
| J4 | contains "GUARDIAN" | Navy `#003399` |
| G6 | = 0.03 | Purple `#6600CC` |
| G6 | = 0.05 | Navy `#003399` |
| E27 | contains "COMPOUNDING" | Green `#00AA44` |
| E27 | contains "POSITIVE" | Light Green `#88CC44` |
| E27 | contains "MARGINAL" | Yellow `#FFDD00` |
| E27 | contains "UNDERWATER" | Red `#FF0000` |
| H33:H53 | = "UNWIND NOW" | Dark Red `#880000` |
| H33:H53 | = "ICEBERG" | Purple `#6600CC` |
| H33:H53 | = "TWAP" | Blue `#0044FF` |
| H33:H53 | = "DARK POOL" | Teal `#009999` |
| H33:H53 | = "HOLD" | Orange `#FF6600` |
| O58:O62 | not empty | Red `#FF0000` |

---

## The $100M Harvest Math (Live Example)

```
VIX Position:       $20,000,000
VIX Daily Return:   +16.8%
─────────────────────────────────
Daily VIX PnL:      $3,360,000     ← E14
Harvest Rate:       15%
Harvest Amount:     $504,000       ← E15  "Volatility Tax"
─────────────────────────────────
Margin Rate:        15%
New TRS Exposure:   $3,360,000     ← E16  (zero cash outlay)
TRS Multiplier:     6.67×          ← E17

→ Deploy: VST ($1.2M) → GEV ($1.0M) → CCJ ($0.7M) → remainder to Tier 1+2
```

---

## Full Workflow

```
[INPUTS: VIX / GEX / Oil / AUM / ADV]
              │
              ▼
        B4: Engine Mode
    BLACK SWAN / SHIELD / RECYCLE / SYMBIOSIS
              │
    ┌─────────┼──────────────────┐
    │         │                  │
BLACK SWAN  SHIELD           RECYCLE
    │         │                  │
Unwind all  Hold VIX         Harvest Engine (E14-E17)
  TRS legs  No deploy        15% VIX PnL → Margin
    │                        → New TRS Exposure
    │                             │
    │                        Ghost Slicer (G33:G53)
    │                        MIN(notional, ADV × cap)
    │                        3% at $100M / 5% at $1B
    │                             │
    │                     Per-Name Algo (H33:H53)
    │                     ICEBERG / TWAP / VWAP / DARK POOL
    │                             │
    │                     Phase 1 FIRST: VST → GEV → CCJ
    │                     Phase 2 after: Tier 1+2
    │                             │
    └─────────────────────────────┘
                    │
           Alpha vs Risk Panel
           E22: Alpha Created
           E23: Risk Consumed
           E24: Net Alpha
           E25: Efficiency (target > 1.5×)
           E26: Annualised Yield %
                    │
             O58-O62: Alerts
```

---

## Named Ranges

| Name | Cell | Value |
|------|------|-------|
| `VIX` | B3 | Live VIX index |
| `GEX` | B4 | Live gamma exposure ($) |
| `Oil` | B5 | Live crude price ($/bbl) |
| `AUM` | B6 | Total AUM ($) |
| `TRS_Spread_Bps` | B8 | Prime broker SOFR spread |
| `Holding_Days` | B9 | Days since first deployment |
| `VIX_Position` | B14 | Dollar size of VIX long |
| `VIX_Daily_Return` | B15 | Today's VIX % move |
| `Harvest_Rate` | B16 | Fraction of VIX PnL to harvest |
| `Margin_Rate` | B17 | TRS initial margin % |
| `ADV_Cap` | G6 | Ghost (3%) or Guardian (5%) slicer cap |
