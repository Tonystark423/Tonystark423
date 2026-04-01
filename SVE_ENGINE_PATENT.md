# Stark Volatility-Energy (SVE) Engine
## Patent Filing Package — Mechanics of the Claim

**Application Title:**
*System and Method for Recursive Optimization of Total Return Swaps via Cross-Asset Energy-Volatility Term Structure Analysis*

**Inventors:** Stark Capital Research Division
**Filing Classification:** Financial Instrument Processing / Algorithmic Risk Management (CPC G06Q 40/04)

---

## Technical Abstract

The invention comprises a computational engine that monitors the divergence between energy commodity backwardation and volatility term-structure contango. By applying a 2σ threshold to the **Stark Energy-Vol Differential (S_evd)**, the system executes synthetic exposure through a Total Return Swap (TRS) architecture. The system further utilizes a **Collateral Velocity (C_v)** processor that ingests real-time central bank liquidity data (M2/repo rates) to dynamically adjust margin buffers, mitigating risk during 3SD liquidity shocks.

The engine is distinguished from prior art by its recursive flywheel architecture: harvested volatility premium is re-deployed as TRS collateral, the collateral earns the prevailing repo rate, and that repo-rate signal is fed back into the C_v processor to update margin requirements in real time — creating a self-reinforcing liquidity cycle that is structurally immune to the margin-call cascades it monitors.

---

## Claims

### Independent Claim A — Stark Energy-Vol Differential (S_evd) Signal Generator

**Claim A.1 (Primary Signal):**
A system for generating a cross-asset term-structure divergence signal comprising:

(a) a first data processor that continuously samples the **energy backwardation slope** defined as:
```
B_energy = (F_energy[t0] - F_energy[t+3mo]) / F_energy[t0]
```
where `F_energy[t0]` is the front-month energy futures price and `F_energy[t+3mo]` is the three-month deferred contract price; a positive `B_energy` indicates energy backwardation (near-term scarcity premium);

(b) a second data processor that continuously samples the **volatility term-structure slope** defined as:
```
C_vol = (VIX_futures[t+1mo] - VIX[t0]) / VIX[t0]
```
where `VIX[t0]` is the spot VIX and `VIX_futures[t+1mo]` is the one-month VIX futures price; a positive `C_vol` indicates volatility contango (market expects future fear to exceed present);

(c) a divergence computation module that calculates the **Stark Energy-Vol Differential**:
```
S_evd = B_energy - (-C_vol) = B_energy + C_vol
```
A positive `S_evd` signals a structural tension: energy markets price in *near-term* cost pressure while volatility markets price in *deferred* fear — a mispricing exploitable via synthetic equity exposure;

(d) a sigma-normalizer that computes `S_evd` against a rolling 60-day distribution:
```
S_evd_normalized = (S_evd - μ_60d) / σ_60d
```

(e) a threshold gate that emits a BUY signal when `S_evd_normalized ≥ 2.0` (2σ above rolling mean) and a REDUCE signal when `S_evd_normalized ≤ -1.0`.

---

**Claim A.2 (Execution Linkage):**
The system of Claim A.1 wherein the BUY signal triggers execution of one or more Total Return Swap (TRS) legs via a ghost-slicing module that constrains each clip to a maximum of 3% of the ticker's Average Daily Volume (ADV) at AUM < $500M and 5% ADV at AUM ≥ $500M, preventing market impact from exceeding 5 basis points.

---

**Claim A.3 (Regime Override):**
The system of Claim A.1 wherein the BUY signal is suppressed when the engine's regime state is BLACK SWAN (`VIX > 35 OR oil > $140`), and automatically reinstated upon regime normalization without manual intervention.

---

### Independent Claim B — Sovereign Liquidity Flywheel (C_v Processor)

> *"Most desks look at the VIX; we look at the plumbing of the fiat system."*

**The Problem Addressed:**
Existing volatility-harvesting systems are vulnerable to liquidity-shock margin calls because they model risk from asset prices alone. They do not observe the underlying monetary plumbing (M2 velocity, repo market stress) that *causes* the margin calls 48–72 hours before asset prices reflect them.

