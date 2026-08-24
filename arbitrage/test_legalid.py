#!/usr/bin/env python3
"""Identity-evidence tests. No network — fixtures mirror getItem payloads."""
import unittest

from arbitrage import legalid

ITINSTOCK = {"registrationNumber": "12704142", "vat": "GB483890250",
             "name": "IT In Stock Ltd", "postcode": "NG10 1EA"}


def item(**legal):
    acct = legal.pop("account_type", "BUSINESS")
    return {"seller": {"username": "itinstock", "sellerAccountType": acct,
                       "sellerLegalInfo": legal}}


class Normalisation(unittest.TestCase):
    def test_uk_company_numbers_are_zero_padded(self):
        # 3708416 and 03708416 are the same company
        self.assertTrue(legalid.company_match("3708416", "03708416"))

    def test_prefixed_company_numbers(self):
        self.assertTrue(legalid.company_match("SC123456", "sc 123456"))

    def test_vat_country_prefix_optional(self):
        self.assertTrue(legalid.vat_match("483890250", "GB483890250"))
        self.assertTrue(legalid.vat_match("GB 483 890 250", "gb483890250"))

    def test_different_numbers_do_not_match(self):
        self.assertFalse(legalid.company_match("12704142", "03708416"))
        self.assertFalse(legalid.vat_match("GB483890250", "GB999999999"))

    def test_empty_never_matches(self):
        self.assertFalse(legalid.company_match("", ""))
        self.assertFalse(legalid.vat_match("", "GB483890250"))
        self.assertFalse(legalid.name_match("", "IT In Stock"))

    def test_corporate_suffixes_ignored(self):
        self.assertTrue(legalid.name_match("IT In Stock Ltd", "IT In Stock"))

    def test_short_names_do_not_substring_match(self):
        self.assertFalse(legalid.name_match("ab", "abcdefgh"))


class Hierarchy(unittest.TestCase):
    def test_registration_is_confirming(self):
        obs = legalid.extract(item(name="IT In Stock Ltd",
                                   registrationNumber="12704142"))
        tier, why = legalid.evaluate(obs, ITINSTOCK)
        self.assertEqual(tier, "registration")
        self.assertTrue(legalid.is_confirming(tier), why)

    def test_vat_is_confirming(self):
        obs = legalid.extract(item(name="Other Name",
                                   vatDetails=[{"vatId": "GB 483 890 250"}]))
        tier, _ = legalid.evaluate(obs, ITINSTOCK)
        self.assertEqual(tier, "vat")
        self.assertTrue(legalid.is_confirming(tier))

    def test_name_plus_address_ranks_below_numbers(self):
        obs = legalid.extract(item(name="IT In Stock Ltd",
                                   legalAddress={"postalCode": "NG10 1EA"}))
        tier, _ = legalid.evaluate(obs, ITINSTOCK)
        self.assertEqual(tier, "name_address")
        self.assertFalse(legalid.is_confirming(tier))

    def test_name_alone_is_supporting_only(self):
        obs = legalid.extract(item(name="IT In Stock Ltd"))
        tier, why = legalid.evaluate(obs, ITINSTOCK)
        self.assertEqual(tier, "name")
        self.assertFalse(legalid.is_confirming(tier))
        self.assertIn("supporting", why)

    def test_vatdetails_accepts_dict_or_list(self):
        for shape in ({"vatId": "GB483890250"}, [{"vatId": "GB483890250"}]):
            obs = legalid.extract(item(name="x", vatDetails=shape))
            self.assertEqual(legalid.evaluate(obs, ITINSTOCK)[0], "vat")


class AbsenceIsNotRefutation(unittest.TestCase):
    def test_missing_block_is_unavailable_not_rejection(self):
        obs = legalid.extract({"seller": {"username": "itinstock"}})
        tier, why = legalid.evaluate(obs, ITINSTOCK)
        self.assertIsNone(tier)
        self.assertEqual(why, "legal_info_unavailable")

    def test_one_bare_listing_does_not_close_the_route(self):
        # fields are conditional: sample several before concluding
        obs = [legalid.extract({"seller": {"username": "itinstock"}}),
               legalid.extract(item(name="IT In Stock Ltd",
                                    registrationNumber="12704142"))]
        tier, _ = legalid.best_of(obs, ITINSTOCK)
        self.assertEqual(tier, "registration")

    def test_all_bare_reports_unavailable_with_sample_size(self):
        obs = [legalid.extract({"seller": {"username": "x"}})] * 3
        tier, why = legalid.best_of(obs, ITINSTOCK)
        self.assertIsNone(tier)
        self.assertIn("unavailable", why)
        self.assertIn("3", why)

    def test_published_but_mismatched_is_distinguished(self):
        obs = legalid.extract(item(name="Totally Different Co",
                                   registrationNumber="99999999"))
        tier, why = legalid.evaluate(obs, ITINSTOCK)
        self.assertIsNone(tier)
        self.assertNotIn("unavailable", why)
        self.assertIn("different entity", why)

    def test_best_of_prefers_strongest_tier(self):
        obs = [legalid.extract(item(name="IT In Stock Ltd")),
               legalid.extract(item(name="z",
                                    vatDetails=[{"vatId": "GB483890250"}]))]
        self.assertEqual(legalid.best_of(obs, ITINSTOCK)[0], "vat")


if __name__ == "__main__":
    unittest.main()
