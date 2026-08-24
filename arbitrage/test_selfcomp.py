#!/usr/bin/env python3
"""Regression tests pinned to the dealer-closeout false positives."""
import unittest

from arbitrage import selfcomp


class NameMatching(unittest.TestCase):
    def test_exact_store_is_self(self):
        hit, _ = selfcomp.is_self_comp("www.itinstock.com", "itinstock")
        self.assertTrue(hit)

    def test_suffixed_handle_is_self(self):
        for handle in ("itinstock-uk", "itinstock_store", "itinstock2024",
                       "ITInStock Ltd"):
            hit, why = selfcomp.is_self_comp("www.itinstock.com", handle)
            self.assertTrue(hit, f"{handle} not matched: {why}")

    def test_independent_sellers_survive(self):
        for handle in ("haubrich-it", "inetgrouponline", "motorboogie",
                       "partsbuego", "etontech", "dazzlingdeals007"):
            hit, _ = selfcomp.is_self_comp("www.itinstock.com", handle)
            self.assertFalse(hit, handle)

    def test_short_cores_do_not_collide(self):
        # "it" must not swallow every seller containing those letters
        hit, _ = selfcomp.is_self_comp("it.com", "digitalworld")
        self.assertFalse(hit)

    def test_missing_identity_is_not_a_match(self):
        self.assertFalse(selfcomp.is_self_comp("", "itinstock")[0])
        self.assertFalse(selfcomp.is_self_comp("www.itinstock.com", "")[0])


class Stripping(unittest.TestCase):
    def test_unattributed_items_are_kept_and_counted(self):
        items = [{"t": "a", "p": 1.0}, {"t": "b", "p": 2.0, "s": "itinstock"}]
        kept, dropped, reasons = selfcomp.strip_self_comps(
            items, "www.itinstock.com")
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(reasons["unattributed"], 1)


class FixedRatio(unittest.TestCase):
    # The nine itinstock PASSes: eBay ask was web price / 0.791666 in every
    # case. This is the signature the structural detector must catch.
    COHORT = [
        {"seller": "itinstock", "key": "TSZ1535987",      "source_price": 760.0,  "comp_price": 960.0},
        {"seller": "itinstock", "key": "FAN-7130-1U-R",   "source_price": 760.0,  "comp_price": 960.0},
        {"seller": "itinstock", "key": "P9K04A",          "source_price": 760.0,  "comp_price": 960.0},
        {"seller": "itinstock", "key": "CA07670-E236",    "source_price": 760.0,  "comp_price": 960.0},
        {"seller": "itinstock", "key": "CA08226-E906",    "source_price": 779.0,  "comp_price": 984.0},
        {"seller": "itinstock", "key": "P9K08A",          "source_price": 731.5,  "comp_price": 924.0},
        {"seller": "itinstock", "key": "55949BX",         "source_price": 712.5,  "comp_price": 900.0},
        {"seller": "itinstock", "key": "QFX10000-RE",     "source_price": 712.5,  "comp_price": 900.0},
        {"seller": "itinstock", "key": "N9K-C93108TC-FX", "source_price": 665.0,  "comp_price": 840.0},
        # genuinely independent sellers: no constant multiple
        {"seller": "etontech",        "key": "P9K08A",          "source_price": 731.5, "comp_price": 1670.0},
        {"seller": "inetgrouponline", "key": "N9K-C93108TC-FX", "source_price": 665.0, "comp_price": 965.0},
        {"seller": "haubrich-it",     "key": "VCNRTXA4000",     "source_price": 585.09, "comp_price": 791.24},
    ]

    def test_dual_channel_seller_is_flagged(self):
        hits = selfcomp.fixed_ratio_sellers(self.COHORT)
        self.assertIn("itinstock", hits)
        self.assertEqual(hits["itinstock"]["n"], 9)
        self.assertAlmostEqual(hits["itinstock"]["ratio"], 1.263158, places=5)

    def test_independent_sellers_are_not_flagged(self):
        hits = selfcomp.fixed_ratio_sellers(self.COHORT)
        for seller in ("etontech", "inetgrouponline", "haubrich-it"):
            self.assertNotIn(seller, hits)

    def test_needs_distinct_products(self):
        # the same product repeated is not evidence of a channel markup
        same = [dict(r, key="ONE") for r in self.COHORT[:4]]
        self.assertEqual(selfcomp.fixed_ratio_sellers(same), {})

    def test_ignores_unusable_rows(self):
        bad = [{"seller": "x", "key": "a", "source_price": 0, "comp_price": 1},
               {"seller": "x", "key": "b", "source_price": "-", "comp_price": 1},
               {"seller": "x", "key": "c"}]
        self.assertEqual(selfcomp.fixed_ratio_sellers(bad), {})


if __name__ == "__main__":
    unittest.main()
