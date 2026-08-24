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
        tier, _ = legalid.evaluate(obs, ITINSTOCK)
        self.assertEqual(tier, legalid.UNAVAILABLE)
        self.assertFalse(legalid.is_confirming(tier))

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
        self.assertEqual(tier, legalid.UNAVAILABLE)
        self.assertIn("3", why)
        self.assertIn("NOT evidence against", why)

    def test_published_but_mismatched_is_a_different_state(self):
        obs = legalid.extract(item(name="Totally Different Co",
                                   registrationNumber="99999999"))
        tier, why = legalid.evaluate(obs, ITINSTOCK)
        self.assertEqual(tier, legalid.NO_MATCH)
        self.assertIn("against first-party", why)

    def test_no_match_and_unavailable_never_collapse(self):
        """The whole point: both leave a row candidate_active and they mean
        opposite things, so they must never share a value."""
        bare = legalid.extract({"seller": {"username": "x"}})
        mism = legalid.extract(item(name="Other Co",
                                    registrationNumber="99999999"))
        a, _ = legalid.best_of([bare] * 3, ITINSTOCK)
        b, _ = legalid.best_of([mism] * 3, ITINSTOCK)
        self.assertNotEqual(a, b)
        self.assertEqual(a, legalid.UNAVAILABLE)
        self.assertEqual(b, legalid.NO_MATCH)
        for t in (a, b):
            self.assertFalse(legalid.is_confirming(t))
            self.assertIn(t, legalid.NON_EVIDENCE)

    def test_any_published_block_outranks_bare_listings(self):
        # a seller that publishes details is resolvable even if unmatched
        bare = legalid.extract({"seller": {"username": "x"}})
        mism = legalid.extract(item(name="Other Co",
                                    registrationNumber="99999999"))
        self.assertEqual(legalid.best_of([bare, mism], ITINSTOCK)[0],
                         legalid.NO_MATCH)


class ResolvingPower(unittest.TestCase):
    def test_breakdown_separates_the_two_negatives(self):
        got = legalid.resolving_power(
            ["registration", "vat", "name_address", "name",
             legalid.NO_MATCH, legalid.UNAVAILABLE, legalid.UNAVAILABLE])
        self.assertEqual(got, {"confirmed": 2, "corroborated": 1,
                               "supporting": 1, "no_match": 1,
                               "unavailable": 2})

    def test_empty_population(self):
        self.assertEqual(sum(legalid.resolving_power([]).values()), 0)

    def test_best_of_prefers_strongest_tier(self):
        obs = [legalid.extract(item(name="IT In Stock Ltd")),
               legalid.extract(item(name="z",
                                    vatDetails=[{"vatId": "GB483890250"}]))]
        self.assertEqual(legalid.best_of(obs, ITINSTOCK)[0], "vat")


if __name__ == "__main__":
    unittest.main()
