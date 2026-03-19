/**
 * OPERATIONAL DASHBOARD ENGINE v1.0
 * $1B Live Alpha vs Risk — Unified Shield / Recycle / Execution / TRS
 *
 * Entry point: buildDashboard(inputs)
 * Returns:     { engineState, executionPlan, trsTracker, alphaRisk, alerts }
 */

// ─────────────────────────────────────────────────────────────────────────────
// 1. CONSTANTS
// ─────────────────────────────────────────────────────────────────────────────

// At $1B: slicer cap is 5% of ADV (Guardian invisibility threshold)
// At $100M: slicer cap drops to 3% of ADV ("Ghost" mode — even stealthier)
const ADV_CAP_BY_SCALE = {
  "1B":   0.05,
  "100M": 0.03,
};

function getScale(aum) {
  return aum >= 500_000_000 ? "1B" : "100M";
}

function getAdvCap(aum) {
  return ADV_CAP_BY_SCALE[getScale(aum)];
}

const RECYCLE_BASKET = [
  // Phase 1 — Primary recycle targets (deploy first on RECYCLE trigger)
  // VST, GEV, CCJ: direct energy/power beneficiaries — profit from the same oil spike
  // that triggers RECYCLE, so the hedge and the deployment are correlated in the same direction
  { ticker: "VST",   company: "Vistra Corp",        weight: 0.08, notional: 80_000_000,  phase: 1 },
  { ticker: "GEV",   company: "GE Vernova",          weight: 0.07, notional: 70_000_000,  phase: 1 },
  { ticker: "CCJ",   company: "Cameco Corp",         weight: 0.05, notional: 50_000_000,  phase: 1 },
  // Phase 2 — Tier 1: Very Low energy sensitivity
  { ticker: "MSFT",  company: "Microsoft",           weight: 0.16, notional: 160_000_000, phase: 2 },
  { ticker: "V",     company: "Visa",                weight: 0.14, notional: 140_000_000, phase: 2 },
  { ticker: "MA",    company: "Mastercard",          weight: 0.14, notional: 140_000_000, phase: 2 },
  { ticker: "ACN",   company: "Accenture",           weight: 0.11, notional: 110_000_000, phase: 2 },
  // Phase 2 — Tier 2: Low energy sensitivity
  { ticker: "UNH",   company: "UnitedHealth",        weight: 0.10, notional: 100_000_000, phase: 2 },
  { ticker: "JNJ",   company: "Johnson & Johnson",   weight: 0.10, notional: 100_000_000, phase: 2 },
  { ticker: "ABBV",  company: "AbbVie",              weight: 0.08, notional:  80_000_000, phase: 2 },
  { ticker: "PG",    company: "Procter & Gamble",    weight: 0.04, notional:  40_000_000, phase: 2 },
  { ticker: "COST",  company: "Costco",              weight: 0.04, notional:  40_000_000, phase: 2 },
  { ticker: "BRK.B", company: "Berkshire Hathaway",  weight: 0.02, notional:  20_000_000, phase: 2 },
];

// ─────────────────────────────────────────────────────────────────────────────
// HARVEST ENGINE  (VIX Premium → Margin → New TRS Exposure)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Calculates the "Volatility Tax" harvest and resulting TRS deployment capacity.
 *
 * Math (example at $100M, VIX +16.8%):
 *   vixPosition   = $20M
 *   dailyVixPnl   = $20M × 16.8% = $3.36M
 *   harvestAmount = $3.36M × 15% = $504,000   ← "Volatility Tax"
 *   marginRate    = 15%
 *   newExposure   = $504k / 15%  = $3.36M     ← new 493 notional via TRS
 *
 * Result: zero net cash outlay — profit self-funds margin for new TRS leg.
 */
