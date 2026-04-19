"""
Crash Test & Convexity Analysis — "The Vault" vs "The Herd"
============================================================
Models:

  R_p = α + β(R_m) + Convexity(VIX)

Under a normal market:
  - Lower β because MAG7 is trimmed
  - Korea arb adds uncorrelated α

Under a crash (R_m < 0):
  - VIX spikes, VIX hedge pays out
  - Convexity kicks in, flattening drawdown — the "smile"
  - Cash / dry powder is preserved for buying the bottom

Key outputs
-----------
  1. Scenario table : portfolio vs benchmark across 5 market regimes
  2. Convexity curve : R_p for each R_m from -30% to +30%
  3. Crash test      : 20% market correction deep-dive
  4. Liquidation value : cash + hedge proceeds available to buy the dip
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Portfolio config
# ---------------------------------------------------------------------------

@dataclass
class VaultConfig:
    """Describes the active portfolio's key parameters."""
    # Beta vs broad market (lower than 1.0 due to MAG7 reduction)
    beta: float = 0.62

    # Unconditional alpha per period (Korea arb, carry, etc.)
    alpha: float = 0.018

    # VIX convexity coefficient:
    # For every 1% the market falls below 0, the VIX hedge offsets this fraction.
    vix_convexity: float = 0.35

    # VIX activation threshold — hedge only contributes when market falls past this
    vix_threshold: float = -0.05   # hedge activates at -5% market move

    # Cash / hedge weight available as dry powder after a crash
    cash_weight:      float = 0.10
    vix_hedge_weight: float = 0.08

    # VIX payoff multiplier in a crash (VIX typically 4–5x in a -20% event)
    vix_payoff_mult: float = 4.2


@dataclass
class HerdConfig:
    """Standard retail / closet-indexer portfolio."""
    beta:  float = 0.97    # near-index beta
    alpha: float = 0.003   # tiny alpha from slight tilt
    vix_convexity: float = 0.0   # no hedge
    vix_threshold: float = 0.0
    cash_weight:       float = 0.02
    vix_hedge_weight:  float = 0.00
    vix_payoff_mult:   float = 0.0


# ---------------------------------------------------------------------------
# Return model
# ---------------------------------------------------------------------------

def portfolio_return(r_market: float, cfg: VaultConfig | HerdConfig) -> float:
    """
    R_p = α + β·R_m + Convexity(VIX)

    Convexity term is only active when R_m < vix_threshold.
    It offsets a fraction of the downside via VIX payout.
    """
    linear   = cfg.alpha + cfg.beta * r_market
    convex   = 0.0

    if r_market < cfg.vix_threshold:
        excess_down = cfg.vix_threshold - r_market   # how far past threshold
        convex = cfg.vix_convexity * excess_down      # hedge offsets this fraction

    return linear + convex


def crash_detail(r_market: float, cfg: VaultConfig) -> dict:
    """
    Break down the portfolio return in a crash scenario.
    Returns all components and the resulting dry-powder available.
    """
    linear_loss  = cfg.beta * r_market
    alpha_cont   = cfg.alpha
    vix_cont     = 0.0
    vix_pnl      = 0.0

    if r_market < cfg.vix_threshold:
        excess_down = cfg.vix_threshold - r_market
        vix_cont    = cfg.vix_convexity * excess_down
        # Actual VIX P&L: hedge weight × payoff multiplier × |market move|
        vix_pnl = cfg.vix_hedge_weight * cfg.vix_payoff_mult * abs(r_market)

    r_p = portfolio_return(r_market, cfg)

    # Liquidation value = cash + VIX hedge proceeds (available to buy the dip)
    liquidation_value = cfg.cash_weight + vix_pnl

    return {
        "r_market":          r_market,
        "r_portfolio":       r_p,
        "alpha_contribution":alpha_cont,
        "linear_loss":       linear_loss,
        "vix_convexity_offset": vix_cont,
        "vix_pnl":           vix_pnl,
        "benchmark_drawdown":r_market,          # benchmark = market (β=1)
        "vault_vs_herd":     r_p - r_market,    # outperformance in the crash
        "liquidation_value": liquidation_value,  # dry powder for buying the bottom
    }


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    ("Melt-up  +30%",    +0.30),
    ("Strong   +15%",    +0.15),
    ("Flat      +2%",    +0.02),
    ("Mild correction -10%", -0.10),
    ("Crash   -20%",     -0.20),
    ("Severe  -30%",     -0.30),
]


def run_scenario_table(vault: VaultConfig, herd: HerdConfig) -> list[dict]:
    rows = []
    for label, r_m in SCENARIOS:
        r_vault = portfolio_return(r_m, vault)
        r_herd  = portfolio_return(r_m, herd)
        rows.append({
            "scenario":    label,
            "r_market":    r_m,
            "r_vault":     r_vault,
            "r_herd":      r_herd,
            "vault_edge":  r_vault - r_herd,
        })
    return rows


