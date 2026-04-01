# [EXEC] Tab — Full Pre-Formatted Layout
# VIX Alpha → 493 Workflow at $1B Scale

---

## Sheet Layout

```
     A                  B                    C                D               E
1  [INPUTS]           VALUE              [STATUS]
2  ──────────────────────────────────────────────────────────────────────────────
3  VIX                [live]             ENGINE MODE      ← B4 formula
4  GEX                [live]             ROUTING          ← H4 formula
5  Oil ($/bbl)        [live]             EXEC PATH        ← I4 formula
6  AUM ($)            [live]
7  ADV (basket avg)   [live]
8
9  ──────────────────────────────────────────────────────────────────────────────
10 [PnL TRACKER]
11 ──────────────────────────────────────────────────────────────────────────────
12 VIX Premium In     [live]             Deployable Cash  ← L4 formula
13 493 Basket Cost    [live]             Net PnL          ← M4 formula
14 Open TRS Notional  [live]             PnL %            ← N4 formula
15
16 ──────────────────────────────────────────────────────────────────────────────
17 [RECYCLE LIST]     WEIGHT   NOTIONAL  ADV      ROUTING      STATUS
18 ──────────────────────────────────────────────────────────────────────────────
19 MSFT               18%      $180M     [live]   ← H19        ← J19
20 V                  15%      $150M     [live]   ← H20        ← J20
21 MA                 15%      $150M     [live]   ← H21        ← J21
22 ACN                12%      $120M     [live]   ← H22        ← J22
23 UNH                10%      $100M     [live]   ← H23        ← J23
24 JNJ                10%      $100M     [live]   ← H24        ← J24
25 ABBV                8%       $80M     [live]   ← H25        ← J25
26 PG                  5%       $50M     [live]   ← H26        ← J26
27 COST                5%       $50M     [live]   ← H27        ← J27
28 BRK.B               2%       $20M     [live]   ← H28        ← J28
29
30 ──────────────────────────────────────────────────────────────────────────────
31 [ALERTS]
32 ──────────────────────────────────────────────────────────────────────────────
33 Shield Alert       ← O33
34 Termination Alert  ← O34
35 Rebalance Alert    ← O35
```

---

## Cell-by-Cell Formula Reference

### Section 1 — Engine Mode

**B4 (Engine Mode)**
```
=IF(B1>27,              "🚨 BLACK SWAN: STOP RECYCLING, MAXIMIZE SHIELD",
 IF(AND(B1>24,B3>115),  "♻️ RECYCLE: MOVE VIX PROFIT TO VST/GEV",
                         "🌊 SYMBIOSIS: MONITOR 493 DECOUPLING"))
```

**G6 (ADV Slicer Cap — Ghost vs Guardian, time-aware)**
```
=IF(NOW()-INT(NOW())>=TIMEVALUE("15:50:00"), 0.02,
 IF(B6>=500000000, 0.05, 0.03))
```
> Returns 2% during MOC window (3:50–4:00 PM), 3% at $100M, 5% at $1B otherwise.

**H4 (Routing Decision)**
```
=IF((B6/B7)>G6, "EXECUTE VIA SWAP", "EXECUTE VIA DARK POOL")
```

**I4 (Execution Path)**
```
=IF(H4="EXECUTE VIA SWAP", "→ TRS Desk", "→ Dark Pool Broker")
```

---

### Section 2 — PnL & Deployable Cash

**L4 (Deployable Cash)**
```
=B12-B13
```
> VIX Premium collected minus cost of 493 basket already deployed.

**M4 (Net PnL)**
```
=B12-B13-B14*(B8/10000)*(B9/365)
```
> Net of VIX premium, basket cost, and TRS financing cost (AUM-scaled).

**M10 (Symbiosis PnL Reconciliation)**
```
=(VIX_Roll_Yield + E14) - (TRS_Notional*(TRS_Spread_Bps/10000)*(1/365) + G26)
```
Where `G26` = today's total slippage across all 493 names.

