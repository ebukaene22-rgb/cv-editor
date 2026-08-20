"""Supplier reliability and defensive stock buffering.

Suppliers are scored empirically, from what they actually did, not from what
their sales deck promised. A £25-margin product with a 15% post-order stock-out
rate is worth less than a £15-margin product fulfilled correctly 99.5% of the
time — the failures cost margin, account health and repeat custom at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from ecommerce_os.money import ZERO, rate

# Weights sum to 1.00. Fill rate and dispatch dominate because they are what a
# customer actually experiences.
WEIGHT_FILL_RATE = Decimal("0.30")
WEIGHT_ON_TIME_DISPATCH = Decimal("0.25")
WEIGHT_VALID_TRACKING = Decimal("0.15")
WEIGHT_FEED_ACCURACY = Decimal("0.10")
WEIGHT_RETURN_RESOLUTION = Decimal("0.10")
WEIGHT_NON_DEFECT = Decimal("0.10")


@dataclass(frozen=True)
class SupplierPerformance:
    """Observed rates, each in [0, 1], over a rolling window."""

    fill_rate: Decimal = ZERO
    on_time_dispatch_rate: Decimal = ZERO
    valid_tracking_rate: Decimal = ZERO
    feed_accuracy: Decimal = ZERO
    return_resolution_quality: Decimal = ZERO
    non_defect_rate: Decimal = ZERO


def supplier_score(performance: SupplierPerformance) -> Decimal:
    """Weighted reliability in [0, 1]."""
    total = (
        WEIGHT_FILL_RATE * rate(performance.fill_rate)
        + WEIGHT_ON_TIME_DISPATCH * rate(performance.on_time_dispatch_rate)
        + WEIGHT_VALID_TRACKING * rate(performance.valid_tracking_rate)
        + WEIGHT_FEED_ACCURACY * rate(performance.feed_accuracy)
        + WEIGHT_RETURN_RESOLUTION * rate(performance.return_resolution_quality)
        + WEIGHT_NON_DEFECT * rate(performance.non_defect_rate)
    )
    return total.quantize(Decimal("0.0001"))


def sellable_stock(
    supplier_qty: int,
    feed_age_minutes: int,
    reliability: Decimal,
    *,
    base_buffer: int = 2,
    stale_buffer_period_minutes: int = 30,
) -> int:
    """Reduce raw supplier quantity to what we are willing to promise.

    The buffer grows with both feed staleness and supplier unreliability: an
    hour-old feed from a supplier that misses one order in twenty is not
    evidence of stock, it is evidence of a number that used to be true.
    """
    if supplier_qty < 0:
        raise ValueError("supplier_qty cannot be negative")
    if feed_age_minutes < 0:
        raise ValueError("feed_age_minutes cannot be negative")
    if stale_buffer_period_minutes <= 0:
        raise ValueError("stale_buffer_period_minutes must be positive")

    reliability = rate(reliability)

    stale_buffer = feed_age_minutes // stale_buffer_period_minutes
    reliability_buffer = int(
        ((Decimal("1") - reliability) * supplier_qty).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )

    buffer = base_buffer + stale_buffer + reliability_buffer
    return max(0, supplier_qty - buffer)


def feed_is_stale(
    feed_age_minutes: int,
    expected_frequency_minutes: int | None,
    *,
    tolerance_multiple: int = 3,
) -> bool:
    """A feed is stale once it is materially overdue against its own SLA.

    An undefined refresh frequency counts as stale: we cannot assert freshness
    we never agreed.
    """
    if expected_frequency_minutes is None:
        return True
    return feed_age_minutes > expected_frequency_minutes * tolerance_multiple
