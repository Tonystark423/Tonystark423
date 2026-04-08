"""
Volatility Harvesting Engine
=============================
Core thesis: VIX premium mean-reverts. The spike IS the signal.
Waiting for news confirmation = entering after the premium collapses.

Modules
-------
  1. VIX Regime Detector      — classify current vol environment
  2. Premium Decay Model       — how fast harvested premium erodes post-spike
  3. Entry Timing Analyser     — quantify the cost of news-lag
  4. Harvesting P&L Simulator  — systematic vol-sell vs news-follower comparison
  5. Term Structure Scanner    — contango vs backwardation signal

Key insight
-----------
  Implied Vol (IV) > Realised Vol (RV) on average ~80% of the time.
  That spread is the harvestable premium.
  During a VIX spike the spread widens dramatically — then mean-reverts
  in days, not weeks. A news-based entry lags by 3–10 days and captures
  only the tail of the premium, not the spike itself.
"""

from __future__ import annotations

import math
import json
import random
import statistics
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# 1. VIX Regime Detector
# ---------------------------------------------------------------------------

class VIXRegime(Enum):
    CALM        = "CALM        (VIX  < 15)  — low premium, avoid selling"
    NORMAL      = "NORMAL      (VIX 15–20)  — fair premium, selective entry"
    ELEVATED    = "ELEVATED    (VIX 20–28)  — good premium, scale in"
    SPIKE       = "SPIKE       (VIX 28–40)  — peak premium, primary harvest zone"
    PANIC       = "PANIC       (VIX  > 40)  — extreme premium, size carefully"


def classify_vix(vix: float) -> VIXRegime:
    if vix < 15:
        return VIXRegime.CALM
    elif vix < 20:
        return VIXRegime.NORMAL
    elif vix < 28:
        return VIXRegime.ELEVATED
    elif vix < 40:
        return VIXRegime.SPIKE
    else:
        return VIXRegime.PANIC


def iv_rv_spread(vix: float, realised_vol_ann: float) -> dict:
    """
    The harvestable premium = IV - RV.
    IV is approximated from VIX (VIX ≈ 30-day implied vol in annualised %).
    """
    iv      = vix / 100.0          # VIX 25 => IV = 25% annualised
    spread  = iv - realised_vol_ann
    ratio   = iv / realised_vol_ann if realised_vol_ann else float("inf")

    return {
        "vix":             vix,
        "implied_vol":     iv,
        "realised_vol":    realised_vol_ann,
        "spread":          spread,
        "iv_rv_ratio":     ratio,
        "regime":          classify_vix(vix).value,
        "harvestable":     spread > 0,
        "premium_quality": _premium_quality(ratio),
    }


def _premium_quality(ratio: float) -> str:
    if ratio < 1.0:
        return "NEGATIVE — RV > IV, do not sell vol"
    elif ratio < 1.2:
        return "THIN     — marginal premium"
    elif ratio < 1.5:
        return "FAIR     — normal carry"
    elif ratio < 2.0:
        return "RICH     — spike territory, good entry"
    else:
        return "EXTREME  — panic premium, best harvest entry"


# ---------------------------------------------------------------------------
# 2. Premium Decay Model (mean-reversion of VIX post-spike)
# ---------------------------------------------------------------------------

def vix_mean_reversion(
    vix_spike: float,
    vix_long_run: float = 18.0,
    half_life_days: int = 10,
    days: int = 30,
) -> list[dict]:
    """
    Ornstein–Uhlenbeck mean reversion for VIX post-spike.

        dVIX = κ(μ - VIX)dt    (drift only, no noise for clarity)
        κ = ln(2) / half_life

    half_life_days: days for VIX to close half the gap to long-run mean.
    """
    kappa = math.log(2) / half_life_days
    path  = []
    vix   = vix_spike

    for day in range(days + 1):
        premium_remaining = (vix - vix_long_run) / (vix_spike - vix_long_run)
        path.append({
            "day":               day,
            "vix":               vix,
            "premium_pct_left":  max(premium_remaining, 0.0),
            "premium_decayed":   max(1.0 - premium_remaining, 0.0),
        })
        # OU step
        vix = vix + kappa * (vix_long_run - vix)
        vix = max(vix, vix_long_run)

    return path


