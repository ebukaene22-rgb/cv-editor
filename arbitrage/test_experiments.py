import csv
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import experiments as E
import scan
import signals as S


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(scan.SCHEMA)

    def add(self, ts, domain, sku, available, price=10.0, title="Product",
            group=None, region="US", compare=20.0, currency="USD"):
        self.conn.execute(
            "INSERT INTO obs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ts, domain, group, region, sku, title, "Vendor", price, compare,
             currency, available, 500, "https://example.test/item", "Test"))

    def test_depletion_uses_elapsed_days_and_does_not_bridge_missing_rows(self):
        times = ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z",
                 "2026-01-03T00:00:00Z"]
        for ts in times:
            for i in range(4):
                self.add(ts, "shop.test", f"stable-{i}", 1)
        self.add(times[0], "shop.test", "cycle", 0)
        self.add(times[1], "shop.test", "cycle", 1)
        self.add(times[2], "shop.test", "cycle", 0)
        self.add(times[0], "shop.test", "gap", 0)
        self.add(times[2], "shop.test", "gap", 1)

        result = S.depletion_signals(self.conn, "shop.test")

        self.assertEqual(result["cycle"]["restocks"], 1)
        self.assertEqual(result["cycle"]["stockouts"], 1)
        self.assertEqual(result["cycle"]["cycles"], 1)
        self.assertAlmostEqual(result["cycle"]["sku_days"], 2.0)
        self.assertEqual(result["gap"]["restocks"], 0)
        self.assertEqual(result["gap"]["valid_intervals"], 0)

    def test_condition_and_bundle_cohorts_are_explicit(self):
        ts = "2026-01-01T00:00:00Z"
        self.add(ts, "shop.test", "OB-1", 1, title="Camera OPEN BOX")
        self.add(ts, "shop.test", "KIT-1", 1, title="Coffee Starter Kit")
        rates = {"USD": 1.0, "GBP": 0.8}
        with tempfile.TemporaryDirectory() as tmp:
            openbox = os.path.join(tmp, "openbox.csv")
            bundles = os.path.join(tmp, "bundles.csv")
            self.assertEqual(E.write_openbox_cohort(
                self.conn, rates, openbox, 30), 1)
            self.assertEqual(E.write_bundle_cohort(
                self.conn, rates, bundles, 20), 1)
            with open(openbox, newline="") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row["source_condition"], "open_box")
            self.assertIn("condition_match", row)
            with open(bundles, newline="") as f:
                row = next(csv.DictReader(f))
            self.assertIn("component_map_json", row)

    def test_liquidation_underwriting_reports_gate_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manifest.csv")
            with open(path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=E.LIQUIDATION_FIELDS)
                writer.writeheader()
                writer.writerow({
                    "line_id": "1", "title": "Known model", "quantity": "10",
                    "stated_retail_each_gbp": "100",
                    "deterministic_identity": "yes",
                    "expected_resale_each_gbp": "60", "sellable_rate": "0.8",
                    "fulfilment_each_gbp": "5", "notes": "",
                })
            result = E.underwrite_liquidation(
                path, bid=100, freight=20, testing=10, disposal=0, fee_rate=0.15)
        self.assertEqual(result["identity_coverage_pct"], 100)
        self.assertEqual(result["manifest_value_coverage_pct"], 100)
        self.assertAlmostEqual(result["expected_revenue_gbp"], 480)
        self.assertAlmostEqual(result["expected_contribution_gbp"], 238)
        self.assertEqual(result["largest_uncertain_profit_share_pct"], 0)


if __name__ == "__main__":
    unittest.main()
