"""
Hedge-to-Equity Pivot Engine
==============================
Operationalises the full rotation cycle:

  VIX spikes  →  Hedge appreciates
  VIX target hit  →  Sell tranche of hedge
  Proceeds  →  Fill pre-set VALO limit orders (TSM, NVDA, Korea)
  Result  →  Principal untouched; new equity bought with volatility profits

Pivot Schedule
--------------
  VIX 35  →  Sell 25% of VIX long  →  Fill Target 1 (TSM + NVDA)
  VIX 45  →  Sell 50% of VIX long  →  Fill Target 2 (TSM + NVDA)
  VIX 55+ →  Sell remaining 25%    →  Deploy into Korea arb / broad market

Portfolio Health Check
----------------------
  After each pivot, recalculate:
    • New weights
    • Projected Tracking Error change
    • Active Share change
    • Vault growth trajectory
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# VALO — Volatility-Adjusted Limit Order (TSM / NVDA specific)
# ---------------------------------------------------------------------------

VIX_BASE = 18.0   # long-run baseline (current environment ~18-20)
VIX_NOW  = 28.71  # current VIX — already +10.71 above baseline


@dataclass
class VALOSpec:
    ticker:        str
    current_price: float
    vix_base:      float = VIX_BASE

    def limit(self, vix_target: float) -> float:
        """P_limit = P_curr × (1 − (VIX_target − VIX_base) / 100)"""
        return self.current_price * (1.0 - (vix_target - self.vix_base) / 100.0)

    def discount(self, vix_target: float) -> float:
        return (vix_target - self.vix_base) / 100.0


TARGETS = [
    VALOSpec("TSM",  323.00),
    VALOSpec("NVDA", 875.00),
    VALOSpec("KB",    58.00),   # KB Financial — Korea leg
]

VIX_LADDER = [VIX_NOW, 30, 35, 40, 45, 50, 55]


def build_valo_table(targets: list[VALOSpec], vix_levels: list[float]) -> list[dict]:
    rows = []
    for t in targets:
        for vix in vix_levels:
            rows.append({
                "ticker":       t.ticker,
                "vix":          vix,
                "current":      t.current_price,
                "limit_price":  round(t.limit(vix), 2),
                "discount_pct": round(t.discount(vix) * 100, 1),
            })
    return rows


# ---------------------------------------------------------------------------
# Hedge liquidation schedule
# ---------------------------------------------------------------------------

@dataclass
class HedgePosition:
    """Current VIX long position."""
    notional:         float    # total hedge value at current VIX
    vix_entry:        float    # VIX level when hedge was initiated
    vix_now:          float    # current VIX
    vix_payoff_mult:  float = 4.2   # typical VIX payoff in a spike


def hedge_pnl(pos: HedgePosition) -> float:
    """Approximate mark-to-market gain on VIX long."""
    vix_move = (pos.vix_now - pos.vix_entry) / pos.vix_entry
    return pos.notional * vix_move * pos.vix_payoff_mult * 0.5   # 0.5 = option delta


@dataclass
class PivotEvent:
    """One tranche of the hedge-to-equity rotation."""
    vix_trigger:     float
    hedge_sell_pct:  float    # fraction of hedge to liquidate
    equity_targets:  list[tuple[str, float]]  # (ticker, allocation_pct of proceeds)
    label:           str


PIVOT_SCHEDULE: list[PivotEvent] = [
    PivotEvent(
        vix_trigger    = 35.0,
        hedge_sell_pct = 0.25,
        equity_targets = [("TSM", 0.50), ("NVDA", 0.50)],
        label          = "Target 1 — Initial rotation",
    ),
    PivotEvent(
        vix_trigger    = 45.0,
        hedge_sell_pct = 0.50,
        equity_targets = [("TSM", 0.40), ("NVDA", 0.40), ("KB", 0.20)],
        label          = "Target 2 — Full rotation",
    ),
    PivotEvent(
        vix_trigger    = 55.0,
        hedge_sell_pct = 0.25,
        equity_targets = [("KB", 0.60), ("SPY", 0.40)],
        label          = "Target 3 — Deploy remainder into Korea + broad market",
    ),
]


def simulate_pivot(
    hedge: HedgePosition,
    schedule: list[PivotEvent],
    valo_specs: list[VALOSpec],
) -> list[dict]:
    """
    For each pivot event, compute:
      - VIX move required
      - Hedge proceeds available
      - Dollar allocation per equity target
      - VALO limit price for each target at that VIX level
    """
    valo_map = {s.ticker: s for s in valo_specs}
    hedge_remaining = hedge.notional
    results = []

    for ev in schedule:
        proceeds_gross = hedge_remaining * ev.hedge_sell_pct
        hedge_remaining -= proceeds_gross

        allocations = []
        for ticker, frac in ev.equity_targets:
            dollars = proceeds_gross * frac
            spec    = valo_map.get(ticker)
            limit_p = round(spec.limit(ev.vix_trigger), 2) if spec else None
            shares  = math.floor(dollars / limit_p) if limit_p else None
            allocations.append({
                "ticker":       ticker,
                "dollars":      round(dollars, 2),
                "limit_price":  limit_p,
                "shares":       shares,
                "discount_pct": round(spec.discount(ev.vix_trigger) * 100, 1) if spec else None,
            })

        results.append({
            "label":             ev.label,
            "vix_trigger":       ev.vix_trigger,
            "hedge_sell_pct":    ev.hedge_sell_pct,
            "proceeds":          round(proceeds_gross, 2),
            "hedge_remaining":   round(hedge_remaining, 2),
            "allocations":       allocations,
        })

    return results


# ---------------------------------------------------------------------------
# Portfolio Health Check
# ---------------------------------------------------------------------------

@dataclass
class PortfolioSnapshot:
    label:    str
    weights:  dict[str, float]   # ticker → weight
    r_series: list[float]        # portfolio return per period
    b_series: list[float]        # benchmark return per period
    periods_per_year: int = 4


def tracking_error(snap: PortfolioSnapshot) -> float:
    excess = [rp - rb for rp, rb in zip(snap.r_series, snap.b_series)]
    return statistics.stdev(excess) * math.sqrt(snap.periods_per_year)


def active_share(weights: dict[str, float], benchmark: dict[str, float]) -> float:
    all_tickers = set(weights) | set(benchmark)
    return 0.5 * sum(
        abs(weights.get(t, 0.0) - benchmark.get(t, 0.0)) for t in all_tickers
    )


BENCHMARK_WEIGHTS = {
    "SPY":  0.50, "QQQ": 0.15, "NVDA": 0.06,
    "MSFT": 0.07, "AAPL":0.07, "TSM":  0.04,
    "KB":   0.00, "CASH":0.00, "VIX":  0.00,
}

# Shared return series (Q2-24 through Q3-25)
R_PORTFOLIO_BASE = [0.051, 0.112, 0.068, 0.031, 0.022, 0.091]
R_BENCHMARK      = [0.048, 0.055, 0.021, 0.051, 0.038, 0.049]


def health_check(snapshots: list[PortfolioSnapshot]) -> list[dict]:
    results = []
    for snap in snapshots:
        te = tracking_error(snap)
        as_ = active_share(snap.weights, BENCHMARK_WEIGHTS)
        excess = [rp - rb for rp, rb in zip(snap.r_series, snap.b_series)]
        mean_xs = statistics.mean(excess)
        ir = (mean_xs * snap.periods_per_year) / te if te else 0.0

        results.append({
            "label":          snap.label,
            "tracking_error": te,
            "active_share":   as_,
            "mean_excess_pa": mean_xs * snap.periods_per_year,
            "info_ratio":     ir,
            "te_class":       _te_class(te),
            "as_class":       _as_class(as_),
        })
    return results


def _te_class(te: float) -> str:
    if te < 0.04: return "LOW    (<4%)"
    if te < 0.07: return "MODERATE (4-7%)"
    if te < 0.12: return "HIGH   (7-12%) — target zone"
    return "CONCENTRATED (>12%)"


def _as_class(as_: float) -> str:
    if as_ < 0.60: return "CLOSET INDEXER (<60%)"
    if as_ < 0.80: return "ACTIVE (60-80%)"
    return "HIGH CONVICTION (>80%)"


# ---------------------------------------------------------------------------
# Vault growth projection
# ---------------------------------------------------------------------------

def vault_growth(
    initial: float,
    alpha_pa: float,
    benchmark_pa: float,
    years: int = 5,
    harvest_boost_pa: float = 0.02,   # extra annual return from vol harvesting
) -> list[dict]:
    """
    Compound growth of Vault vs passive index.
    harvest_boost_pa: incremental return from systematic vol selling.
    """
    vault_rate = benchmark_pa + alpha_pa + harvest_boost_pa
    path = []
    v_vault = initial
    v_herd  = initial

    for yr in range(years + 1):
        path.append({
            "year":        yr,
            "vault_value": round(v_vault, 2),
            "herd_value":  round(v_herd,  2),
            "vault_edge":  round(v_vault - v_herd, 2),
        })
        v_vault *= (1 + vault_rate)
        v_herd  *= (1 + benchmark_pa)

    return path


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _d(v: float) -> str:  return f"${v:>12,.2f}"
def _p(v: float) -> str:  return f"{v*100:>+7.2f}%"
def _pp(v: float) -> str: return f"{v:>6.1f}%"


def print_valo_table(rows: list[dict]) -> None:
    print("\n" + "=" * 68)
    print("  VALO LIMIT ORDER TABLE")
    print(f"  Formula: P_limit = P_curr × (1 − (VIX_target − {VIX_BASE:.0f}) / 100)")
    print(f"  Current VIX: {VIX_NOW:.2f}  (+{VIX_NOW-VIX_BASE:.2f} above baseline)")
    print("=" * 68)

    current_ticker = None
    for row in rows:
        if row["ticker"] != current_ticker:
            current_ticker = row["ticker"]
            print(f"\n  {current_ticker}  (current {_d(row['current']).strip()})")
            print(f"  {'VIX':>6}  {'Limit Price':>12}  {'Discount':>9}  Regime")
            print(f"  {'-'*55}")

        if   row["vix"] < 28: regime = ""
        elif row["vix"] < 35: regime = "ELEVATED — watch"
        elif row["vix"] < 42: regime = "SPIKE    — T1 fires   <<"
        elif row["vix"] < 50: regime = "PANIC    — T2 fires   <<"
        else:                  regime = "EXTREME  — T3 fires   <<"

        now_flag = "  << NOW" if abs(row["vix"] - VIX_NOW) < 1 else ""
        print(
            f"  {row['vix']:>6.2f}  "
            f"  ${row['limit_price']:>10.2f}  "
            f"  {row['discount_pct']:>7.1f}%  "
            f"{regime}{now_flag}"
        )


def print_pivot(events: list[dict]) -> None:
    print("\n" + "=" * 68)
    print("  HEDGE-TO-EQUITY PIVOT SCHEDULE")
    print("=" * 68)
    for ev in events:
        print(f"\n  [{ev['vix_trigger']:.0f}] {ev['label']}")
        print(f"       Sell {ev['hedge_sell_pct']*100:.0f}% of hedge  →  "
              f"{_d(ev['proceeds']).strip()} proceeds")
        print(f"       Hedge remaining: {_d(ev['hedge_remaining']).strip()}")
        print(f"       Allocations:")
        for alloc in ev["allocations"]:
            shares_str = f"{alloc['shares']} shares" if alloc["shares"] else "market"
            print(
                f"         {alloc['ticker']:<6}  "
                f"{_d(alloc['dollars']).strip():>12}  "
                f"@ ${alloc['limit_price'] or 'mkt':>7}  "
                f"({alloc['discount_pct'] or 0:.1f}% below)  "
                f"= {shares_str}"
            )


def print_health(results: list[dict]) -> None:
    print("\n" + "=" * 68)
    print("  PORTFOLIO HEALTH CHECK")
    print("=" * 68)
    print(f"  {'Scenario':<22} {'TE':>8}  {'Active Share':>13}  {'IR':>7}  {'α p.a.':>8}")
    print(f"  {'-'*60}")
    for r in results:
        print(
            f"  {r['label']:<22} "
            f"  {r['tracking_error']*100:>6.2f}%  "
            f"  {r['active_share']*100:>11.1f}%  "
            f"  {r['info_ratio']:>6.2f}  "
            f"  {r['mean_excess_pa']*100:>+6.2f}%"
        )
    print()
    for r in results:
        print(f"  {r['label']}")
        print(f"    TE:    {r['te_class']}")
        print(f"    AS:    {r['as_class']}")


def print_growth(path: list[dict], initial: float) -> None:
    print("\n" + "=" * 68)
    print(f"  VAULT GROWTH PROJECTION  (starting ${initial:,.0f})")
    print("=" * 68)
    print(f"  {'Year':>5}  {'Vault':>14}  {'Herd (Index)':>14}  {'Edge':>14}")
    print(f"  {'-'*54}")
    for pt in path:
        bar = "█" * min(int(pt["vault_edge"] / initial * 60), 30)
        print(
            f"  {pt['year']:>5}  "
            f"  {_d(pt['vault_value']):>13}  "
            f"  {_d(pt['herd_value']):>13}  "
            f"  {_d(pt['vault_edge']):>13}  {bar}"
        )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    NOTIONAL = 1_000_000

    print("HEDGE-TO-EQUITY PIVOT ENGINE")
    print("=" * 68)

    # 1. VALO table
    rows = build_valo_table(TARGETS, VIX_LADDER)
    print_valo_table(rows)

    # 2. Pivot simulation — hedge currently worth 8% of notional
    hedge = HedgePosition(
        notional        = NOTIONAL * 0.08,   # $80k hedge position
        vix_entry       = 18.0,
        vix_now         = VIX_NOW,
        vix_payoff_mult = 4.2,
    )
    current_pnl = hedge_pnl(hedge)
    print(f"\n  Current hedge mark-to-market gain: {_d(current_pnl).strip()}")
    print(f"  (VIX moved from {hedge.vix_entry:.1f} → {hedge.vix_now:.2f}; "
          f"+{VIX_NOW - hedge.vix_entry:.2f} pts)")

    pivot_events = simulate_pivot(hedge, PIVOT_SCHEDULE, TARGETS)
    print_pivot(pivot_events)

    # 3. Health check: before pivot vs after each pivot tranche
    pre_weights = {
        "SPY": 0.38, "QQQ": 0.05, "NVDA": 0.03, "MSFT": 0.04,
        "AAPL":0.04, "TSM": 0.02, "KB":   0.15, "CASH": 0.10,
        "VIX": 0.08, "OTHER": 0.11,
    }
    # After T1: VIX hedge reduced 25%, TSM + NVDA increase
    post_t1_weights = {
        "SPY": 0.38, "QQQ": 0.05, "NVDA": 0.06, "MSFT": 0.04,
        "AAPL":0.04, "TSM": 0.04, "KB":   0.15, "CASH": 0.10,
        "VIX": 0.06, "OTHER": 0.08,
    }
    # After T2: further rotation into equity
    post_t2_weights = {
        "SPY": 0.38, "QQQ": 0.05, "NVDA": 0.09, "MSFT": 0.04,
        "AAPL":0.04, "TSM": 0.07, "KB":   0.18, "CASH": 0.05,
        "VIX": 0.02, "OTHER": 0.08,
    }

    # Projected return series: post-pivot outperforms more as arb closes
    r_post_t1 = [0.055, 0.118, 0.072, 0.038, 0.029, 0.098]
    r_post_t2 = [0.061, 0.125, 0.079, 0.044, 0.035, 0.107]

    snapshots = [
        PortfolioSnapshot("Pre-pivot (now)",  pre_weights,    R_PORTFOLIO_BASE, R_BENCHMARK),
        PortfolioSnapshot("Post T1 (VIX 35)", post_t1_weights, r_post_t1,       R_BENCHMARK),
        PortfolioSnapshot("Post T2 (VIX 45)", post_t2_weights, r_post_t2,       R_BENCHMARK),
    ]
    health = health_check(snapshots)
    print_health(health)

    # 4. Vault growth: alpha 7.5% pa + 2% harvest boost vs index 10% pa
    growth = vault_growth(
        initial          = NOTIONAL,
        alpha_pa         = 0.075,
        benchmark_pa     = 0.100,
        years            = 5,
        harvest_boost_pa = 0.020,
    )
    print_growth(growth, NOTIONAL)

    # Save
    output = {
        "valo_table":    rows,
        "pivot_events":  pivot_events,
        "health_check":  health,
        "vault_growth":  growth,
    }
    with open("hedge_to_equity_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: hedge_to_equity_results.json")


if __name__ == "__main__":
    demo()
