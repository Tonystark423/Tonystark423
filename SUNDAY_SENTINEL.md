# Sunday Night Sentinel — v2.9
## Autonomous Overnight Monitor · Energy Arbitrage Engine

---

## Thesis: The Energy Arbitrage

The structural asymmetry powering this engine:

| Side | Player | Energy Posture | VIX Spike Effect |
|------|--------|---------------|-----------------|
| Cloud AI | MSFT / GOOG | Energy **Dependent** — 5GW data centers | Margin compression → sell-off → GEX crashes |
| Edge AI | AAPL | Energy **Sovereign** — on-device, buybacks | Sentiment gap only → mean-reverts 3–5 sessions |

**When oil spikes on Sunday night:**
1. Cloud AI (energy junkies) sell off → VIX gaps up
2. VIX gap-up → Harvest Engine fires → **War Tax collected**
3. AAPL gaps down (risk-off only, not structural) → **call premiums cheapen**
4. War Tax > Call Discount → **net-positive: you buy optionality at a discount, funded by oil fear**

> The Sentinel removes human emotion. It doesn't read the news. It reads the **VIX-to-Energy Delta**.

---

## Trigger Conditions

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Brent Crude Sunday close | ≥ $120/bbl | `ALERT` — Cloud AI margin tax active |
| VIX Futures Sunday | > 30 | Upgrade to `DEFENSIVE LOCK` posture |
| Brent gap from Friday | > $5 | `WATCH` |
| All else | — | `STANDBY` |

---

## Posture Decision (Simple API)

```
IF (Brent > $120 OR VIX Futures > 30):
  posture = "🚨 DEFENSIVE LOCK"
  vixAction  = "Increase Harvest to 25%"
  aaplAction = "Pause new Gamma entry; hold current orchard."
ELSE:
  posture = "🛡️ SHIELD ACTIVE"
  vixAction  = "Maintain 15% Recycle"
  aaplAction = "Resume v2.7 Slicer at Monday Open."
```

---

## Energy Arbitrage Index (EAI)

**Cell EAI (LENS Tab)**

```
=War_Tax / Call_Discount_Value
```

| EAI Value | Interpretation | Action |
|-----------|---------------|--------|
| > 2.0 | STRONG ARBITRAGE — oil spike highly net-positive | Add full new tranche at open |
| 1.0 – 2.0 | POSITIVE ARBITRAGE — War Tax covers discount | Add partial tranche |
| < 1.0 | WATCH — build harvest before adding Gamma | Hold; accumulate |
| N/A | No existing tranches (discount = 0) | Estimate from IV model |

---

## War Tax Formula

```
Step 1: VIX Monday PnL  = vixPosition × vixGapPct
Step 2: War Tax         = VIX Monday PnL × harvestRate (15%)
Step 3: New Contracts   = floor(War Tax / (premiumMonday × 100))
Step 4: Net Advantage   = War Tax − (New Contracts × premiumMonday × 100)
```

**VIX Gap Projection from Oil:**
```
vixGapFromOil  = (brentGap / $10) × oilSensitivity (1.5 VIX pts per $10)
vixProjected   = MAX(vixFuturesSunday, vixFriday + vixGapFromOil)
```

---

## AAPL Gap Model

AAPL is energy-sovereign — gaps are **sentiment only**, not structural.

```
aaplGapPct = IF(brentSunday >= 120):
  base  = -2.0%
  extra = MAX(0, (vixProjected - 27) / 27 × -2%)   ← amplifier for extreme VIX
  total = base + extra
ELSE:
  0%  ← below alert threshold, no gap modeled
```

**Call Premium Discount:**
```
premiumDiscountPct = MAX(0, -aaplGapPct × 1.5)   ← options amplify spot moves 1.5×
premiumMonday      = avgPremiumFriday × (1 - premiumDiscountPct)
```

---

## Regime Projection (Monday Open)

| VIX Projected | Oil Sunday | Monday Regime | Risk Level | Action |
|--------------|-----------|--------------|-----------|--------|
| > 35 | any | BLACK SWAN | TERMINATE TRS | Halt TRS. Maximize VIX shield. |
| 27 – 35 | any | BLACK SWAN | STOP RECYCLING | No new TRS. Harvest at 25%. |
| 22 – 27 | > $115 | RECYCLE | ELEVATED | Deploy VST/GEV/CCJ. Add AAPL contracts. |
| 22 – 27 | ≤ $115 | SHIELD | CRITICAL | Accumulate harvest only. Wait for gate. |
| < 22 | any | SYMBIOSIS | NORMAL | Ghost Slicer full schedule. |

---

## LENS Tab Cell Formulas

### Sentinel Status
**Cell S1:**
```
=IF(OR(Brent>=120, VIX_Futures>30), "🚨 ALERT",
 IF(Brent_Gap>5, "👁️ WATCH", "✅ STANDBY"))
```

