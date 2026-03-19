# TRS Parameters — Dual Scale: $100M Ghost / $1B Guardian

> **Context:** At any scale, direct equity purchases in a regime-change move
> trigger slippage and signal your hand. All Recycle List deployment routes
> through a prime broker via TRS or Custom Baskets to maintain invisibility.
> At $100M the ADV cap drops to 3% ("Ghost Mode") — even stealthier.

---

## Ghost Slicer Formula (Cell G10 / G33:G53)

```
=MIN(Required_Notional, Daily_Volume_493 × ADV_Cap)
```

| Scale | ADV Cap | Mode | Formula |
|-------|---------|------|---------|
| $100M | **3%** | 👻 Ghost | `=MIN(C33, D33*0.03)` |
| $1B   | **5%** | 🏛️ Guardian | `=MIN(C33, D33*0.05)` |

Scale-adaptive version (auto-switches):
```
=MIN(C33, D33 * IF(AUM>=500000000, 0.05, 0.03))
```

---

## $100M Harvest Engine — Volatility Tax Math

When VIX spikes, the VIX long generates "Internal Liquidity" that self-funds
new TRS exposure — **zero cash outlay.**

```
Portfolio Split (at $100M):
  VIX Long:          $20M  (20% of AUM)
  493 Basket:        $80M  (80% of AUM)

Today's Harvest Example (VIX +16.8%):
  Daily VIX PnL:     $20M × 16.8%         = $3,360,000
  Harvest Amount:    $3,360,000 × 15%     =   $504,000   ← "Volatility Tax"
  Margin Rate:       15%
  New TRS Exposure:  $504,000 / 15%       = $3,360,000   ← zero cash outlay
  TRS Multiplier:    1 / 15%              =        6.67×

→ Deploy: VST ($1.2M) → GEV ($1.0M) → CCJ ($0.7M) → remainder to Tier 1+2
```

**Cell formulas (EXEC tab):**

| Cell | Formula | Output |
|------|---------|--------|
| E14 | `=VIX_Position * (VIX_Daily_Return/100)` | Daily VIX PnL |
| E15 | `=E14 * Harvest_Rate` | Harvest Amount |
| E16 | `=E15 / Margin_Rate` | New TRS Exposure |
| E17 | `=1 / Margin_Rate` | TRS Multiplier |

---

## $100M TRS Execution Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Notional** | $80,000,000 | 80% of AUM in basket |
| **Structure** | Custom Basket TRS | Single swap referencing all 13 names |
| **Tenor** | 90 days (rolling) | Roll quarterly |
| **Reference Rate** | SOFR + spread | Agreed with prime broker at inception |
| **Collateral** | VIX position | Posted as initial margin (15% haircut) |
| **Threshold (G10)** | **3% of ADV** | Ghost mode — stealthier than Guardian |
| **Max Leg Size** | $15M per name | Caps single-name concentration |
| **Rebalance Trigger** | riskLevel change | Re-weight when engine status rotates |
| **Termination Event** | VIX > 35 OR GEX < -$50M | Scale-adjusted termination |

---

## $1B TRS Execution Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Notional** | $1,000,000,000 | Total swap notional across basket |
| **Structure** | Custom Basket TRS | Single swap referencing all 13 names |
| **Tenor** | 90 days (rolling) | Roll quarterly; review at each regime change |
| **Reference Rate** | SOFR + spread | Agreed with prime broker at inception |
| **Collateral** | VIX position (haircut TBD) | Posted as initial margin |
| **Threshold (G10)** | **5% of ADV** | Guardian mode |
| **Max Leg Size** | $150M per name | Caps single-name concentration |
| **Rebalance Trigger** | riskLevel change | Re-weight when engine status rotates |
| **Termination Event** | VIX > 35 OR GEX < -$500M | Unwind swap, return to Shield mode |

---

## Basket Weighting (Recycle Phase)

### Phase 1 — Primary Recycle Targets (deploy first, correlated with oil shock trigger)

| Ticker | Company | Why | Weight $1B | Notional $1B | Weight $100M | Notional $100M |
|--------|---------|-----|-----------|-------------|-------------|----------------|
| VST | Vistra Corp | Power gen — direct oil/energy price beneficiary | 8% | $80M | 8% | $6.4M |
| GEV | GE Vernova | Grid infrastructure — energy transition play | 7% | $70M | 7% | $5.6M |
| CCJ | Cameco Corp | Uranium/nuclear — oil shock accelerates nuclear demand | 5% | $50M | 5% | $4.0M |

### Phase 2 — Tier 1+2 (deploy after Phase 1 is sized)

| Ticker | Weight $1B | Notional $1B | Weight $100M | Notional $100M |
|--------|-----------|-------------|-------------|----------------|
| MSFT | 16% | $160M | 16% | $12.8M |
| V | 14% | $140M | 14% | $11.2M |
| MA | 14% | $140M | 14% | $11.2M |
| ACN | 11% | $110M | 11% | $8.8M |
| UNH | 10% | $100M | 10% | $8.0M |
| JNJ | 10% | $100M | 10% | $8.0M |
| ABBV | 8% | $80M | 8% | $6.4M |
| PG | 4% | $40M | 4% | $3.2M |
| COST | 4% | $40M | 4% | $3.2M |
| BRK.B | 2% | $20M | 2% | $1.6M |
| **Total** | **100%** | **$1,000M** | **100%** | **$80M** |

---

## Full EXEC Tab Formula Stack

| Cell | Formula | Purpose |
|------|---------|---------|
| B4 | `=IF(B1>27,"🚨 BLACK SWAN: STOP RECYCLING, MAXIMIZE SHIELD",IF(AND(B1>24,B3>115),"♻️ RECYCLE: MOVE VIX PROFIT TO VST/GEV/CCJ","🌊 SYMBIOSIS: MONITOR 493 DECOUPLING"))` | Engine mode |
| G6 | `=IF(AUM>=500000000,0.05,0.03)` | Ghost Slicer cap (3% or 5%) |
| G10 | `=MIN(Required_Notional,(Daily_Volume_493*G6))` | Per-name execution limit |
| H4 | `=IF((AUM_Allocation/Average_Daily_Volume)>G6,"EXECUTE VIA SWAP","EXECUTE VIA DARK POOL")` | Routing decision |
| I4 | `=IF(H4="EXECUTE VIA SWAP","→ TRS Desk","→ Dark Pool Broker")` | Execution path |
| J4 | `=IF(AUM>=500000000,"🏛️ $1B GUARDIAN MODE","👻 $100M GHOST MODE")` | Scale label |
| E14 | `=VIX_Position*(VIX_Daily_Return/100)` | Daily VIX PnL |
| E15 | `=E14*Harvest_Rate` | Harvest amount (Volatility Tax) |
| E16 | `=E15/Margin_Rate` | New TRS exposure unlocked |
| E17 | `=1/Margin_Rate` | TRS multiplier |

---

## Execution Flow

```
VIX Alpha Harvested
       │
       ▼
  H4 Routing Check
  (AUM / ADV > 5%?)
       │
  ┌────┴────┐
  YES       NO
   │         │
TRS Desk  Dark Pool
   │         │
   └────┬────┘
        │
  Basket Deployed
  into 493 Names
        │
   Monitor for
  riskLevel change
        │
  ┌─────┴──────┐
CRITICAL     NORMAL
  │              │
Hold TRS      Roll or
  open        Unwind
```
