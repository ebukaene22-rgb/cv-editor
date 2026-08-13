import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research.execution import (
    BP,
    CostAssumptions,
    Quote,
    Side,
    marketable_limit_fill,
    round_trip_ladder,
)


class TestQuote(unittest.TestCase):
    def test_mid_and_spread(self):
        q = Quote(bid=99.95, ask=100.05)
        self.assertAlmostEqual(q.mid, 100.0)
        self.assertAlmostEqual(q.spread_bp, 10.0)

    def test_crossed_quote_rejected(self):
        with self.assertRaises(ValueError):
            Quote(bid=100.10, ask=100.00)

    def test_non_positive_rejected(self):
        with self.assertRaises(ValueError):
            Quote(bid=0.0, ask=1.0)


class TestMarketableLimitFill(unittest.TestCase):
    def setUp(self):
        self.q = Quote(bid=99.95, ask=100.05)

    def test_long_entry_fills_at_ask_with_slippage(self):
        r = marketable_limit_fill(
            self.q, Side.LONG, is_entry=True, limit_offset_bp=5, slippage_bp=2
        )
        self.assertTrue(r.filled)
        self.assertAlmostEqual(r.price, 100.05 * (1 + 2 * BP))

    def test_long_entry_missed_when_slippage_exceeds_limit(self):
        r = marketable_limit_fill(
            self.q, Side.LONG, is_entry=True, limit_offset_bp=5, slippage_bp=6
        )
        self.assertFalse(r.filled)
        self.assertIn("limit", r.reason)

    def test_short_entry_sells_at_bid(self):
        r = marketable_limit_fill(
            self.q, Side.SHORT, is_entry=True, limit_offset_bp=5, slippage_bp=0
        )
        self.assertTrue(r.filled)
        self.assertAlmostEqual(r.price, 99.95)

    def test_short_exit_buys_at_ask(self):
        r = marketable_limit_fill(
            self.q, Side.SHORT, is_entry=False, limit_offset_bp=5, slippage_bp=0
        )
        self.assertTrue(r.filled)
        self.assertAlmostEqual(r.price, 100.05 * 1.0)

    def test_negative_inputs_rejected(self):
        with self.assertRaises(ValueError):
            marketable_limit_fill(
                self.q, Side.LONG, is_entry=True, limit_offset_bp=-1
            )


class TestRoundTripLadder(unittest.TestCase):
    def setUp(self):
        self.entry = Quote(bid=99.95, ask=100.05)   # mid 100
        self.exit = Quote(bid=100.95, ask=101.05)   # mid 101
        self.costs = CostAssumptions(
            commission_bp_per_side=0.5,
            slippage_bp_per_side=2.0,
            borrow_fee_annual_bp=100.0,
        )

    def test_long_ladder_hand_computed(self):
        ladder = round_trip_ladder(self.entry, self.exit, Side.LONG, 20, self.costs)
        self.assertAlmostEqual(ladder["gross_mid"], 0.01)
        self.assertAlmostEqual(ladder["spread"], 100.95 / 100.05 - 1)
        self.assertAlmostEqual(
            ladder["spread_commission"], 100.95 / 100.05 - 1 - 1.0 * BP
        )
        slipped = (100.95 * (1 - 2 * BP)) / (100.05 * (1 + 2 * BP)) - 1
        self.assertAlmostEqual(
            ladder["spread_commission_slippage"], slipped - 1.0 * BP
        )
        # Long pays no borrow: bottom rung equals prior rung.
        self.assertAlmostEqual(
            ladder["all_in"], ladder["spread_commission_slippage"]
        )

    def test_ladder_is_monotonically_worse(self):
        ladder = round_trip_ladder(self.entry, self.exit, Side.LONG, 20, self.costs)
        self.assertGreater(ladder["gross_mid"], ladder["spread"])
        self.assertGreater(ladder["spread"], ladder["spread_commission"])
        self.assertGreater(
            ladder["spread_commission"], ladder["spread_commission_slippage"]
        )
        self.assertGreaterEqual(
            ladder["spread_commission_slippage"], ladder["all_in"]
        )

    def test_short_ladder_includes_borrow(self):
        # Price falls: shorts profit gross.
        exit_ = Quote(bid=98.95, ask=99.05)  # mid 99
        ladder = round_trip_ladder(self.entry, exit_, Side.SHORT, 20, self.costs)
        self.assertAlmostEqual(ladder["gross_mid"], 100.0 / 99.0 - 1)
        self.assertAlmostEqual(ladder["spread"], 99.95 / 99.05 - 1)
        expected_borrow = 100.0 * BP * 20 / 252
        self.assertAlmostEqual(
            ladder["all_in"],
            ladder["spread_commission_slippage"] - expected_borrow,
        )

    def test_negative_holding_days_rejected(self):
        with self.assertRaises(ValueError):
            round_trip_ladder(self.entry, self.exit, Side.LONG, -1, self.costs)


if __name__ == "__main__":
    unittest.main()
