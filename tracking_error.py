"""
Tracking Error, Active Share & Return Distribution
===================================================
Answers three questions:
  1. TE    — how different is your return *stream* from the index?
             1-2%  => closet indexer
             7-12% => successfully decoupled (target zone)
  2. Active Share — how different are your *holdings* from the index?
             < 60% => closet indexer
             > 80% => high-conviction active
  3. Distribution signature — "The Vault" vs "The Herd"
             Plots the excess-return PDF of your portfolio alongside
             the benchmark so the asymmetric shape is visible.

Formulas
--------
  TE          = std(r_p - r_b) × sqrt(periods_per_year)
  Active Share = 0.5 × Σ |w_p_i - w_b_i|
  Excess ret  = r_portfolio_t - r_benchmark_t
"""

from __future__ import annotations

import math
import json
import random
import statistics
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ReturnSeries:
    """Paired portfolio / benchmark returns, one entry per period."""
    labels:      list[str]
    r_portfolio: list[float]   # portfolio returns each period
    r_benchmark: list[float]   # index returns each period (SPY / QQQ)
    periods_per_year: int = 4  # 4 = quarterly, 12 = monthly, 252 = daily


@dataclass
class Holding:
    """Single security weight in portfolio vs benchmark."""
    ticker: str
    w_portfolio: float   # weight in your portfolio  (0–1)
    w_benchmark: float   # weight in the index       (0–1)


# ---------------------------------------------------------------------------
# Tracking Error
# ---------------------------------------------------------------------------

def tracking_error(series: ReturnSeries) -> dict:
    """
    Annualised Tracking Error.

        TE = std( r_p - r_b ) × sqrt( periods_per_year )
    """
    if len(series.r_portfolio) != len(series.r_benchmark):
        raise ValueError("r_portfolio and r_benchmark must have equal length")
    if len(series.r_portfolio) < 2:
        raise ValueError("Need at least 2 periods to compute TE")

    excess = [rp - rb for rp, rb in zip(series.r_portfolio, series.r_benchmark)]
    std_excess = statistics.stdev(excess)
    te = std_excess * math.sqrt(series.periods_per_year)

    mean_excess = statistics.mean(excess)
    information_ratio = mean_excess * series.periods_per_year / te if te else 0.0

    return {
        "tracking_error_annualised": te,
        "mean_excess_return_per_period": mean_excess,
        "information_ratio": information_ratio,
        "n_periods": len(excess),
        "excess_returns": excess,
        "classification": _classify_te(te),
    }


def _classify_te(te: float) -> str:
    if te < 0.02:
        return "CLOSET INDEXER  (TE < 2%) — no meaningful decoupling"
    elif te < 0.04:
        return "LOW ACTIVE      (2–4%)   — slight tilt, still index-like"
    elif te < 0.07:
        return "MODERATE ACTIVE (4–7%)   — meaningful bets, some decoupling"
    elif te < 0.12:
        return "HIGH ACTIVE     (7–12%)  — decoupled; target zone for asymmetric returns"
    else:
        return "CONCENTRATED    (>12%)   — very high active risk; monitor carefully"


# ---------------------------------------------------------------------------
# Active Share
# ---------------------------------------------------------------------------

def active_share(holdings: list[Holding]) -> dict:
    """
    Active Share = 0.5 × Σ |w_portfolio_i - w_benchmark_i|

    Ranges from 0 (identical to index) to 1 (nothing in common).
    """
    total = sum(abs(h.w_portfolio - h.w_benchmark) for h in holdings)
    share = 0.5 * total

    return {
        "active_share": share,
        "classification": _classify_as(share),
        "holdings_detail": [
            {
                "ticker": h.ticker,
                "w_portfolio": h.w_portfolio,
                "w_benchmark": h.w_benchmark,
                "delta": h.w_portfolio - h.w_benchmark,
            }
            for h in sorted(holdings, key=lambda h: abs(h.w_portfolio - h.w_benchmark), reverse=True)
        ],
    }


def _classify_as(share: float) -> str:
    if share < 0.20:
        return "PURE INDEX FUND (<20%)"
    elif share < 0.60:
        return "CLOSET INDEXER  (20–60%) — fee drag without active upside"
    elif share < 0.80:
        return "ACTIVE          (60–80%) — meaningful divergence from index"
    else:
        return "HIGH CONVICTION (>80%)   — distinct portfolio signature"


# ---------------------------------------------------------------------------
# Monte Carlo simulation — "The Vault" vs "The Herd"
# ---------------------------------------------------------------------------

def _normal_sample(mu: float, sigma: float, n: int, seed: int) -> list[float]:
    """Reproducible normal samples using Python's built-in random."""
    rng = random.Random(seed)
    return [rng.gauss(mu, sigma) for _ in range(n)]