# ---------------------------------------------------------------------------
# 3. Entry Timing Analyser — cost of news-lag
# ---------------------------------------------------------------------------

def news_lag_cost(
    decay_path: list[dict],
    immediate_entry_day: int = 1,
    news_entry_day: int = 7,        # "the bottom is in" lag
    option_premium_base: float = 0.08,  # 8% option premium at VIX spike
) -> dict:
    """
    Compare premium captured by immediate entry vs news-follower.

    Premium captured ≈ option_premium_base × premium_pct_left at entry day.
    """
    def get_pct(day: int) -> float:
        for pt in decay_path:
            if pt["day"] == day:
                return pt["premium_pct_left"]
        return 0.0

    pct_immediate = get_pct(immediate_entry_day)
    pct_news      = get_pct(news_entry_day)

    premium_immediate = option_premium_base * pct_immediate
    premium_news      = option_premium_base * pct_news
    premium_lost      = premium_immediate - premium_news
    pct_left_on_table = premium_lost / option_premium_base if option_premium_base else 0

    return {
        "immediate_entry_day":   immediate_entry_day,
        "news_entry_day":        news_entry_day,
        "pct_premium_at_entry_immediate": pct_immediate,
        "pct_premium_at_entry_news":      pct_news,
        "premium_captured_immediate":     premium_immediate,
        "premium_captured_news":          premium_news,
        "premium_left_on_table":          premium_lost,
        "pct_of_spike_missed":            pct_left_on_table,
    }


# ---------------------------------------------------------------------------
# 4. Harvesting P&L Simulator
# ---------------------------------------------------------------------------

@dataclass
class HarvestEvent:
    """Single vol-selling event."""
    day:          int
    vix_at_entry: float
    premium_sold: float      # option premium received
    realised_vol: float      # vol that actually occurred during the trade
    days_to_expiry: int = 21


def simulate_harvest_pnl(
    events: list[HarvestEvent],
    notional: float = 1_000_000,
) -> dict:
    """
    P&L for each harvest event.

    Simplified model:
      premium_received = premium_sold × notional
      realised_loss    = max(realised_vol - IV, 0) × notional × scaling
      net_pnl          = premium_received - realised_loss
    """
    records = []
    total_pnl = 0.0

    for ev in events:
        iv         = ev.vix_at_entry / 100.0
        daily_iv   = iv / math.sqrt(252)
        daily_rv   = ev.realised_vol / math.sqrt(252)
        vol_spread = daily_iv - daily_rv
        # P&L approximation: spread × sqrt(T) × notional × vega_scaling
        net = vol_spread * math.sqrt(ev.days_to_expiry) * notional * 0.4
        total_pnl += net
        records.append({
            "day":            ev.day,
            "vix_at_entry":   ev.vix_at_entry,
            "iv":             iv,
            "realised_vol":   ev.realised_vol,
            "vol_spread":     vol_spread,
            "net_pnl":        net,
            "regime":         classify_vix(ev.vix_at_entry).name,
        })

    wins  = [r for r in records if r["net_pnl"] > 0]
    losses= [r for r in records if r["net_pnl"] <= 0]

    return {
        "events":       records,
        "total_pnl":    total_pnl,
        "win_rate":     len(wins) / len(records) if records else 0,
        "avg_win":      statistics.mean(r["net_pnl"] for r in wins)  if wins   else 0,
        "avg_loss":     statistics.mean(r["net_pnl"] for r in losses) if losses else 0,
        "payoff_ratio": (
            abs(statistics.mean(r["net_pnl"] for r in wins) /
                statistics.mean(r["net_pnl"] for r in losses))
            if wins and losses else float("inf")
        ),
    }


# ---------------------------------------------------------------------------
# 5. Term Structure Scanner (Contango vs Backwardation)
# ---------------------------------------------------------------------------

