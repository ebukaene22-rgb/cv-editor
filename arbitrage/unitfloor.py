#!/usr/bin/env python3
"""
Unit-value floor gate -- runs BEFORE identity enrichment, marketplace
resolution, or mechanism scoring.

Promoted to a core experimental rule after the small-goods liquidation KILL
(experiments/UNIT-VALUE-FLOOR.md). Fees and fulfilment are near-fixed per
unit while margin scales with price, so below a computable exit price the
contribution target is unreachable AT ANY acquisition discount. Screening
on that first prevents re-testing the same economic failure under a new
mechanism label.

Usage:
    floor_exit_price(target_cm=15, ship=5)      -> minimum exit price
    passes(exit_price, target_cm=15, ship=5)    -> bool
    screen_cohort(rows, ...)                    -> (kept, rejected, report)
"""
import fees

DEFAULT_TARGET_CM = 15.0
DEFAULT_SHIP = 5.0
BUY_TO_EXIT = 0.40          # generous sourcing discount assumed
PREFAIL_MEDIAN_EXIT = 30.0  # cohort-level tripwire


def floor_exit_price(target_cm=DEFAULT_TARGET_CM, ship=DEFAULT_SHIP,
                     seller_country="AE", category="default",
                     buy_to_exit=BUY_TO_EXIT):
    """Minimum exit price at which target_cm is achievable at all."""
    lo, hi = 1.0, 5000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        e = fees.Economics(seller_country=seller_country, category=category,
                           outbound_ship_base=ship, outbound_ship_per_kg=0,
                           inbound_ship_base=2.5, inbound_ship_per_kg=0)
        cm, _, _ = e.contribution(mid * buy_to_exit, mid, grams=500)
        if cm is None or cm < target_cm:
            lo = mid
        else:
            hi = mid
    return hi


def passes(exit_price, target_cm=DEFAULT_TARGET_CM, ship=DEFAULT_SHIP, **kw):
    if not exit_price:
        return False
    return exit_price >= floor_exit_price(target_cm, ship, **kw)


def screen_cohort(rows, exit_key="expected_exit_gbp",
                  target_cm=DEFAULT_TARGET_CM, ship=DEFAULT_SHIP):
    """
    rows: dicts carrying an expected exit price.
    -> (kept, rejected, report dict). Report flags a PRE-FAILED cohort when
    the median expected exit is below PREFAIL_MEDIAN_EXIT -- that is the
    signature of re-running a known-dead economic regime.
    """
    import statistics
    floor = floor_exit_price(target_cm, ship)
    kept, rejected = [], []
    for r in rows:
        (kept if passes(r.get(exit_key), target_cm, ship) else rejected).append(r)
    exits = [r.get(exit_key) for r in rows if r.get(exit_key)]
    med = statistics.median(exits) if exits else 0.0
    return kept, rejected, {
        "floor_exit_gbp": round(floor, 2), "target_cm": target_cm,
        "ship_assumed": ship, "n_in": len(rows), "n_kept": len(kept),
        "median_exit_gbp": round(med, 2),
        "cohort_prefailed": med < PREFAIL_MEDIAN_EXIT,
    }