| M10 result | Meaning | Next action |
|-----------|---------|-------------|
| **> 0** | You are the House — Mag 7 Alumni paying for 493 | Hold current ADV cap |
| **< 0** | Moving too fast — execution cost > VIX revenue | Dial ADV cap to 2% tomorrow |

**N10 (Tomorrow's ADV Cap)**
```
=IF(M10>0, G6, 0.02)
```

**N4 (PnL %)**
```
=M4/B6
```
> Net PnL as a percentage of total AUM.

---

### Section 3 — Per-Name Routing (rows 19–28)

**H19:H28 (Per-Name Routing)** — paste into H19, drag to H28:
```
=IF((C19/D19)>$G$6, "SWAP", "DARK POOL")
```

**J19:J28 (Per-Name Status)** — paste into J19, drag to J28:
```
=IF($B$1>35, "🚨 BLACK SWAN — Kill TRS",
 IF(AND($B$1>27,$B$1<=35), "🚨 EXTREME — Maximize Shield",
 IF(AND($B$1>22,$B$2<0),   "🔒 SHIELD — Continue Harvest",
 IF(AND($B$1>24,$B$3>115), "♻️ DEPLOY — Recycle Phase",
 IF($B$1<20,               "🌊 SYMBIOSIS — Physical Equity",
                            "⏳ WATCH — Prepare Parameters")))))
```

---

### Section 4 — Alerts

**O33 (Black Swan Alert)**
```
=IF(B1>27, "🚨 BLACK SWAN: Stop recycling. Maximize VIX shield immediately.", "")
```

**O34 (Termination Alert)**
```
=IF(OR(B1>35,B2<-500000000), "🚨 TERMINATE TRS: VIX>35 or GEX<-$500M. Unwind immediately.", "")
```

**O35 (Recycle Alert)**
```
=IF(AND(B1>24,B3>115,B1<=27), "♻️ RECYCLE: Deploy VIX profit → VST / GEV first, then Tier 1+2.", "")
```

---

## Conditional Formatting Rules

| Range | Condition | Fill Color |
|-------|-----------|------------|
| B4 | contains "BLACK SWAN" | Dark Red `#880000` |
| B4 | contains "SHIELD" | Red `#FF0000` |
| B4 | contains "RECYCLE" | Orange `#FF6600` |
| B4 | contains "SYMBIOSIS" | Green `#00AA44` |
| H4 | contains "SWAP" | Yellow `#FFDD00` |
| H4 | contains "DARK POOL" | Blue `#0044FF` |
| O33 | not empty | Red `#FF0000` |
| O34 | not empty | Dark Red `#880000` |
| O35 | not empty | Orange `#FF6600` |
| N4 | > 0 | Green `#00AA44` |
| N4 | < 0 | Red `#FF0000` |

---

## Named Ranges

| Name | Cell | Value |
|------|------|-------|
| `VIX` | B1 | Live VIX index |
| `GEX` | B2 | Live gamma exposure ($) |
| `Oil` | B3 | Live crude price ($/bbl) |
| `AUM_Allocation` | B6 | Total AUM in dollars |
| `Average_Daily_Volume` | B7 | Weighted avg ADV across basket |
| `VIX_Premium_In` | B12 | Cumulative VIX premium collected |
| `Basket_Cost` | B13 | Cumulative 493 basket deployment cost |
| `TRS_Notional` | B14 | Current open TRS notional |

---

## Workflow Summary

```
[INPUTS: VIX / GEX / Oil / AUM]
            │
            ▼
      B4: Engine Mode
   SHIELD / RECYCLE / SYMBIOSIS
            │
     ┌──────┴──────┐
  SHIELD        RECYCLE
     │              │
  Hold VIX      H4 Routing
  No deploy    (AUM/ADV > 5%?)
                   │
             ┌─────┴─────┐
           SWAP       DARK POOL
             │              │
          TRS Desk    Dark Pool Broker
             │              │
             └──────┬────────┘
                    │
             Deploy J19:J28
             (per-name status)
                    │
             L4: Deployable Cash
             M4: Net PnL
             N4: PnL %
                    │
             O33/O34/O35: Alerts
```
