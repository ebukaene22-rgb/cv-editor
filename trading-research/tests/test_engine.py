import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research.engine import Event, run_event_study
from research.execution import CostAssumptions, Quote, Side


def make_event(i, side=Side.LONG, cluster=None, observable=0, entry=1):
    return Event(
        event_id=f"ev{i}",
        symbol=f"SYM{i}",
        observable_ts=observable,
        entry_ts=entry,
        side=side,
        cluster_key=cluster if cluster is not None else i,
    )


class TestEngine(unittest.TestCase):
    def test_look_ahead_is_a_hard_error(self):
        bad = [make_event(0, observable=5, entry=1)]
        with self.assertRaises(ValueError) as ctx:
            run_event_study(
                bad,
                entry_quotes=lambda e: Quote(99.95, 100.05),
                exit_quotes=lambda e: Quote(100.95, 101.05),
                holding_days=20,
                costs=CostAssumptions(),
                n_boot=100,
            )
        self.assertIn("look-ahead", str(ctx.exception))

    def test_profitable_synthetic_study_positive_at_every_rung(self):
        # 1% mid-to-mid gain on a 10bp-spread stock comfortably clears costs.
        events = [make_event(i, cluster=i // 2) for i in range(20)]
        res = run_event_study(
            events,
            entry_quotes=lambda e: Quote(99.95, 100.05),
            exit_quotes=lambda e: Quote(100.95, 101.05),
            holding_days=20,
            costs=CostAssumptions(commission_bp_per_side=0.5, slippage_bp_per_side=2),
            n_boot=500,
            seed=3,
        )
        self.assertEqual(res.fill_rate, 1.0)
        for rung, summary in res.summaries.items():
            self.assertGreater(summary.point, 0, msg=rung)
        # Ladder ordering holds in aggregate too.
        self.assertGreater(
            res.summaries["gross_mid"].point, res.summaries["all_in"].point
        )

    def test_edge_smaller_than_costs_dies_on_the_ladder(self):
        # 5bp gross gain, 10bp spread: gross positive, executable negative.
        events = [make_event(i, cluster=i) for i in range(10)]
        res = run_event_study(
            events,
            entry_quotes=lambda e: Quote(99.95, 100.05),
            exit_quotes=lambda e: Quote(100.00, 100.10),  # mid 100.05
            holding_days=1,
            costs=CostAssumptions(commission_bp_per_side=0.5),
            n_boot=200,
            seed=1,
        )
        self.assertGreater(res.summaries["gross_mid"].point, 0)
        self.assertLess(res.summaries["spread"].point, 0)

    def test_missed_fills_are_recorded_not_repriced(self):
        events = [make_event(0)]
        res = run_event_study(
            events,
            entry_quotes=lambda e: Quote(99.95, 100.05),
            exit_quotes=lambda e: Quote(100.95, 101.05),
            holding_days=1,
            # slippage beyond the 5bp limit offset -> miss
            costs=CostAssumptions(slippage_bp_per_side=8),
            limit_offset_bp=5,
            n_boot=100,
        )
        self.assertEqual(res.fill_rate, 0.0)
        self.assertEqual(res.summaries, {})
        self.assertIn("limit", res.outcomes[0].miss_reason)

    def test_short_side_supported(self):
        events = [make_event(i, side=Side.SHORT, cluster=0) for i in range(4)]
        res = run_event_study(
            events,
            entry_quotes=lambda e: Quote(99.95, 100.05),
            exit_quotes=lambda e: Quote(98.95, 99.05),
            holding_days=5,
            costs=CostAssumptions(borrow_fee_annual_bp=200),
            n_boot=100,
        )
        self.assertEqual(res.fill_rate, 1.0)
        self.assertGreater(res.summaries["all_in"].point, 0)


if __name__ == "__main__":
    unittest.main()
