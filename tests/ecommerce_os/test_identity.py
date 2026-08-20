from __future__ import annotations

import pytest

from ecommerce_os.identity import (
    gtin_check_digit,
    normalize_brand,
    normalize_gtin,
    normalize_mpn,
    normalize_title,
    parse_pack_count,
)

# A real, check-digit-valid EAN-13.
VALID_EAN13 = "4006381333931"


class TestGtin:
    def test_valid_ean13_is_padded_to_gtin14(self):
        assert normalize_gtin(VALID_EAN13) == "0" + VALID_EAN13

    def test_separators_and_whitespace_are_stripped(self):
        assert normalize_gtin(" 4-006381 333931 ") == "0" + VALID_EAN13

    def test_bad_check_digit_is_rejected_rather_than_trusted(self):
        # A typo'd GTIN is worse than a missing one: it would otherwise be
        # treated as deterministic proof of identity.
        assert normalize_gtin("4006381333930") is None

    def test_implausible_length_is_rejected(self):
        assert normalize_gtin("12345") is None

    def test_absent_gtin_is_none(self):
        assert normalize_gtin(None) is None
        assert normalize_gtin("") is None

    def test_check_digit_round_trips(self):
        body = VALID_EAN13[:-1]
        assert gtin_check_digit(body) == int(VALID_EAN13[-1])

    @pytest.mark.parametrize("length", [8, 12, 13, 14])
    def test_all_gtin_lengths_normalise_to_14(self, length):
        body = "1" * (length - 1)
        candidate = body + str(gtin_check_digit(body))
        assert normalize_gtin(candidate) == candidate.zfill(14)


class TestNormalisation:
    def test_brand_is_casefolded_and_deaccented(self):
        assert normalize_brand("Nescafé") == "nescafe"

    def test_corporate_suffixes_are_dropped(self):
        assert normalize_brand("Acme Ltd") == "acme"
        assert normalize_brand("ACME GmbH") == "acme"

    def test_mpn_separators_are_meaningless(self):
        assert normalize_mpn("abc-123") == normalize_mpn("ABC 123") == "ABC123"

    def test_two_character_mpn_is_a_feed_artefact(self):
        # Would otherwise collide across the entire catalogue.
        assert normalize_mpn("A1") is None

    def test_title_noise_words_are_removed(self):
        assert normalize_title("Genuine NEW Brita Maxtra for UK") == "brita maxtra"

    def test_empty_inputs_yield_none(self):
        assert normalize_brand("") is None
        assert normalize_title("   ") is None
        assert normalize_mpn(None) is None


class TestPackCount:
    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Brita Maxtra Pro 3 Pack", 3),
            ("Brita Maxtra Pro 3-Pack", 3),
            ("Brita Maxtra Pro, pack of 24", 24),
            ("Widget x12", 12),
            ("Widget 6 pcs", 6),
            ("Widget 10 count", 10),
        ],
    )
    def test_common_forms(self, title, expected):
        assert parse_pack_count(title) == expected

    def test_compound_pack_multiplies(self):
        # "2 x 3 pack" is six units - not two, and not three.
        assert parse_pack_count("Brita Maxtra Pro 2 x 3 pack") == 6

    def test_no_pack_information_is_none_not_one(self):
        # Assuming a single unit when the feed is silent is how a case of 24
        # gets sold for the price of one.
        assert parse_pack_count("Brita Maxtra Pro Filter") is None

    def test_model_numbers_are_not_mistaken_for_pack_sizes(self):
        assert parse_pack_count("Printer Model 2200 maintenance kit") is None
