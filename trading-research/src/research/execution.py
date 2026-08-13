"""Pessimistic execution modeling and the cost ladder.

Two rules govern everything here:

1. No fill is assumed that a real aggressive order would not have received.
   Buys pay the ask (plus slippage), sells receive the bid (minus slippage),
   and a marketable limit that slippage pushes through its limit price is a
   miss, not a fill.

2. Returns are never a single number. `round_trip_ladder` reports the same
   trade at five cumulative cost rungs; survival requirements in experiment
   specs name the rung that must stay positive.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

BP = 1e-4
TRADING_DAYS_PER_YEAR = 252


class Side(Enum):
    LONG = 1
    SHORT = -1


@dataclass(frozen=True)
class Quote:
    bid: float
    ask: float

    def __post_init__(self) -> None:
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError(f"non-positive quote: bid={self.bid} ask={self.ask}")
        if self.ask < self.bid:
            raise ValueError(f"crossed quote: bid={self.bid} > ask={self.ask}")

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread_bp(self) -> float:
        return (self.ask - self.bid) / self.mid / BP


@dataclass(frozen=True)
class FillResult:
    filled: bool
    price: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class CostAssumptions:
    """All per-side quantities in basis points unless stated otherwise."""

    commission_bp_per_side: float = 0.5
    slippage_bp_per_side: float = 0.0
    borrow_fee_annual_bp: float = 0.0  # applied to SHORT round trips only


def marketable_limit_fill(
    quote: Quote,
    side: Side,
    *,
    is_entry: bool,
    limit_offset_bp: float = 5.0,
    slippage_bp: float = 0.0,
) -> FillResult:
    """Simulate an aggressive marketable-limit order against a quote.

    A LONG entry (or SHORT exit) buys: assumed fill at ask worsened by
    slippage, capped by the limit `ask * (1 + offset)`; if slippage pushes
    the price beyond the limit, the order does not fill. Selling is
    symmetric on the bid. Offsets and slippage must be non-negative.
    """
    if limit_offset_bp < 0 or slippage_bp < 0:
        raise ValueError("limit_offset_bp and slippage_bp must be >= 0")

    buying = (side is Side.LONG) == is_entry
    if buying:
        limit = quote.ask * (1 + limit_offset_bp * BP)
        px = quote.ask * (1 + slippage_bp * BP)
        if px > limit:
            return FillResult(False, reason="slippage exceeded buy limit")
    else:
        limit = quote.bid * (1 - limit_offset_bp * BP)
        px = quote.bid * (1 - slippage_bp * BP)
        if px < limit:
            return FillResult(False, reason="slippage exceeded sell limit")
    return FillResult(True, price=px)


# Rung names, in cumulative order. Keys of the dict round_trip_ladder returns.
LADDER_RUNGS = (
    "gross_mid",
    "spread",
    "spread_commission",
    "spread_commission_slippage",
    "all_in",
)


def round_trip_ladder(
    entry: Quote,
    exit_: Quote,
    side: Side,
    holding_days: float,
    costs: CostAssumptions,
) -> dict[str, float]:
    """Cost ladder for one aggressively executed round trip.

    Rungs (cumulative):
      gross_mid                   mid-to-mid, the academic number
      spread                      cross the bid/ask both ways
      spread_commission           + commissions both sides
      spread_commission_slippage  + slippage both sides
      all_in                      + borrow for shorts (longs: equal to prior rung)
    """
    if holding_days < 0:
        raise ValueError("holding_days must be >= 0")

    slip = costs.slippage_bp_per_side * BP
    if side is Side.LONG:
        gross = exit_.mid / entry.mid - 1
        spread = exit_.bid / entry.ask - 1
        slipped = (exit_.bid * (1 - slip)) / (entry.ask * (1 + slip)) - 1
    else:
        gross = entry.mid / exit_.mid - 1
        spread = entry.bid / exit_.ask - 1
        slipped = (entry.bid * (1 - slip)) / (exit_.ask * (1 + slip)) - 1

    commission = 2 * costs.commission_bp_per_side * BP
    borrow = (
        costs.borrow_fee_annual_bp * BP * holding_days / TRADING_DAYS_PER_YEAR
        if side is Side.SHORT
        else 0.0
    )

    return {
        "gross_mid": gross,
        "spread": spread,
        "spread_commission": spread - commission,
        "spread_commission_slippage": slipped - commission,
        "all_in": slipped - commission - borrow,
    }
