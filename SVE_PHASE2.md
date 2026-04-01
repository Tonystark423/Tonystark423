# SVE Engine — Phase 2 Patent Supplement
## Multi-PB Collateral Architecture & Capacity Mapping

**Supplement to:** `SVE_ENGINE_PATENT.md` (Claims A–C), `SVE_CLAIMS_FINAL.md` (Claims D–G)
**New Independent Claims:** H (Collateral Asymmetry), I (Capacity Map),
J (Global Netting / Omnibus Exit), K (Leakage Surveillance)

---

## Core Problem Statement: Collateral Asymmetry

> *"The greatest threat at Phase 2 is not a market crash — it is Collateral
> Asymmetry. If PB-1 hikes margin to 15% while PB-2 stays at 10%, a 'Locked'
> liquidity state can occur."*

A **Locked State** is defined as:
```
Locked ⟺ ∃ PB_i where:
  (marginRate_i > wtdAvgMargin + δ)       [outlier margin]
  AND collateralPosted_i < notional_i × marginRate_i   [shortfall]
  AND ¬(∃ TPRA link to donor PB with excess collateral)  [no sweep path]
```

The SVE Phase 2 engine prevents Locked States by maintaining a pre-positioned
Tri-Party Repo (TPRA) mesh and sweeping collateral automatically when asymmetry
is detected — before the margin call reaches the desk terminal.

---

## Independent Claim H — Collateral Asymmetry Detector + TPRA Sweep Engine

### H.1 — Asymmetry Detection

A system for real-time detection of prime broker margin rate divergence comprising:

**(a)** a **multi-PB margin monitor** that continuously samples margin rates
`{r_1, r_2, ..., r_N}` from N prime brokers and computes the notional-weighted
average:
```
r̄ = Σ(r_i × notional_i) / Σ(notional_i)
```

**(b)** an **outlier gate** that flags PB_i as a margin outlier when:
```
r_i > r̄ + δ_outlier   (default δ_outlier = 4 percentage points)
```

**(c)** a **shortfall quantifier**:
```
shortfall_i = max(0, notional_i × r_i − collateralPosted_i)
```

**(d)** a **3σ stress pre-positioning module** that simulates the margin hike
a 35% VIX spike would cause at the most aggressive PB:
```
stressHike_PB1 = min(25%, r̄ × 2.25)
stressShortfall = notional_PB1 × (stressHike_PB1 − r_PB1_current)
```
and pre-positions that collateral buffer *before* the VIX spike occurs —
the defining feature of pre-emptive vs reactive margin management.

---

### H.2 — TPRA Sweep Plan (Collateral Neutralization)

The system of Claim H.1 wherein upon detection of any shortfall:

**(a)** donor PBs are ranked by `marginExcess_i = collateralPosted_i − notional_i × r_i`
(most over-collateralized first);

**(b)** the minimum-sweep plan is computed:
```
for each outlier PB (sorted by shortfall descending):
  allocate min(donor.marginExcess, remainingShortfall)
  route via pre-positioned Tri-Party Repo link
```

**(c)** the sweep executes via existing TPRA infrastructure — no new market-facing
trades are generated, no net position changes; this is a pure collateral
reallocation between the engine's own prime brokerage accounts;

**(d)** the sweep completes before the margin call is processed by the outlier PB,
eliminating forced liquidation risk.

---

### H.3 — Regulatory Boundary (Non-Wash Architecture)

The TPRA sweep explicitly differs from a wash trade in every legally relevant dimension:

| Dimension | Wash Trade (Illegal) | TPRA Sweep (H.2) |
|-----------|---------------------|------------------|
| Market-facing execution | Yes — creates artificial volume | No — internal collateral transfer |
| Net position change | Zero (by design to deceive) | Zero (because it's collateral, not position) |
| Intent | Deceive market participants | Satisfy margin obligation |
| Regulatory status | CEA §4c(a)(5), SEC Rule 10b-5 | Standard prime brokerage settlement |
| Disclosure | Concealed | Reported to PBs as collateral transfer |

---

## Independent Claim I — C_m Capacity Mapping / Thermal Guardrail

### I.1 — Top-of-Book Depth Analysis

A system for preventing self-induced market impact during large notional
deployment comprising:

**(a)** a **venue depth monitor** that continuously samples Level-2 order book
depth for each execution venue, aggregating the top-of-book dollar depth:
```
ToB_v = Σ(price_i × size_i)  for top 5 bid/ask levels on venue v
```

**(b)** a **participation cap** that limits the engine's allocation to any
venue to:
```
tobCap_v = ToB_v × tobCapPct   (default tobCapPct = 10%)
```
Above this threshold the engine transitions from "market noise" (indistinguishable
from pension rebalancing) to "market impact" (price-moving participant);

**(c)** the **Capacity scalar C_m**:
```
C_m = min(1.0, totalRemainingCap / targetNewNotional)

where totalRemainingCap = Σ max(0, tobCap_v − currentAllocation_v)
```
`C_m = 1.0` = full capacity; `C_m = 0` = thermal halt (all venues at cap);

**(d)** a **thermal routing algorithm** that distributes deployable notional
to the "coolest" venues first (lowest currentAllocation / tobCap ratio),
maximizing total deployment while keeping each venue below the 10% threshold.

---

### I.2 — Thermal Status Ladder

| C_m | Thermal Status | Action |
|-----|---------------|--------|
| ≥ 0.95 | FULL CAPACITY | Deploy at normal Ghost Slicer pace |
| 0.70–0.95 | PARTIAL CAPACITY | Throttle to available venues; skip WARM |
| 0.30–0.70 | CONSTRAINED | Reduce target; wait for ToB recovery |
| < 0.05 | THERMAL HALT | Passive-only; no new clips |

---

### I.3 — $150M Constraint Formalization

At $150M AUM with a 4-venue execution mesh, the system reaches thermal
constraint when:
```
targetNewNotional > Σ(ToB_v × 0.10)  across all venues
```

Empirically, for mid-cap equity names (VST/GEV/CCJ), combined ToB depth
averages $800M–$1.2B during normal sessions. The 10% cap allows up to
$80M–$120M deployment per session — consistent with the Phase 2 expansion
timeline requiring 13–17 days to full notional.

---

## Independent Claim J — Global Netting Engine + Omnibus Exit

### J.1 — Cross-PB Position Aggregation

A system for computing net economic exposure across multiple prime brokers
comprising:

**(a)** a **position aggregator** that collects per-PB, per-ticker positions
and computes true net notional:
```
net(ticker) = Σ(notional_i × sign_i)  across all PBs
              where sign = +1 (LONG), −1 (SHORT)
```

**(b)** an **internal offset identifier** that detects when the same ticker
has long legs at one PB and short legs at another — these are economically
offsetting and can be netted via internal book transfer without any market
execution;

**(c)** the **Omnibus Exit** sequence — a minimum-touch unwind plan sorted
by absolute net notional descending, each line item specifying:
- ticker, net side, exit notional
- routing: Ghost Slicer 3%/5% ADV caps via C_m-cleared venues;

**(d)** a **collateral efficiency report** ranking PBs by gross/collateral
utilization — identifying which PB relationships are capital-efficient and
which are over-collateralized relative to current book.

---

### J.2 — Omnibus Exit vs Wash Trade (Regulatory Distinction)

The Omnibus Exit described in Claim J.1 differs from a wash trade in
all relevant dimensions:

- **Intent:** reduce net economic exposure, not create artificial activity
- **Execution:** each leg is a genuine, single-directional clip
- **Net result:** net position is reduced (not maintained at zero as a deception)
- **Disclosure:** all executions reported to prime brokers and clearing in standard fashion

The cross-PB rebalancing that *is* legitimate — moving $X of position from
PB-1 to PB-2 for margin efficiency — involves an actual position close at
PB-1 and genuine open at PB-2, with a true economic rationale (lower margin rate,
better financing, concentration limit compliance).

---

## Independent Claim K — Leakage Surveillance (Post-Execution Adversarial Detection)

### K.1 — Adverse-Selection Correlation Monitor

A system for detecting prime broker internal information leakage comprising:

**(a)** a **fill history aggregator** that records for each completed execution:
```
{pbId, ticker, side, fillPrice, fillTimeMs, postFillPrice_2ms, postFillPrice_50ms, notional}
```

**(b)** an **adverse-selection metric** computed per fill:
```
AS_2ms  = sign × (postFillPrice_2ms  − fillPrice) / fillPrice × 10,000   [bps]
AS_50ms = sign × (postFillPrice_50ms − fillPrice) / fillPrice × 10,000
```
where `sign = +1` for buys (adverse = price fell), `−1` for sells (adverse = price rose);

**(c)** a **size-leakage correlation** per PB — if larger fills at PB_i
systematically produce larger adverse-selection measures, the PB's internal
market-making desk is receiving client order-flow information:
```
leakage_correlation_i = corr(notional_j, AS_2ms_j)  for fills j routed via PB_i
```
A value below `−0.60` indicates systematic size-informed leakage;

**(d)** a **hostile flag** when:
```
leakage_correlation_i < −0.80  AND  avg(AS_2ms_i) < −2×leakageThreshold
```

**(e)** an **automatic pivot** upon hostile detection: route ≤ 5% of flow
through hostile PB (for surveillance continuity) and shift 80% of expansion
to the dark-pool-specialist node.

---

### K.2 — Regulatory Boundary (vs Spoofing)

The leakage detection method of Claim K.1 is distinguished from spoofing
in every legally relevant dimension:

| Dimension | Spoof (Illegal) | Claim K.1 |
|-----------|----------------|-----------|
| Orders placed | Non-executable, fake intent | Real fills only — no orders placed for detection |
| Market disruption | Artificial price signal | No new orders; uses completed fill data |
| Intent | Deceive other participants | Monitor own execution quality |
| Regulatory status | CEA §4c(a)(5)(B), Dodd-Frank | Standard transaction cost analysis (TCA) |
| Information used | Injected false data | Own historical fill data |

Any TCA provider that computes adverse-selection ratios across broker channels
performs equivalent analysis. The SVE novelty is the automatic routing pivot
triggered by the leakage signal.

---

## Phase 2 Competitor Coverage Matrix

| Feature | Claim | Competitor Boundary |
|---------|-------|---------------------|
| Weighted-avg margin outlier detection across ≥2 PBs | H.1 | Real-time multi-PB margin asymmetry monitor |
| Pre-emptive TPRA sweep triggered by margin divergence | H.2 | Automated collateral rebalancing before margin call |
| 3σ VIX stress pre-positioning | H.1.d | Forward collateral buffer seeded by vol-stress model |
| ToB depth 10% cap as passive-only threshold | I.1–I.2 | C_m scalar governing deployment pace |
| Coolest-venue-first thermal routing | I.1.d | L2 depth-aware execution allocation |
| Cross-PB internal offset via book transfer | J.1.b | No-market-execution netting of offsetting legs |
| Size-leakage correlation for PB adverse-selection | K.1.c | Automated TCA-driven hostile-PB detection |
| Automatic 80%/5% routing pivot on hostile flag | K.1.e | Post-fill signal → execution routing decision |

---

## Formula Register — Phase 2

| Symbol | Definition | Claim |
|--------|-----------|-------|
| `r̄` | Notional-weighted avg margin rate across all PBs | H.1 |
| `δ_outlier` | Outlier threshold above `r̄` (default 4pp) | H.1.b |
| `shortfall_i` | `max(0, notional_i × r_i − collateralPosted_i)` | H.1.c |
| `ToB_v` | Top-of-book dollar depth on venue v | I.1.a |
| `tobCapPct` | Max participation rate (default 10%) | I.1.b |
| `C_m` | Capacity scalar `= min(1, totalRemainingCap / target)` | I.1.c |
| `net(ticker)` | `Σ(notional_i × sign_i)` across all PBs | J.1.a |
| `AS_2ms` | Adverse selection in bps at 2ms post-fill | K.1.b |
| `leakage_correlation` | `corr(notional, AS_2ms)` per PB | K.1.c |

---

## Implementation Reference

| Function | Claim | Description |
|----------|-------|-------------|
| `buildCollateralAsymmetry()` | H.1–H.2 | Multi-PB margin monitor + TPRA sweep plan |
| `buildCapacityMap()` | I.1–I.2 | TOB depth → C_m thermal guardrail + routing |
| `buildGlobalNettingEngine()` | J.1 | Cross-PB aggregation + Omnibus Exit sequence |
| `buildLeakageSurveillance()` | K.1 | Adverse-selection correlation per PB |

All wired into `buildDashboard()` as Layer 10b.
Activate by supplying `primeBrokers`, `venues`, `pbPositions`, `fillHistory` inputs.

---

*SVE Engine Phase 2 — Patent Supplement v3.0*
*Stark Financial Holdings — March 2026*
*Supplements SVE_ENGINE_PATENT.md and SVE_CLAIMS_FINAL.md*