**Claim B.1 (Collateral Velocity Measurement):**
A liquidity-monitoring processor comprising:

(a) an **M2 Contraction Signal** module that samples weekly M2 money supply data and computes the rolling 4-week rate of change:
```
ΔM2_4w = (M2[t] - M2[t-4w]) / M2[t-4w]
```
A value below -0.5% annualized triggers a **Liquidity Warning**;

(b) a **Repo Stress Indicator** that monitors the spread between the Secured Overnight Financing Rate (SOFR) and the Federal Funds Rate target:
```
RepoStress = SOFR - FFR_target
```
A spread exceeding +25bps triggers a **Plumbing Alert** — indicating repo market dysfunction ahead of the equity vol response;

(c) the **Collateral Velocity scalar**:
```
C_v = 1 - max(0, (RepoStress / 0.0025) × 0.10 + max(0, -ΔM2_4w / 0.005) × 0.15)
```
`C_v` ranges from 0.0 to 1.0 — a value of 1.0 indicates full liquidity (normal operations); a value of 0.70 indicates a 30% collateral haircut should be applied to all TRS margin buffers;

(d) a **3SD Shock Gate** that immediately halts all new TRS seeding when:
```
SHOCK = (RepoStress > 3 × σ_RepoStress_90d) OR (ΔM2_4w < -3 × σ_ΔM2_90d)
```

---

**Claim B.2 (Dynamic Margin Buffer Adjustment):**
The system of Claim B.1 wherein the required margin buffer `M_required` for each open TRS leg is dynamically adjusted:
```
M_required = M_base / C_v
```
where `M_base` is the standard margin (e.g., 15% of notional). When `C_v` falls to 0.75, required margin rises from 15% to 20% — the system automatically routes a portion of the VIX harvest to fund the margin increment rather than new TRS deployment.

---

**Claim B.3 (The Sovereign Flywheel — Recursive Architecture):**
The system of Claims B.1 and B.2 wherein the engine implements a self-reinforcing collateral cycle comprising four sequentially recursive stages:

```
Stage 1 (HARVEST):   dailyWarTax = vixPosition × vixGapPct × harvestRate
                     → harvested vol premium deposited as TRS collateral

Stage 2 (EARN):      collateralYield = depositedCollateral × SOFR
                     → collateral earns repo rate while idle

Stage 3 (SIGNAL):    C_v update ingests new SOFR reading from Stage 2
                     → if SOFR rising → C_v falls → margin buffers thicken
                     → if SOFR stable → C_v ≈ 1.0 → full deployment capacity

Stage 4 (DEPLOY):    newTrsCapacity = (depositedCollateral × C_v) / marginRate
                     → net new TRS notional = Stage 4 output - Stage 2 yield reinvested
                     → return to Stage 1
```

This four-stage recursion constitutes the **Sovereign Liquidity Flywheel**: the system is simultaneously *long* volatility (Stage 1 harvest), *long* the repo rate (Stage 2 earn), *short* liquidity fear (Stage 3 C_v update), and *long* synthetic equity growth (Stage 4 deploy) — four orthogonal positions in a single self-funding loop.

---

**Claim B.4 (Moat Definition — Temporal Alpha):**
The system of Claim B.3 provides a **48–72 hour early warning advantage** over equity-vol-only systems because:

(a) repo stress emerges in overnight lending markets before equity vol reflects it;
(b) M2 contraction manifests in weekly Fed H.6 release before credit spreads widen;
(c) the C_v scalar pre-thickens margin buffers *before* the margin call cascade hits competing desks;
(d) when competitors face forced liquidation (the margin call cascade), the SVE engine is already fully margined and can *add* TRS exposure at distressed prices — generating the largest War Tax at the moment of maximum fear.

---

### Independent Claim C — Recursive TRS Optimization via Term Structure Convergence

**Claim C.1 (Convergence Harvesting):**
A method for extracting alpha from the convergence between energy backwardation and volatility contango comprising:

(a) entry: TRS leg opened when `S_evd_normalized ≥ 2.0` (two standard deviations above mean);

(b) sizing: notional = `MIN(harvestAmount / marginRate, MAX_TRS_NOTIONAL_PER_TICKER)`;

