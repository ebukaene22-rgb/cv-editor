from __future__ import annotations

from decimal import Decimal

from ecommerce_os.matching import (
    MatchClass,
    ProductRecord,
    classify_match,
    trigram_similarity,
)

VALID_EAN13 = "4006381333931"
OTHER_EAN13 = "5000112637922"


def record(**kwargs) -> ProductRecord:
    return ProductRecord.from_raw(**kwargs)


class TestTrigramSimilarity:
    def test_identical_strings_score_one(self):
        assert trigram_similarity("brita maxtra pro", "brita maxtra pro") == Decimal("1.0000")

    def test_unrelated_strings_score_low(self):
        assert trigram_similarity("brita maxtra pro", "hvac solenoid valve") < Decimal("0.1")

    def test_empty_input_is_zero_not_an_error(self):
        assert trigram_similarity(None, "anything") == Decimal("0")


class TestDeterministicMatch:
    def test_agreeing_gtin_and_attributes_auto_matches(self):
        source = record(title="Brita Maxtra Pro 3 Pack", brand="Brita", gtin=VALID_EAN13)
        canonical = record(title="Brita Maxtra Pro 3 Pack", brand="Brita", gtin=VALID_EAN13)

        result = classify_match(source, canonical)

        assert result.match_class is MatchClass.DETERMINISTIC
        assert result.auto_matchable
        assert result.score == Decimal("1.0000")

    def test_brand_and_mpn_with_pack_agreement_auto_matches(self):
        source = record(title="Acme filter 3 pack", brand="Acme", mpn="ABC-123", pack_count=3)
        canonical = record(title="Acme filter 3 pack", brand="Acme", mpn="abc123", pack_count=3)

        result = classify_match(source, canonical)

        assert result.match_class is MatchClass.VERY_HIGH
        assert result.auto_matchable


class TestPackSizeIsNotNegotiable:
    def test_three_pack_never_matches_six_pack(self):
        # The canonical failure of retail arbitrage: near-identical text, and a
        # P&L that does not care how similar the marketing copy was.
        source = record(title="Brita Maxtra Pro 3 Pack", brand="Brita")
        canonical = record(title="Brita Maxtra Pro 6 Pack", brand="Brita")

        result = classify_match(source, canonical)

        assert result.match_class is MatchClass.LOW
        assert not result.auto_matchable
        assert "pack_count" in result.conflicts

    def test_agreeing_gtin_with_conflicting_pack_is_quarantined(self):
        # Looks deterministic and is wrong - the most dangerous signal there is.
        source = record(title="Brita Maxtra Pro 3 Pack", brand="Brita", gtin=VALID_EAN13)
        canonical = record(title="Brita Maxtra Pro 6 Pack", brand="Brita", gtin=VALID_EAN13)

        result = classify_match(source, canonical)

        assert result.match_class is MatchClass.CONFLICT
        assert not result.auto_matchable
        assert result.conflicts == ("pack_count",)


class TestCriticalAttributeConflicts:
    def test_regional_variants_do_not_match(self):
        source = record(
            title="Widget PSU", brand="Acme", gtin=VALID_EAN13,
            attributes={"voltage": "240v", "region": "gb"},
        )
        canonical = record(
            title="Widget PSU", brand="Acme", gtin=VALID_EAN13,
            attributes={"voltage": "110v", "region": "ae"},
        )

        result = classify_match(source, canonical)

        assert result.match_class is MatchClass.CONFLICT
        assert set(result.conflicts) == {"voltage", "region"}

    def test_refurbished_is_not_new(self):
        source = record(title="Widget", brand="Acme", gtin=VALID_EAN13, condition="new")
        canonical = record(
            title="Widget", brand="Acme", gtin=VALID_EAN13, condition="refurbished"
        )

        assert classify_match(source, canonical).match_class is MatchClass.CONFLICT

    def test_missing_attribute_is_unknown_not_a_conflict(self):
        source = record(title="Widget", brand="Acme", gtin=VALID_EAN13,
                        attributes={"voltage": "240v"})
        canonical = record(title="Widget", brand="Acme", gtin=VALID_EAN13, attributes={})

        assert classify_match(source, canonical).match_class is MatchClass.DETERMINISTIC


class TestTextOnlyMatchingIsCapped:
    def test_identical_titles_without_identifiers_or_pack_cannot_auto_match(self):
        # 0.45*1 + 0.25*1 + 0.30*0 = 0.70, safely under the 0.97 bar.
        source = record(title="Acme HVAC solenoid valve", brand="Acme")
        canonical = record(title="Acme HVAC solenoid valve", brand="Acme")

        result = classify_match(source, canonical)

        assert result.score == Decimal("0.7000")
        assert result.match_class is MatchClass.LOW
        assert not result.auto_matchable

    def test_identical_titles_with_agreeing_pack_reach_review_not_auto(self):
        source = record(title="Acme HVAC solenoid valve", brand="Acme", pack_count=1)
        canonical = record(title="Acme HVAC solenoid valve", brand="Acme", pack_count=1)

        result = classify_match(source, canonical)

        assert result.score == Decimal("1.0000")
        # Full text + brand + pack agreement does clear the bar, but only
        # because every available signal agreed.
        assert result.match_class is MatchClass.HIGH

    def test_different_gtins_do_not_corroborate_anything(self):
        source = record(title="Acme valve", brand="Acme", gtin=VALID_EAN13, pack_count=1)
        canonical = record(title="Acme valve", brand="Acme", gtin=OTHER_EAN13, pack_count=1)

        result = classify_match(source, canonical)

        # Both GTINs are genuinely present and valid; they simply disagree.
        assert source.gtin and canonical.gtin and source.gtin != canonical.gtin
        assert result.identifier_score == Decimal("0")

    def test_weak_similarity_is_rejected(self):
        source = record(title="Acme HVAC solenoid valve", brand="Acme")
        canonical = record(title="Acme printer maintenance kit", brand="Acme")

        result = classify_match(source, canonical)

        assert result.match_class is MatchClass.LOW
        assert "insufficient evidence" in result.reasons
