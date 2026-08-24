import csv
import gzip
import json
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

    def test_mpn_condition_families_are_strict(self):
        self.assertTrue(comp.EbayComp._condition_matches(
            "New - Open box", "open_box"))
        self.assertTrue(comp.EbayComp._condition_matches(
            "Certified - Refurbished", "certified_refurbished"))
        self.assertFalse(comp.EbayComp._condition_matches(
            "Seller refurbished", "certified_refurbished"))
        self.assertFalse(comp.EbayComp._condition_matches("New", "open_box"))
        self.assertTrue(comp.EbayComp._condition_matches(
            "For parts or not working", "for_parts", "7000"))

    def test_liquidation_condition_mapping_is_conservative(self):
        self.assertEqual(MPN._liquidation_condition_family(
            "Untested Customer Returns;Used"), "for_parts")
        self.assertEqual(MPN._liquidation_condition_family("Used"), "used")
        self.assertEqual(MPN._liquidation_condition_family("Like New"),
                         "open_box")

    def test_liquidation_exit_audit_freezes_one_gtin_per_model(self):
        class Ebay:
            def __init__(self):
                self.calls = []

            def lookup_gtin(self, gtin, **kwargs):
                self.calls.append((gtin, kwargs["condition"]))
                return {"resolution_status": "NOT_FOUND"}

        fields = ["model", "manufacturers", "valid_gtins", "conditions",
                  "lot_count", "total_quantity"]
        with tempfile.TemporaryDirectory() as tmp:
            universe = os.path.join(tmp, "universe.csv")
            output = os.path.join(tmp, "output.csv.gz")
            with open(universe, "w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "model": "W1", "manufacturers": "Maker",
                    "valid_gtins": "123456789012;1234567890123",
                    "conditions": "Untested Customer Returns;Used",
                    "lot_count": "1", "total_quantity": "2",
                })
            ebay = Ebay()
            result = MPN.run_liquidation_exit_audit(
                ebay, universe, output)
        self.assertEqual(ebay.calls, [("123456789012", "for_parts")])
        self.assertEqual(result["identities"], 1)
        self.assertFalse(result["advance_economics"])

    def test_source_brand_matching_uses_only_approved_families(self):
        self.assertEqual(MPN.source_brand_match("Frigidaire", "Electrolux"),
                         "CORPORATE_BRAND_FAMILY")
        self.assertEqual(MPN.source_brand_match("Whirlpool", "Maytag"),
                         "CORPORATE_BRAND_FAMILY")
        self.assertEqual(MPN.source_brand_match("General Electric", "GE"),
                         "EXACT_BRAND")
        self.assertEqual(MPN.source_brand_match("DeWalt", "Black & Decker"), "")

    def test_liquidation_coverage_requires_three_frozen_identities(self):
        resolution_fields = ["mpn", "usable_market"]
        coverage_fields = ["source", "mpn", "exact_search_results"]
        with tempfile.TemporaryDirectory() as tmp:
            resolution = os.path.join(tmp, "resolution.csv")
            coverage = os.path.join(tmp, "coverage.csv")
            with open(resolution, "w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=resolution_fields)
                writer.writeheader()
                for mpn in ("A1", "B2", "C3"):
                    writer.writerow({"mpn": mpn, "usable_market": "1"})
            with open(coverage, "w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=coverage_fields)
                writer.writeheader()
                for source in ("one", "two"):
                    for mpn in ("A1", "B2", "C3"):
                        writer.writerow({
                            "source": source, "mpn": mpn,
                            "exact_search_results": "1" if source == "one" else "0",
                        })
            result = MPN.run_liquidation_coverage_gate(coverage, resolution)
        self.assertEqual(result["searches"], 6)
        self.assertEqual(result["matched_identities"], 3)
        self.assertTrue(result["source_gate_passed"])

    def test_direct_liquidation_parser_reads_structured_manifest(self):
        state = {"__SSR_STATE__": {"single-product": {"product": {
            "masterSku": "LOT1", "price": 100, "units": 2,
            "products": [{"manufacturer": "Whirlpool", "model": "A1",
                          "condition": "Used", "quantity": 2,
                          "retailPrice": 50}],
        }}}}
        html = ("<html><script>window.__INITIAL_STATE__ = " +
                json.dumps(state) + ";</script></html>")
        product = MPN.parse_direct_liquidation_page(html)
        self.assertEqual(product["masterSku"], "LOT1")
        self.assertEqual(product["products"][0]["model"], "A1")

    def test_mpn_basket_parser_uses_structured_url_suffix(self):
        row = MPN._parse_candidate(
            "https://www.ereplacementparts.com/parts/dishwasher/"
            "general-electric/erp260801/motor-and-pump-kit-wd26x10013/",
            "2026-08-15")
        self.assertEqual(row["brand"], "General Electric")
        self.assertEqual(row["mpn"], "WD26X10013")
        self.assertEqual(row["source_category"], "dishwasher")

    def test_mpn_economics_rejects_dominated_row_before_unknown_costs(self):
        source_fields = ["brand", "mpn", "source_verified_at",
                         "source_price_usd", "source_stock",
                         "source_shipping_usd", "source_shipping_status"]
        resolution_fields = [
            "cohort", "source_category", "brand", "mpn", "title",
            "source_url", "usable_market", "coherent_depth", "p25_price"]
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source.csv")
            resolution = os.path.join(tmp, "resolution.csv.gz")
            output = os.path.join(tmp, "economics.csv")
            with open(source, "w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=source_fields)
                writer.writeheader()
                writer.writerow({
                    "brand": "DeWalt", "mpn": "N097361",
                    "source_verified_at": "2026-08-24T00:00:00Z",
                    "source_price_usd": "8.73", "source_stock": "In Stock",
                    "source_shipping_usd": "",
                    "source_shipping_status": "ADDRESS_QUOTE_REQUIRED"})
            with gzip.open(resolution, "wt", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=resolution_fields)
                writer.writeheader()
                writer.writerow({
                    "cohort": "tool", "source_category": "angle-grinder",
                    "brand": "DeWalt", "mpn": "N097361", "title": "Gear",
                    "source_url": "https://source.test/n097361",
                    "usable_market": "1", "coherent_depth": "3",
                    "p25_price": "15.27"})
            totals = MPN.run_economics_gate(
                source, resolution, output, usd_to_gbp=0.73228)
            with open(output, newline="") as stream:
                row = next(csv.DictReader(stream))
        self.assertEqual(totals["rejected_pre_cost"], 1)
        self.assertFalse(totals["precheck_passed"])
        self.assertEqual(row["gross_spread_pre_cost_usd"], "6.54")
        self.assertEqual(row["net_contribution_upper_bound_gbp"], "4.79")
        self.assertEqual(row["economics_status"],
                         "REJECT_PRE_COST_SPREAD_BELOW_15_GBP")

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
