"""
Portfolio Performance Attribution
==================================
Decomposes total return into:
  1. Market Beta      — passive index return (SPY / QQQ baseline)
  2. Strategic Alpha  — value added by active decisions
       a. Korea Arbitrage   : regional price-inefficiency capture
       b. MAG7 Avoidance    : avoided drawdown from underweighting Mag-7

Formula reference
-----------------
  market_beta      = w_mkt  × r_mkt
  korea_alpha      = (r_korea - r_benchmark) × w_korea
  mag7_avoidance   = (r_mag7_benchmark - r_mag7_actual) × Δw_mag7
  total_return     = market_beta + korea_alpha + mag7_avoidance + residual
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Period:
    """Holds weights and returns for a single measurement period."""
    label: str

    # --- Market (benchmark) ---
    w_mkt: float          # weight allocated to the passive index (0–1)
    r_mkt: float          # return of the passive index (e.g. SPY) as decimal

    # --- Korea arbitrage ---
    w_korea: float        # weight allocated to Korean position
    r_korea: float        # actual return of Korean position
    r_benchmark: float    # benchmark return for the same period (e.g. MSCI EM)

    # --- MAG7 ---
    w_mag7_benchmark: float   # MAG7 weight in the index
    w_mag7_actual: float      # MAG7 weight in your portfolio (reduced)
    r_mag7: float             # MAG7 actual return this period

    # --- Actual portfolio total return (for residual calc) ---
    r_portfolio: float        # realised portfolio return


@dataclass
class Attribution:
    """Attribution output for one period."""
    label: str
    market_beta: float
    korea_alpha: float
    mag7_avoidance: float
    residual: float
    total_explained: float
    r_portfolio: float

    def as_dict(self) -> dict:
        return {
            "period":           self.label,
            "market_beta":      round(self.market_beta,    6),
            "korea_alpha":      round(self.korea_alpha,    6),
            "mag7_avoidance":   round(self.mag7_avoidance, 6),
            "residual":         round(self.residual,       6),
            "total_explained":  round(self.total_explained,6),
            "r_portfolio":      round(self.r_portfolio,    6),
        }


# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------

def market_beta(p: Period) -> float:
    """
    Passive baseline return.

        w_mkt × r_mkt
    """
    return p.w_mkt * p.r_mkt


def korea_arbitrage_alpha(p: Period) -> float:
    """
    Excess return captured from Korean regional price inefficiency.

        (r_korea - r_benchmark) × w_korea
    """
    return (p.r_korea - p.r_benchmark) * p.w_korea


def mag7_avoidance_alpha(p: Period) -> float:
    """
    Alpha from deliberately underweighting MAG7.
    A positive value means the portfolio benefited from the reduction
    (i.e. MAG7 fell and you held less than the index).

        (r_mag7_benchmark_weight - r_mag7_actual_weight) × r_mag7
      = Δw_mag7 × r_mag7

    Because r_mag7 is negative in a drawdown, holding less (Δw > 0)
    gives a positive avoidance contribution.
    """
    delta_w = p.w_mag7_benchmark - p.w_mag7_actual
    return delta_w * p.r_mag7


def attribute(p: Period) -> Attribution:
    """Compute full attribution for one period."""
    mb   = market_beta(p)
    ka   = korea_arbitrage_alpha(p)
    mag7 = mag7_avoidance_alpha(p)

    total_explained = mb + ka + mag7
    residual        = p.r_portfolio - total_explained

    return Attribution(
        label           = p.label,
        market_beta     = mb,
        korea_alpha     = ka,
        mag7_avoidance  = mag7,
        residual        = residual,
        total_explained = total_explained,
        r_portfolio     = p.r_portfolio,
    )


# ---------------------------------------------------------------------------
# Multi-period aggregation
# ---------------------------------------------------------------------------

def cumulative_attribution(periods: list[Period]) -> dict:
    """
    Sum attribution components across all periods.
    Returns both per-period breakdown and the cumulative totals.
    """
    records = [attribute(p) for p in periods]

    cumulative = {
        "market_beta":    sum(r.market_beta    for r in records),
        "korea_alpha":    sum(r.korea_alpha    for r in records),
        "mag7_avoidance": sum(r.mag7_avoidance for r in records),
        "residual":       sum(r.residual       for r in records),
        "r_portfolio":    sum(r.r_portfolio    for r in records),
    }
    cumulative["total_explained"] = (
        cumulative["market_beta"]
        + cumulative["korea_alpha"]
        + cumulative["mag7_avoidance"]
    )

    return {"periods": [r.as_dict() for r in records], "cumulative": cumulative}


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _pct(v: float) -> str:
    return f"{v*100:+.3f}%"


def print_attribution(result: dict) -> None:
    periods    = result["periods"]
    cumulative = result["cumulative"]

    # --- Per-period table ---
    col = 14
    header = (
        f"{'Period':<12} "
        f"{'MktBeta':>{col}} "
        f"{'KoreaAlpha':>{col}} "
        f"{'MAG7Avoid':>{col}} "
        f"{'Residual':>{col}} "
        f"{'Explained':>{col}} "
        f"{'Portfolio':>{col}}"
    )
    sep = "-" * len(header)

    print("\nPERIOD-BY-PERIOD ATTRIBUTION")
    print(sep)
    print(header)
    print(sep)

    for p in periods:
        print(
            f"{p['period']:<12} "
            f"{_pct(p['market_beta']):>{col}} "
            f"{_pct(p['korea_alpha']):>{col}} "
            f"{_pct(p['mag7_avoidance']):>{col}} "
            f"{_pct(p['residual']):>{col}} "
            f"{_pct(p['total_explained']):>{col}} "
            f"{_pct(p['r_portfolio']):>{col}}"
        )

    print(sep)

    # --- Cumulative summary ---
    c = cumulative
    print("\nCUMULATIVE ATTRIBUTION SUMMARY")
    print(sep)
    print(f"  1. Market Beta (passive baseline)    : {_pct(c['market_beta'])}")
    print(f"  2. Strategic Alpha")
    print(f"       a. Korea Arbitrage              : {_pct(c['korea_alpha'])}")
    print(f"       b. MAG7 Avoidance               : {_pct(c['mag7_avoidance'])}")
    print(f"  ------------------------------------------------")
    print(f"     Total Explained                   : {_pct(c['total_explained'])}")
    print(f"     Residual (unexplained)             : {_pct(c['residual'])}")
    print(f"  ================================================")
    print(f"     Actual Portfolio Return            : {_pct(c['r_portfolio'])}")

    beat = c["r_portfolio"] - c["market_beta"]
    print(f"\n  >> Outperformance vs passive index   : {_pct(beat)}")
    if beat > 0:
        print("     Status: BEATING the benchmark — system is adding value.")
    elif beat < 0:
        print("     Status: LAGGING the benchmark — system needs tuning.")
    else:
        print("     Status: MATCHING the benchmark exactly.")
    print(sep)


# ---------------------------------------------------------------------------
# Example / demo
# ---------------------------------------------------------------------------

def demo() -> None:
    """
    Illustrative three-quarter run with made-up but plausible numbers.
    Replace with real data or wire up to a data feed.
    """
    periods = [
        Period(
            label              = "2024-Q2",
            w_mkt              = 0.50,   r_mkt              =  0.048,   # SPY +4.8%
            w_korea            = 0.15,   r_korea            =  0.073,   # KR position +7.3%
            r_benchmark        =  0.031,                                 # MSCI EM +3.1%
            w_mag7_benchmark   = 0.30,   w_mag7_actual      = 0.18,     # reduced by 12 pp
            r_mag7             =  0.092,                                 # MAG7 +9.2% (you missed upside)
            r_portfolio        =  0.051,
        ),
        Period(
            label              = "2024-Q3",
            w_mkt              = 0.50,   r_mkt              =  0.055,
            w_korea            = 0.15,   r_korea            =  0.041,
            r_benchmark        =  0.028,
            w_mag7_benchmark   = 0.30,   w_mag7_actual      = 0.18,
            r_mag7             = -0.114,                                 # MAG7 -11.4% drawdown
            r_portfolio        =  0.068,
        ),
        Period(
            label              = "2024-Q4",
            w_mkt              = 0.50,   r_mkt              =  0.021,
            w_korea            = 0.15,   r_korea            =  0.089,
            r_benchmark        =  0.033,
            w_mag7_benchmark   = 0.30,   w_mag7_actual      = 0.20,     # slightly increased
            r_mag7             = -0.031,
            r_portfolio        =  0.044,
        ),
    ]

    result = cumulative_attribution(periods)
    print_attribution(result)

    with open("attribution_results.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nDetailed results saved to: attribution_results.json")


if __name__ == "__main__":
    demo()