# ---------------------------------------------------------------------------
# Convexity curve (the "smile")
# ---------------------------------------------------------------------------

def convexity_curve(
    vault: VaultConfig,
    herd:  HerdConfig,
    steps: int = 25,
) -> list[dict]:
    """
    R_p for market moves from -35% to +35%.
    The "smile" appears below vix_threshold where convexity lifts the vault.
    """
    points = []
    lo, hi = -0.35, 0.35
    for i in range(steps + 1):
        r_m     = lo + (hi - lo) * i / steps
        r_vault = portfolio_return(r_m, vault)
        r_herd  = portfolio_return(r_m, herd)
        points.append({"r_market": r_m, "r_vault": r_vault, "r_herd": r_herd})
    return points


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _pct(v: float, width: int = 8) -> str:
    return f"{v*100:+{width}.2f}%"


def _bar(v: float, scale: float = 300.0, width: int = 30) -> str:
    filled = min(int(abs(v) * scale), width)
    if v >= 0:
        return " " * (width - filled) + "█" * filled + " | "
    else:
        return " " * width + " | " + "░" * filled


def print_scenario_table(rows: list[dict]) -> None:
    print("\n" + "=" * 72)
    print("  SCENARIO TABLE: The Vault vs The Herd")
    print("=" * 72)
    print(f"  {'Scenario':<26} {'Market':>8}  {'Vault':>8}  {'Herd':>8}  {'Edge':>8}")
    print(f"  {'-'*62}")
    for r in rows:
        edge_str = _pct(r["vault_edge"])
        flag = " <-- VAULT WINS" if r["vault_edge"] > 0 else ""
        print(
            f"  {r['scenario']:<26}"
            f"  {_pct(r['r_market'])}"
            f"  {_pct(r['r_vault'])}"
            f"  {_pct(r['r_herd'])}"
            f"  {edge_str}{flag}"
        )


def print_crash_test(detail: dict) -> None:
    print("\n" + "=" * 72)
    print("  CRASH TEST: -20% Market Correction")
    print("=" * 72)
    print(f"  Market drawdown          : {_pct(detail['r_market'])}")
    print(f"  Benchmark (Herd) loss    : {_pct(detail['benchmark_drawdown'])}")
    print(f"  Alpha contribution       : {_pct(detail['alpha_contribution'])}")
    print(f"  Linear (β × R_m)         : {_pct(detail['linear_loss'])}")
    print(f"  VIX convexity offset     : {_pct(detail['vix_convexity_offset'])}  <- the 'smile'")
    print(f"  VIX hedge P&L            : {_pct(detail['vix_pnl'])}")
    print(f"  ────────────────────────────────────────")
    print(f"  Vault portfolio return   : {_pct(detail['r_portfolio'])}")
    print(f"  Vault vs benchmark edge  : {_pct(detail['vault_vs_herd'])}")
    print(f"\n  Dry powder (liquidation value)")
    print(f"  Cash reserve             : 10.0%")
    print(f"  VIX proceeds             : {_pct(detail['vix_pnl'])}")
    print(f"  ──────────────────────────────")
    print(f"  Total available to buy   : {_pct(detail['liquidation_value'])}")
    print(f"\n  >> At -20%, the Herd is selling. The Vault is buying.")


def print_convexity_curve(curve: list[dict]) -> None:
    """ASCII 'smile' chart."""
    print("\n" + "=" * 72)
    print("  CONVEXITY CURVE — Return 'Smile'")
    print("  (Vault vs Herd across market moves, left=crash, right=melt-up)")
    print("=" * 72)
    mid = 35
    for pt in curve:
        r_m  = pt["r_market"]
        diff = pt["r_vault"] - pt["r_herd"]   # vault outperformance
        bar_len = int(abs(diff) * 400)
        bar_len = min(bar_len, mid)

        if diff >= 0:
            bar = " " * mid + "█" * bar_len
        else:
            bar = " " * (mid - bar_len) + "░" * bar_len

        smile_marker = " <-- smile" if r_m < -0.05 and diff > 0 else ""
        print(f"  R_m={_pct(r_m,6)}  {bar}{smile_marker}")

    print(f"\n  Legend: '█' = Vault outperforms  '░' = Vault underperforms")
    print(f"  The smile appears in crash territory (left side) where VIX fires.")
    print(f"  Vault trails in melt-ups — the accepted trade-off for crash protection.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def demo() -> None:
    vault = VaultConfig()
    herd  = HerdConfig()

    # Scenario table
    rows = run_scenario_table(vault, herd)
    print_scenario_table(rows)

    # 20% crash deep-dive
    crash = crash_detail(-0.20, vault)
    print_crash_test(crash)

    # Convexity smile
    curve = convexity_curve(vault, herd)
    print_convexity_curve(curve)

    # Save
    output = {
        "scenarios":        rows,
        "crash_test":       crash,
        "convexity_curve":  curve,
    }
    with open("stress_test_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: stress_test_results.json")


if __name__ == "__main__":
    demo()
