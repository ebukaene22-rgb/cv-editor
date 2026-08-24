#!/usr/bin/env python3
"""Parser tests for the identity-evidence route. No network."""
import unittest

from arbitrage import storelink


class HandleParsing(unittest.TestCase):
    def test_storefront_and_seller_links(self):
        html = ('<a href="https://www.ebay.co.uk/str/gymsharkstore">eBay</a>'
                '<a href="https://www.ebay.com/usr/rokform">shop</a>')
        self.assertEqual(storelink.handles_in(html),
                         {"gymsharkstore", "rokform"})

    def test_see_other_items_link(self):
        html = '<a href="https://www.ebay.co.uk/sch/i.html?_ssn=itinstock">x</a>'
        self.assertIn("itinstock", storelink.handles_in(html))

    def test_item_links_are_not_handles(self):
        # /itm/ is a listing, not a store; digits are never handles
        html = '<a href="https://www.ebay.com/itm/123456789">item</a>'
        self.assertEqual(storelink.handles_in(html), set())

    def test_navigation_paths_are_not_handles(self):
        html = ('<a href="https://www.ebay.co.uk/help/home">help</a>'
                '<a href="https://www.ebay.com/deals">deals</a>')
        self.assertEqual(storelink.handles_in(html), set())

    def test_empty_and_none_are_safe(self):
        self.assertEqual(storelink.handles_in(""), set())
        self.assertEqual(storelink.handles_in(None), set())


class Confirmation(unittest.TestCase):
    def test_punctuation_differences_still_confirm(self):
        # eBay store SLUGS drop the punctuation usernames carry
        ok, why = storelink.confirms(
            "gymshark.com", "gymshark-store", linked={"gymsharkstore"})
        self.assertTrue(ok, why)

    def test_reseller_handle_is_not_confirmed(self):
        ok, _ = storelink.confirms(
            "gymshark.com", "hidie_gymshark", linked={"gymsharkstore"})
        self.assertFalse(ok)

    def test_no_links_does_not_confirm(self):
        ok, why = storelink.confirms("rokform.com", "rokform", linked=set())
        self.assertFalse(ok)
        # and the reason must not read as proof of absence
        self.assertIn("not absence", why)

    def test_unrelated_link_does_not_confirm(self):
        ok, _ = storelink.confirms(
            "rokform.com", "rokform", linked={"someoneelse"})
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