def term_structure(
    spot_vix: float,
    vix1m: float,
    vix3m: float,
    vix6m: float,
) -> dict:
    """
    VIX term structure shape signals regime and carry direction.

    Contango  (spot < 1m < 3m < 6m): normal market, roll-down carry positive
    Backwardation (spot > 1m > 3m):  stress/panic — near-term fear > future fear
    """
    contango = spot_vix < vix1m < vix3m < vix6m
    backwardation = spot_vix > vix1m > vix3m

    roll_yield_1m = (vix1m - spot_vix) / spot_vix   # positive = contango carry
    shape = (
        "CONTANGO     — roll-down carry positive; calm conditions"
        if contango else
        "BACKWARDATION — near-term panic; spike harvest opportunity"
        if backwardation else
        "MIXED        — partial inversion; transition phase"
    )

    return {
        "spot_vix":    spot_vix,
        "vix_1m":      vix1m,
        "vix_3m":      vix3m,
        "vix_6m":      vix6m,
        "shape":       shape,
        "contango":    contango,
        "backwardation": backwardation,
        "roll_yield_1m": roll_yield_1m,
        "harvest_signal": backwardation or spot_vix > 28,
    }


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _pct(v: float, w: int = 7) -> str:
    return f"{v*100:+{w}.2f}%"


def print_regime(spread_result: dict) -> None:
    print("\n" + "=" * 65)
    print("  VIX REGIME & IV/RV SPREAD")
    print("=" * 65)
    print(f"  VIX (Implied Vol)    : {spread_result['vix']:.1f}  ({_pct(spread_result['implied_vol'])} ann)")
    print(f"  Realised Vol         : {_pct(spread_result['realised_vol'])} ann")
    print(f"  Harvestable Spread   : {_pct(spread_result['spread'])}")
    print(f"  IV/RV Ratio          : {spread_result['iv_rv_ratio']:.2f}x")
    print(f"  Premium Quality      : {spread_result['premium_quality']}")
    print(f"  Regime               : {spread_result['regime']}")


def print_decay(path: list[dict], spike_vix: float) -> None:
    print("\n" + "=" * 65)
    print(f"  VIX MEAN REVERSION — post-spike from {spike_vix:.0f}")
    print("=" * 65)
    print(f"  {'Day':>4}  {'VIX':>6}  {'Premium Left':>13}  {'Bar'}")
    print(f"  {'-'*55}")
    for pt in path:
        if pt["day"] % 3 == 0 or pt["day"] <= 2:
            bar = "█" * int(pt["premium_pct_left"] * 30)
            news_flag = " << news confirms 'bottom'" if pt["day"] == 7 else ""
            entry_flag = " << HARVEST ENTRY" if pt["day"] == 1 else ""
            print(
                f"  {pt['day']:>4}  {pt['vix']:>6.1f}  "
                f"{pt['premium_pct_left']*100:>12.1f}%  "
                f"{bar}{entry_flag}{news_flag}"
            )


def print_lag_cost(lag: dict) -> None:
    print("\n" + "=" * 65)
    print("  NEWS-LAG COST ANALYSIS")
    print("=" * 65)
    print(f"  Immediate entry (Day {lag['immediate_entry_day']:>2}):")
    print(f"    Premium captured  : {_pct(lag['premium_captured_immediate'])}")
    print(f"    % of spike premium: {lag['pct_premium_at_entry_immediate']*100:.1f}%")
    print(f"\n  News-follower (Day {lag['news_entry_day']:>2} — 'bottom is in'):  ")
    print(f"    Premium captured  : {_pct(lag['premium_captured_news'])}")
    print(f"    % of spike premium: {lag['pct_premium_at_entry_news']*100:.1f}%")
    print(f"\n  Premium left on table : {_pct(lag['premium_left_on_table'])}")
    print(f"  Fraction of spike missed: {lag['pct_of_spike_missed']*100:.1f}%")
    print(f"\n  >> By Day 7 the VIX has already mean-reverted ~{lag['pct_of_spike_missed']*100:.0f}% of the way back.")
    print(f"     The news told you the trade was safe — right as the trade was over.")


