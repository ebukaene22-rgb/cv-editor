import csv
import gzip
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))

import comp
import identifiers as ID
import scan


class IdentifierTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(scan.SCHEMA)

    def add(self, sku, url, category="Parts"):
        self.conn.execute(
            "INSERT INTO obs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("2026-01-01T00:00:00Z", "shop.test", "parts", "US", sku,
             "Product", "Vendor", 10.0, 20.0, "USD", 1, 100, url, category))

    def test_gtin_normalization_and_check_digit(self):
        self.assertEqual(ID.normalize_gtin("847974-010426"), "847974010426")
        self.assertTrue(ID.valid_gtin("847974010426"))
        self.assertFalse(ID.valid_gtin("847974010427"))
        self.assertIsNone(ID.normalize_gtin("SKU847974010426"))

    def test_product_ajax_url_preserves_locale_path(self):
        url = "https://shop.test/en-gb/products/widget™?variant=123"
        self.assertEqual(
            ID.product_ajax_url(url),
            "https://shop.test/en-gb/products/widget%E2%84%A2.js")

    def test_audit_reports_coverage_collisions_and_exact_resolution(self):
        self.add("SKU-A", "https://shop.test/products/a?variant=1")
        self.add("SKU-B", "https://shop.test/products/b?variant=2")
        payloads = {
            "https://shop.test/products/a.js": {
                "id": 10, "title": "A", "vendor": "Maker",
                "variants": [
                    {"id": 1, "title": "One", "sku": "SKU-A1",
                     "barcode": "847974010426", "price": 1000,
                     "available": True},
                    {"id": 2, "title": "Two", "sku": "SKU-A2",
                     "barcode": "847974010426", "price": 1000,
                     "available": False},
                ],
            },
            "https://shop.test/products/b.js": {
                "id": 20, "title": "B", "vendor": "Maker",
                "variants": [
                    {"id": 3, "title": "Three", "sku": "SKU-B",
                     "barcode": "847974010427", "price": 2000,
                     "available": True},
                    {"id": 4, "title": "Four", "sku": "",
                     "barcode": None, "price": 2000, "available": True},
                ],
            },
        }

        def fetcher(url, timeout):
            return payloads[url]

        class Ebay:
            def lookup_gtin(self, gtin, region):
                return {"n": 4, "exact_gtin_items": 2}

        stores = [{"platform": "shopify", "domain": "shop.test",
                   "currency": "USD", "region": "US", "group": "parts"}]
        with tempfile.TemporaryDirectory() as tmp:
            coverage = os.path.join(tmp, "coverage.csv")
            ledger = os.path.join(tmp, "ledger.csv.gz")
            totals = ID.run_audit(
                self.conn, stores, coverage, ledger, sample_per_store=10,
                delay=0, fetcher=fetcher, ebay=Ebay(), max_ebay_lookups=10)
            with open(coverage, newline="") as stream:
                rows = list(csv.DictReader(stream))
            with gzip.open(ledger, "rt", newline="") as stream:
                evidence = list(csv.DictReader(stream))

        store = next(row for row in rows if row["row_scope"] == "store_total")
        self.assertEqual(totals["variants"], 4)
        self.assertEqual(store["variants_with_valid_gtin"], "2")
        self.assertEqual(store["gtin_coverage_pct"], "50.00")
        self.assertEqual(store["invalid_barcodes"], "1")
        self.assertEqual(store["gtin_collision_groups"], "1")
        self.assertEqual(store["ebay_gtins_exact_confirmed"], "1")
        self.assertEqual(len(evidence), 4)

    def test_exact_gtin_lookup_never_uses_synthetic_data(self):
        client = comp.EbayComp(self.conn, synthetic=True)
        with self.assertRaises(RuntimeError):
            client.lookup_gtin("847974010426")

    def test_audit_retries_rate_limits(self):
        self.add("SKU-A", "https://shop.test/products/a")
        attempts = []

        def fetcher(url, timeout):
            attempts.append(url)
            if len(attempts) == 1:
                raise urllib.error.HTTPError(url, 429, "rate limited", {}, None)
            return {"id": 1, "title": "A", "vendor": "Maker", "variants": []}

        stores = [{"platform": "shopify", "domain": "shop.test"}]
        with tempfile.TemporaryDirectory() as tmp:
            totals = ID.run_audit(
                self.conn, stores, os.path.join(tmp, "coverage.csv"),
                os.path.join(tmp, "ledger.csv.gz"), delay=0, fetcher=fetcher,
                retries=1)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(totals["products_succeeded"], 1)


if __name__ == "__main__":
    unittest.main()