(c) carry: while open, each TRS leg accrues: `dailyCarry = notional × (underlyingReturn - SOFR - spreadBps/10000)`;

(d) exit: TRS leg reduced when `S_evd_normalized ≤ 0` (mean reversion complete) OR regime = BLACK SWAN;

(e) reinvestment: proceeds from closed TRS legs immediately re-enter Stage 1 of the Sovereign Flywheel (Claim B.3).

---

**Claim C.2 (Self-Funding Threshold — Decoupling):**
The system reaches **Decoupled status** — the point at which the 493-stock basket is entirely self-funding — when:
```
P1_SystemicAlpha = (Cumulative_TRS_Gain + Cumulative_VIX_RollYield) - Total_Financing_Costs
P1_SystemicAlpha / AUM ≥ 5%
```
Above this threshold, no new external capital is required to maintain full TRS deployment. The engine is perpetually self-sustaining from the Sovereign Flywheel alone.

---

## Formula Appendix

### A. Stark Energy-Vol Differential (S_evd)

| Symbol | Definition | Data Source |
|--------|-----------|-------------|
| `F_energy[t0]` | Front-month WTI/Brent futures price | CME/ICE real-time |
| `F_energy[t+3mo]` | 3-month deferred energy futures | CME/ICE real-time |
| `B_energy` | `(F[t0] - F[t+3mo]) / F[t0]` | Computed |
| `VIX[t0]` | CBOE Spot VIX | CBOE real-time |
| `VIX_futures[t+1mo]` | 1-month VIX futures (VX contract) | CBOE real-time |
| `C_vol` | `(VIX_futures - VIX) / VIX` | Computed |
| `S_evd` | `B_energy + C_vol` | Core signal |
| `S_evd_normalized` | `(S_evd - μ_60d) / σ_60d` | Threshold input |

**Signal Ladder:**

| S_evd_normalized | Signal | Action |
|-----------------|--------|--------|
| ≥ 3.0 | STRONG BUY | Full ADV cap deployment; add AAPL call tranche |
| ≥ 2.0 | BUY | Standard Ghost Slicer execution |
| 0.0 – 2.0 | HOLD | Maintain existing legs; no new seeding |
| ≤ -1.0 | REDUCE | Close weakest TRS leg; recycle to VIX shield |
| ≤ -2.0 | EXIT | Full TRS reduction; maximize cash buffer |

---

### B. Collateral Velocity (C_v)

```
RepoStress    = SOFR - FFR_target
ΔM2_4w        = (M2_current - M2_4w_ago) / M2_4w_ago

repoComponent = max(0, (RepoStress / 0.0025) × 0.10)
m2Component   = max(0, (-ΔM2_4w / 0.005) × 0.15)

C_v           = 1 - min(0.50, repoComponent + m2Component)
M_required    = M_base / C_v
```

**C_v Lookup Table:**

| SOFR Spread | ΔM2 (4w) | C_v | Effective Margin | Status |
|-------------|----------|-----|-----------------|--------|
| +0bps | 0% | 1.00 | 15.0% | NORMAL |
| +15bps | -0.3% | 0.85 | 17.6% | WATCH |
| +25bps | -0.5% | 0.73 | 20.5% | WARNING |
| +40bps | -1.0% | 0.57 | 26.3% | CRITICAL |
| +63bps (3σ) | any | SHOCK | HALT | SHOCK — halt all seeding |

---

### C. Sovereign Flywheel Recursion

```
t = 0:  WarTax_0     = vixPosition × vixGapPct × 0.15
        Collateral_0 = WarTax_0

t = 1:  CollYield_1  = Collateral_0 × SOFR_annual / 252
        C_v_1        = f(SOFR_1, ΔM2_1)
        TRScap_1     = (Collateral_0 × C_v_1) / marginRate

t = n:  Collateral_n = Collateral_{n-1} + WarTax_n + CollYield_n
        TRScap_n     = (Collateral_n × C_v_n) / marginRate

Steady state: ∂(TRScap) / ∂t > 0 as long as C_v > marginRate / (1 + SOFR)
```

