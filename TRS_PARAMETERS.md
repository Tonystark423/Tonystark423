# $1B TRS Parameters — The Great Convergence

> **Context:** At $1B AUM, individual equity purchases trigger slippage.
> All Recycle List deployment must route through a prime broker via
> Total Return Swaps (TRS) or Custom Baskets to maintain Guardian invisibility.

---

## Invisibility Formula (Cell H4)

With `AUM_Allocation` in a named range and `Average_Daily_Volume` per ticker:

```
=IF((AUM_Allocation / Average_Daily_Volume) > 0.05, "EXECUTE VIA SWAP", "EXECUTE VIA DARK POOL")
```

| Result | Meaning |
|--------|---------|
| `EXECUTE VIA SWAP` | Position > 5% of ADV — must use TRS to avoid market impact |
| `EXECUTE VIA DARK POOL` | Position ≤ 5% of ADV — can route via dark pool without slippage |

---

## $1B TRS Execution Parameters

Hand these to the execution desk when rotating VIX alpha into the 493 Recycle List:

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Notional** | $1,000,000,000 | Total swap notional across basket |
| **Structure** | Custom Basket TRS | Single swap referencing all 10 names |
| **Tenor** | 90 days (rolling) | Roll quarterly; review at each regime change |
| **Reference Rate** | SOFR + spread | Agreed with prime broker at inception |
| **Collateral** | VIX position (haircut TBD) | Posted as initial margin |
| **Threshold (H4)** | 5% of ADV per name | Triggers swap vs dark pool routing |
| **Max Leg Size** | $150M per name | Caps single-name concentration |
| **Rebalance Trigger** | riskLevel change | Re-weight when engine status rotates |
| **Termination Event** | VIX > 35 OR GEX < -$500M | Unwind swap, return to Shield mode |

---

## Basket Weighting (Recycle Phase)

Allocate the $1B notional across the 10 names weighted by inverse energy sensitivity:

| Ticker | Weight | Notional |
|--------|--------|----------|
| MSFT | 18% | $180M |
| V | 15% | $150M |
| MA | 15% | $150M |
| ACN | 12% | $120M |
| UNH | 10% | $100M |
| JNJ | 10% | $100M |
| ABBV | 8% | $80M |
| PG | 5% | $50M |
| COST | 5% | $50M |
| BRK.B | 2% | $20M |
| **Total** | **100%** | **$1,000M** |

---

## Full EXEC Tab Formula Stack

| Cell | Formula | Purpose |
|------|---------|---------|
| B4 | `=IF(AND(B1>25,B2<0),"🛡️ SHIELD",IF(AND(B1>22,B3>115),"♻️ RECYCLE","🌊 SYMBIOSIS"))` | Engine mode |
| H4 | `=IF((AUM_Allocation/Average_Daily_Volume)>0.05,"EXECUTE VIA SWAP","EXECUTE VIA DARK POOL")` | Routing decision |
| I4 | `=IF(H4="EXECUTE VIA SWAP","→ TRS Desk","→ Dark Pool Broker")` | Execution path |

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
