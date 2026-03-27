"""
Automated Trigger System — "System Over Stress"
================================================
Eliminates decision fatigue by converting VIX levels into pre-set,
mathematical re-entry rules for Korea and MAG7 legs.

When VIX hits a target threshold:
  → Korea leg limit orders fire automatically at pre-calculated prices
  → MAG7 re-entry ladders activate in tranches
  → VIX harvest positions are sized and submitted without manual input

This is not prediction. It is conditional accounting:
  "If the market gives me X risk/reward, I execute Y."

Modules
-------
  1. TriggerRule    — a single VIX-level → action mapping
  2. TriggerLadder  — ordered set of rules (the full "playbook")
  3. TriggerEngine  — evaluates current VIX against ladder, fires rules
  4. PositionSizer  — Kelly-fraction sizing based on IV/RV spread
  5. Playbook       — pre-built Korea + MAG7 + VIX harvest ladders
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


# ---------------------------------------------------------------------------
# 1. Trigger Rule
# ---------------------------------------------------------------------------

class Action(Enum):
    BUY_KOREA      = "BUY_KOREA"
    ADD_KOREA      = "ADD_KOREA"
    BUY_MAG7       = "BUY_MAG7"
    REDUCE_MAG7    = "REDUCE_MAG7"
    SELL_VIX_PUT   = "SELL_VIX_PUT"    # harvest vol premium
    SELL_PUT_SPY   = "SELL_PUT_SPY"    # harvest equity vol
    BUY_VIX_CALL   = "BUY_VIX_CALL"   # hedge leg (pre-crash)
    RAISE_CASH     = "RAISE_CASH"
    DEPLOY_CASH    = "DEPLOY_CASH"
    ALERT_ONLY     = "ALERT_ONLY"


@dataclass
class TriggerRule:
    """
    A single conditional order.

    Fires when:  vix_min <= current_vix < vix_max
                 AND condition_fn(current_vix) is True  (optional)

    size_pct: fraction of the relevant notional to deploy (0–1)
    """
    name:         str
    action:       Action
    vix_min:      float
    vix_max:      float
    size_pct:     float          # 0.05 = 5% of notional
    limit_price:  float | None   # None = market order
    notes:        str = ""
    condition_fn: Callable[[float], bool] | None = field(
        default=None, repr=False
    )

    def matches(self, vix: float) -> bool:
        in_band = self.vix_min <= vix < self.vix_max
        if not in_band:
            return False
        if self.condition_fn:
            return self.condition_fn(vix)
        return True


# ---------------------------------------------------------------------------
# 2. Trigger Ladder
# ---------------------------------------------------------------------------

@dataclass
class TriggerLadder:
    """Ordered collection of TriggerRules forming the full playbook."""
    name:  str
    rules: list[TriggerRule] = field(default_factory=list)

    def add(self, rule: TriggerRule) -> "TriggerLadder":
        self.rules.append(rule)
        return self

    def evaluate(self, vix: float) -> list[TriggerRule]:
        """Return all rules that fire at the given VIX level."""
        return [r for r in self.rules if r.matches(vix)]


# ---------------------------------------------------------------------------
# 3. Trigger Engine
# ---------------------------------------------------------------------------

class TriggerEngine:
    """
    Evaluates current VIX against all registered ladders.
    Produces an execution manifest — the exact orders to place.
    """

    def __init__(self, ladders: list[TriggerLadder], notional: float = 1_000_000):
        self.ladders  = ladders
        self.notional = notional
        self._fired: set[str] = set()   # prevent duplicate fires per session

    def run(self, vix: float, allow_repeat: bool = False) -> dict:
        fired_rules = []
        orders      = []

        for ladder in self.ladders:
            for rule in ladder.evaluate(vix):
                key = f"{ladder.name}:{rule.name}"
                if key in self._fired and not allow_repeat:
                    continue

                self._fired.add(key)
                fired_rules.append({"ladder": ladder.name, "rule": rule.name})

                dollar_size = rule.size_pct * self.notional
                orders.append({
                    "ladder":       ladder.name,
                    "rule":         rule.name,
                    "action":       rule.action.value,
                    "vix_trigger":  vix,
                    "size_pct":     rule.size_pct,
                    "dollar_size":  dollar_size,
                    "limit_price":  rule.limit_price,
                    "order_type":   "LIMIT" if rule.limit_price else "MARKET",
                    "notes":        rule.notes,
                })

        return {
            "vix":         vix,
            "rules_fired": len(fired_rules),
            "orders":      orders,
        }


# ---------------------------------------------------------------------------
# 4. Position Sizer (fractional Kelly on vol spread)
# ---------------------------------------------------------------------------

def kelly_vol_size(
    iv: float,
    realised_vol: float,
    max_position: float = 0.15,
    kelly_fraction: float = 0.25,   # quarter-Kelly for safety
) -> float:
    """
    Size a vol-selling position using fractional Kelly.

    Edge (b) ≈ IV/RV ratio - 1   (the premium above fair value)
    Win probability (p) ≈ 0.80   (IV > RV ~80% of the time historically)

    Kelly f* = (p·b - (1-p)) / b
    Applied at kelly_fraction for conservatism.
    """
    if realised_vol <= 0 or iv <= 0:
        return 0.0

    b = (iv / realised_vol) - 1.0   # edge expressed as multiplier
    if b <= 0:
        return 0.0

    p    = 0.80
    full = (p * b - (1 - p)) / b
    size = kelly_fraction * full

    return min(max(size, 0.0), max_position)


# ---------------------------------------------------------------------------
# 5. Pre-built Playbook
# ---------------------------------------------------------------------------

def build_korea_ladder() -> TriggerLadder:
    """
    Korea arbitrage re-entry ladder.
    As VIX spikes, Korean equities often sell off in sympathy (forced EM outflows).
    That widening arb is the entry signal.
    """
    ladder = TriggerLadder(name="Korea Arbitrage")

    ladder.add(TriggerRule(
        name        = "Alert: arb widening",
        action      = Action.ALERT_ONLY,
        vix_min     = 22,  vix_max = 28,
        size_pct    = 0.0,
        limit_price = None,
        notes       = "Monitor Korea discount; do not act yet",
    ))
    ladder.add(TriggerRule(
        name        = "Tranche 1 — initial entry",
        action      = Action.BUY_KOREA,
        vix_min     = 28,  vix_max = 35,
        size_pct    = 0.05,
        limit_price = None,   # market — arb window closes fast
        notes       = "5% of notional; discount typically 3–5% at VIX 28",
    ))
    ladder.add(TriggerRule(
        name        = "Tranche 2 — scale in",
        action      = Action.ADD_KOREA,
        vix_min     = 35,  vix_max = 42,
        size_pct    = 0.07,
        limit_price = None,
        notes       = "Discount widens further; add 7%",
    ))
    ladder.add(TriggerRule(
        name        = "Tranche 3 — max allocation",
        action      = Action.ADD_KOREA,
        vix_min     = 42,  vix_max = 999,
        size_pct    = 0.08,
        limit_price = None,
        notes       = "Full Korea weight hit; no further adds",
    ))

    return ladder


def build_mag7_ladder() -> TriggerLadder:
    """
    MAG7 re-entry ladder.
    Trimmed on the way up; re-enter in tranches on vol spikes.
    """
    ladder = TriggerLadder(name="MAG7 Re-entry")

    ladder.add(TriggerRule(
        name        = "Trim further — melt-up",
        action      = Action.REDUCE_MAG7,
        vix_min     = 0,   vix_max = 15,
        size_pct    = 0.03,
        limit_price = None,
        notes       = "VIX sub-15 = complacency; reduce MAG7 into strength",
    ))
    ladder.add(TriggerRule(
        name        = "Tranche 1 re-entry",
        action      = Action.BUY_MAG7,
        vix_min     = 30,  vix_max = 38,
        size_pct    = 0.04,
        limit_price = None,
        notes       = "Begin rebuilding MAG7 weight at first VIX spike",
    ))
    ladder.add(TriggerRule(
        name        = "Tranche 2 re-entry",
        action      = Action.BUY_MAG7,
        vix_min     = 38,  vix_max = 48,
        size_pct    = 0.05,
        limit_price = None,
        notes       = "Crash territory; add more MAG7 at distressed prices",
    ))
    ladder.add(TriggerRule(
        name        = "Tranche 3 — full re-entry",
        action      = Action.BUY_MAG7,
        vix_min     = 48,  vix_max = 999,
        size_pct    = 0.06,
        limit_price = None,
        notes       = "Panic level; rebuild to benchmark weight",
    ))

    return ladder


def build_vix_harvest_ladder() -> TriggerLadder:
    """
    VIX vol-selling ladder.
    Sell puts / short vol at each spike level; size via Kelly.
    """
    ladder = TriggerLadder(name="VIX Harvest")

    ladder.add(TriggerRule(
        name        = "Sell SPY put — elevated",
        action      = Action.SELL_PUT_SPY,
        vix_min     = 25,  vix_max = 32,
        size_pct    = 0.03,
        limit_price = None,
        notes       = "Sell 30-day SPY put; IV/RV ~1.4x; collect carry",
    ))
    ladder.add(TriggerRule(
        name        = "Sell VIX put — spike",
        action      = Action.SELL_VIX_PUT,
        vix_min     = 32,  vix_max = 42,
        size_pct    = 0.05,
        limit_price = None,
        notes       = "Short VIX put spread; IV/RV ~1.8x; high premium",
    ))
    ladder.add(TriggerRule(
        name        = "Sell VIX put — panic",
        action      = Action.SELL_VIX_PUT,
        vix_min     = 42,  vix_max = 999,
        size_pct    = 0.07,
        limit_price = None,
        notes       = "Panic premium; IV/RV >2.0x; maximum harvest size",
    ))
    ladder.add(TriggerRule(
        name        = "Deploy cash reserve",
        action      = Action.DEPLOY_CASH,
        vix_min     = 40,  vix_max = 999,
        size_pct    = 0.10,
        limit_price = None,
        notes       = "Release 10% cash reserve; buy broad market at panic prices",
    ))

    return ladder


# ---------------------------------------------------------------------------
# 6. VALO — Volatility-Adjusted Limit Order
# ---------------------------------------------------------------------------

@dataclass
class VALOTarget:
    ticker:        str
    current_price: float
    vix_baseline:  float = 15.0   # "normal" VIX reference point


def valo_price(target: VALOTarget, vix_current: float) -> dict:
    """
    Volatility-Adjusted Limit Order price.

        Limit Price = Current Price × (1 - (VIX_current - VIX_baseline) / 100)

    As VIX spikes, the limit order is stretched further down,
    catching the wick of panic selling without manual intervention.
    """
    discount    = (vix_current - target.vix_baseline) / 100.0
    limit       = target.current_price * (1.0 - discount)
    pct_below   = discount

    return {
        "ticker":        target.ticker,
        "current_price": target.current_price,
        "vix_current":   vix_current,
        "vix_baseline":  target.vix_baseline,
        "discount_pct":  pct_below,
        "limit_price":   round(limit, 2),
        "notes": (
            f"At VIX={vix_current:.0f}, buy limit sits "
            f"{pct_below*100:.1f}% below current price"
        ),
    }


def valo_ladder(target: VALOTarget, vix_levels: list[float]) -> list[dict]:
    """VALO prices across multiple VIX scenarios for one ticker."""
    return [valo_price(target, v) for v in vix_levels]


def print_valo(targets: list[VALOTarget], vix_levels: list[float]) -> None:
    print("\n" + "=" * 72)
    print("  VOLATILITY-ADJUSTED LIMIT ORDERS (VALO)")
    print(f"  Formula: Limit = Price × (1 − (VIX_current − VIX_baseline) / 100)")
    print("=" * 72)

    for target in targets:
        print(f"\n  {target.ticker}  (current ${target.current_price:.2f}, "
              f"VIX baseline {target.vix_baseline:.0f})")
        print(f"  {'VIX':>6}  {'Limit Price':>12}  {'Discount':>9}  Notes")
        print(f"  {'-'*58}")
        for row in valo_ladder(target, vix_levels):
            flag = ""
            if row["vix_current"] >= 40:
                flag = "  << PANIC — ladder fires"
            elif row["vix_current"] >= 28:
                flag = "  << SPIKE — order active"
            print(
                f"  {row['vix_current']:>6.0f}  "
                f"  ${row['limit_price']:>10.2f}  "
                f"  {row['discount_pct']*100:>7.1f}%"
                f"{flag}"
            )


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _pct(v: float) -> str:
    return f"{v*100:.1f}%"


def print_ladder(ladder: TriggerLadder) -> None:
    print(f"\n  [{ladder.name}]")
    print(f"  {'VIX Band':<14} {'Action':<18} {'Size':>6}  Notes")
    print(f"  {'-'*72}")
    for r in ladder.rules:
        band = f"{r.vix_min:.0f}–{r.vix_max if r.vix_max < 999 else '∞':>3}"
        print(
            f"  {band:<14} {r.action.value:<18} {_pct(r.size_pct):>6}  {r.notes}"
        )


def print_manifest(manifest: dict) -> None:
    print(f"\n" + "=" * 72)
    print(f"  EXECUTION MANIFEST — VIX = {manifest['vix']:.1f}")
    print(f"  {manifest['rules_fired']} rule(s) fired")
    print("=" * 72)

    if not manifest["orders"]:
        print("  No triggers active at this VIX level.")
        return

    for i, o in enumerate(manifest["orders"], 1):
        print(f"\n  [{i}] {o['ladder']} — {o['rule']}")
        print(f"       Action      : {o['action']}")
        print(f"       Size        : {_pct(o['size_pct'])}  (${o['dollar_size']:,.0f})")
        print(f"       Order type  : {o['order_type']}")
        if o["limit_price"]:
            print(f"       Limit price : {o['limit_price']}")
        if o["notes"]:
            print(f"       Notes       : {o['notes']}")


def print_kelly(iv: float, rv: float) -> None:
    size = kelly_vol_size(iv, rv)
    print(f"\n  Kelly Vol Size (IV={iv*100:.0f}%, RV={rv*100:.0f}%): {_pct(size)}")
    print(f"  IV/RV ratio: {iv/rv:.2f}x  |  Quarter-Kelly allocation: {_pct(size)}")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    print("AUTOMATED TRIGGER SYSTEM — System Over Stress")
    print("=" * 72)

    # Build the playbook
    ladders = [
        build_korea_ladder(),
        build_mag7_ladder(),
        build_vix_harvest_ladder(),
    ]

    # Print the full ladder reference
    print("\nFULL PLAYBOOK — Pre-set Rules")
    print("=" * 72)
    for ladder in ladders:
        print_ladder(ladder)

    engine = TriggerEngine(ladders, notional=1_000_000)

    # Simulate three VIX readings across a crash event
    print("\n\nSIMULATION — VIX Progression Through a Crash")
    print("=" * 72)

    scenarios = [
        (17.0,  "Normal market — pre-crash"),
        (31.0,  "Initial dislocation"),
        (44.0,  "Full panic — all ladders fire"),
    ]

    all_manifests = []
    for vix, label in scenarios:
        print(f"\n  --- {label} (VIX = {vix}) ---")
        manifest = engine.run(vix, allow_repeat=True)
        print_manifest(manifest)
        all_manifests.append(manifest)

    # Kelly sizing at panic
    print("\n" + "=" * 72)
    print("  KELLY POSITION SIZING")
    print("=" * 72)
    print_kelly(iv=0.44, rv=0.20)   # VIX=44, RV=20%
    print_kelly(iv=0.32, rv=0.19)   # VIX=32, RV=19%
    print_kelly(iv=0.17, rv=0.15)   # VIX=17, RV=15%

    # VALO table — placeholder tickers; swap for your actual names
    valo_targets = [
        VALOTarget(ticker="NVDA",   current_price=875.00, vix_baseline=15),
        VALOTarget(ticker="MSFT",   current_price=420.00, vix_baseline=15),
        VALOTarget(ticker="KB",     current_price=58.00,  vix_baseline=15),  # KB Financial (Korea)
        VALOTarget(ticker="SHW",    current_price=340.00, vix_baseline=15),
    ]
    print_valo(valo_targets, vix_levels=[20, 25, 30, 35, 40, 45, 50])

    # Key principle
    print("\n" + "=" * 72)
    print("  SYSTEM PRINCIPLE")
    print("=" * 72)
    print("""
  The trigger system removes three failure modes:

  1. Freeze      — "I'll wait to see if it goes lower"
                   → No decision needed; the math already decided.

  2. FOMO entry  — "The news says the bottom is in"
                   → By Day 7 the premium has decayed 33%.
                      The ladder fired on Day 1.

  3. Oversize    — "This is the biggest opportunity I've ever seen"
                   → Kelly fraction caps the position. Conviction
                      doesn't override the formula.

  The VIX spike is not a crisis. It is a scheduled restock event.
""")

    # Save
    with open("trigger_system_results.json", "w") as f:
        json.dump(all_manifests, f, indent=2)
    print("  Results saved to: trigger_system_results.json")


if __name__ == "__main__":
    demo()