**Flywheel Break-Even Condition:**
The flywheel sustains itself (no external capital required) when:
```
daily_WarTax + daily_CollYield > daily_TRS_Financing
vixPosition × avgDailyVixReturn × 0.15 + Collateral × SOFR/252 > TRS_notional × (SOFR + spread) / 252
```

---

### D. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    SVE ENGINE — DATA FLOWS                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CME Energy Futures ──► B_energy ─────────┐                    │
│  CBOE VIX / VX Futures ─► C_vol ──────────┼──► S_evd           │
│                                           │     │              │
│                                       2σ gate   │              │
│                                           │  BUY / HOLD /      │
│                                           │  REDUCE signal     │
│                                           │     ▼              │
│  Fed H.6 M2 ──────────────────► ΔM2_4w ──►  C_v processor     │
│  SOFR / FFR ─────────────────► RepoStress ─►  │               │
│                                               ▼               │
│                          ┌────── M_required = M_base / C_v    │
│                          │                                     │
│                          │    SOVEREIGN FLYWHEEL               │
│                          │  ┌──────────────────────────────┐   │
│                          └─►│ Stage 1: VIX Harvest (15%)   │   │
│                             │ Stage 2: Collateral → SOFR   │   │
│                             │ Stage 3: SOFR → C_v update   │   │
│                             │ Stage 4: C_v × coll / margin │   │
│                             │            → TRS Notional    │   │
│                             └──────────────┬───────────────┘   │
│                                            │ recurse ↑         │
│                                            ▼                   │
│                              Ghost Slicer (3%/5% ADV cap)      │
│                              → VST / GEV / CCJ TRS Legs        │
│                              → AAPL Call Overlay (78-bin)      │
│                              → P1 Systemic Alpha (LENS)        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prior Art Differentiation

| Feature | Prior Art (Standard Vol Desk) | SVE Engine |
|---------|------------------------------|------------|
| Risk signal | VIX spot level | S_evd: energy/vol term-structure *divergence* |
| Margin model | Static % of notional | C_v: dynamic, driven by repo/M2 plumbing |
| Execution | Block trades or standard VWAP | Ghost Slicer: 3%/5% ADV clips, sqrt impact model |
| Collateral | Idle cash | Sovereign Flywheel: collateral earns SOFR, re-enters loop |
| Timing edge | Same-day VIX reaction | 48–72hr lead via repo/M2 early warning |
| AAPL hedge | Separate book | Integrated: call overlay funded entirely by War Tax |
| Self-funding | Never | Decoupling at P1 ≥ 5% AUM |

---

## Dependent Claims Summary

| Claim | Title | Depends On |
|-------|-------|-----------|
| A.1 | S_evd Signal Generator | Independent |
| A.2 | Ghost Slicer Execution Linkage | A.1 |
| A.3 | BLACK SWAN Override | A.1 |
| B.1 | Collateral Velocity (C_v) | Independent |
| B.2 | Dynamic Margin Adjustment | B.1 |
| B.3 | Sovereign Flywheel (recursive) | B.1, B.2 |
| B.4 | 48–72hr Temporal Alpha (Moat) | B.3 |
| C.1 | TRS Convergence Harvesting | A.1, B.3 |
| C.2 | Self-Funding / Decoupling | B.3, C.1 |

---

## Implementation Reference

The SVE Engine is implemented in `operationalDashboard.js`:

| Function | Claim | Description |
|----------|-------|-------------|
| `computeSevd()` | A.1 | S_evd signal from energy + vol term structures |
| `computeCollateralVelocity()` | B.1–B.2 | C_v scalar from SOFR/M2 |
| `buildSovereignFlywheel()` | B.3–B.4 | Recursive 4-stage flywheel state |
| `buildSundayNightSentinel()` | B.4 | 48hr early warning via Sunday energy gap |
| `buildHarvestPlan()` | C.1 | War Tax → TRS capacity |
| `buildSystemicAlpha()` | C.2 | P1 Decoupling threshold |
| `getSliceLimit()` + `getExecutionAlgo()` | A.2 | Ghost Slicer ADV caps |

---

*SVE Engine v2.9 — Patent Filing Package*
*Stark Capital Research Division — March 2026*