function buildHarvestPlan(vixPosition, vixDailyReturnPct, harvestRate = 0.15, marginRate = 0.15) {
  const dailyVixPnl    = vixPosition * (vixDailyReturnPct / 100);
  const harvestAmount  = dailyVixPnl * harvestRate;
  const newTrsExposure = marginRate > 0 ? harvestAmount / marginRate : 0;
  const multiplier     = marginRate > 0 ? 1 / marginRate : 0;

  return {
    vixPosition,
    dailyVixPnl:    Math.round(dailyVixPnl),
    harvestRate,
    harvestAmount:  Math.round(harvestAmount),
    marginRate,
    newTrsExposure: Math.round(newTrsExposure),
    multiplier:     +multiplier.toFixed(2),
    note: `$${(harvestAmount / 1000).toFixed(0)}k harvest as ${(marginRate * 100).toFixed(0)}% margin → $${(newTrsExposure / 1_000_000).toFixed(2)}M new exposure`,
  };
}

// Slippage estimate in bps by execution algo
const SLIPPAGE_BPS = {
  "UNWIND NOW":         25,
  "HOLD":                0,
  "ICEBERG":            15,
  "TWAP":                8,
  "VWAP":                5,
  "DARK POOL":           2,
  "VWAP REBALANCE":      3,
};

// ─────────────────────────────────────────────────────────────────────────────
// 2. ENGINE STATE  (Shield / Recycle / Symbiosis — from ecosystemGuardianEngine)
// ─────────────────────────────────────────────────────────────────────────────

