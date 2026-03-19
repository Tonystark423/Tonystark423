/**
 * ECOSYSTEM GUARDIAN ENGINE v1.0
 * Manages Scaling, Synthetics, and VIX Alpha Recycling.
 */

function updateEngineStatus(aum, vix, oil, gex) {
  const status = {
    allocation: "",
    action: "",
    riskLevel: ""
  };

  // 1. Scaling Logic: Physical vs Synthetic
  if (aum >= 1000000000) {
    status.allocation = "70% Synthetic (TRS) / 30% Physical";
  } else if (aum >= 100000000) {
    status.allocation = "30% Synthetic / 70% Physical";
  } else {
    status.allocation = "100% Physical (Direct Equity)";
  }

  // 2. The Shield Trigger (VIX & Gamma)
  if (vix > 25 && gex < 0) {
    // Extreme vol + negative gamma: dealers are short gamma, accelerating moves
    status.action = "SHIELD ACTIVE: Do Not Sell VIX. Hold 493 Floor.";
    status.riskLevel = "CRITICAL";
  } else if (vix > 25 && gex >= 0) {
    // Extreme vol but positive gamma: dealers absorb moves, reduce synthetic exposure
    status.action = "HEDGE: Trim Synthetic Legs. Await Gamma Flip Confirmation.";
    status.riskLevel = "HIGH";
  } else if (vix > 22 && oil > 115) {
    // Elevated vol + oil shock: recycle VIX premium into energy-resilient names
    status.action = "RECYCLE: Harvest VIX Alpha -> Buy Energy-Resilient 493.";
    status.riskLevel = "ELEVATED";
  } else if (vix > 20) {
    // Early vol expansion: watch for regime change, no action yet
    status.action = "WATCH: Monitor VIX Expansion. Prepare Shield Parameters.";
    status.riskLevel = "WARNING";
  } else {
    // Calm market: run full alpha capture
    status.action = "SYMBIOSIS: Maintain Core 493 Alpha Long.";
    status.riskLevel = "NORMAL";
  }

  return status;
}
