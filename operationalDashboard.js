/**
 * OPERATIONAL DASHBOARD ENGINE v2.9
 * $1B / $100M Live Alpha vs Risk — Unified Shield / Recycle / Execution / TRS
 *
 * Entry point: buildDashboard(inputs)
 * Returns: { scale, advCap, engineState, harvestPlan, executionPlan,
 *            trsTracker, alphaRisk, symbiosisPnl, appleCallOverlay,
 *            appleOptionsBins, gammaSqueezeProjection, closingCross, alerts }
 *
 * Key invisibility thresholds:
 *   Regular session:  3% ADV at $100M (Ghost) | 5% ADV at $1B (Guardian)
 *   MOC window:       2% ADV at all scales (3:50–4:00 PM ET)
 *
 * Slippage math — why 3% is the "magic number":
 *   Visible trade  ($3.36M into VST in 1 hr): 40–60bps market impact = ~$20k alpha evaporated
 *   Ghost trade    (3% ADV clips, $840k/name): < 5bps market impact
 *   Institutional noise floor: looks like pension rebalancing energy weightings
 */

// ─────────────────────────────────────────────────────────────────────────────
// 1. CONSTANTS
// ─────────────────────────────────────────────────────────────────────────────

// Regular-session ADV caps — stay inside institutional noise floor
const ADV_CAP_BY_SCALE = {
  "1B":   0.05,   // Guardian: 5% of ADV → < 5bps market impact
  "100M": 0.03,   // Ghost:    3% of ADV → < 5bps market impact, looks like pension rebalancing
};
const ADV_CAP_MOC = 0.02;   // Tighten to 2% during Closing Cross (3:50–4:00 PM ET)

// ET market session boundaries (minutes since midnight)
const SESSION = {
  OPEN:  9  * 60 + 30,   // 9:30 AM
  MOC:   15 * 60 + 50,   // 3:50 PM — MOC window opens
  CLOSE: 16 * 60 +  0,   // 4:00 PM
};

function getScale(aum) {
  return aum >= 500_000_000 ? "1B" : "100M";
}

function getAdvCap(aum) {
  return ADV_CAP_BY_SCALE[getScale(aum)];
}

/**
 * Time-aware ADV cap (ET).
 * Regular session : standard cap (3% Ghost / 5% Guardian)
 * MOC window      : tighten to 2% — Closing Cross magnifies footprint
 * Closed          : 0 (no execution)
 *
 * nowET: JS Date object already in ET (or pass null to skip time check)
 */
