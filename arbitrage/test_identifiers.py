import csv
import gzip
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))

import comp
import identifiers as ID
import mpn as MPN
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
        self.assertEqual(ID.gtin_type("847974010426"), "UPC-A")
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
                     "barcode": "4006381333931", "price": 2000,
                     "available": True},
                    {"id": 4, "title": "Four", "sku": "",
                     "barcode": "847974010427", "price": 2000,
                     "available": True},
                    {"id": 5, "title": "Five", "sku": "",
                     "barcode": None, "price": 2000, "available": True},
                ],
            },
        }

        def fetcher(url, timeout):
            return payloads[url]

        class Ebay:
            def lookup_gtin(self, gtin, region, **kwargs):
                return {"n": 4, "inspected": 4, "exact_gtin_items": 4,
                        "coherent": True, "usable_market": True,
                        "resolution_status": "EXACT_USABLE", "median": 25,
                        "p25": 20, "p75": 30, "currency": "USD"}

        stores = [{"platform": "shopify", "domain": "shop.test",
                   "currency": "USD", "region": "US", "group": "parts"}]
        with tempfile.TemporaryDirectory() as tmp:
            coverage = os.path.join(tmp, "coverage.csv")
            ledger = os.path.join(tmp, "ledger.csv.gz")
            resolution = os.path.join(tmp, "resolution.csv.gz")
            totals = ID.run_audit(
                self.conn, stores, coverage, ledger, sample_per_store=10,
                delay=0, fetcher=fetcher, ebay=Ebay(), max_ebay_lookups=10,
                resolution_path=resolution)
            with open(coverage, newline="") as stream:
                rows = list(csv.DictReader(stream))
            with gzip.open(ledger, "rt", newline="") as stream:
                evidence = list(csv.DictReader(stream))

        store = next(row for row in rows if row["row_scope"] == "store_total")
        self.assertEqual(totals["variants"], 5)
        self.assertEqual(store["variants_with_valid_gtin"], "3")
        self.assertEqual(store["gtin_coverage_pct"], "60.00")
        self.assertEqual(store["invalid_barcodes"], "1")
        self.assertEqual(store["gtin_collision_groups"], "1")
        self.assertEqual(store["variants_with_exact_source_identity"], "1")
        self.assertEqual(store["source_identity_coverage_pct"], "20.00")
        self.assertEqual(store["ebay_gtins_exact_confirmed"], "1")
        self.assertEqual(store["ebay_gtins_usable_market"], "1")
        self.assertEqual(len(evidence), 5)
        collision = [row for row in evidence if row["gtin"] == "847974010426"]
        self.assertTrue(all(row["source_identity_status"] ==
                            "REJECT_SOURCE_COLLISION" for row in collision))
        exact = next(row for row in evidence if row["gtin"] == "4006381333931")
        self.assertEqual(exact["identity_status"], "EXACT")

    def test_exact_gtin_lookup_never_uses_synthetic_data(self):
        client = comp.EbayComp(self.conn, synthetic=True)
        with self.assertRaises(RuntimeError):
            client.lookup_gtin("847974010426")

    def test_unknown_ebay_marketplace_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported eBay region"):
            comp.marketplace_id("AE")

    def test_mpn_lookup_requires_exact_brand_and_mpn_with_depth(self):
        client = comp.EbayComp(self.conn, synthetic=True)

        def browse(url, marketplace):
            if "item_summary" in url:
                return {"total": 4, "itemSummaries": [
                    {"itemId": f"v1|{index}|0"} for index in range(4)]}
            return {"items": [
                {"itemId": "v1|1|0", "title": "Pump", "brand": "GE",
                 "mpn": "WD26X10013", "condition": "New",
                 "price": {"value": "40", "currency": "USD"}},
                {"itemId": "v1|2|0", "title": "Pump", "brand": "General Electric",
                 "mpn": "WD26-X10013", "condition": "New",
                 "price": {"value": "50", "currency": "USD"}},
                {"itemId": "v1|3|0", "title": "Pump", "brand": "GE",
                 "mpn": "WD26X10013", "condition": "New",
                 "price": {"value": "60", "currency": "USD"}},
                {"itemId": "v1|4|0", "title": "Wrong", "brand": "Other",
                 "mpn": "WD26X10013", "condition": "New",
                 "price": {"value": "10", "currency": "USD"}},
            ]}

        client._browse_json = browse
        result = client._live_mpn(
            "General Electric", "WD26X10013", "EBAY_US", 20, 20, 3)
        self.assertEqual(result["exact_mpn_items"], 4)
        self.assertEqual(result["exact_brand_mpn_items"], 3)
        self.assertEqual(result["coherent_depth"], 3)
        self.assertTrue(result["usable_market"])
        self.assertEqual(result["median"], 50)

    def test_mpn_depth_excludes_secondary_condition_items(self):
        details = [
            {"brand": "DeWalt", "mpn": "N039404", "condition": "New",
             "pack": "", "lot_size": "", "price": 20, "currency": "USD"},
            {"brand": "DeWalt", "mpn": "N039404", "condition": "Open box",
             "pack": "", "lot_size": "", "price": 5, "currency": "USD"},
        ]
        result = comp.EbayComp._classify_mpn_result(
            "DeWalt", "N039404", details, 2, 2, False, 2)
        self.assertEqual(result["exact_brand_mpn_items"], 2)
        self.assertEqual(result["coherent_depth"], 1)
        self.assertFalse(result["usable_market"])
        self.assertEqual(result["median"], 20)

    def test_mpn_basket_parser_uses_structured_url_suffix(self):
        row = MPN._parse_candidate(
            "https://www.ereplacementparts.com/parts/dishwasher/"
            "general-electric/erp260801/motor-and-pump-kit-wd26x10013/",
            "2026-08-15")
        self.assertEqual(row["brand"], "General Electric")
        self.assertEqual(row["mpn"], "WD26X10013")
        self.assertEqual(row["source_category"], "dishwasher")

    def test_gtin_lookup_batches_details_and_requires_coherence(self):
        client = comp.EbayComp(self.conn, synthetic=True)
        calls = []
        conflict = [False]

        def browse(url, marketplace):
            calls.append(url)
            if "item_summary" in url:
                return {"total": 2, "itemSummaries": [
                    {"itemId": "v1|1|0"}, {"itemId": "v1|2|0"}]}
            return {"items": [
                {"itemId": "v1|1|0", "title": "Widget", "gtin": "847974010426",
                 "brand": "Maker", "model": "W1", "categoryId": "1",
                 "price": {"value": "20", "currency": "GBP"}},
                {"itemId": "v1|2|0", "title": "Widget", "gtin": "847974010426",
                 "brand": "Maker", "model": "W2" if conflict[0] else "W1",
                 "categoryId": "1",
                 "price": {"value": "30", "currency": "GBP"}},
            ]}

        client._browse_json = browse
        result = client._live_gtin("847974010426", "EBAY_GB", 50, 20, 3)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["exact_gtin_items"], 2)
        self.assertTrue(result["coherent"])
        self.assertFalse(result["usable_market"])
        self.assertEqual(result["resolution_status"], "EXACT_SHALLOW")
        self.assertEqual(result["median"], 25)
        conflict[0] = True
        result = client._live_gtin("847974010426", "EBAY_GB", 50, 20, 3)
        self.assertFalse(result["coherent"])
        self.assertEqual(result["resolution_status"], "AMBIGUOUS")
        self.assertEqual(result["ambiguous_fields"], ["model"])

    def test_gtin_lookup_chunks_bulk_item_details(self):
        client = comp.EbayComp(self.conn, synthetic=True)
        calls = []

        def browse(url, marketplace):
            calls.append(url)
            if "item_summary" in url:
                return {"total": 21, "itemSummaries": [
                    {"itemId": f"v1|{index}|0"} for index in range(21)]}
            ids = urllib.parse.parse_qs(
                urllib.parse.urlsplit(url).query)["item_ids"][0].split(",")
            return {"items": [
                {"itemId": item_id, "gtin": "847974010426",
                 "brand": "Maker", "model": "W1", "categoryId": "1",
                 "price": {"value": "20", "currency": "GBP"}}
                for item_id in ids]}

        client._browse_json = browse
        result = client._live_gtin("847974010426", "EBAY_GB", 50, 50, 3)
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["inspected"], 21)
        self.assertEqual(result["resolution_status"], "EXACT_USABLE")

    def test_gtin_lookup_falls_back_when_bulk_access_is_denied(self):
        client = comp.EbayComp(self.conn, synthetic=True)
        calls = []

        def browse(url, marketplace):
            calls.append(url)
            if "item_summary" in url:
                return {"total": 1, "itemSummaries": [{"itemId": "v1|1|0"}]}
            if "item_ids=" in url:
                return None
            return {"itemId": "v1|1|0", "gtin": "847974010426",
                    "brand": "Maker", "model": "W1", "categoryId": "1",
                    "price": {"value": "20", "currency": "GBP"}}

        client._browse_json = browse
        result = client._live_gtin("847974010426", "EBAY_GB", 50, 50, 1)
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["exact_gtin_items"], 1)
        self.assertEqual(result["resolution_status"], "EXACT_USABLE")

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

    def test_ebay_annotation_ignores_failed_source_rows(self):
        rows = [{"fetch_status": "error", "fetch_error": "HTTP 404"}]

        class Ebay:
            def lookup_gtin(self, gtin, region, **kwargs):
                raise AssertionError("a failed source row must not be resolved")

        results = ID._resolve_ebay(rows, Ebay(), "GB", 10, 50, 3)
        self.assertEqual(results, {})

    def test_ebay_lookup_limit_uses_stable_hash_order(self):
        gtins = ["4006381333931", "847974010426", "5012345678900"]
        rows = [{"gtin": gtin, "source_identity_status": "EXACT_SOURCE"}
                for gtin in gtins]
        attempted = []

        class Ebay:
            def lookup_gtin(self, gtin, region, **kwargs):
                attempted.append(gtin)
                return {"n": 0, "resolution_status": "NOT_FOUND"}

        ID._resolve_ebay(rows, Ebay(), "GB", 2, 50, 3)
        expected = sorted(
            gtins, key=lambda value: ID.hashlib.sha1(value.encode()).hexdigest())[:2]
        self.assertEqual(attempted, expected)


if __name__ == "__main__":
    unittest.main()