def print_harvest_pnl(result: dict) -> None:
    print("\n" + "=" * 65)
    print("  HARVEST P&L — Systematic Vol Seller")
    print("=" * 65)
    print(f"  {'Day':>4}  {'VIX':>6}  {'Regime':<12}  {'Vol Spread':>11}  {'Net P&L':>12}")
    print(f"  {'-'*58}")
    for ev in result["events"]:
        print(
            f"  {ev['day']:>4}  {ev['vix_at_entry']:>6.1f}  "
            f"{ev['regime']:<12}  "
            f"{_pct(ev['vol_spread']):>11}  "
            f"${ev['net_pnl']:>10,.0f}"
        )
    print(f"  {'-'*58}")
    print(f"  Total P&L    : ${result['total_pnl']:>12,.0f}")
    print(f"  Win Rate     : {result['win_rate']*100:.0f}%")
    print(f"  Avg Win      : ${result['avg_win']:>10,.0f}")
    print(f"  Avg Loss     : ${result['avg_loss']:>10,.0f}")
    print(f"  Payoff Ratio : {result['payoff_ratio']:.2f}x")


def print_term_structure(ts: dict) -> None:
    print("\n" + "=" * 65)
    print("  VIX TERM STRUCTURE")
    print("=" * 65)
    print(f"  Spot VIX   : {ts['spot_vix']:.1f}")
    print(f"  1M VIX     : {ts['vix_1m']:.1f}")
    print(f"  3M VIX     : {ts['vix_3m']:.1f}")
    print(f"  6M VIX     : {ts['vix_6m']:.1f}")
    print(f"  Shape      : {ts['shape']}")
    print(f"  Roll Yield : {_pct(ts['roll_yield_1m'])}  (1M)")
    print(f"  Harvest Signal: {'YES — enter vol-sell' if ts['harvest_signal'] else 'NO  — wait'}")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    print("VOLATILITY HARVESTING ENGINE")
    print("=" * 65)

    # --- 1. Regime at VIX=35 (spike), RV=18% ---
    spread = iv_rv_spread(vix=35.0, realised_vol_ann=0.18)
    print_regime(spread)

    # --- 2. Decay path from VIX=35 spike ---
    decay = vix_mean_reversion(vix_spike=35.0, vix_long_run=18.0, half_life_days=10, days=21)
    print_decay(decay, spike_vix=35.0)

    # --- 3. News-lag cost ---
    lag = news_lag_cost(
        decay_path           = decay,
        immediate_entry_day  = 1,
        news_entry_day       = 7,
        option_premium_base  = 0.08,
    )
    print_lag_cost(lag)

    # --- 4. Harvest P&L across a year of events ---
    events = [
        HarvestEvent(day=  5, vix_at_entry=37.0, premium_sold=0.09, realised_vol=0.22),
        HarvestEvent(day= 28, vix_at_entry=29.5, premium_sold=0.06, realised_vol=0.19),
        HarvestEvent(day= 61, vix_at_entry=22.0, premium_sold=0.04, realised_vol=0.17),
        HarvestEvent(day= 90, vix_at_entry=18.5, premium_sold=0.03, realised_vol=0.16),
        HarvestEvent(day=142, vix_at_entry=41.0, premium_sold=0.11, realised_vol=0.28),  # panic
        HarvestEvent(day=180, vix_at_entry=31.0, premium_sold=0.07, realised_vol=0.20),
        HarvestEvent(day=220, vix_at_entry=16.0, premium_sold=0.02, realised_vol=0.15),  # calm — thin
        HarvestEvent(day=255, vix_at_entry=33.0, premium_sold=0.08, realised_vol=0.21),
    ]
    harvest = simulate_harvest_pnl(events, notional=1_000_000)
    print_harvest_pnl(harvest)

    # --- 5. Term structure at the spike (backwardation = harvest signal) ---
    ts = term_structure(spot_vix=35.0, vix1m=30.0, vix3m=24.0, vix6m=21.0)
    print_term_structure(ts)

    # Save
    output = {
        "iv_rv_spread":    spread,
        "decay_path":      decay,
        "news_lag_cost":   lag,
        "harvest_pnl":     {k: v for k, v in harvest.items() if k != "events"},
        "term_structure":  ts,
    }
    with open("vol_harvesting_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: vol_harvesting_results.json")


if __name__ == "__main__":
    demo()