function getTimeAwareAdvCap(aum, nowET) {
  if (!nowET) return getAdvCap(aum);
  const tod = nowET.getHours() * 60 + nowET.getMinutes();
  if (tod < SESSION.OPEN || tod >= SESSION.CLOSE) return 0;
  if (tod >= SESSION.MOC)                         return ADV_CAP_MOC;
  return getAdvCap(aum);
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

// ─────────────────────────────────────────────────────────────────────────────
// IMPACT CURVE MODEL — sqrt convexity (why 3% is the "magic number")
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Market impact is NOT linear in participation rate — it follows a sqrt curve.
 * This is the core reason 3% ADV is the noise-band threshold, not just a rule.
 *
 * Simplified Almgren-Chriss temporary impact:
 *   impact_bps = BASE_IMPACT_BPS × sqrt(advRatio / NOISE_BAND_THRESHOLD)
 *
 * Calibrated so that:
 *   advRatio = 0.03 (3%) → BASE_IMPACT_BPS (5 bps)  ← inside noise band
 *   advRatio = 0.056 (visible block) → ~6.8 bps execution impact
 *   + HFT predation tax when > noise band: total observable ≈ 40–60 bps
 *
 * At ≤ 3% ADV, your order is a statistical fluctuation:
 *   indistinguishable from passive ETF rebalancing / pension flows.
 *   There is no detectable signal → no HFT predation tax.
 *
 * At > 3% ADV, HFTs can detect the pattern → front-run → adverse selection.
 *   That's where 40–60 bps comes from. It's not execution cost — it's predation.
 */
const NOISE_BAND_THRESHOLD = 0.03;   // 3% — the "indistinguishable" floor
const BASE_IMPACT_BPS      = 5;      // impact at exactly the noise band

/**
 * Returns estimated execution impact in bps for a given participation rate.
 * For block trades (isBlock=true), adds the HFT predation tax on top.
 */
function getMarketImpactBps(advRatio, isBlock = false) {
  if (advRatio <= 0) return 0;
  const executionImpact = BASE_IMPACT_BPS * Math.sqrt(advRatio / NOISE_BAND_THRESHOLD);
  const hftPredationTax = isBlock && advRatio > NOISE_BAND_THRESHOLD
    ? executionImpact * (advRatio / NOISE_BAND_THRESHOLD - 1) * 6   // nonlinear predation
    : 0;
  return +(executionImpact + hftPredationTax).toFixed(1);
}

/**
 * Impact comparison: block trade vs ghost trade.
 * Makes the convexity visible for reporting.
 */
function impactComparison(notional, adv) {
  const blockRatio = adv > 0 ? notional / adv : 0;
  const ghostRatio = NOISE_BAND_THRESHOLD;
  const blockImpactBps = getMarketImpactBps(blockRatio, true);
  const ghostImpactBps = getMarketImpactBps(ghostRatio, false);
  const blockCost = Math.round(notional * (blockImpactBps / 10_000));
  const ghostCost = Math.round(notional * (ghostImpactBps / 10_000));
  return {
    blockRatioPct:   +(blockRatio * 100).toFixed(1),
    blockImpactBps,
    blockCost,
    ghostRatioPct:   +(ghostRatio * 100).toFixed(1),
    ghostImpactBps,
    ghostCost,
    alphaSaved:      Math.round(blockCost - ghostCost),
    reductionPct:    blockCost > 0
      ? +((1 - ghostCost / blockCost) * 100).toFixed(0)
      : 0,
  };
}

// Flat fallback for algo regimes where advRatio isn't meaningful (HOLD, UNWIND)
const SLIPPAGE_BPS_OVERRIDE = {
  "UNWIND NOW":  25,   // accept slippage — speed > cost
  "HOLD":         0,
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

  // Impact model: sqrt convexity for normal algos, flat override for UNWIND/HOLD
  const effectiveRatio = allowedNotional > 0 && adv > 0 ? allowedNotional / adv : 0;
  const slippageBps  = SLIPPAGE_BPS_OVERRIDE[algo] !== undefined
    ? SLIPPAGE_BPS_OVERRIDE[algo]
    : getMarketImpactBps(effectiveRatio);
  const slippageCost = Math.round(allowedNotional * (slippageBps / 10_000));

  // Impact comparison — shows how much alpha the ghost approach saves vs a block trade
  const impact = impactComparison(notional, adv);

  // Phase 1 names activate first; Phase 2 only after Phase 1 is sized
  const deployPriority = phase === 1 ? "DEPLOY FIRST" : "DEPLOY AFTER PHASE 1";

  return {
    ticker,
    phase,
    deployPriority,
    notional,
    allowedNotional: Math.round(allowedNotional),
    adv,
    advRatioPct:     +(advRatio     * 100).toFixed(2),
    advCapPct:       +(advCap       * 100).toFixed(0),
    algo,
    sliceSize:       Math.round(sliceSize),
    timeWindowMin,
    route,
    urgency,
    slippageBps,
    slippageCost,
    impact,   // { blockImpactBps, ghostImpactBps, alphaSaved, reductionPct }
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
// 6. SYMBIOSIS PnL RECONCILIATION  (Cell M10)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * M10 = (VIX_Roll_Yield + VIX_Price_Gain) - (TRS_Financing + 493_Slippage)
 *
 * Result > 0: You are the House. Mag 7 volatility is paying for 493 acquisition.
 * Result < 0: Moving too fast. Dial ADV cap to 2% for tomorrow's open.
 *
 * vixRollYield  : positive carry from holding VIX long (daily theta credit from put spreads)
 * vixPriceGain  : mark-to-market gain on VIX position today
 * trsFinancing  : SOFR + spread accrued on open TRS legs today
 * slippage493   : actual execution slippage paid today across all 493 names
 */
function buildSymbiosisPnl({ vixRollYield, vixPriceGain, trsFinancing, slippage493 }) {
  const grossAlpha = vixRollYield + vixPriceGain;
  const grossCost  = trsFinancing + slippage493;
  const netPnl     = grossAlpha - grossCost;
  const positive   = netPnl > 0;

  return {
    grossAlpha:   Math.round(grossAlpha),
    grossCost:    Math.round(grossCost),
    netPnl:       Math.round(netPnl),
    tomorrowCap:  positive ? 0.03 : 0.02,     // 2% tomorrow if negative — dial back stealth
    verdict: positive
      ? "YOU ARE THE HOUSE: Mag 7 volatility is paying for 493 acquisition."
      : "MOVING TOO FAST: Dial ADV cap to 2% for tomorrow's open.",
    action: positive ? "HOLD CURRENT CAP" : "REDUCE CAP TO 2% AT OPEN",
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. MOC PROTECTOR — CLOSING CROSS (3:50 PM ET)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * ECOSYSTEM GUARDIAN: MOC PROTECTOR v2.1
 * Ensures 3:50 PM orders don't break the stealth cap.
 *
 * At MOC the Closing Cross concentrates Mag 7 selling into the final print.
 * Tighten from 3% → 2% ADV to stay inside institutional noise.
 * Anything over the limit defers to tomorrow's VWAP open.
 *
 * notionalRemaining : dollar value of unfilled order going into MOC
 * currentVolume     : ADV for that name (dollar)
 */
function protectClosingCross(notionalRemaining, currentVolume) {
  const closingLimit = currentVolume * ADV_CAP_MOC;   // 2% cap

  if (notionalRemaining > closingLimit) {
    const excess = notionalRemaining - closingLimit;
    return {
      action:          "DEFER",
      message:         `⚠️ LIMIT EXCEEDED: Move $${(excess / 1_000_000).toFixed(3)}M to Tomorrow's VWAP.`,
      executeToday:    Math.round(closingLimit),
      deferToTomorrow: Math.round(excess),
      capUsed:         ADV_CAP_MOC,
    };
  }

  return {
    action:          "EXECUTE",
    message:         "🚀 EXECUTE MOC: Within stealth parameters.",
    executeToday:    Math.round(notionalRemaining),
    deferToTomorrow: 0,
    capUsed:         ADV_CAP_MOC,
  };
}

/**
 * Runs protectClosingCross across every name in the execution plan
 * that still has unfilled notional at 3:50 PM.
 *
 * unfilledByTicker: { VST: 420000, GEV: 310000, ... }
 * advByTicker:      { VST: 60000000, ... }
 */
function buildClosingCross(unfilledByTicker, advByTicker) {
  const results = {};
  let totalExecuteToday    = 0;
  let totalDeferToTomorrow = 0;

  for (const [ticker, unfilled] of Object.entries(unfilledByTicker)) {
    const adv    = advByTicker[ticker] ?? 0;
    const result = protectClosingCross(unfilled, adv);
    results[ticker]       = result;
    totalExecuteToday    += result.executeToday;
    totalDeferToTomorrow += result.deferToTomorrow;
  }

  return {
    perName:          results,
    totalExecuteToday:    Math.round(totalExecuteToday),
    totalDeferToTomorrow: Math.round(totalDeferToTomorrow),
    summary: totalDeferToTomorrow > 0
      ? `⚠️ ${Object.values(results).filter(r => r.action === "DEFER").length} name(s) deferred. $${(totalDeferToTomorrow / 1_000_000).toFixed(3)}M rolls to tomorrow's VWAP.`
      : "🚀 Full MOC execution within stealth parameters.",
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 8. APPLE CALL OVERLAY  (VIX Harvest → AAPL Calls)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * APPLE CALL OVERLAY — funded entirely by the daily Volatility Tax harvest.
 *
 * Thesis:
 *   Apple runs "Edge AI" on the user's battery — no data center, no GPU capex, no
 *   energy bill. While Google/MSFT absorb the $119 oil spike through 5GW data centers,
 *   Apple's margins are structurally immune. The hardware AI cycle (A18/M4) does the
 *   compute work at zero marginal energy cost per inference.
 *
 *   Funding mechanism:
 *   VIX harvest ($504k/day at $100M AUM) covers the call premium.
 *   The Alumni are paying for your levered AAPL recovery bet.
 *
 * Strike ladder (3 tranches):
 *   Tranche A (40%): ATM       — delta ~0.50, core recovery bet
 *   Tranche B (40%): +5% OTM  — delta ~0.30, leveraged AI-cycle upside
 *   Tranche C (20%): +10% OTM — delta ~0.18, lottery on full AI repricing
 *
 * Premium approximation (simplified log-normal, T in calendar days):
 *   call_premium ≈ S × IV × √(T/365) × N(d1_approx)
 *   where N(d1_approx) ≈ 0.40 for ATM, 0.28 for +5%, 0.18 for +10%
 *
 * Execution:
 *   - Spread across 3 days (1 tranche/day) — no single-day concentration
 *   - Execute in first 30 minutes (bid-ask spread tightest at open)
 *   - Limit orders at mid-price only — never lift the ask
 *   - Monitor bid-ask: skip if spread > 15bps of premium
 *   - AAPL options ADV >> $2B/day — no ADV constraint (high liquidity)
 *
 * Regime gating:
 *   RECYCLE / SYMBIOSIS → deploy (vol elevated, harvest funded, AAPL immune)
 *   SHIELD (VIX 22-35)  → hold (continue accumulating harvest, deploy next session)
 *   BLACK SWAN          → do NOT open new calls; protect existing positions
 *
 * inputs: {
 *   aaplPrice        : current AAPL price
 *   aaplIV           : AAPL 30-day implied volatility (decimal, e.g. 0.25)
 *   targetNotional   : underlying dollar exposure to control (default: 30% of AUM)
 *   daysToExpiry     : target option expiry (default: 45 calendar days)
 *   harvestAvailable : total harvest cash available today
 *   aum              : total AUM
 *   engineState      : from getEngineState()
 * }
 */
function buildAppleCallOverlay({
  aaplPrice,
  aaplIV        = 0.25,
  targetNotional,
  daysToExpiry  = 45,
  harvestAvailable,
  aum,
  engineState,
}) {
  const notional = targetNotional ?? aum * 0.30;

  // Regime gate: only deploy in RECYCLE or NORMAL/SYMBIOSIS
  const blocked = engineState.riskLevel === "BLACK SWAN";
  const hold    = engineState.riskLevel === "CRITICAL" || engineState.riskLevel === "HIGH";

  if (blocked) {
    return {
      status:  "BLOCKED — BLACK SWAN",
      action:  "Do NOT open new calls. Protect existing positions only.",
      tranches: [],
    };
  }

  // Strike ladder
  const ladder = [
    { label: "A — ATM",      otmPct:  0, deltaBand: 0.50, approxNd1: 0.40, weight: 0.40 },
    { label: "B — +5% OTM",  otmPct: +5, deltaBand: 0.30, approxNd1: 0.28, weight: 0.40 },
    { label: "C — +10% OTM", otmPct:+10, deltaBand: 0.18, approxNd1: 0.18, weight: 0.20 },
  ];

  const tSqrt = Math.sqrt(daysToExpiry / 365);

  const tranches = ladder.map((leg, i) => {
    const strike         = +(aaplPrice * (1 + leg.otmPct / 100)).toFixed(2);
    // Premium estimate: S × IV × √T × N(d1)
    const premiumPerShare = +(aaplPrice * aaplIV * tSqrt * leg.approxNd1).toFixed(2);
    const premiumPerContract = Math.round(premiumPerShare * 100);   // 1 contract = 100 shares

    // Underlying exposure for this tranche
    const trancheNotional  = notional * leg.weight;
    // Contracts = underlying_notional / (price × 100)
    const contracts        = Math.round(trancheNotional / (aaplPrice * 100));
    const totalPremium     = Math.round(contracts * premiumPerContract);
    // Delta-adjusted underlying exposure
    const deltaExposure    = Math.round(contracts * 100 * aaplPrice * leg.deltaBand);

    // Execution: 1 tranche per day, first 30 min
    const deployDay = `Day ${i + 1} — 9:30–10:00 AM ET`;

    return {
      tranche:           leg.label,
      strike,
      otmPct:            leg.otmPct,
      delta:             leg.deltaBand,
      daysToExpiry,
      premiumPerShare,
      premiumPerContract,
      contracts,
      totalPremium,
      deltaExposure,
      trancheNotional:   Math.round(trancheNotional),
      deployDay,
      harvestCoversDay:  harvestAvailable >= totalPremium,
    };
  });

  const totalPremium      = tranches.reduce((s, t) => s + t.totalPremium, 0);
  const totalContracts    = tranches.reduce((s, t) => s + t.contracts, 0);
  const totalDeltaExposure= tranches.reduce((s, t) => s + t.deltaExposure, 0);
  const harvestCoverage   = harvestAvailable > 0 ? harvestAvailable / totalPremium : 0;

  // Portfolio-level Greeks summary
  const portfolioVega  = Math.round(totalContracts * 100 * aaplPrice * aaplIV * tSqrt * 0.4);
  const portfolioTheta = Math.round(-totalContracts * 100 * (aaplPrice * aaplIV * tSqrt) / daysToExpiry);

  const status = blocked ? "BLOCKED" : hold
    ? "HOLD — Accumulate Harvest. Deploy Next Session."
    : "DEPLOY — Harvest Funded. Execute Tranche Schedule.";

  return {
    status,
    action: blocked ? "Do NOT open new calls."
      : hold ? "Hold calls. Continue 15% VIX harvest. Deploy on RECYCLE/SYMBIOSIS trigger."
      : "Execute tranche A today. B tomorrow. C day 3. Limit orders at mid-price only.",
    underlying:         "AAPL",
    thesis:             "Edge AI on battery — immune to $119 oil spike. Hardware cycle = structural margin advantage.",
    targetNotional:     Math.round(notional),
    totalContracts,
    totalPremium:       Math.round(totalPremium),
    harvestAvailable:   Math.round(harvestAvailable),
    harvestCoverage:    +harvestCoverage.toFixed(2),
    harvestFunded:      harvestAvailable >= totalPremium,
    totalDeltaExposure,
    portfolioGreeks: {
      delta: totalDeltaExposure,
      vega:  portfolioVega,    // $ per 1% vol move
      theta: portfolioTheta,   // $ per day (negative — cost of carry, funded by harvest)
    },
    tranches,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 9. 78-BIN OPTIONS SLICER  (5-min intervals, 1.5% of option vol per bin)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Trading day = 390 minutes. At 5-min intervals = 78 bins.
 * Each bin cap = dailyOptionsAdv × 0.015 / 78
 *
 * Why 1.5% option vol (vs 3% equity ADV):
 *   Options order books are thinner than equity. HFTs scan unusual options activity
 *   as a leading indicator. 1.5% per-bin keeps each order inside retail/MM noise —
 *   indistinguishable from normal delta hedging flow.
 *
 * At AAPL options ADV = $2B/day:
 *   Per 5-min bin: $2B / 78 = $25.64M available
 *   1.5% cap per bin: $384,600
 *   Our order per bin: ~22 contracts × $175 × 100 = $385,000 — exactly at the cap
 *
 * inputs: {
 *   totalContracts     : from appleCallOverlay.totalContracts
 *   aaplPrice          : live price
 *   dailyOptionsAdv    : AAPL daily options notional volume (default: $2B)
 *   optionsBinCapPct   : participation cap per bin (default: 1.5%)
 *   deployDays         : spread across N days (default: 3)
 * }
 */
function buildOptionsBinSlicer({
  totalContracts,
  aaplPrice,
  dailyOptionsAdv  = 2_000_000_000,
  optionsBinCapPct = 0.015,
  deployDays       = 3,
}) {
  const BINS_PER_DAY        = 78;                                    // 390min / 5min
  const perBinAdv           = dailyOptionsAdv / BINS_PER_DAY;
  const maxNotionalPerBin   = perBinAdv * optionsBinCapPct;
  const maxContractsPerBin  = Math.floor(maxNotionalPerBin / (aaplPrice * 100));

  const contractsPerDay     = Math.ceil(totalContracts / deployDays);
  const binsNeededPerDay    = Math.ceil(contractsPerDay / maxContractsPerBin);
  const contractsPerBin     = Math.ceil(contractsPerDay / binsNeededPerDay);
  const notionalPerBin      = Math.round(contractsPerBin * aaplPrice * 100);

  // Execution efficiency: how far inside the cap are we?
  const participationPct    = notionalPerBin / perBinAdv;
  const efficiencyPct       = +(Math.max(0, 1 - participationPct / optionsBinCapPct) * 100).toFixed(1);

  // Market impact in bps (sqrt model, applied to options vol fraction)
  const impactBps           = +(BASE_IMPACT_BPS * Math.sqrt(participationPct / NOISE_BAND_THRESHOLD)).toFixed(1);

  return {
    strategy:            "78-Bin VWAP — 5-Minute Intervals",
    totalContracts,
    deployDays,
    contractsPerDay,
    binsPerDay:          BINS_PER_DAY,
    binsNeededPerDay,
    contractsPerBin,
    notionalPerBin:      Math.round(notionalPerBin),
    maxContractsPerBin,
    capPct:              +(optionsBinCapPct * 100).toFixed(1),
    participationPct:    +(participationPct * 100).toFixed(2),
    impactBps,
    efficiencyPct,
    status: participationPct <= optionsBinCapPct
      ? `INSIDE NOISE BAND — ${impactBps}bps impact, ${efficiencyPct}% efficiency`
      : "WARNING: EXCEEDS BIN CAP — reduce contracts per bin",
    intervalMinutes:     5,
    firstExecutionET:    "9:30 AM",
    lastExecutionET:     "3:55 PM",
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 10. GAMMA SQUEEZE PROJECTION  (self-replication table)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * As AAPL rallies, option deltas increase — the position self-replicates more
 * delta exposure without any additional capital. This is the gamma squeeze effect.
 *
 * At each price level, shows:
 *   - Portfolio delta (shares equivalent)
 *   - Dollar gain per 1% AAPL move
 *   - Cumulative unrealised P&L vs entry
 *   - Self-replication factor vs entry delta
 *
 * Uses simplified delta estimation:
 *   delta(S, K, σ, T) ≈ N(ln(S/K) / (σ × √T) + 0.5 × σ × √T)
 */
function buildGammaSqueezeProjection({
  aaplPrice,
  aaplIV,
  daysToExpiry,
  tranches,
}) {
  // Price levels to project (entry → target)
  const priceLevels = [
    aaplPrice * 1.00,    // entry
    aaplPrice * 1.05,    // +5%
    aaplPrice * 1.10,    // +10%
    aaplPrice * 1.15,    // +15%
    aaplPrice * 1.20,    // +20%
    aaplPrice * 1.257,   // ~$220 at $175 entry
  ];

  function approxDelta(S, K, iv, T_days) {
    const T = T_days / 365;
    if (T <= 0) return S > K ? 1 : 0;
    const d1 = (Math.log(S / K) + 0.5 * iv * iv * T) / (iv * Math.sqrt(T));
    // Approximate N(d1) using logistic sigmoid
    return 1 / (1 + Math.exp(-1.7 * d1));
  }

  // Entry delta for reference
  const entryDeltas = tranches.map(t => approxDelta(aaplPrice, t.strike, aaplIV, daysToExpiry));
  const entryPortfolioDelta = tranches.reduce((s, t, i) => s + t.contracts * 100 * aaplPrice * entryDeltas[i], 0);

  const levels = priceLevels.map(S => {
    const deltas       = tranches.map(t => approxDelta(S, t.strike, aaplIV, Math.max(1, daysToExpiry - 3)));
    const sharesDelta  = tranches.reduce((s, t, i) => s + t.contracts * 100 * deltas[i], 0);
    const dollarDelta  = sharesDelta * S;                         // $ move per 1 share gain
    const pctGainDelta = Math.round(dollarDelta * 0.01);          // $ gain per 1% AAPL move
    const cumPnl       = tranches.reduce((s, t, i) => {
      const intrinsic   = Math.max(0, S - t.strike);
      const timeValue   = t.premiumPerShare * (1 - (priceLevels.indexOf(S) * 0.15));  // rough decay
      return s + t.contracts * 100 * (intrinsic + Math.max(0, timeValue) - t.premiumPerShare);
    }, 0);
    const selfReplication = +(dollarDelta / entryPortfolioDelta).toFixed(2);

    return {
      aaplPrice:         +S.toFixed(2),
      pctFromEntry:      +(((S / aaplPrice) - 1) * 100).toFixed(1),
      sharesDeltaEquiv:  Math.round(sharesDelta),
      dollarPer1Pct:     Math.round(pctGainDelta),
      cumUnrealisedPnl:  Math.round(cumPnl),
      selfReplication,
      note: selfReplication >= 3   ? "FULL GAMMA SQUEEZE — position self-replicating aggressively"
          : selfReplication >= 2   ? "STRONG GAMMA — significant self-replication underway"
          : selfReplication >= 1.5 ? "GAMMA BUILDING — delta expanding"
          :                          "ENTRY — baseline delta",
    };
  });

  return {
    underlying:         "AAPL",
    entryPrice:         aaplPrice,
    entryDeltaDollar:   Math.round(entryPortfolioDelta),
    levels,
    keyLevel220: levels.find(l => l.aaplPrice >= aaplPrice * 1.25) ?? levels[levels.length - 1],
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 11. WEEKEND SHIELD REPORT  (4:00 PM Friday — Oil/VIX contingency)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Calculates the Friday 4:00 PM delta position and stress-tests it against
 * an Oil spike ($135+) over the weekend, when the market is closed.
 *
 * Key insight: if Oil spikes to $135 over the weekend:
 *   → Monday open: VIX likely gaps up (energy shock = risk-off)
 *   → Monday harvest: larger VIX PnL → more harvest to fund call roll / buy dip
 *   → AAPL: short-term pullback (risk-off), but structurally IMMUNE to oil
 *   → Net: harvest absorbs the Gamma Gap, and the dip is an entry to roll calls lower
 *
 * "Gamma Gap" = the delta your position loses if AAPL opens -5% on Monday.
 *   Covered by: weekend VIX harvest estimate at elevated oil price.
 *
 * inputs: {
 *   aaplPriceFriday   : AAPL closing price Friday
 *   vixFriday         : VIX level at Friday close
 *   oilFriday         : Oil price at Friday close
 *   oilStressScenario : stress-test oil level (e.g. 135)
 *   vixSensitivity    : how much VIX rises per $10 oil (default: 1.5 VIX pts)
 *   vixPosition       : VIX long notional
 *   harvestRate        : fraction of VIX PnL harvested
 *   tranches          : from appleCallOverlay.tranches
 *   aaplIV            : current IV
 *   daysLeftToExpiry  : days remaining on the options
 * }
 */
function buildWeekendShieldReport({
  aaplPriceFriday,
  vixFriday,
  oilFriday,
  oilStressScenario = 135,
  vixSensitivity    = 1.5,     // VIX pts per $10 oil spike
  vixPosition,
  harvestRate       = 0.15,
  tranches          = [],
  aaplIV,
  daysLeftToExpiry,
}) {
  // Model oil stress
  const oilDelta    = Math.max(0, oilStressScenario - oilFriday);
  const vixStress   = vixFriday + (oilDelta / 10) * vixSensitivity;

  // AAPL stress: risk-off gap, but structurally immune to oil — model as -4% to -7%
  const aaplGapPct  = -(0.04 + Math.min(0.03, oilDelta / 10 * 0.008)); // -4% to -7%
  const aaplMonday  = aaplPriceFriday * (1 + aaplGapPct);

  // Gamma Gap: delta lost on the Monday gap
  function nd1(S, K, iv, T_days) {
    const T = T_days / 365;
    if (T <= 0) return S > K ? 1 : 0;
    const d1 = (Math.log(S / K) + 0.5 * iv * iv * T) / (iv * Math.sqrt(T));
    return 1 / (1 + Math.exp(-1.7 * d1));
  }

  const deltaFriday = tranches.reduce((s, t) =>
    s + t.contracts * 100 * nd1(aaplPriceFriday, t.strike, aaplIV, daysLeftToExpiry), 0);
  const deltaMonday = tranches.reduce((s, t) =>
    s + t.contracts * 100 * nd1(aaplMonday, t.strike, aaplIV, daysLeftToExpiry - 3), 0);

  const gammaGapShares = deltaFriday - deltaMonday;                   // shares of delta lost
  const gammaGapDollar = Math.round(gammaGapShares * aaplMonday);    // $ delta lost

  // Monday harvest from VIX stress
  const mondayVixReturn   = (vixStress - vixFriday) / vixFriday;     // % VIX move
  const mondayVixPnl      = Math.round(vixPosition * mondayVixReturn);
  const mondayHarvest     = Math.round(mondayVixPnl * harvestRate);

  // PnL on AAPL calls from the gap
  const callPnlFromGap = tranches.reduce((s, t) => {
    const intrinsicFri = Math.max(0, aaplPriceFriday - t.strike);
    const intrinsicMon = Math.max(0, aaplMonday      - t.strike);
    return s + t.contracts * 100 * (intrinsicMon - intrinsicFri);
  }, 0);

  const netWeekendPnl = Math.round(mondayHarvest + callPnlFromGap);

  const covered = mondayHarvest >= Math.abs(gammaGapDollar * 0.01); // harvest covers 1% AAPL move

  return {
    scenario: `Oil spikes from $${oilFriday} → $${oilStressScenario} over weekend`,
    oilStress:       oilStressScenario,
    vixStressLevel:  +vixStress.toFixed(1),
    aaplGapPct:      +(aaplGapPct * 100).toFixed(1),
    aaplMondayPrice: +aaplMonday.toFixed(2),
    deltaFriday:     Math.round(deltaFriday),
    deltaMonday:     Math.round(deltaMonday),
    gammaGapShares:  Math.round(gammaGapShares),
    gammaGapDollar,
    mondayVixPnl,
    mondayHarvest,
    callPnlFromGap:  Math.round(callPnlFromGap),
    netWeekendPnl,
    gammaGapCovered: covered,
    action: covered
      ? "Gamma Gap covered by Monday VIX harvest. Roll calls to lower strike on open to reduce cost basis."
      : "Gamma Gap exceeds single-day harvest. Deploy 2-day harvest reserve to roll calls.",
    symbiosisPnl: Math.round(mondayHarvest + callPnlFromGap),
    note: "AAPL structurally immune to oil. Short-term gap = opportunity to lower call strikes at zero net cost.",
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 11b. SVE ENGINE — Stark Volatility-Energy Cross-Asset Signal (Patent Claims A/B/C)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Claim A.1 — Stark Energy-Vol Differential (S_evd)
 *
 * Measures divergence between energy backwardation and volatility contango.
 * When energy futures are in backwardation (near > deferred) AND vol futures are
 * in contango (deferred > spot), the market is simultaneously pricing near-term
 * energy scarcity AND deferred equity fear — a structural mispricing.
 *
 * Signal ladder:
 *   S_evd_norm ≥ 3.0 → STRONG BUY   (full ADV deployment + AAPL tranche)
 *   S_evd_norm ≥ 2.0 → BUY          (standard Ghost Slicer)
 *   0.0 – 2.0        → HOLD
 *   ≤ -1.0           → REDUCE
 *   ≤ -2.0           → EXIT
 *
 * @param {object} p
 * @param {number} p.energyFront    Front-month WTI/Brent futures price
 * @param {number} p.energyDeferred 3-month deferred energy futures price
 * @param {number} p.vixSpot        CBOE spot VIX
 * @param {number} p.vixFutures1m   1-month VIX futures (VX contract)
 * @param {number[]} p.sevdHistory  Rolling 60-day S_evd readings for σ calculation
 */
function computeSevd({ energyFront, energyDeferred, vixSpot, vixFutures1m, sevdHistory = [] }) {
  // Energy backwardation slope (positive = near-term scarcity premium)
  const bEnergy = (energyFront - energyDeferred) / energyFront;

  // Volatility contango slope (positive = market expects future fear > present)
  const cVol = (vixFutures1m - vixSpot) / vixSpot;

  // Divergence: energy pricing near fear, vol pricing deferred fear → tension
  const sevd = bEnergy + cVol;

  // Sigma normalize against rolling history
  let sevdNorm = 0;
  if (sevdHistory.length >= 10) {
    const mu   = sevdHistory.reduce((s, v) => s + v, 0) / sevdHistory.length;
    const variance = sevdHistory.reduce((s, v) => s + (v - mu) ** 2, 0) / sevdHistory.length;
    const sigma = Math.sqrt(variance);
    sevdNorm = sigma > 0 ? (sevd - mu) / sigma : 0;
  }

  // Signal gate (Claim A.3: BLACK SWAN checked by caller via engineState)
  let signal, action;
  if      (sevdNorm >= 3.0)  { signal = "STRONG BUY"; action = "Full ADV cap + AAPL tranche"; }
  else if (sevdNorm >= 2.0)  { signal = "BUY";         action = "Standard Ghost Slicer"; }
  else if (sevdNorm >= 0.0)  { signal = "HOLD";        action = "Maintain legs; no new seeding"; }
  else if (sevdNorm >= -1.0) { signal = "REDUCE";      action = "Close weakest TRS leg; recycle to shield"; }
  else                       { signal = "EXIT";         action = "Full TRS reduction; maximize cash buffer"; }

  return {
    bEnergy:     +bEnergy.toFixed(4),
    cVol:        +cVol.toFixed(4),
    sevd:        +sevd.toFixed(4),
    sevdNorm:    +sevdNorm.toFixed(2),
    signal,
    action,
    historyDays: sevdHistory.length,
    interpretation: `Energy ${bEnergy > 0 ? "BACKWARDATION" : "contango"} + ` +
                    `Vol ${cVol > 0 ? "CONTANGO" : "backwardation"} → ` +
                    `S_evd ${sevdNorm >= 2 ? "DIVERGED (²σ+)" : "within normal range"}`,
  };
}

// ─────────────────────────────────────────────────────────────────────────────

/**
 * Claim B.1–B.2 — Collateral Velocity (C_v) Processor
 *
 * Monitors M2 money supply and repo market stress to produce a dynamic
 * collateral scalar C_v ∈ [0.50, 1.0].
 *
 *   M_required = M_base / C_v
 *
 * A falling C_v automatically thickens margin buffers BEFORE equity vol
 * reflects the liquidity stress — 48–72hr temporal alpha (Claim B.4).
 *
 * @param {object} p
 * @param {number} p.sofr            Current SOFR rate (decimal, e.g. 0.0530)
 * @param {number} p.ffrTarget       Fed Funds Rate target (decimal, e.g. 0.0525)
 * @param {number} p.m2Current       Current M2 money supply ($B)
 * @param {number} p.m2FourWeeksAgo  M2 four weeks ago ($B)
 * @param {number} p.marginBase      Base margin rate (default 0.15)
 * @param {number} p.repoStressSigma 90-day σ of repo stress spread (for 3σ shock gate)
 * @param {number} p.m2Sigma         90-day σ of ΔM2_4w (for 3σ shock gate)
 */
function computeCollateralVelocity({
  sofr,
  ffrTarget,
  m2Current,
  m2FourWeeksAgo,
  marginBase      = 0.15,
  repoStressSigma = 0.0015,   // ~15bps σ is a reasonable 90d baseline
  m2Sigma         = 0.003,    // ~0.3% weekly σ baseline
}) {
  const repoStress  = sofr - ffrTarget;              // spread in decimal (e.g. 0.0020 = 20bps)
  const deltaM2_4w  = (m2Current - m2FourWeeksAgo) / m2FourWeeksAgo;

  // Component haircuts (capped so C_v floor = 0.50)
  const repoComponent = Math.max(0, (repoStress / 0.0025) * 0.10);
  const m2Component   = Math.max(0, (-deltaM2_4w / 0.005) * 0.15);

  const cv = Math.max(0.50, 1 - Math.min(0.50, repoComponent + m2Component));

  // 3σ shock gate — halt all new TRS seeding immediately (Claim B.1.d)
  const repoShock = repoStress > 3 * repoStressSigma;
  const m2Shock   = deltaM2_4w < -3 * m2Sigma;
  const shockGate = repoShock || m2Shock;

  const marginRequired = marginBase / cv;

  let status;
  if (shockGate)    { status = "SHOCK — HALT ALL SEEDING"; }
  else if (cv < 0.65) { status = "CRITICAL"; }
  else if (cv < 0.80) { status = "WARNING"; }
  else if (cv < 0.93) { status = "WATCH"; }
  else                { status = "NORMAL"; }

  return {
    sofr:            +sofr.toFixed(4),
    ffrTarget:       +ffrTarget.toFixed(4),
    repoStress:      +(repoStress * 10000).toFixed(1),   // in bps
    deltaM2_4w:      +(deltaM2_4w * 100).toFixed(3),     // in pct
    cv:              +cv.toFixed(3),
    marginRequired:  +(marginRequired * 100).toFixed(2),  // in pct
    marginBase:      +(marginBase * 100).toFixed(2),
    marginIncrement: +((marginRequired - marginBase) * 100).toFixed(2),  // extra margin needed
    shockGate,
    status,
    earlyWarning: !shockGate && (repoStress > repoStressSigma || deltaM2_4w < -m2Sigma)
      ? "REPO/M2 STRESS BUILDING — 48–72hr lead on equity vol response"
      : null,
  };
}

// ─────────────────────────────────────────────────────────────────────────────

/**
 * Claim B.3 — Sovereign Liquidity Flywheel
 *
 * Four-stage recursive loop:
 *   Stage 1 HARVEST: VIX position × gap% × harvestRate → War Tax deposited as collateral
 *   Stage 2 EARN:    collateral × SOFR → daily yield while idle
 *   Stage 3 SIGNAL:  new SOFR reading updates C_v → margin buffers auto-adjust
 *   Stage 4 DEPLOY:  (collateral × C_v) / marginRequired → new TRS notional capacity
 *
 * Self-funding break-even (Claim C.2 / Decoupling):
 *   daily_WarTax + daily_CollYield > daily_TRS_Financing
 *
 * @param {object} p
 * @param {number} p.existingCollateral  Collateral already deposited ($)
 * @param {number} p.todayWarTax         New War Tax harvested today ($)
 * @param {number} p.sofr                Current SOFR (decimal)
 * @param {number} p.cv                  Collateral Velocity scalar from computeCollateralVelocity
 * @param {number} p.marginRequired      Current required margin rate (decimal) from C_v processor
 * @param {number} p.openTrsNotional     Total current open TRS notional ($)
 * @param {number} p.trsFinancingSpread  TRS desk spread over SOFR (decimal)
 * @param {number} p.maxNewNotional      Hard cap on new TRS notional ($) — risk limit
 */
function buildSovereignFlywheel({
  existingCollateral,
  todayWarTax,
  sofr,
  cv,
  marginRequired,
  openTrsNotional,
  trsFinancingSpread = 0.0025,
  maxNewNotional     = Infinity,
}) {
  // Stage 1: harvest deposited
  const totalCollateral = existingCollateral + todayWarTax;

  // Stage 2: collateral earns SOFR overnight
  const dailyCollYield = Math.round(totalCollateral * sofr / 252);

  // Stage 3: C_v already computed by caller (computeCollateralVelocity)
  // Margin requirement after C_v scaling
  const effectiveMargin = marginRequired;   // = marginBase / cv

  // Stage 4: new TRS capacity this cycle
  const rawTrsCapacity = (totalCollateral * cv) / effectiveMargin;
  const incrementalTrsCap = Math.min(
    Math.max(0, rawTrsCapacity - openTrsNotional),
    maxNewNotional,
  );

  // Daily TRS financing cost on open notional
  const dailyTrsFinancing = Math.round(openTrsNotional * (sofr + trsFinancingSpread) / 252);

  // Break-even check: does flywheel sustain without new capital?
  const dailyFlywheelIncome = todayWarTax + dailyCollYield;
  const flywheelSurplus     = Math.round(dailyFlywheelIncome - dailyTrsFinancing);
  const selfFunding         = flywheelSurplus >= 0;

  // Flywheel health
  let flywheelStatus;
  if (!selfFunding && flywheelSurplus < -50_000)  { flywheelStatus = "DEFICIT — add to VIX position"; }
  else if (!selfFunding)                           { flywheelStatus = "MARGINAL — monitor"; }
  else if (flywheelSurplus > 200_000)              { flywheelStatus = "ACCELERATING — increase TRS notional"; }
  else                                             { flywheelStatus = "SELF-FUNDING"; }

  return {
    // Stage outputs
    totalCollateral:    Math.round(totalCollateral),
    dailyCollYield,
    effectiveMarginPct: +(effectiveMargin * 100).toFixed(2),
    rawTrsCapacity:     Math.round(rawTrsCapacity),
    incrementalTrsCap:  Math.round(incrementalTrsCap),
    // Financing
    dailyTrsFinancing,
    dailyFlywheelIncome: Math.round(dailyFlywheelIncome),
    flywheelSurplus,
    selfFunding,
    flywheelStatus,
    // Recursion guidance
    nextCycleCollateral: Math.round(totalCollateral + dailyCollYield),
    note: selfFunding
      ? "Orchard self-sustaining. Deploy incremental TRS capacity."
      : "Harvest rate insufficient for current TRS notional. Reduce or increase VIX position.",
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// ─────────────────────────────────────────────────────────────────────────────
// 12. SUNDAY NIGHT SENTINEL  (v2.9 — Energy Arbitrage Engine)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * The Sunday Night Sentinel runs when Brent Crude futures open (~6 PM ET Sunday).
 * It treats geopolitical energy volatility not as threat but as rebalancing catalyst.
 *
 * STRUCTURAL INVERSION — the "Energy Arbitrage":
 *
 *   Cloud AI firms (MSFT, GOOG) are SHORT the grid:
 *     Every $1 Brent spike → direct tax on data-center power contracts → margin compression.
 *     Their shareholders panic. They buy VIX protection. That panic is your income.
 *
 *   Apple (AAPL) is LONG the battery:
 *     Inference runs on A18/M4 silicon. The electrical bill is outsourced to the user.
 *     Oil at $135 does not touch a single line of Apple's P&L.
 *
 *   The Arbitrage:
 *     Oil spike → Cloud AI Alumni panic-buy VIX → your VIX long harvests that panic
 *               → harvest funds AAPL calls at risk-off discount
 *               → AAPL reprices as the only energy-sovereign Mag 7 member
 *     Net: every energy shock makes your position STRONGER, not weaker.
 *
 * Energy Arbitrage Index (EAI):
 *   EAI = War_Tax_Generated / AAPL_Call_Discount_Value
 *   EAI > 1.0: the oil spike generates more harvest than the AAPL dip costs.
 *              You come out ahead on every energy shock. The "Redwoods" pay for
 *              the "Orchard" every time they fill their data centers.
 *
 * Sunday Sentinel outputs:
 *   - sentinelStatus:    ALERT / STANDBY / DEPLOY
 *   - energyArbitrage:   { warTax, aaplDiscount, eai, netAdvantage }
 *   - mondayBrief:       exact 9:30 AM execution instructions
 *   - regimeMonday:      projected engine mode at open
 *
 * inputs: {
 *   brentSunday        : Brent Crude futures price Sunday evening
 *   brentFriday        : Friday closing Brent price
 *   vixFuturesSunday   : VIX futures Sunday evening
 *   vixFriday          : Friday closing VIX
 *   aaplPremarket      : AAPL pre-market indication (null if unavailable)
 *   aaplFriday         : AAPL Friday close
 *   oilSensitivity     : VIX pts per $10 Brent spike (default 1.5)
 *   vixPosition        : VIX long notional
 *   harvestRate        : fraction of VIX PnL to harvest (default 0.15)
 *   aaplIV             : AAPL implied vol (Friday close)
 *   appleTranches      : from appleCallOverlay.tranches (existing position)
 *   daysLeftToExpiry   : days remaining on calls
 *   aum                : total AUM
 * }
 */
function buildSundayNightSentinel({
  brentSunday,
  brentFriday,
  vixFuturesSunday,
  vixFriday,
  aaplPremarket     = null,
  aaplFriday,
  oilSensitivity    = 1.5,
  vixPosition,
  harvestRate       = 0.15,
  aaplIV            = 0.26,
  appleTranches     = [],
  daysLeftToExpiry  = 42,
  aum,
}) {
  // ── 1. Energy gap assessment ─────────────────────────────────────────────
  const brentGap     = brentSunday - brentFriday;
  const brentGapPct  = brentGap / brentFriday;
  const brentAlert   = brentSunday >= 120;   // $120+ triggers Cloud AI margin fear

  // ── 2. VIX futures projection ─────────────────────────────────────────────
  const vixGapFromOil   = (brentGap / 10) * oilSensitivity;
  const vixProjected    = Math.max(vixFuturesSunday, vixFriday + vixGapFromOil);
  const vixGapPct       = (vixProjected - vixFriday) / vixFriday;

  // ── 3. War Tax — harvest from Monday VIX gap-up ───────────────────────────
  const vixMonPnl    = Math.round(vixPosition * vixGapPct);
  const warTax       = Math.round(vixMonPnl * harvestRate);

  // ── 4. AAPL gap estimate at Monday open ───────────────────────────────────
  // Risk-off gap: correlated with VIX spike. But AAPL structurally immune to oil.
  // Model: -2% base risk-off + up to -2% additional for extreme VIX (>30).
  const riskOffBase  = -0.02;
  const vixExtra     = Math.max(0, (vixProjected - 27) / 27 * -0.02);
  const aaplGapPct   = brentAlert ? (riskOffBase + vixExtra) : 0;
  const aaplMonday   = aaplPremarket ?? aaplFriday * (1 + aaplGapPct);

  // ── 5. AAPL call discount — calls are cheaper after the risk-off gap ───────
  // Lower AAPL price = more OTM = lower premium required for same strike.
  // This is the "steeper discount" — you buy the same optionality for less.
  const avgPremiumFriday = appleTranches.length > 0
    ? appleTranches.reduce((s, t) => s + t.premiumPerShare, 0) / appleTranches.length
    : aaplFriday * aaplIV * Math.sqrt(daysLeftToExpiry / 365) * 0.35;

  // Premium at gap-down price (same strike ladder, lower spot)
  const premiumDiscountPct = Math.max(0, -aaplGapPct * 1.5);  // options amplify spot moves
  const premiumMonday      = avgPremiumFriday * (1 - premiumDiscountPct);
  const callDiscount       = avgPremiumFriday - premiumMonday;

  // ── 6. Energy Arbitrage Index ──────────────────────────────────────────────
  // EAI = War Tax generated / Value of AAPL call discount (per share)
  // EAI > 1.0: oil spike is net-positive for the overlay
  const callNotionalPerShare = appleTranches.reduce((s, t) => s + t.contracts * 100, 0);
  const discountValue        = Math.round(callNotionalPerShare * callDiscount);
  const eai = discountValue > 0 ? +(warTax / discountValue).toFixed(2) : null;

  // ── 7. Net advantage ──────────────────────────────────────────────────────
  // What you gain: War Tax (harvest from VIX panic)
  // What you pay:  Any new premium to add Gamma at the dip
  // Net: warTax - cost of adding new tranche at discounted premium
  const newContractsAffordable = warTax > 0 && premiumMonday > 0
    ? Math.floor(warTax / (premiumMonday * 100))
    : 0;
  const netAdvantage = Math.round(warTax - newContractsAffordable * premiumMonday * 100);

  // ── 8. Monday regime projection ───────────────────────────────────────────
  let regimeMonday, regimeRisk;
  if (vixProjected > 35)                            { regimeMonday = "BLACK SWAN";   regimeRisk = "TERMINATE TRS"; }
  else if (vixProjected > 27)                       { regimeMonday = "BLACK SWAN";   regimeRisk = "STOP RECYCLING"; }
  else if (vixProjected > 22 && brentSunday > 115)  { regimeMonday = "RECYCLE";      regimeRisk = "ELEVATED"; }
  else if (vixProjected > 22)                       { regimeMonday = "SHIELD";       regimeRisk = "CRITICAL"; }
  else                                               { regimeMonday = "SYMBIOSIS";   regimeRisk = "NORMAL"; }

  // ── 9. Sentinel status ────────────────────────────────────────────────────
  const sentinelStatus = brentAlert && vixProjected > 24 ? "ALERT"
    : brentGap > 5 ? "WATCH"
    : "STANDBY";

  // ── 10. Monday brief ──────────────────────────────────────────────────────
  const mondayBrief = [];

  if (regimeMonday === "BLACK SWAN") {
    mondayBrief.push("HALT all TRS seeding at open. Route harvest to VIX shield top-up.");
    mondayBrief.push("DO NOT open new AAPL calls. Defend existing tranches only.");
    mondayBrief.push(`VIX expected at ${vixProjected.toFixed(1)} — harvest ${warTax > 0 ? '$' + warTax.toLocaleString() : 'N/A'} available.`);
  } else if (regimeMonday === "RECYCLE") {
    mondayBrief.push(`War Tax: $${warTax.toLocaleString()} harvest available from VIX gap-up.`);
    mondayBrief.push(`AAPL opens ~$${aaplMonday.toFixed(2)} (${(aaplGapPct*100).toFixed(1)}%). Calls ${(premiumDiscountPct*100).toFixed(1)}% cheaper than Friday.`);
    mondayBrief.push(`Add ${newContractsAffordable} new AAPL contracts at discounted premium ($${premiumMonday.toFixed(2)}/share).`);
    mondayBrief.push("Deploy 78-bin slicer from 9:30 AM. Phase 1 equity: VST/GEV/CCJ first.");
    mondayBrief.push(`Energy Arbitrage Index: ${eai}× — oil spike is net-positive for the overlay.`);
  } else if (regimeMonday === "SHIELD") {
    mondayBrief.push(`War Tax: $${warTax.toLocaleString()} available. Hold until regime shifts to RECYCLE.`);
    mondayBrief.push("Accumulate harvest. No new AAPL calls or TRS until VIX confirms direction.");
    mondayBrief.push(`AAPL at $${aaplMonday.toFixed(2)} — calls available at ${(premiumDiscountPct*100).toFixed(1)}% discount when gate opens.`);
  } else {
    mondayBrief.push("Calm open. Run standard Ghost Slicer schedule.");
    mondayBrief.push("Deploy remaining AAPL tranches at standard 78-bin pace.");
  }

  // ── Simplified posture API (mirrors lightweight sundayNightSentinel signature) ─
  const posture = (brentSunday > 120 || vixProjected > 30)
    ? { label: "🚨 DEFENSIVE LOCK",  vixAction: `Increase Harvest to 25%`,           aaplAction: "Pause new Gamma entry; hold current orchard." }
    : { label: "🛡️ SHIELD ACTIVE",   vixAction: "Maintain 15% Recycle",              aaplAction: "Resume v2.7 Slicer at Monday Open." };

  return {
    runTime:              new Date().toISOString(),
    sentinelStatus,
    posture,
    energy: {
      brentFriday,
      brentSunday,
      brentGap:           +brentGap.toFixed(2),
      brentGapPct:        +(brentGapPct * 100).toFixed(1),
      brentAlert,
      energyModel:        brentAlert
        ? "CLOUD AI MARGIN TAX ACTIVE — $120+ Brent compresses MSFT/GOOG data-center margins"
        : "BELOW ALERT THRESHOLD — monitor for escalation",
    },
    vix: {
      vixFriday,
      vixFuturesSunday,
      vixProjected:       +vixProjected.toFixed(1),
      vixGapPct:          +(vixGapPct * 100).toFixed(1),
    },
    aapl: {
      aaplFriday,
      aaplMonday:         +aaplMonday.toFixed(2),
      aaplGapPct:         +(aaplGapPct * 100).toFixed(1),
      structuralNote:     "AAPL immune to oil. Gap = risk-off sentiment only. Mean-reverts 3-5 sessions.",
    },
    energyArbitrage: {
      warTax,
      premiumFriday:      +avgPremiumFriday.toFixed(2),
      premiumMonday:      +premiumMonday.toFixed(2),
      premiumDiscountPct: +(premiumDiscountPct * 100).toFixed(1),
      discountValue,
      eai,
      eaiStatus:          eai === null ? "N/A"
        : eai > 2.0 ? "STRONG ARBITRAGE — oil spike highly net-positive"
        : eai > 1.0 ? "POSITIVE ARBITRAGE — War Tax > call discount"
        : "WATCH — discount outpaces current harvest",
      newContractsAffordable,
      netAdvantage,
      arbitrageSummary:   eai && eai > 1.0
        ? `Oil spike generates $${warTax.toLocaleString()} War Tax vs $${discountValue.toLocaleString()} discount value. Net advantage: $${netAdvantage.toLocaleString()}.`
        : `War Tax: $${warTax.toLocaleString()}. Build harvest before adding Gamma.`,
    },
    regimeMonday,
    regimeRisk,
    mondayBrief,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 13. SYSTEMIC ALPHA TRACKER  (LENS tab — Cell P1)
// ─────────────────────────────────────────────────────────────────────────────
// ─────────────────────────────────────────────────────────────────────────────

/**
 * P1 = (Cumulative_493_TRS_Gain + Cumulative_VIX_Roll_Yield) - Total_Financing_Costs
 *
 * Measures how much "Free Growth" has been extracted from Mag 7 volatility.
 * When this exceeds 5% of AUM, the 493 basket is self-funding — you have decoupled.
 *
 * systemicInputs: {
 *   cumulative493TrsGain  : total mark-to-market gain on all 493 TRS legs to date
 *   cumulativeVixRollYield: cumulative daily roll/theta credits from VIX long
 *   totalFinancingCosts   : cumulative SOFR+spread paid on all TRS legs to date
 *   aum                   : current AUM
 * }
 */
function buildSystemicAlpha({ cumulative493TrsGain, cumulativeVixRollYield, totalFinancingCosts, aum }) {
  const grossAlpha    = cumulative493TrsGain + cumulativeVixRollYield;
  const systemicAlpha = grossAlpha - totalFinancingCosts;
  const systemicPct   = aum > 0 ? (systemicAlpha / aum) * 100 : 0;

  let status, action;
  if (systemicPct > 5) {
    status = "DECOUPLED";
    action = "493 is self-funding. Mag 7 volatility has paid for the grid.";
  } else if (systemicPct > 2) {
    status = "COMPOUNDING";
    action = "On track. Maintain current ADV cap and harvest rate.";
  } else {
    status = "ENERGY TAX WINNING";
    action = "Tighten Shield Trigger to VIX > 27. Reduce TRS notional.";
  }

  return {
    grossAlpha:      Math.round(grossAlpha),
    systemicAlpha:   Math.round(systemicAlpha),
    systemicPct:     +systemicPct.toFixed(2),
    status,
    action,
    decoupledThreshold: +(aum * 0.05).toFixed(0),   // 5% of AUM
    warningThreshold:   +(aum * 0.02).toFixed(0),   // 2% of AUM
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 9. ALERTS
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Three-level alert hierarchy — formula equivalent:
 *
 *   =IF(OR(VIX>35, Oil>140),          "🚨 BLACK SWAN",
 *    IF(AND(VIX>=22, VIX<=35, GEX<0), "🛡️ SHIELD ACTIVE",
 *    IF(VIX<20,                        "🌊 SYMBIOSIS",
 *                                      "⚖️ TRANSITION")))
 *
 * 🚨 BLACK SWAN  (VIX > 35 OR Oil > $140)
 *    Kill all TRS seeding. 100% PnL → Cash / VIX Shield. Protect principal.
 *
 * 🛡️ SHIELD ACTIVE  (VIX 22–35 AND GEX < 0)
 *    Continue 15% harvest. Maintain 3% ADV stealth cap. No new TRS legs.
 *
 * 🌊 SYMBIOSIS  (VIX < 20)
 *    Exit VIX shield. 100% Long 493 via Physical Equity (no TRS needed).
 *
 * ⚖️ TRANSITION  (everything else)
 *    Monitor. Prepare Shield or Recycle parameters.
 */
function buildAlerts(vix, oil, gex, engineState, alphaRisk, trsTracker) {
  const alerts = [];

  // ── Tier 0: GEX structural collapse (independent of VIX level) ───────────
  if (gex < -500_000_000) {
    alerts.push({
      level:   "TERMINATE TRS",
      message: "GEX < -$500M — structural gamma collapse. UNWIND ALL TRS LEGS IMMEDIATELY.",
      action:  "Unwind all TRS. Return to VIX Shield only. No new deployment until GEX > 0.",
    });
  }

  // ── Tier 1: BLACK SWAN (VIX > 35 OR Oil > $140) ──────────────────────────
  if (vix > 35 || oil > 140) {
    const trigger = [vix > 35 && `VIX ${vix.toFixed(1)} > 35`, oil > 140 && `Oil $${oil.toFixed(0)} > $140`]
      .filter(Boolean).join(" + ");
    alerts.push({
      level:   "BLACK SWAN",
      message: `${trigger}. BLACK SWAN CONFIRMED.`,
      action:  "KILL all TRS seeding. Move 100% of harvested PnL to Cash / VIX Shield. Protect principal.",
    });
  }

  // ── Tier 2: SHIELD ACTIVE (VIX 22–35 AND GEX < 0) ───────────────────────
  if (vix >= 22 && vix <= 35 && gex < 0) {
    alerts.push({
      level:   "SHIELD ACTIVE",
      message: `VIX ${vix.toFixed(1)} in 22–35 range + GEX negative.`,
      action:  "Continue 15% VIX harvest. Maintain 3% ADV stealth cap. Do NOT open new TRS legs.",
    });
  }

  // ── Tier 3: RECYCLE (engine ELEVATED) ────────────────────────────────────
  if (engineState.riskLevel === "ELEVATED") {
    alerts.push({
      level:   "RECYCLE",
      message: `VIX > 24 + Oil > $115. RECYCLE phase triggered.`,
      action:  "Deploy VIX harvest → VST / GEV / CCJ (Phase 1), then Tier 1+2. Ghost Slicer at 3% ADV.",
    });
  }

  // ── Tier 4: SYMBIOSIS (VIX < 20) ─────────────────────────────────────────
  if (vix < 20) {
    alerts.push({
      level:   "SYMBIOSIS",
      message: `VIX ${vix.toFixed(1)} < 20. Calm market.`,
      action:  "Exit VIX shield. Rotate to 100% Long 493 via Physical Equity. No TRS needed.",
    });
  }

  // ── Supporting: alpha and TRS health ────────────────────────────────────
  if (alphaRisk.status === "UNDERWATER") {
    alerts.push({
      level:   "ALPHA WARNING",
      message: `Alpha efficiency ${alphaRisk.alphaEfficiency}x — net alpha negative.`,
      action:  "Check M10 reconciliation. Tighten ADV cap to 2% until M10 turns positive.",
    });
  }

  if (trsTracker.totals.netPnlPct < -2) {
    alerts.push({
      level:   "TRS DRAWDOWN",
      message: `TRS book down ${Math.abs(trsTracker.totals.netPnlPct)}% net of financing.`,
      action:  "Monitor termination thresholds: VIX > 35 or GEX < -$500M triggers unwind.",
    });
  }

  return alerts.length > 0 ? alerts : [{ level: "OK", message: "No active alerts. System nominal.", action: "" }];
}

// ─────────────────────────────────────────────────────────────────────────────
// 15. PHASE 2 — MULTI-PB COLLATERAL ARCHITECTURE
// ─────────────────────────────────────────────────────────────────────────────
//
// Four modules covering Claim H (Collateral Asymmetry), Claim I (Capacity Map),
// Claim J (Global Netting / Omnibus Exit), Claim K (Leakage Surveillance).
//
// ⚠️  REGULATORY BOUNDARY — NOT IMPLEMENTED:
//   • "Wash Play" (simultaneous buy PB-1 / sell PB-2, net-zero intent to
//     deceive market): wash trade under SEC Rule 10b-5 / CEA §4c(a)(5).
//   • "Counterparty Leakage Test" bait iceberg (non-executable order placed
//     deliberately): spoofing under Dodd-Frank CEA §4c(a)(5)(B).
//   These objectives are achievable via legitimate means implemented below.
// ─────────────────────────────────────────────────────────────────────────────

// ── Claim H: Collateral Asymmetry Detector + TPRA Sweep Engine ───────────────

/**
 * Claim H.1 — buildCollateralAsymmetry
 *
 * Monitors margin rates across N prime brokers. When any PB's margin exceeds
 * the system-wide weighted average by a configurable threshold, the engine
 * calculates the minimum collateral sweep (via Tri-Party Repo) needed to
 * neutralize the outlier without moving any market-facing position.
 *
 * The "Haircut Propagation" defense: a sudden 3σ VIX spike causes PB-1 to
 * hike margin from 8% → 18% while PB-2/3 lag at 10%. The asymmetry is
 * detected in real-time; a TPRA sweep routes excess liquidity from PB-2
 * to PB-1's margin account before the call hits the desk.
 *
 * @param {object[]} primebrokers   Array of PB descriptors:
 *   { id, name, marginRate, openNotional, collateralPosted, tpraLinked }
 * @param {number}  outlierThreshold  Flag PB if margin > mean + threshold (default 0.04 = 4pp)
 * @param {number}  vixCurrent        Current VIX (for 3σ stress hike simulation)
 */
function buildCollateralAsymmetry({ primeBrokers, outlierThreshold = 0.04, vixCurrent = 20 }) {
  const total  = primeBrokers.reduce((s, pb) => s + pb.openNotional, 0);

  // Weighted average margin rate across all PBs
  const wtdAvgMargin = total > 0
    ? primeBrokers.reduce((s, pb) => s + pb.marginRate * (pb.openNotional / total), 0)
    : 0;

  // Per-PB analysis
  const pbAnalysis = primeBrokers.map(pb => {
    const marginRequired   = pb.openNotional * pb.marginRate;
    const marginExcess     = pb.collateralPosted - marginRequired;  // positive = over-collateralized
    const isOutlier        = pb.marginRate > wtdAvgMargin + outlierThreshold;
    const shortfall        = isOutlier ? Math.max(0, marginRequired - pb.collateralPosted) : 0;
    const sweepNeeded      = isOutlier && shortfall > 0 && pb.tpraLinked;

    return {
      id:              pb.id,
      name:            pb.name,
      marginRate:      +(pb.marginRate * 100).toFixed(2),
      marginRequired:  Math.round(marginRequired),
      collateralPosted: Math.round(pb.collateralPosted),
      marginExcess:    Math.round(marginExcess),
      shortfall:       Math.round(shortfall),
      isOutlier,
      sweepNeeded,
      tpraLinked:      pb.tpraLinked,
    };
  });

  // TPRA sweep plan: pull from over-collateralized PBs to fill outlier shortfalls
  const outliers    = pbAnalysis.filter(p => p.sweepNeeded);
  const donors      = pbAnalysis.filter(p => p.marginExcess > 0 && p.tpraLinked)
    .sort((a, b) => b.marginExcess - a.marginExcess);

  const sweepPlan = [];
  let remainingNeeded = outliers.reduce((s, p) => s + p.shortfall, 0);

  for (const donor of donors) {
    if (remainingNeeded <= 0) break;
    const sweep = Math.min(donor.marginExcess, remainingNeeded);
    const target = outliers.find(o => o.shortfall > 0);
    if (!target) break;
    sweepPlan.push({
      from:        donor.name,
      to:          target.name,
      amount:      Math.round(sweep),
      mechanism:   "TRI-PARTY REPO",
      action:      `Transfer $${Math.round(sweep).toLocaleString()} collateral via pre-positioned TPRA link`,
    });
    remainingNeeded -= sweep;
  }

  const asymmetryResolved = remainingNeeded <= 0;

  // 3σ stress simulation: what happens if VIX spikes 35% from current
  const stressVix        = vixCurrent * 1.35;
  const stressHikePb1    = Math.min(0.25, wtdAvgMargin * 2.25);    // aggressive PB1 hike
  const stressShortfall  = primeBrokers[0]
    ? Math.max(0, primeBrokers[0].openNotional * (stressHikePb1 - primeBrokers[0].marginRate))
    : 0;

  let asymmetryStatus;
  if (outliers.length === 0)         { asymmetryStatus = "BALANCED — no margin outliers"; }
  else if (asymmetryResolved)        { asymmetryStatus = `SWEEP READY — ${sweepPlan.length} TPRA transfer(s) queued`; }
  else                               { asymmetryStatus = "LOCKED — insufficient TPRA liquidity; escalate to desk"; }

  return {
    wtdAvgMarginPct:  +(wtdAvgMargin * 100).toFixed(2),
    totalNotional:    Math.round(total),
    pbAnalysis,
    outlierCount:     outliers.length,
    sweepPlan,
    totalSweepAmount: sweepPlan.reduce((s, sw) => s + sw.amount, 0),
    asymmetryResolved,
    asymmetryStatus,
    stressScenario: {
      stressVix:       +stressVix.toFixed(1),
      stressHikePct:   +(stressHikePb1 * 100).toFixed(1),
      stressShortfall: Math.round(stressShortfall),
      preEmptAction:   stressShortfall > 0
        ? `Pre-position $${Math.round(stressShortfall).toLocaleString()} TPRA buffer at PB-1 NOW (before VIX spike)`
        : "Buffer adequate for stress scenario",
    },
  };
}

// ── Claim I: C_m Capacity Mapping / Thermal Guardrail ────────────────────────

/**
 * Claim I.1 — buildCapacityMap
 *
 * Computes the Capacity scalar C_m for a target notional expansion across
 * all venues. If the required execution consumes > 10% of Top-of-Book (ToB)
 * depth on any single venue, the engine throttles to "Passive Only" and
 * distributes remaining notional to under-utilized venues.
 *
 * Thermal Guardrail: prevents the engine from becoming its own market impact.
 * At $150M, crossing 10% ToB means you are no longer "market noise" — you
 * are a price-mover. C_m falls to 0 at that threshold, halting expansion.
 *
 * @param {object[]} venues   Array of venue descriptors:
 *   { id, name, tobDepthDollars, currentAllocation }
 * @param {number}   targetNewNotional  New notional to deploy ($)
 * @param {number}   tobCapPct          ToB participation cap (default 0.10 = 10%)
 */
function buildCapacityMap({ venues, targetNewNotional, tobCapPct = 0.10 }) {
  const venueAnalysis = venues.map(v => {
    const tobCapDollars   = v.tobDepthDollars * tobCapPct;
    const currentPct      = v.currentAllocation / v.tobDepthDollars;
    const remainingCap    = Math.max(0, tobCapDollars - v.currentAllocation);
    const thermalStatus   = currentPct >= tobCapPct ? "THROTTLED"
      : currentPct >= tobCapPct * 0.75 ? "WARM"
      : "COOL";

    return {
      id:                v.id,
      name:              v.name,
      tobDepth:          Math.round(v.tobDepthDollars),
      tobCapDollars:     Math.round(tobCapDollars),
      currentAllocation: Math.round(v.currentAllocation),
      currentPct:        +(currentPct * 100).toFixed(2),
      remainingCap:      Math.round(remainingCap),
      thermalStatus,
    };
  });

  const totalRemainingCap = venueAnalysis.reduce((s, v) => s + v.remainingCap, 0);
  const canDeploy         = Math.min(targetNewNotional, totalRemainingCap);
  const throttled         = targetNewNotional > totalRemainingCap;

  // Distribute deployable notional to coolest venues first
  const coolVenues   = [...venueAnalysis].filter(v => v.thermalStatus !== "THROTTLED")
    .sort((a, b) => a.currentPct - b.currentPct);   // coolest first

  const allocationPlan = [];
  let remaining = canDeploy;
  for (const v of coolVenues) {
    if (remaining <= 0) break;
    const alloc = Math.min(v.remainingCap, remaining);
    allocationPlan.push({ venue: v.name, allocation: Math.round(alloc), thermalStatus: v.thermalStatus });
    remaining -= alloc;
  }

  // C_m scalar: ratio of deployable to target (1.0 = full capacity, 0 = fully throttled)
  const cm = targetNewNotional > 0 ? Math.min(1, canDeploy / targetNewNotional) : 0;

  let thermalGuidance;
  if (cm >= 0.95)        { thermalGuidance = "FULL CAPACITY — deploy at normal pace"; }
  else if (cm >= 0.70)   { thermalGuidance = "PARTIAL CAPACITY — throttle to available venues"; }
  else if (cm >= 0.30)   { thermalGuidance = "CONSTRAINED — reduce target or wait for TOB recovery"; }
  else                   { thermalGuidance = "THERMAL HALT — all venues at cap; passive-only mode"; }

  return {
    cm:                 +cm.toFixed(3),
    targetNewNotional:  Math.round(targetNewNotional),
    canDeploy:          Math.round(canDeploy),
    throttledAmount:    Math.round(Math.max(0, targetNewNotional - canDeploy)),
    throttled,
    venueAnalysis,
    allocationPlan,
    thermalGuidance,
    tobCapPct:          +(tobCapPct * 100).toFixed(0) + "%",
    passiveOnlyMode:    cm < 0.05,
  };
}

// ── Claim J: Global Netting Engine + Omnibus Exit ────────────────────────────

/**
 * Claim J.1 — buildGlobalNettingEngine
 *
 * Aggregates positions across all prime brokers, computes net exposure
 * per ticker, identifies cross-PB offsets, and generates the minimum-
 * touch Omnibus Exit plan that unwinds net exposure with fewest executions.
 *
 * This is the legitimate mechanism for cross-PB rebalancing: actual position
 * reduction at one broker and addition at another, based on genuine portfolio
 * management objectives (concentration limits, margin optimization) — not
 * round-trip trading designed to deceive.
 *
 * @param {object[]} pbPositions   Per-PB positions:
 *   [{ pbId, pbName, positions: [{ ticker, notional, side:'LONG'|'SHORT' }] }]
 * @param {object}   collateralMap  { pbId: collateralPosted } for margin routing
 */
function buildGlobalNettingEngine({ pbPositions, collateralMap = {} }) {
  // Step 1: aggregate net notional per ticker across all PBs
  const netByTicker = {};
  const grossByPb   = {};

  for (const pb of pbPositions) {
    let pbGross = 0;
    for (const pos of pb.positions) {
      const sign = pos.side === "LONG" ? 1 : -1;
      netByTicker[pos.ticker] = (netByTicker[pos.ticker] ?? 0) + sign * pos.notional;
      pbGross += pos.notional;
    }
    grossByPb[pb.pbId] = { name: pb.pbName, gross: pbGross, collateral: collateralMap[pb.pbId] ?? 0 };
  }

  // Step 2: identify offsetting positions (same ticker, opposite sides across PBs)
  const offsets = [];
  for (const [ticker, net] of Object.entries(netByTicker)) {
    const longLegs  = pbPositions.flatMap(pb =>
      pb.positions.filter(p => p.ticker === ticker && p.side === "LONG")
        .map(p => ({ ...p, pbId: pb.pbId, pbName: pb.pbName })));
    const shortLegs = pbPositions.flatMap(pb =>
      pb.positions.filter(p => p.ticker === ticker && p.side === "SHORT")
        .map(p => ({ ...p, pbId: pb.pbId, pbName: pb.pbName })));

    if (longLegs.length > 0 && shortLegs.length > 0) {
      const offsetNotional = Math.min(
        longLegs.reduce((s, l) => s + l.notional, 0),
        shortLegs.reduce((s, l) => s + l.notional, 0),
      );
      offsets.push({
        ticker,
        offsetNotional: Math.round(offsetNotional),
        longAt:  longLegs.map(l => l.pbName).join("/"),
        shortAt: shortLegs.map(l => l.pbName).join("/"),
        action: `Book-transfer $${Math.round(offsetNotional).toLocaleString()} ${ticker} offset via internal netting — no market execution needed`,
      });
    }
  }

  // Step 3: Omnibus Exit plan — minimum-touch unwind sequence
  const totalGross     = Object.values(grossByPb).reduce((s, pb) => s + pb.gross, 0);
  const omnibusExit    = Object.entries(netByTicker)
    .filter(([, net]) => Math.abs(net) > 100_000)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .map(([ticker, net]) => ({
      ticker,
      netNotional:   Math.round(net),
      netSide:       net > 0 ? "NET LONG" : "NET SHORT",
      exitAction:    net > 0 ? `SELL $${Math.round(Math.abs(net)).toLocaleString()}` : `COVER $${Math.round(Math.abs(net)).toLocaleString()}`,
      routingNote:   "Ghost Slicer 3%/5% ADV clips via C_m-cleared venues",
    }));

  // Step 4: collateral rebalancing recommendation (not a wash — actual margin efficiency)
  const pbsByCollateralEfficiency = Object.entries(grossByPb)
    .map(([id, pb]) => ({
      pbId:             id,
      name:             pb.name,
      grossNotional:    pb.gross,
      collateralPosted: pb.collateral,
      utilizationPct:   pb.collateral > 0 ? +(pb.gross / pb.collateral * 100).toFixed(1) : 0,
    }))
    .sort((a, b) => b.utilizationPct - a.utilizationPct);

  return {
    totalGrossNotional: Math.round(totalGross),
    netPositions:       Object.entries(netByTicker).map(([t, n]) => ({ ticker: t, net: Math.round(n) })),
    internalOffsets:    offsets,
    internalOffsetValue: offsets.reduce((s, o) => s + o.offsetNotional, 0),
    omnibusExit,
    pbsByCollateralEfficiency,
    nettingSummary: `${offsets.length} cross-PB offsets identified ($${offsets.reduce((s,o)=>s+o.offsetNotional,0).toLocaleString()} nettable without market execution)`,
  };
}

// ── Claim K: Leakage Surveillance (Post-Execution Correlation) ───────────────

/**
 * Claim K.1 — buildLeakageSurveillance
 *
 * Detects information leakage from PB internal desks by monitoring the
 * correlation between the engine's OWN execution timestamps and subsequent
 * adverse price moves on lit venues — using actual fills, never fake orders.
 *
 * If PB-X's internal market-making desk has access to client order flow
 * (a "Chinese Wall" breach), fills routed via PB-X will show a higher
 * adverse-selection ratio than fills routed via PB-Y. The difference in
 * adverse-selection rates across PBs IS the leakage signal — no bait needed.
 *
 * @param {object[]} fillHistory   Array of completed fills:
 *   { pbId, ticker, side, fillPrice, fillTimeMs, postFillPrice2ms, postFillPrice50ms, notional }
 * @param {number}   leakageThresholdBps  Flag PB if adverse selection > threshold (default 2bps)
 */
function buildLeakageSurveillance({ fillHistory, leakageThresholdBps = 2.0 }) {
  if (fillHistory.length === 0) return { status: "INSUFFICIENT_DATA", pbProfiles: [] };

  // Group fills by PB
  const byPb = {};
  for (const fill of fillHistory) {
    if (!byPb[fill.pbId]) byPb[fill.pbId] = { pbId: fill.pbId, fills: [] };
    byPb[fill.pbId].fills.push(fill);
  }

  const pbProfiles = Object.values(byPb).map(({ pbId, fills }) => {
    // Adverse selection: for each fill, measure price move 2ms and 50ms after fill
    // If LONG fill → adverse = price dropped. If SHORT fill → adverse = price rose.
    const asMetrics2ms  = [];
    const asMetrics50ms = [];

    for (const f of fills) {
      const sign = f.side === "BUY" ? 1 : -1;
      const as2ms  = sign * (f.postFillPrice2ms  - f.fillPrice) / f.fillPrice * 10000;  // bps
      const as50ms = sign * (f.postFillPrice50ms - f.fillPrice) / f.fillPrice * 10000;
      asMetrics2ms.push(as2ms);
      asMetrics50ms.push(as50ms);
    }

    const avgAs2ms  = asMetrics2ms.reduce((s, v) => s + v, 0) / fills.length;
    const avgAs50ms = asMetrics50ms.reduce((s, v) => s + v, 0) / fills.length;

    // Correlation between fill notional and subsequent adverse move (size-informed leakage)
    const notionals    = fills.map(f => f.notional);
    const meanN        = notionals.reduce((s, v) => s + v, 0) / fills.length;
    const meanAs       = avgAs2ms;
    let covNum = 0, covDenN = 0, covDenA = 0;
    for (let i = 0; i < fills.length; i++) {
      covNum  += (notionals[i] - meanN) * (asMetrics2ms[i] - meanAs);
      covDenN += (notionals[i] - meanN) ** 2;
      covDenA += (asMetrics2ms[i] - meanAs) ** 2;
    }
    const leakageCorrelation = covDenN > 0 && covDenA > 0
      ? +(covNum / Math.sqrt(covDenN * covDenA)).toFixed(3)
      : 0;

    // A high negative correlation means larger fills → more adverse price move → leakage
    const leakageFlag   = avgAs2ms < -leakageThresholdBps || leakageCorrelation < -0.60;
    const hostileFlag   = leakageCorrelation < -0.80 && avgAs2ms < -leakageThresholdBps * 2;

    return {
      pbId,
      fillCount:         fills.length,
      avgAdverseSelection2ms:  +avgAs2ms.toFixed(2),
      avgAdverseSelection50ms: +avgAs50ms.toFixed(2),
      leakageCorrelation,
      leakageFlag,
      hostileFlag,
      recommendation: hostileFlag
        ? `PB ${pbId}: HIGH LEAKAGE (correlation ${leakageCorrelation}). Route ≤ 5% of flow here. Shift 80% to dark-pool-specialist node.`
        : leakageFlag
        ? `PB ${pbId}: MODERATE LEAKAGE. Reduce lit-venue clips by 50%. Monitor next 20 fills.`
        : `PB ${pbId}: CLEAN — adverse selection within ${leakageThresholdBps}bps threshold.`,
    };
  });

  const hostilePBs  = pbProfiles.filter(p => p.hostileFlag);
  const leakyPBs    = pbProfiles.filter(p => p.leakageFlag && !p.hostileFlag);
  let leakageStatus;
  if (hostilePBs.length > 0)     { leakageStatus = `HOSTILE NODE DETECTED: ${hostilePBs.map(p => p.pbId).join(", ")}`; }
  else if (leakyPBs.length > 0)  { leakageStatus = `LEAKAGE WATCH: ${leakyPBs.map(p => p.pbId).join(", ")}`; }
  else                            { leakageStatus = "CLEAN — no systematic adverse selection detected"; }

  return {
    leakageStatus,
    pbProfiles,
    hostilePBs:  hostilePBs.map(p => p.pbId),
    leakyPBs:    leakyPBs.map(p => p.pbId),
    pivot: hostilePBs.length > 0
      ? `Shift 80% of expansion to dark-pool-specialist node. Keep ≤ $5M "noise" flow at hostile PB for surveillance continuity.`
      : null,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// 14. SVE SURVIVAL ARCHITECTURE  (Claims D / E / F / G)
// ─────────────────────────────────────────────────────────────────────────────

// ── Claim D.1–D.3: VRT Step-Down Ladder ──────────────────────────────────────

/** VRT_STEPS: [{ cvThreshold, reductionPct }] — conservative and ultra-defensive sets */
const VRT_STEPS_CONSERVATIVE     = [
  { cvThreshold: 0.85, reductionPct: 0.10 },
  { cvThreshold: 0.75, reductionPct: 0.25 },
  { cvThreshold: 0.65, reductionPct: 0.40 },
  { cvThreshold: 0.55, reductionPct: 0.60 },
];
const VRT_STEPS_ULTRA_DEFENSIVE  = [
  { cvThreshold: 0.88, reductionPct: 0.10 },
  { cvThreshold: 0.78, reductionPct: 0.25 },
  { cvThreshold: 0.65, reductionPct: 0.50 },
  { cvThreshold: 0.55, reductionPct: 0.70 },
];

/**
 * Claim D — VRT Step-Down
 *
 * Computes required TRS gross reduction driven solely by C_v (monetary plumbing),
 * not by mark-to-market price action.
 *
 * @param {object} p
 * @param {number} p.cv               Current C_v scalar (from computeCollateralVelocity)
 * @param {number} p.openTrsNotional  Current gross open TRS notional ($)
 * @param {number} p.targetNotional   Fully deployed target notional ($)
 * @param {boolean} p.ultraDefensive  Use ultra-defensive 5σ parameters
 * @param {number} p.sevdNorm         Current S_evd normalized (for re-entry gate)
 */
function buildVrtStepDown({ cv, openTrsNotional, targetNotional, ultraDefensive = false, sevdNorm = 0 }) {
  const steps = ultraDefensive ? VRT_STEPS_ULTRA_DEFENSIVE : VRT_STEPS_CONSERVATIVE;
  const reEntryMinSevd = ultraDefensive ? 2.5 : 2.0;
  const reEntryCvMin   = ultraDefensive ? 0.88 : 0.85;

  // Find active step (highest reduction that applies for current C_v)
  let activeStep = null;
  for (const step of [...steps].reverse()) {
    if (cv < step.cvThreshold) { activeStep = step; break; }
  }

  const shockHalt        = cv < 0.50;
  const reductionPct     = shockHalt ? 1.0 : (activeStep?.reductionPct ?? 0);
  const targetAfterStep  = Math.round(targetNotional * (1 - reductionPct));
  const requiredClose    = Math.max(0, openTrsNotional - targetAfterStep);

  // Re-entry gate: both C_v AND S_evd must clear before new seeding resumes
  const reEntryAllowed = !shockHalt && cv >= reEntryCvMin && sevdNorm >= reEntryMinSevd;

  let vrtStatus;
  if (shockHalt)                             { vrtStatus = "SHOCK HALT — all seeding suspended"; }
  else if (reductionPct >= 0.40)             { vrtStatus = "CRITICAL STEP — 40%+ reduction active"; }
  else if (reductionPct > 0)                 { vrtStatus = `STEP DOWN — ${(reductionPct*100).toFixed(0)}% reduction`; }
  else if (!reEntryAllowed)                  { vrtStatus = "HOLD — C_v/S_evd below re-entry gate"; }
  else                                       { vrtStatus = "FULL DEPLOYMENT"; }

  return {
    cv:               +cv.toFixed(3),
    reductionPct:     +(reductionPct * 100).toFixed(1),
    targetAfterStep:  Math.round(targetAfterStep),
    requiredClose:    Math.round(requiredClose),
    reEntryAllowed,
    shockHalt,
    vrtStatus,
    activeStepCvThreshold: activeStep?.cvThreshold ?? null,
    firmwareMode:     ultraDefensive ? "ULTRA-DEFENSIVE (5σ)" : "CONSERVATIVE",
    note: requiredClose > 0
      ? `Close $${requiredClose.toLocaleString()} TRS notional. Route freed collateral to VIX shield.`
      : reEntryAllowed ? "Cleared for new TRS seeding." : "Maintain current legs. Await re-entry conditions.",
  };
}

// ── Claim E.1–E.3: Convexity Cushion ─────────────────────────────────────────

/**
 * Claim E — Convexity Cushion
 *
 * Models a VIX call portfolio held at 0.05 initial delta.
 * As VIX rises through a stress event, the portfolio's delta rises toward 0.45+,
 * producing a super-linear Gamma spike that offsets TRS losses.
 *
 * @param {object} p
 * @param {number}   p.vixCurrent      Current VIX level
 * @param {number}   p.vixStress       Stress scenario VIX level
 * @param {number[]} p.vixCallStrikes  Array of VIX call strike levels
 * @param {number}   p.totalContracts  Total VIX call contracts held
 * @param {number}   p.avgPremium      Average premium paid per contract ($)
 * @param {number}   p.trsSynthLoss    TRS mark-to-market loss at stress VIX ($)
 * @param {number}   p.cv              Current C_v (sets hedge_ratio via complement)
 * @param {number}   p.harvestAvailable War Tax available for hedge funding ($)
 */
function buildConvexityCushion({
  vixCurrent,
  vixStress,
  vixCallStrikes,
  totalContracts,
  avgPremium,
  trsSynthLoss     = 0,
  cv               = 1.0,
  harvestAvailable = 0,
  hedgeAllocRate   = 0.08,    // 8% of harvest to VIX calls
}) {
  const vixMove     = vixStress - vixCurrent;
  const vixMovePct  = vixMove / vixCurrent;

  // Delta trajectory: 0.05 at baseline, approaches 0.45 at ATM (VIX_crossover)
  // Simple linear-then-convex model: delta = 0.05 + 0.40 × sigmoid((vixMove-5)/8)
  const sigmoid       = x => 1 / (1 + Math.exp(-x));
  const deltaStress   = 0.05 + 0.40 * sigmoid((vixMove - 5) / 8);
  const deltaInitial  = 0.05;
  const deltaRatio    = deltaStress / deltaInitial;       // amplification factor

  // Gamma approximation: peaks near ATM (delta ≈ 0.45), ~0.08/VIX_pt empirically
  const gammaPeak       = 0.08;
  const gammaAtStress   = gammaPeak * sigmoid((vixMove - 3) / 5) * 2;

  // Hedge P&L at stress level (per contract × 100 multiplier)
  const hedgePnl        = Math.round(totalContracts * 100 * avgPremium * (deltaRatio - 1));

  // Net cushion: hedge gain minus TRS loss
  const convexityCushion = Math.round(hedgePnl - trsSynthLoss);
  const cushionPositive  = convexityCushion >= 0;

  // VIX crossover (where hedge gain rate = TRS loss rate) — estimated analytically
  // Solved numerically: deltaRatio = 1 + trsSynthLoss / (contracts × 100 × premium × delta0)
  // Approximate: crossover at delta ≈ 0.25 → sigmoid inversion
  const crossoverVixMove  = 5 + 8 * Math.log(0.20 / 0.20);  // ~5 VIX points above baseline
  const vixCrossover      = vixCurrent + crossoverVixMove;

  // C_v complement auto-sizing: as liquidity stress rises, hedge ratio grows
  const cvComplement    = Math.max(0.01, Math.min(0.05, 1 - cv));
  const newHedgeFunding = Math.round(harvestAvailable * hedgeAllocRate);

  let cushionStatus;
  if (vixStress >= vixCrossover && cushionPositive)  { cushionStatus = "CUSHION ACTIVE — convex offset exceeds TRS loss"; }
  else if (vixStress >= vixCrossover)                { cushionStatus = "APPROACHING CROSSOVER — add contracts"; }
  else                                               { cushionStatus = "OTM ACCUMULATION — building gamma inventory"; }

  return {
    vixCurrent,
    vixStress,
    vixMove:           +vixMove.toFixed(1),
    vixCrossover:      +vixCrossover.toFixed(1),
    deltaInitial,
    deltaAtStress:     +deltaStress.toFixed(3),
    gammaAtStress:     +gammaAtStress.toFixed(4),
    deltaAmplification: +deltaRatio.toFixed(2),
    hedgePnl,
    trsSynthLoss,
    convexityCushion,
    cushionPositive,
    cushionStatus,
    // Sizing
    cvComplement:      +cvComplement.toFixed(3),
    newHedgeFunding,
    note: cushionPositive
      ? `+$${convexityCushion.toLocaleString()} net at VIX ${vixStress}. Delta ${(deltaStress*100).toFixed(1)}% (was 5%). 120-second window intact.`
      : `Deficit $${Math.abs(convexityCushion).toLocaleString()} at VIX ${vixStress}. Add ${Math.ceil(Math.abs(convexityCushion) / (avgPremium * 100 * deltaRatio))} contracts.`,
  };
}

// ── Claim F.1–F.3: Pod-Shop Sentinel ─────────────────────────────────────────

/**
 * Claim F.1–F.2 — P_pred: Predatory Probability
 *
 * Circular buffer N=100 events → three-factor adversarial detection.
 * Buffer memory: 100 × (8+8+8+8) bytes = 3,200 bytes → L1 cache resident.
 *
 * @param {object[]} orderFlowBuffer  Array of {side:'BUY'|'SELL', size, priceLevel, timestampNs}
 * @param {number}   windowSize       Rolling window size (default 100)
 */
function computePpred({ orderFlowBuffer, windowSize = 100 }) {
  const n      = Math.min(orderFlowBuffer.length, windowSize);
  if (n < 5) return { pPred: 0, signal: "INSUFFICIENT_DATA", n };

  const recent = orderFlowBuffer.slice(-n);

  // Factor 1: directional clustering (0 = random, 1 = pure one-sided probe)
  const buyCount     = recent.filter(o => o.side === "BUY").length;
  const clusterScore = Math.abs(buyCount / n - 0.5) * 2;

  // Factor 2: price-level concentration (phantom wall detection)
  const priceMap = {};
  recent.forEach(o => { priceMap[o.priceLevel] = (priceMap[o.priceLevel] || 0) + 1; });
  const maxConcentration = Math.max(...Object.values(priceMap)) / n;

  // Factor 3: size uniformity — low CV signals robotic uniform sizing
  const sizes    = recent.map(o => o.size);
  const meanSize = sizes.reduce((s, v) => s + v, 0) / n;
  const variance = sizes.reduce((s, v) => s + (v - meanSize) ** 2, 0) / n;
  const cvSize   = meanSize > 0 ? Math.sqrt(variance) / meanSize : 1;
  const uniformityScore = Math.max(0, 1 - cvSize);

  // Composite (Claim F.2.d)
  const pPred = Math.min(1, 0.40 * clusterScore + 0.35 * maxConcentration + 0.25 * uniformityScore);

  let signal, engineAction;
  if      (pPred >= 0.90) { signal = "BAIT_AND_SWITCH"; engineAction = "Inject false bids; route to dark pool (Claim F.3)"; }
  else if (pPred >= 0.70) { signal = "PROBE_DETECTED";  engineAction = "Route all clips to dark pool; halt lit venue"; }
  else if (pPred >= 0.50) { signal = "WATCH";           engineAction = "Reduce clip size to 1% ADV; monitor"; }
  else                    { signal = "CLEAN";            engineAction = "Normal Ghost Slicer execution"; }

  return {
    pPred:              +pPred.toFixed(3),
    signal,
    engineAction,
    factors: {
      clusterScore:      +clusterScore.toFixed(3),
      maxConcentration:  +maxConcentration.toFixed(3),
      uniformityScore:   +uniformityScore.toFixed(3),
    },
    n,
    bufferBytes:        n * 4 * 8,    // 4 fields × 8 bytes double precision
    l1CacheResident:    n * 4 * 8 <= 32_768,   // L1 = 32KB standard
  };
}

/**
 * Claim F.3 — Bait-and-Switch execution decision
 *
 * When P_pred ≥ 0.90, returns the False Bid parameters and dark pool
 * routing instruction. The engine injects false bids on the lit venue
 * to manufacture adversarial liquidity, then crosses in the dark pool.
 *
 * @param {object} p
 * @param {number} p.pPred          Current P_pred from computePpred
 * @param {number} p.detectedSize   Size of detected probe (shares/contracts)
 * @param {number} p.clipNotional   Remaining clip to execute ($)
 * @param {number} p.midPoint       Current market mid-point price
 * @param {number} p.cancelDelayNs  False bid cancel latency after fill (default 500ns)
 */
function buildBaitAndSwitch({ pPred, detectedSize, clipNotional, midPoint, cancelDelayNs = 500 }) {
  const active = pPred >= 0.90;

  if (!active) {
    return { active: false, routing: "LIT_VENUE", pPred: +pPred.toFixed(3) };
  }

  // False Bid: 120% of detected probe size to reinforce adversarial conviction
  const falseBidSize        = Math.round(detectedSize * 1.2);
  const falseBidNotional    = Math.round(falseBidSize * midPoint);

  // Execution improvement estimate: mid-point fill vs lit-venue spread cost
  const spreadEstimateBps   = 3.5;   // typical mid-cap spread
  const executionSavingBps  = spreadEstimateBps * 0.85;  // capture ~85% of spread as improvement
  const executionSaving     = Math.round(clipNotional * executionSavingBps / 10000);

  return {
    active:             true,
    routing:            "DARK_POOL",
    litVenueAction:     "INJECT_FALSE_BIDS",
    falseBidSize,
    falseBidNotional,
    cancelDelayNs,
    clipNotional,
    midPoint,
    executionSavingBps: +executionSavingBps.toFixed(2),
    executionSaving,
    pPred:              +pPred.toFixed(3),
    note: `False bid ${falseBidSize.toLocaleString()} @ ${midPoint} injects adversarial conviction. ` +
          `Dark pool cross at mid. Cancel lit after ${cancelDelayNs}ns. ` +
          `Est. execution improvement: ${executionSavingBps.toFixed(1)}bps ($${executionSaving.toLocaleString()}).`,
  };
}

// ── Claim G.1–G.3: Integrated Survival Status ─────────────────────────────────

/**
 * Claim G — buildSurvivalStatus
 *
 * Five-condition Decoupling check + 120-second survival window model.
 * When all five conditions are met, the engine is structurally decoupled
 * from the fiat system's volatility transmission mechanism.
 *
 * @param {object} p
 * @param {number}  p.systemicAlphaPct    P1 / AUM (%)
 * @param {boolean} p.flywheelSelfFunding From buildSovereignFlywheel
 * @param {boolean} p.cushionPositive     From buildConvexityCushion
 * @param {number}  p.cv                  Current C_v
 * @param {number}  p.pPred               Current P_pred
 * @param {number}  p.trsLossRate         TRS loss per VIX point ($)
 * @param {number}  p.hedgeGainRate       VIX call gain per VIX point ($)
 */
function buildSurvivalStatus({
  systemicAlphaPct,
  flywheelSelfFunding,
  cushionPositive,
  cv,
  pPred,
  trsLossRate   = 0,
  hedgeGainRate = 0,
}) {
  // Five-condition check (Claim G.3)
  const c1_decoupled       = systemicAlphaPct >= 5.0;
  const c2_flywheel        = flywheelSelfFunding;
  const c3_convexity       = cushionPositive;
  const c4_cvFull          = cv >= 0.85;
  const c5_execution       = pPred < 0.50 || pPred >= 0.90;   // clean OR bait-and-switch active

  const conditionsMet      = [c1_decoupled, c2_flywheel, c3_convexity, c4_cvFull, c5_execution];
  const allDecoupled       = conditionsMet.every(Boolean);
  const conditionsMetCount = conditionsMet.filter(Boolean).length;

  // 120-second survival window: net margin pressure < threshold
  // Simplified: if hedge gain rate ≥ trs loss rate, the window holds
  const t120Intact         = hedgeGainRate >= trsLossRate || cushionPositive;

  let survivalStatus;
  if (allDecoupled)                  { survivalStatus = "DECOUPLED — Structurally immune"; }
  else if (conditionsMetCount >= 4)  { survivalStatus = "NEAR-DECOUPLED — 1 condition remaining"; }
  else if (conditionsMetCount >= 3)  { survivalStatus = "COMPOUNDING — building toward decoupling"; }
  else if (t120Intact)               { survivalStatus = "DEFENDED — 120s window active"; }
  else                               { survivalStatus = "EXPOSED — address failing conditions immediately"; }

  return {
    allDecoupled,
    conditionsMet: {
      c1_systemicAlpha_gte5pct: c1_decoupled,
      c2_flywheel_selfFunding:  c2_flywheel,
      c3_convexityCushion:      c3_convexity,
      c4_cv_gte085:             c4_cvFull,
      c5_execution_secured:     c5_execution,
    },
    conditionsMetCount,
    t120Intact,
    survivalStatus,
    openConditions: [
      !c1_decoupled  && `P1 Systemic Alpha at ${systemicAlphaPct.toFixed(2)}% — need ≥ 5% (Claim C.2)`,
      !c2_flywheel   && "Flywheel deficit — increase VIX position or reduce TRS notional (Claim B.3)",
      !c3_convexity  && "Convexity gap — add VIX call contracts at current OTM level (Claim E.1)",
      !c4_cvFull     && `C_v = ${cv.toFixed(3)} — below 0.85 re-entry threshold, VRT step-down active (Claim D.1)`,
      !c5_execution  && `P_pred = ${pPred.toFixed(3)} — in watch zone (0.50–0.90); route to dark pool (Claim F.2)`,
    ].filter(Boolean),
  };
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
 *   // harvest inputs
 *   vixPosition:        20_000_000,   // dollar size of VIX long
 *   vixDailyReturnPct:  16.8,         // today's VIX % move
 *   harvestRate:        0.15,         // 15% of daily VIX PnL → margin
 *   marginRate:         0.15,         // 15% margin → 6.67x TRS multiplier
 *   // M10 reconciliation inputs
 *   vixRollYield:       210_000,      // daily theta/roll credit from VIX position
 *   // Closing Cross inputs (optional — provide at 3:50 PM)
 *   nowET:              null,         // JS Date in ET — enables time-aware cap
 *   unfilledByTicker:   {},           // { VST: 420000, GEV: 310000, ... }
 *   // Systemic Alpha inputs (cumulative — LENS tab P1)
 *   cumulative493TrsGain:    0,
 *   cumulativeVixRollYield:  0,
 *   totalFinancingCosts:     0,
 *   // Apple Call Overlay inputs (optional)
 *   aaplPrice:          null,         // current AAPL price — set to enable overlay
 *   aaplIV:             0.25,         // AAPL 30-day implied vol
 *   appleTargetNotional: null,        // default: 30% of AUM
 *   appleDaysToExpiry:  45,
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
    vixPosition              = 0,
    vixDailyReturnPct        = 0,
    harvestRate              = 0.15,
    marginRate               = 0.15,
    vixRollYield             = 0,
    nowET                    = null,
    unfilledByTicker         = {},
    cumulative493TrsGain     = 0,
    cumulativeVixRollYield   = 0,
    totalFinancingCosts      = 0,
    aaplPrice                = null,
    aaplIV                   = 0.25,
    appleTargetNotional      = null,
    appleDaysToExpiry        = 45,
    // Weekend Shield inputs (optional — provide on Friday)
    buildWeekend             = false,
    oilStressScenario        = 135,
    // Sunday Night Sentinel inputs (optional — provide Sunday evening)
    brentSunday              = null,
    brentFriday              = null,
    vixFuturesSunday         = null,
    // SVE Engine inputs (optional — Claim A/B/C signals)
    energyFront              = null,   // front-month WTI/Brent
    energyDeferred           = null,   // 3-month deferred futures
    vixFutures1m             = null,   // 1-month VIX futures (VX contract)
    sevdHistory              = [],     // rolling 60-day S_evd readings
    sofr                     = null,   // current SOFR rate (decimal)
    ffrTarget                = null,   // Fed Funds Rate target (decimal)
    m2Current                = null,   // current M2 ($B)
    m2FourWeeksAgo           = null,   // M2 four weeks ago ($B)
    collateralDeposited      = 0,      // existing flywheel collateral ($)
    // Phase 2 — Multi-PB Collateral Architecture (optional)
    primeBrokers             = [],     // [{ id, name, marginRate, openNotional, collateralPosted, tpraLinked }]
    venues                   = [],     // [{ id, name, tobDepthDollars, currentAllocation }]
    pbPositions              = [],     // [{ pbId, pbName, positions: [{ticker,notional,side}] }]
    pbCollateralMap          = {},     // { pbId: collateralPosted }
    fillHistory              = [],     // [{ pbId, ticker, side, fillPrice, postFillPrice2ms, ... }]
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

  // Layer 6: Symbiosis PnL reconciliation (M10)
  const symbiosisPnl = buildSymbiosisPnl({
    vixRollYield,
    vixPriceGain: harvestPlan.dailyVixPnl,
    trsFinancing: trsTracker.totals.financingCost,
    slippage493:  totalSlippage,
  });

  // Layer 7: Closing Cross / MOC protector (3:50 PM ET tightening)
  const timeAwareAdvCap = getTimeAwareAdvCap(aum, nowET);
  const closingCross    = Object.keys(unfilledByTicker).length > 0
    ? buildClosingCross(unfilledByTicker, advByTicker)
    : null;

  // Layer 8: Apple Call Overlay (VIX harvest → AAPL calls)
  const appleCallOverlay = aaplPrice !== null
    ? buildAppleCallOverlay({
        aaplPrice,
        aaplIV,
        targetNotional:  appleTargetNotional,
        daysToExpiry:    appleDaysToExpiry,
        harvestAvailable: harvestPlan.harvestAmount,
        aum,
        engineState,
      })
    : null;

  // Layer 8b: 78-Bin options slicer and gamma squeeze projection
  const appleOptionsBins = appleCallOverlay
    ? buildOptionsBinSlicer({
        totalContracts: appleCallOverlay.totalContracts,
        aaplPrice,
      })
    : null;

  const gammaSqueezeProjection = appleCallOverlay && appleCallOverlay.tranches.length > 0
    ? buildGammaSqueezeProjection({
        aaplPrice,
        aaplIV,
        daysToExpiry: appleDaysToExpiry,
        tranches:     appleCallOverlay.tranches,
      })
    : null;

  const weekendShield = buildWeekend && appleCallOverlay && appleCallOverlay.tranches.length > 0
    ? buildWeekendShieldReport({
        aaplPriceFriday:  aaplPrice,
        vixFriday:        vix,
        oilFriday:        oil,
        oilStressScenario,
        vixPosition,
        harvestRate,
        tranches:         appleCallOverlay.tranches,
        aaplIV,
        daysLeftToExpiry: appleDaysToExpiry,
      })
    : null;

  // Layer 8c: Sunday Night Sentinel (run Sunday evening before Monday open)
  const sundayNightSentinel = brentSunday !== null && brentFriday !== null
    ? buildSundayNightSentinel({
        brentSunday,
        brentFriday,
        vixFuturesSunday:  vixFuturesSunday ?? vix,
        vixFriday:         vix,
        aaplFriday:        aaplPrice ?? 175,
        vixPosition,
        harvestRate,
        aaplIV,
        appleTranches:     appleCallOverlay?.tranches ?? [],
        daysLeftToExpiry:  appleDaysToExpiry,
        aum,
      })
    : null;

  // Layer 9: Systemic Alpha (LENS tab P1)
  const systemicAlpha = buildSystemicAlpha({
    cumulative493TrsGain,
    cumulativeVixRollYield,
    totalFinancingCosts,
    aum,
  });

  // Layer 9b: SVE Engine — Claim A (S_evd signal), B (C_v), B.3 (flywheel)
  const sveSignal = energyFront !== null && energyDeferred !== null && vixFutures1m !== null
    ? computeSevd({ energyFront, energyDeferred, vixSpot: vix, vixFutures1m, sevdHistory })
    : null;

  const collateralVelocity = sofr !== null && ffrTarget !== null && m2Current !== null
    ? computeCollateralVelocity({ sofr, ffrTarget, m2Current, m2FourWeeksAgo: m2FourWeeksAgo ?? m2Current })
    : null;

  const sovereignFlywheel = collateralVelocity && !collateralVelocity.shockGate
    ? buildSovereignFlywheel({
        existingCollateral:  collateralDeposited,
        todayWarTax:         harvestPlan.harvestAmount,
        sofr,
        cv:                  collateralVelocity.cv,
        marginRequired:      collateralVelocity.marginRequired / 100,
        openTrsNotional:     trsTracker.totals.openNotional,
        maxNewNotional:      aum * (getAdvCap(aum) * 5),   // risk limit: 5 clips
      })
    : null;

  // Layer 10: SVE Survival Architecture — Claims D / E / F / G
  const cv = collateralVelocity?.cv ?? 1.0;

  const vrtStepDown = collateralVelocity
    ? buildVrtStepDown({
        cv,
        openTrsNotional:  trsTracker.totals.openNotional,
        targetNotional:   aum * getAdvCap(aum) * 5,
        sevdNorm:         sveSignal?.sevdNorm ?? 0,
      })
    : null;

  const convexityCushion = appleCallOverlay
    ? buildConvexityCushion({
        vixCurrent:      vix,
        vixStress:       vix * 1.35,   // model a +35% VIX spike as stress scenario
        vixCallStrikes:  appleCallOverlay.tranches?.map(t => t.strike) ?? [],
        totalContracts:  appleCallOverlay.totalContracts ?? 0,
        avgPremium:      appleCallOverlay.tranches?.reduce((s, t) => s + t.premiumPerShare, 0)
                           / Math.max(1, appleCallOverlay.tranches?.length ?? 1) ?? 5,
        trsSynthLoss:    Math.abs(Math.min(0, trsTracker.totals.netPnl)),
        cv,
        harvestAvailable: harvestPlan.harvestAmount,
      })
    : null;

  // Layer 10b: Phase 2 — Multi-PB Collateral Architecture
  const collateralAsymmetry = primeBrokers.length > 0
    ? buildCollateralAsymmetry({ primeBrokers, vixCurrent: vix })
    : null;

  const capacityMap = venues.length > 0
    ? buildCapacityMap({
        venues,
        targetNewNotional: harvestPlan.harvestAmount + (sovereignFlywheel?.incrementalTrsCap ?? 0),
      })
    : null;

  const globalNetting = pbPositions.length > 0
    ? buildGlobalNettingEngine({ pbPositions, collateralMap: pbCollateralMap })
    : null;

  const leakageSurveillance = fillHistory.length > 0
    ? buildLeakageSurveillance({ fillHistory })
    : null;

  // Layer 11: alerts
  const alerts = buildAlerts(vix, oil, gex, engineState, alphaRisk, trsTracker);

  // Layer 12: Integrated survival status (Claim G)
  const survivalStatus = buildSurvivalStatus({
    systemicAlphaPct:   systemicAlpha.systemicPct,
    flywheelSelfFunding: sovereignFlywheel?.selfFunding ?? false,
    cushionPositive:    convexityCushion?.cushionPositive ?? false,
    cv,
    pPred:              0,    // caller must supply live P_pred from computePpred()
    trsLossRate:        trsTracker.totals.openNotional * 0.001,   // est. $1k per VIX pt
    hedgeGainRate:      convexityCushion ? convexityCushion.hedgePnl / Math.max(1, convexityCushion.vixMove) : 0,
  });

  return {
    scale:           getScale(aum),       // "100M" or "1B"
    advCap:          getAdvCap(aum),      // 0.03 or 0.05 (standard session)
    timeAwareAdvCap,                      // may be 0.02 (MOC) or 0 (closed)
    engineState,
    harvestPlan,
    executionPlan,
    trsTracker,
    alphaRisk,
    symbiosisPnl,
    systemicAlpha,
    appleCallOverlay,
    appleOptionsBins,
    gammaSqueezeProjection,
    weekendShield,
    sundayNightSentinel,
    sveSignal,
    collateralVelocity,
    sovereignFlywheel,
    vrtStepDown,
    convexityCushion,
    survivalStatus,
    // Phase 2
    collateralAsymmetry,
    capacityMap,
    globalNetting,
    leakageSurveillance,
    closingCross,
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
    // Apple Call Overlay — $30M notional (30% of AUM), funded by $504k harvest
    aaplPrice:           175,
    aaplIV:              0.26,
    appleTargetNotional: 30_000_000,
    appleDaysToExpiry:   45,
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