function getEngineState(vix, oil, gex, aum) {
  let mode, riskLevel, action, allocation;

  // Scaling: physical vs synthetic
  if (aum >= 1_000_000_000) {
    allocation = "70% Synthetic (TRS) / 30% Physical";
  } else if (aum >= 100_000_000) {
    allocation = "30% Synthetic / 70% Physical";
  } else {
    allocation = "100% Physical (Direct Equity)";
  }

  // Regime ladder
  if (vix > 27) {
    mode      = "BLACK SWAN";
    riskLevel = "BLACK SWAN";
    action    = "STOP RECYCLING. MAXIMIZE SHIELD TO FULL NOTIONAL.";
  } else if (vix > 25 && gex < 0) {
    mode      = "SHIELD";
    riskLevel = "CRITICAL";
    action    = "DO NOT SELL VIX. HOLD 493 FLOOR. DEALERS SHORT GAMMA.";
  } else if (vix > 25 && gex >= 0) {
    mode      = "HEDGE";
    riskLevel = "HIGH";
    action    = "TRIM SYNTHETIC LEGS. AWAIT GAMMA FLIP CONFIRMATION.";
  } else if (vix > 24 && oil > 115) {
    mode      = "RECYCLE";
    riskLevel = "ELEVATED";
    action    = "MOVE VIX PROFIT → VST / GEV (Phase 1), THEN TIER 1+2.";
  } else if (vix > 20) {
    mode      = "WATCH";
    riskLevel = "WARNING";
    action    = "MONITOR VIX EXPANSION. PREPARE SHIELD PARAMETERS.";
  } else {
    mode      = "SYMBIOSIS";
    riskLevel = "NORMAL";
    action    = "MONITOR 493 DECOUPLING FROM MAG 7.";
  }

  return { mode, riskLevel, action, allocation };
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. EXECUTION SLICER  (per-name algo + sizing based on regime × ADV%)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Ghost Slicer — per-name execution limit.
 * G10 formula equivalent: =MIN(Required_Notional, Daily_Volume_493 × advCap)
 * At $100M: advCap = 3% (ghost mode)
 * At $1B:   advCap = 5% (standard guardian invisibility)
 */
function getSliceLimit(notional, adv, aum) {
  const cap = getAdvCap(aum);
  return Math.min(notional, adv * cap);
}

function getExecutionAlgo(advRatio, riskLevel, advCap) {
  if (riskLevel === "BLACK SWAN") return "UNWIND NOW";
  if (riskLevel === "CRITICAL" || riskLevel === "HIGH") return "HOLD";
  if (riskLevel === "ELEVATED") {
    // Thresholds are relative to advCap — at 3% cap, start iceberg earlier
    if (advRatio > advCap * 4) return "ICEBERG";   // > 4× cap → full stealth
    if (advRatio > advCap * 2) return "TWAP";      // 2–4× cap → time-spread
    if (advRatio > advCap)     return "VWAP";      // 1–2× cap → volume-timed
    return "DARK POOL";                            // under cap → immediate
  }
  // WARNING or NORMAL: rebalance-only, low urgency
  return "VWAP REBALANCE";
}

function getExecutionPlanForName(name, adv, engineState, aum) {
  const { notional, ticker, phase } = name;
  const advCap   = getAdvCap(aum);
  const advRatio = adv > 0 ? notional / adv : Infinity;
  const algo     = getExecutionAlgo(advRatio, engineState.riskLevel, advCap);
  // Ghost Slicer: cap each order to MIN(required notional, ADV × cap)
  const allowedNotional = getSliceLimit(notional, adv, aum);

  // Slice size = one child order, capped by Ghost Slicer limit
  const sliceSize = {
    "UNWIND NOW":       allowedNotional,
    "HOLD":             0,
    "ICEBERG":          allowedNotional * 0.05,
    "TWAP":             allowedNotional / 12,
    "VWAP":             allowedNotional / 4,
    "DARK POOL":        allowedNotional,
    "VWAP REBALANCE":   allowedNotional / 4,
  }[algo] ?? 0;

  // Time window in minutes for full execution
  const timeWindowMin = {
    "UNWIND NOW":       0,
    "HOLD":             0,
    "ICEBERG":          240,
    "TWAP":             120,
    "VWAP":             60,
    "DARK POOL":        15,
    "VWAP REBALANCE":   60,
  }[algo] ?? 0;

  // Routing: > advCap of ADV must go via TRS desk, else dark pool
  const route = advRatio > advCap ? "TRS DESK" : "DARK POOL";

  const urgency = {
    "UNWIND NOW":       "CRITICAL — Accept Slippage",
    "HOLD":             "BLOCKED — Shield Active",
    "ICEBERG":          "STEALTH — 4hr Window",
    "TWAP":             "MODERATE — 2hr Window",
    "VWAP":             "VOLUME-TIMED — 1hr",
    "DARK POOL":        "IMMEDIATE via Dark Pool",
    "VWAP REBALANCE":   "LOW — Rebalance Only",
  }[algo] ?? "";

  const slippageBps  = SLIPPAGE_BPS[algo] ?? 0;
  const slippageCost = allowedNotional * (slippageBps / 10_000);

  // Phase 1 names activate first; Phase 2 only after Phase 1 is sized
  const deployPriority = phase === 1 ? "DEPLOY FIRST" : "DEPLOY AFTER PHASE 1";

  return {
    ticker,
    phase,
    deployPriority,
    notional,
    allowedNotional: Math.round(allowedNotional),  // ghost slicer cap
    adv,
    advRatioPct:   +(advRatio * 100).toFixed(2),
    advCapPct:     +(advCap   * 100).toFixed(0),
    algo,
    sliceSize:     Math.round(sliceSize),
    timeWindowMin,
    route,
    urgency,
    slippageBps,
    slippageCost:  Math.round(slippageCost),
  };
}

function buildExecutionPlan(advByTicker, engineState, aum) {
  return RECYCLE_BASKET.map(name => {
    const adv = advByTicker[name.ticker] ?? 0;
    return getExecutionPlanForName(name, adv, engineState, aum);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. TRS DEPLOYMENT TRACKER  (per-name open leg summary)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * trsLegs: array of { ticker, openNotional, entryPrice, currentPrice, daysOpen }
 * trsSpreadBps: prime broker SOFR spread in basis points
 */
function buildTrsTracker(trsLegs, trsSpreadBps) {
  let totalNotional   = 0;
  let totalUnrealised = 0;
  let totalFinancing  = 0;

  const legs = trsLegs.map(leg => {
    const { ticker, openNotional, entryPrice, currentPrice, daysOpen } = leg;
    const unrealisedPnl  = openNotional * ((currentPrice - entryPrice) / entryPrice);
    const financingCost  = openNotional * (trsSpreadBps / 10_000) * (daysOpen / 365);
    const netPnl         = unrealisedPnl - financingCost;
    const netPnlPct      = openNotional > 0 ? (netPnl / openNotional) * 100 : 0;

    totalNotional   += openNotional;
    totalUnrealised += unrealisedPnl;
    totalFinancing  += financingCost;

    return {
      ticker,
      openNotional,
      unrealisedPnl:  Math.round(unrealisedPnl),
      financingCost:  Math.round(financingCost),
      netPnl:         Math.round(netPnl),
      netPnlPct:      +netPnlPct.toFixed(2),
      status: netPnl >= 0 ? "POSITIVE" : "UNDERWATER",
    };
  });

  const totalNetPnl = totalUnrealised - totalFinancing;

  return {
    legs,
    totals: {
      openNotional:   Math.round(totalNotional),
      unrealisedPnl:  Math.round(totalUnrealised),
      financingCost:  Math.round(totalFinancing),
      netPnl:         Math.round(totalNetPnl),
      netPnlPct:      totalNotional > 0
                        ? +((totalNetPnl / totalNotional) * 100).toFixed(2)
                        : 0,
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. ALPHA vs RISK PANEL
// ─────────────────────────────────────────────────────────────────────────────

/**
 * alphaInputs:
 *   vixPremiumIn    – cumulative VIX put/call premium collected ($)
 *   basketCost      – total capital deployed into 493 basket ($)
 *   basketValue     – current mark-to-market value of basket ($)
 *   trsNetPnl       – from TRS tracker totals.netPnl ($)
 *   totalSlippage   – sum of slippageCost across executionPlan ($)
 *   aum             – total AUM ($)
 *   holdingDays     – days since first deployment
 */
function buildAlphaRiskPanel(alphaInputs) {
  const {
    vixPremiumIn,
    basketCost,
    basketValue,
    trsNetPnl,
    totalSlippage,
    aum,
    holdingDays,
  } = alphaInputs;

  // Alpha created: VIX premium harvested + basket appreciation + TRS gains
  const basketAppreciation = Math.max(0, basketValue - basketCost);
  const alphaCreated       = vixPremiumIn + basketAppreciation + Math.max(0, trsNetPnl);

  // Risk consumed: unrealised losses + slippage + financing already paid
  const basketDecline  = Math.max(0, basketCost - basketValue);
  const trsLoss        = Math.max(0, -trsNetPnl);
  const riskConsumed   = basketDecline + trsLoss + totalSlippage;

  const netAlpha         = alphaCreated - riskConsumed;
  const alphaEfficiency  = riskConsumed > 0 ? netAlpha / riskConsumed : null;
  const annualisedYield  = holdingDays > 0 && aum > 0
                             ? (netAlpha / aum) * (365 / holdingDays) * 100
                             : null;

  let status;
  if (alphaEfficiency === null)    status = "NO RISK CONSUMED";
  else if (alphaEfficiency > 2.0)  status = "COMPOUNDING";
  else if (alphaEfficiency > 1.0)  status = "POSITIVE";
  else if (alphaEfficiency > 0)    status = "MARGINAL";
  else                             status = "UNDERWATER";

  return {
    alphaCreated:      Math.round(alphaCreated),
    riskConsumed:      Math.round(riskConsumed),
    netAlpha:          Math.round(netAlpha),
    alphaEfficiency:   alphaEfficiency !== null ? +alphaEfficiency.toFixed(2) : null,
    annualisedYieldPct: annualisedYield !== null ? +annualisedYield.toFixed(2) : null,
    breakdown: {
      vixPremiumIn:       Math.round(vixPremiumIn),
      basketAppreciation: Math.round(basketAppreciation),
      trsNetPnl:          Math.round(trsNetPnl),
      basketDecline:      Math.round(basketDecline),
      trsLoss:            Math.round(trsLoss),
      totalSlippage:      Math.round(totalSlippage),
    },
    status,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. ALERTS
// ─────────────────────────────────────────────────────────────────────────────

function buildAlerts(vix, gex, engineState, alphaRisk, trsTracker) {
  const alerts = [];

  if (vix > 27) {
    alerts.push({
      level: "BLACK SWAN",
      message: "VIX > 27. STOP ALL RECYCLING. MAXIMIZE VIX SHIELD TO FULL NOTIONAL IMMEDIATELY.",
    });
  }

  if (vix > 35 || gex < -500_000_000) {
    alerts.push({
      level: "TERMINATE TRS",
      message: `TERMINATE TRS: ${vix > 35 ? "VIX > 35" : "GEX < -$500M"}. UNWIND ALL LEGS. RETURN TO SHIELD.`,
    });
  }

  if (engineState.riskLevel === "ELEVATED") {
    alerts.push({
      level: "RECYCLE",
      message: "RECYCLE TRIGGERED. DEPLOY VIX PROFIT → VST / GEV FIRST (Phase 1), THEN TIER 1+2.",
    });
  }

  if (alphaRisk.status === "UNDERWATER") {
    alerts.push({
      level: "ALPHA WARNING",
      message: `Alpha efficiency ${alphaRisk.alphaEfficiency}x. Net alpha negative. Review basket vs VIX hedge sizing.`,
    });
  }

  if (trsTracker.totals.netPnlPct < -2) {
    alerts.push({
      level: "TRS DRAWDOWN",
      message: `TRS book down ${Math.abs(trsTracker.totals.netPnlPct)}% net of financing. Check termination events.`,
    });
  }

  return alerts.length > 0 ? alerts : [{ level: "OK", message: "No active alerts. System nominal." }];
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. MAIN ENTRY POINT
// ─────────────────────────────────────────────────────────────────────────────

/**
 * inputs: {
 *   vix, oil, gex, aum,
 *   advByTicker:        { VST: 120_000_000, GEV: 85_000_000, CCJ: 60_000_000, MSFT: 3_500_000_000, ... },
 *   trsLegs:            [ { ticker, openNotional, entryPrice, currentPrice, daysOpen }, ... ],
 *   trsSpreadBps:       25,
 *   vixPremiumIn:       18_000_000,
 *   basketCost:         600_000_000,
 *   basketValue:        638_000_000,
 *   holdingDays:        14,
 *   // harvest inputs (optional — used for $100M Volatility Tax math)
 *   vixPosition:        20_000_000,   // dollar size of VIX long
 *   vixDailyReturnPct:  16.8,         // today's VIX % move
 *   harvestRate:        0.15,         // 15% of daily VIX PnL → margin
 *   marginRate:         0.15,         // 15% margin → 6.67x TRS multiplier
 * }
 */
function buildDashboard(inputs) {
  const {
    vix, oil, gex, aum,
    advByTicker,
    trsLegs,
    trsSpreadBps,
    vixPremiumIn,
    basketCost,
    basketValue,
    holdingDays,
    vixPosition       = 0,
    vixDailyReturnPct = 0,
    harvestRate       = 0.15,
    marginRate        = 0.15,
  } = inputs;

  // Layer 1: engine state
  const engineState = getEngineState(vix, oil, gex, aum);

  // Layer 2: execution plan (per name) — AUM-aware slicer (3% at $100M, 5% at $1B)
  const executionPlan = buildExecutionPlan(advByTicker, engineState, aum);

  // Total slippage estimate across all names
  const totalSlippage = executionPlan.reduce((sum, n) => sum + n.slippageCost, 0);

  // Layer 3: Harvest plan (Volatility Tax → new TRS capacity)
  const harvestPlan = buildHarvestPlan(vixPosition, vixDailyReturnPct, harvestRate, marginRate);

  // Layer 4: TRS tracker
  const trsTracker = buildTrsTracker(trsLegs, trsSpreadBps);

  // Layer 5: alpha vs risk
  const alphaRisk = buildAlphaRiskPanel({
    vixPremiumIn,
    basketCost,
    basketValue,
    trsNetPnl:    trsTracker.totals.netPnl,
    totalSlippage,
    aum,
    holdingDays,
  });

  // Layer 6: alerts
  const alerts = buildAlerts(vix, gex, engineState, alphaRisk, trsTracker);

  return {
    scale: getScale(aum),         // "100M" or "1B"
    advCap: getAdvCap(aum),       // 0.03 or 0.05 (ghost slicer threshold)
    engineState,
    harvestPlan,
    executionPlan,
    trsTracker,
    alphaRisk,
    alerts,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 8. EXAMPLE RUN (remove or gate behind a flag in production)
// ─────────────────────────────────────────────────────────────────────────────

if (typeof process !== "undefined" && process.argv[1] === __filename) {
  // ── Example A: $100M scale — VIX spike +16.8% (Ghost Slicer at 3% ADV) ──
  const example100M = buildDashboard({
    vix:              25.4,
    oil:              118.0,
    gex:              -120_000_000,
    aum:              100_000_000,
    // Harvest: $20M VIX long, +16.8% today
    vixPosition:       20_000_000,
    vixDailyReturnPct: 16.8,
    harvestRate:        0.15,
    marginRate:         0.15,
    advByTicker: {
      VST:    60_000_000,
      GEV:    42_000_000,
      CCJ:    30_000_000,
      MSFT: 350_000_000,
      V:    120_000_000,
      MA:   110_000_000,
      ACN:   24_000_000,
      UNH:   52_000_000,
      JNJ:   40_000_000,
      ABBV:  36_000_000,
      PG:    30_000_000,
      COST:  28_000_000,
      "BRK.B": 25_000_000,
    },
    trsLegs: [
      { ticker: "VST", openNotional: 8_000_000, entryPrice: 100, currentPrice: 107.4, daysOpen: 14 },
      { ticker: "GEV", openNotional: 7_000_000, entryPrice: 100, currentPrice: 104.1, daysOpen: 14 },
      { ticker: "CCJ", openNotional: 5_000_000, entryPrice: 100, currentPrice: 109.2, daysOpen: 14 },
    ],
    trsSpreadBps: 25,
    vixPremiumIn:  1_800_000,
    basketCost:   60_000_000,
    basketValue:  63_800_000,
    holdingDays:  14,
  });

  console.log("=== $100M GHOST MODE ===");
  console.log(JSON.stringify(example100M, null, 2));

  // ── Example B: $1B scale — same scenario (Guardian mode at 5% ADV) ──
  const example1B = buildDashboard({
    vix:              25.4,
    oil:              118.0,
    gex:              -120_000_000,
    aum:           1_000_000_000,
    vixPosition:     200_000_000,
    vixDailyReturnPct: 16.8,
    harvestRate:        0.15,
    marginRate:         0.15,
    advByTicker: {
      VST:    120_000_000,
      GEV:     85_000_000,
      CCJ:     60_000_000,
      MSFT: 3_500_000_000,
      V:      900_000_000,
      MA:     850_000_000,
      ACN:    180_000_000,
      UNH:    400_000_000,
      JNJ:    320_000_000,
      ABBV:   280_000_000,
      PG:     240_000_000,
      COST:   220_000_000,
      "BRK.B": 200_000_000,
    },
    trsLegs: [
      { ticker: "VST",  openNotional:  80_000_000, entryPrice: 100, currentPrice: 107.4, daysOpen: 14 },
      { ticker: "GEV",  openNotional:  70_000_000, entryPrice: 100, currentPrice: 104.1, daysOpen: 14 },
      { ticker: "CCJ",  openNotional:  50_000_000, entryPrice: 100, currentPrice: 109.2, daysOpen: 14 },
      { ticker: "MSFT", openNotional: 160_000_000, entryPrice: 100, currentPrice: 102.8, daysOpen: 14 },
    ],
    trsSpreadBps: 25,
    vixPremiumIn:  18_000_000,
    basketCost:   600_000_000,
    basketValue:  638_000_000,
    holdingDays:   14,
  });

  console.log("\n=== $1B GUARDIAN MODE ===");
  console.log(JSON.stringify(example1B, null, 2));
}