### Posture
**Cell S2:**
```
=IF(OR(Brent>=120, VIX_Futures>30),
  "🚨 DEFENSIVE LOCK — Harvest 25% / Hold Gamma",
  "🛡️ SHIELD ACTIVE — Recycle 15% / Resume Slicer")
```

### War Tax
**Cell S3:**
```
=VIX_Position × ((MAX(VIX_Futures, VIX_Friday + (Brent_Gap/10×1.5)) - VIX_Friday) / VIX_Friday) × 0.15
```

### EAI
**Cell S4:**
```
=IF(S6>0, S3/S6, "N/A")
```

### AAPL Gap %
**Cell S5:**
```
=IF(Brent>=120, -0.02 + MAX(0,(MAX(VIX_Futures,VIX_Friday+(Brent_Gap/10×1.5))-27)/27×-0.02), 0)
```

### Call Discount Value
**Cell S6:**
```
=Total_Call_Shares × (Avg_Premium_Friday × MIN(MAX(0,-S5×1.5), 1))
```

### New Contracts Affordable
**Cell S7:**
```
=IF(AND(S3>0, Premium_Monday>0), FLOOR(S3/(Premium_Monday×100), 1), 0)
```

---

## Monday Brief Template

**RECYCLE Regime:**
```
1. War Tax: ${warTax} harvest available from VIX gap-up.
2. AAPL opens ~${aaplMonday} ({aaplGapPct}%). Calls {premiumDiscountPct}% cheaper than Friday.
3. Add {newContracts} new AAPL contracts at discounted premium (${premiumMonday}/share).
4. Deploy 78-bin slicer from 9:30 AM. Phase 1 equity: VST/GEV/CCJ first.
5. Energy Arbitrage Index: {eai}× — oil spike is net-positive for the overlay.
```

**SHIELD Regime:**
```
1. War Tax: ${warTax} available. Hold until regime shifts to RECYCLE.
2. Accumulate harvest. No new AAPL calls or TRS until VIX confirms direction.
3. AAPL at ${aaplMonday} — calls available at {premiumDiscountPct}% discount when gate opens.
```

**BLACK SWAN Regime:**
```
1. HALT all TRS seeding at open. Route harvest to VIX shield top-up.
2. DO NOT open new AAPL calls. Defend existing tranches only.
3. VIX expected at {vixProjected} — harvest ${warTax} available.
```

---

## Conditional Formatting (LENS Tab)

| Cell | Condition | Color |
|------|-----------|-------|
| S1 | contains "ALERT" | Red `#FF0000` |
| S1 | contains "WATCH" | Orange `#FF6600` |
| S1 | contains "STANDBY" | Green `#00AA44` |
| S2 | contains "DEFENSIVE" | Dark Red `#880000` |
| S2 | contains "SHIELD" | Yellow `#FFCC00` |
| S4 (EAI) | > 2.0 | Green `#00AA44` |
| S4 (EAI) | 1.0–2.0 | Yellow `#FFCC00` |
| S4 (EAI) | < 1.0 | Orange `#FF6600` |

---

## Integration with buildDashboard()

Pass Sunday-evening inputs to activate the Sentinel layer:

```javascript
const dashboard = buildDashboard({
  // ... standard Friday inputs ...
  vix:              25.4,   // Friday close
  oil:              118.0,  // Friday close
  aaplPrice:        210.0,  // Friday close

  // Sunday Night Sentinel inputs:
  brentSunday:      124.5,  // Sunday Brent futures
  brentFriday:      118.0,  // Friday close (same as oil above)
  vixFuturesSunday: 27.8,   // Sunday VIX futures
});

// Access:
const { sundayNightSentinel } = dashboard;
console.log(sundayNightSentinel.posture.label);          // "🚨 DEFENSIVE LOCK"
console.log(sundayNightSentinel.energyArbitrage.eai);   // e.g. 2.14
console.log(sundayNightSentinel.mondayBrief);            // action list
```

---

## Example: Iran Strait Closure Scenario

**Inputs:** Brent Sunday $131, VIX Futures 29.5, AAPL Friday $210, VIX Friday 25.4

| Output | Value |
|--------|-------|
| Brent Gap | +$13 (+11.0%) |
| VIX Projected | 27.35 |
| War Tax (15% harvest) | ~$310,000 |
| AAPL Monday gap | -2.7% (~$204.33) |
| Call premium discount | 4.1% cheaper |
| New contracts affordable | ~38 |
| EAI | ~1.87× |
| Posture | 🚨 DEFENSIVE LOCK |
| Monday Regime | RECYCLE |

> Oil fear generates more VIX harvest than it costs in AAPL call premium.
> The orchard grows while the Redwoods burn.

---

## Version History

| Version | Change |
|---------|--------|
| v2.9 | Full Sunday Night Sentinel — EAI, War Tax, posture API, Monday Brief |
| v2.7 | Apple Call Overlay — 78-bin slicer, Gamma Squeeze |
| v2.2 | Weekend Shield Report |
| v2.0 | Ghost Slicer, Harvest Engine, MOC Protector |
| v1.0 | Core Shield/Recycle/Symbiosis engine |
