from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from ecommerce_os.supply import (
    SupplierPerformance,
    feed_is_stale,
    sellable_stock,
    supplier_score,
)


class TestSupplierScore:
    def test_a_perfect_supplier_scores_one(self):
        perfect = SupplierPerformance(
            *(Decimal("1") for _ in range(6))  # every component at 1.0
        )
        assert supplier_score(perfect) == Decimal("1.0000")

    def test_weights_sum_to_one(self, performance):
        # Every component at 0.99 must score exactly 0.99, which only holds if
        # the weights are a proper convex combination.
        assert supplier_score(performance) == Decimal("0.9900")

    def test_fill_rate_carries_the_most_weight(self):
        base = SupplierPerformance(*(Decimal("1") for _ in range(6)))
        worse_fill = replace(base, fill_rate=Decimal("0.5"))
        worse_feed = replace(base, feed_accuracy=Decimal("0.5"))

        assert supplier_score(worse_fill) < supplier_score(worse_feed)

    def test_out_of_range_rate_is_rejected(self):
        with pytest.raises(ValueError):
            supplier_score(SupplierPerformance(fill_rate=Decimal("1.5")))


class TestSellableStock:
    def test_fresh_feed_from_a_reliable_supplier_loses_only_the_base_buffer(self):
        assert sellable_stock(100, feed_age_minutes=0, reliability=Decimal("1")) == 98

    def test_staleness_and_unreliability_compound(self):
        # base 2 + stale 3 (90 // 30) + reliability round(0.05 * 100) = 5 -> 10
        assert sellable_stock(100, feed_age_minutes=90, reliability=Decimal("0.95")) == 90

    def test_a_very_stale_feed_is_not_evidence_of_stock(self):
        assert sellable_stock(10, feed_age_minutes=600, reliability=Decimal("1")) == 0

    def test_buffer_never_goes_negative(self):
        assert sellable_stock(0, feed_age_minutes=0, reliability=Decimal("1")) == 0

    def test_reliability_buffer_scales_with_quantity(self):
        # An unreliable supplier's large number is not proportionally safer.
        small = sellable_stock(10, feed_age_minutes=0, reliability=Decimal("0.9"))
        large = sellable_stock(1000, feed_age_minutes=0, reliability=Decimal("0.9"))

        assert small == 7  # 10 - (2 + 0 + 1)
        assert large == 898  # 1000 - (2 + 0 + 100)

    @pytest.mark.parametrize("bad", [(-1, 0), (10, -5)])
    def test_negative_inputs_are_rejected(self, bad):
        qty, age = bad
        with pytest.raises(ValueError):
            sellable_stock(qty, feed_age_minutes=age, reliability=Decimal("1"))


class TestFeedStaleness:
    def test_a_feed_within_tolerance_is_fresh(self):
        assert not feed_is_stale(120, expected_frequency_minutes=60)

    def test_a_materially_overdue_feed_is_stale(self):
        assert feed_is_stale(200, expected_frequency_minutes=60)

    def test_undefined_frequency_counts_as_stale(self):
        # We cannot assert freshness we never agreed.
        assert feed_is_stale(0, expected_frequency_minutes=None)