def _skewed_sample(
    mu: float, sigma: float, skew: float, n: int, seed: int
) -> list[float]:
    """
    Approximate skew-normal samples via a two-sigma mixture:
      - With probability p_up  draw from N(mu + skew_shift, sigma_up)
      - With probability p_down draw from N(mu - skew_shift, sigma_down)
    skew > 0 => right-skewed (fatter right tail = asymmetric upside).
    """
    rng = random.Random(seed)
    samples = []
    sigma_up   = sigma * (1 + skew * 0.4)
    sigma_down = sigma * (1 - skew * 0.2)
    shift      = sigma * skew * 0.6

    for _ in range(n):
        if rng.random() < 0.55:              # 55% of draws pull from upside tail
            samples.append(rng.gauss(mu + shift, sigma_up))
        else:
            samples.append(rng.gauss(mu - shift * 0.3, sigma_down))
    return samples


def simulate_distributions(
    vault_mu: float,
    vault_sigma: float,
    herd_mu: float,
    herd_sigma: float,
    vault_skew: float = 0.6,   # right-skew for asymmetric upside
    n: int = 10_000,
    seed: int = 42,
) -> dict:
    """
    Simulate quarterly excess-return distributions for:
      - "The Vault"  : decoupled portfolio with positive skew
                       (Korea arb / VIX hedges create asymmetric payoffs)
      - "The Herd"   : closet indexer — symmetric, low-sigma

    Returns summary stats and a text histogram for terminal display.
    """
    vault = _skewed_sample(vault_mu, vault_sigma, vault_skew, n, seed=seed)
    herd  = _normal_sample(herd_mu,  herd_sigma,  n, seed=seed + 1)

    def stats(samples: list[float]) -> dict:
        mu    = statistics.mean(samples)
        sigma = statistics.stdev(samples)
        sorted_s = sorted(samples)
        pct = lambda p: sorted_s[int(p * len(sorted_s))]
        positive_pct = sum(1 for s in samples if s > 0) / len(samples)
        tail_gain    = pct(0.95) - pct(0.50)   # upside capture
        tail_loss    = pct(0.50) - pct(0.05)   # downside exposure
        return {
            "mean":          mu,
            "std":           sigma,
            "p05":           pct(0.05),
            "p25":           pct(0.25),
            "p50":           pct(0.50),
            "p75":           pct(0.75),
            "p95":           pct(0.95),
            "pct_positive":  positive_pct,
            "upside_capture":  tail_gain,
            "downside_exposure": tail_loss,
            "asymmetry_ratio": tail_gain / tail_loss if tail_loss else float("inf"),
        }

    vault_stats = stats(vault)
    herd_stats  = stats(herd)

    return {
        "vault": vault_stats,
        "herd":  herd_stats,
        "n_simulations": n,
    }


# ---------------------------------------------------------------------------
# Text histogram (no matplotlib needed)
# ---------------------------------------------------------------------------

def _text_histogram(
    samples: list[float],
    label: str,
    bins: int = 30,
    width: int = 50,
) -> list[str]:
    lo, hi = min(samples), max(samples)
    step   = (hi - lo) / bins
    counts = [0] * bins

    for s in samples:
        idx = min(int((s - lo) / step), bins - 1)
        counts[idx] += 1

    max_count = max(counts)
    lines = [f"  {label}"]
    for i, count in enumerate(counts):
        bar_val = lo + i * step
        bar_len = int(count / max_count * width)
        bar     = "█" * bar_len
        pct_str = f"{bar_val*100:+5.1f}%"
        lines.append(f"  {pct_str} | {bar}")
    return lines


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _pct(v: float) -> str:
    return f"{v*100:+.2f}%"


def print_tracking_error(te_result: dict) -> None:
    print("\n" + "=" * 65)
    print("  TRACKING ERROR ANALYSIS")
    print("=" * 65)
    print(f"  Annualised TE         : {_pct(te_result['tracking_error_annualised'])}")
    print(f"  Mean excess / period  : {_pct(te_result['mean_excess_return_per_period'])}")
    print(f"  Information Ratio     : {te_result['information_ratio']:.3f}")
    print(f"  Periods analysed      : {te_result['n_periods']}")
    print(f"\n  Classification: {te_result['classification']}")

    print("\n  Period excess returns:")
    for ret in te_result["excess_returns"]:
        bar = ("+" if ret >= 0 else "-") * min(int(abs(ret) * 200), 40)
        print(f"    {_pct(ret):>9}  {bar}")


