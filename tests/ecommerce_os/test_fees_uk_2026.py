"""The UK 2026 fee fixture must resolve and reproduce the verified worked example."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ecommerce_os.data import uk_fee_book_2026
from ecommerce_os.data.fees_uk_2026 import AMAZON_UK_FEE_KINDS, EBAY_UK_FEE_KINDS

AS_OF = date(2026, 8, 20)


@pytest.fixture(scope="module")
def book():
    return uk_fee_book_2026()


class TestEbayUk:
    def test_verified_sku_worked_example(self, book):
        """Rational 20.02.552P at its verified £69.99 eBay UK price."""
        total, breakdown = book.total_fees(
            marketplace="ebay",
            country="GB",
            category="business_industrial",
            price=Decimal("69.99"),
            on_date=AS_OF,
            fee_kinds=EBAY_UK_FEE_KINDS,
        )
        assert breakdown == {
            "final_value": Decimal("8.75"),  # 12.5% B&I, Feb-2026 card
            "regulatory_operating": Decimal("0.24"),
            "order_fixed": Decimal("0.40"),
        }
        assert total == Decimal("9.39")

    def test_per_order_fee_bands_at_ten_pounds(self, book):
        def fixed(price: str) -> Decimal:
            return book.resolve(
                fee_kind="order_fixed",
                marketplace="ebay",
                country="GB",
                category="business_industrial",
                price=Decimal(price),
                on_date=AS_OF,
            ).fixed_fee

        assert fixed("9.99") == Decimal("0.30")
        # £10 exactly pays the higher band — half-open boundary.
        assert fixed("10.00") == Decimal("0.40")

    def test_business_industrial_beats_the_wildcard_rate(self, book):
        rule = book.resolve(
            fee_kind="final_value",
            marketplace="ebay",
            country="GB",
            category="business_industrial",
            price=Decimal("50"),
            on_date=AS_OF,
        )
        assert rule.variable_rate == Decimal("0.125")

    def test_unknown_category_falls_back_to_standard_rate(self, book):
        rule = book.resolve(
            fee_kind="final_value",
            marketplace="ebay",
            country="GB",
            category="garden_machinery",
            price=Decimal("50"),
            on_date=AS_OF,
        )
        assert rule.variable_rate == Decimal("0.128")

    def test_rules_predate_the_collection_date(self, book):
        """Feb-2026 card must not apply to a January 2026 sale."""
        with pytest.raises(LookupError):
            book.resolve(
                fee_kind="final_value",
                marketplace="ebay",
                country="GB",
                category="business_industrial",
                price=Decimal("50"),
                on_date=date(2026, 1, 15),
            )


class TestAmazonUk:
    def test_effective_rates_include_dst_pass_through(self, book):
        total, breakdown = book.total_fees(
            marketplace="amazon",
            country="GB",
            category="business_industrial_scientific",
            price=Decimal("100.00"),
            on_date=AS_OF,
            fee_kinds=AMAZON_UK_FEE_KINDS,
        )
        assert breakdown["referral"] == Decimal("12.24")  # 12% x 1.02
        assert total == Decimal("12.24")

    def test_home_kitchen_is_the_higher_band(self, book):
        total, _ = book.total_fees(
            marketplace="amazon",
            country="GB",
            category="home_kitchen",
            price=Decimal("100.00"),
            on_date=AS_OF,
            fee_kinds=AMAZON_UK_FEE_KINDS,
        )
        assert total == Decimal("15.30")  # 15% x 1.02

    def test_no_wildcard_for_amazon_referral(self, book):
        """An unmapped Amazon category must fail loudly, not borrow a rate."""
        with pytest.raises(LookupError):
            book.resolve(
                fee_kind="referral",
                marketplace="amazon",
                country="GB",
                category="toys_games",
                price=Decimal("50"),
                on_date=AS_OF,
            )


class TestProvenance:
    def test_every_rule_carries_a_source(self, book):
        assert all(rule.source_ref for rule in book.rules)

    def test_every_rule_is_version_stamped_as_search_verified(self, book):
        assert all("search-verified" in rule.schedule_version for rule in book.rules)