def print_active_share(as_result: dict) -> None:
    print("\n" + "=" * 65)
    print("  ACTIVE SHARE ANALYSIS")
    print("=" * 65)
    print(f"  Active Share          : {as_result['active_share']*100:.1f}%")
    print(f"  Classification        : {as_result['classification']}")
    print(f"\n  Top divergences from benchmark:")
    print(f"  {'Ticker':<12} {'Portfolio':>10} {'Benchmark':>10} {'Delta':>10}")
    print(f"  {'-'*44}")
    for h in as_result["holdings_detail"][:8]:
        print(
            f"  {h['ticker']:<12} "
            f"{h['w_portfolio']*100:>9.1f}% "
            f"{h['w_benchmark']*100:>9.1f}% "
            f"{h['delta']*100:>+9.1f}%"
        )


def print_simulation(sim: dict) -> None:
    print("\n" + "=" * 65)
    print('  SIMULATION: "THE VAULT" vs "THE HERD"')
    print("=" * 65)

    def row(label, v_val, h_val, fmt=_pct):
        print(f"  {label:<25} {fmt(v_val):>12}   {fmt(h_val):>12}")

    print(f"  {'Metric':<25} {'The Vault':>12}   {'The Herd':>12}")
    print(f"  {'-'*53}")
    v, h = sim["vault"], sim["herd"]
    row("Mean return",           v["mean"],              h["mean"])
    row("Std deviation",         v["std"],               h["std"])
    row("5th percentile",        v["p05"],               h["p05"])
    row("Median",                v["p50"],               h["p50"])
    row("95th percentile",       v["p95"],               h["p95"])
    row("% positive periods",    v["pct_positive"],      h["pct_positive"],
        fmt=lambda x: f"{x*100:.1f}%")
    row("Upside capture",        v["upside_capture"],    h["upside_capture"])
    row("Downside exposure",     v["downside_exposure"], h["downside_exposure"])
    row("Asymmetry ratio",       v["asymmetry_ratio"],   h["asymmetry_ratio"],
        fmt=lambda x: f"{x:.2f}x")

    print(f"\n  n = {sim['n_simulations']:,} simulated quarterly returns\n")
    print("  The asymmetry ratio = upside_capture / downside_exposure.")
    print("  A ratio > 1.0 means you earn more on wins than you lose on losses.")
    print("  The Vault targets > 1.5x; The Herd hovers near 1.0x.")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    # --- 1. Tracking Error ---
    # Korea arb fires in Q3-24 (+big outperformance) and Q1-25 (misfire).
    # VIX hedge pays in Q4-24 (market drawdown) and costs in Q2-25 (calm market).
    # This variance in excess returns drives a high TE — the target zone.
    series = ReturnSeries(
        labels      = ["Q2-24", "Q3-24", "Q4-24", "Q1-25", "Q2-25", "Q3-25"],
        r_portfolio = [ 0.051,   0.112,   0.068,   0.031,   0.022,   0.091],
        r_benchmark = [ 0.048,   0.055,   0.021,   0.051,   0.038,   0.049],
        periods_per_year = 4,
    )
    te_result = tracking_error(series)
    print_tracking_error(te_result)

    # --- 2. Active Share ---
    holdings = [
        # Ticker              portfolio   benchmark
        Holding("SPY",        0.38,       0.50),   # underweight broad market
        Holding("QQQ",        0.05,       0.15),   # underweight QQQ (MAG7 reduction)
        Holding("KOSPI_ARB",  0.15,       0.00),   # Korea arb — not in index
        Holding("VIX_HEDGE",  0.08,       0.00),   # VIX hedge — not in index
        Holding("AAPL",       0.04,       0.07),
        Holding("MSFT",       0.04,       0.07),
        Holding("NVDA",       0.03,       0.06),
        Holding("GOOGL",      0.03,       0.05),
        Holding("CASH",       0.10,       0.00),
        Holding("OTHER",      0.10,       0.10),
    ]
    as_result = active_share(holdings)
    print_active_share(as_result)

    # --- 3. Monte Carlo distribution ---
    # The Vault: high sigma (decoupled TE ~9%), positive skew from VIX convexity
    # The Herd:  closet indexer, sigma ~0.5% per quarter => TE ~1% annualised
    sim = simulate_distributions(
        vault_mu    =  0.022,   vault_sigma = 0.048,   vault_skew = 0.7,
        herd_mu     =  0.012,   herd_sigma  = 0.005,
        n           = 50_000,
    )
    print_simulation(sim)

    # --- Save ---
    output = {
        "tracking_error": {k: v for k, v in te_result.items() if k != "excess_returns"},
        "active_share":   {k: v for k, v in as_result.items() if k != "holdings_detail"},
        "simulation":     sim,
    }
    with open("tracking_error_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nResults saved to: tracking_error_results.json")


if __name__ == "__main__":
    demo()
