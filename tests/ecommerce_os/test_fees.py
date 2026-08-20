from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ecommerce_os.fees import (
    ANY,
    AmbiguousFeeRuleError,
    FeeBook,
    FeeRule,
    NoFeeRuleError,
)

TODAY = date(2026, 8, 20)


def rule(**kwargs) -> FeeRule:
    defaults = dict(
        marketplace="amazon",
        country="GB",
        category=ANY,
        fee_kind="referral",
        variable_rate=Decimal("0.15"),
        fixed_fee=Decimal("0"),
        effective_from=date(2026, 1, 1),
        schedule_version="2026-01",
    )
    defaults.update(kwargs)
    return FeeRule(**defaults)


class TestNoSilentDefault:
    def test_unknown_combination_raises_rather_than_guessing(self):
        # The single most important behaviour in this module. A generic "15%"
        # fallback is how a portfolio of confidently unprofitable SKUs is built.
        book = FeeBook([rule()])

        with pytest.raises(NoFeeRuleError):
            book.resolve(
                fee_kind="referral",
                marketplace="ebay",
                country="GB",
                category="filters",
                price=Decimal("50"),
                on_date=TODAY,
            )

    def test_missing_fee_kind_raises_even_when_other_kinds_resolve(self):
        book = FeeBook([rule(fee_kind="referral")])

        with pytest.raises(NoFeeRuleError):
            book.total_fees(
                marketplace="amazon",
                country="GB",
                category="filters",
                price=Decimal("50"),
                on_date=TODAY,
                fee_kinds=("referral", "regulatory_operating"),
            )


class TestSpecificity:
    def test_exact_category_beats_wildcard(self):
        book = FeeBook(
            [
                rule(category=ANY, variable_rate=Decimal("0.15")),
                rule(category="filters", variable_rate=Decimal("0.08")),
            ]
        )

        resolved = book.resolve(
            fee_kind="referral",
            marketplace="amazon",
            country="GB",
            category="filters",
            price=Decimal("50"),
            on_date=TODAY,
        )

        assert resolved.variable_rate == Decimal("0.08")

    def test_two_equally_specific_rules_are_a_data_error(self):
        book = FeeBook(
            [
                rule(category="filters", variable_rate=Decimal("0.08")),
                rule(category="filters", variable_rate=Decimal("0.09")),
            ]
        )

        with pytest.raises(AmbiguousFeeRuleError):
            book.resolve(
                fee_kind="referral",
                marketplace="amazon",
                country="GB",
                category="filters",
                price=Decimal("50"),
                on_date=TODAY,
            )


class TestPriceBands:
    def test_bands_are_half_open_at_the_top(self):
        book = FeeBook(
            [
                rule(price_max=Decimal("10"), variable_rate=Decimal("0.20")),
                rule(price_min=Decimal("10"), variable_rate=Decimal("0.08")),
            ]
        )

        def rate_at(price: str) -> Decimal:
            return book.resolve(
                fee_kind="referral",
                marketplace="amazon",
                country="GB",
                category="filters",
                price=Decimal(price),
                on_date=TODAY,
            ).variable_rate

        assert rate_at("9.99") == Decimal("0.20")
        # Exactly at the boundary belongs to the upper band, and only to it.
        assert rate_at("10.00") == Decimal("0.08")


class TestEffectiveDating:
    def test_a_rule_that_has_not_started_does_not_apply(self):
        book = FeeBook([rule(effective_from=date(2026, 9, 1))])

        with pytest.raises(NoFeeRuleError):
            book.resolve(
                fee_kind="referral",
                marketplace="amazon",
                country="GB",
                category="filters",
                price=Decimal("50"),
                on_date=TODAY,
            )

    def test_superseded_schedule_stops_applying(self):
        book = FeeBook(
            [
                rule(effective_to=date(2026, 6, 30), variable_rate=Decimal("0.15")),
                rule(effective_from=date(2026, 7, 1), variable_rate=Decimal("0.12")),
            ]
        )

        resolved = book.resolve(
            fee_kind="referral",
            marketplace="amazon",
            country="GB",
            category="filters",
            price=Decimal("50"),
            on_date=TODAY,
        )

        assert resolved.variable_rate == Decimal("0.12")


class TestStackedFees:
    def test_fees_stack_and_are_itemised(self):
        # A single eBay sale can attract several fee lines at once; treating
        # the referral fee as the whole cost understates it every time.
        book = FeeBook(
            [
                rule(
                    marketplace="ebay",
                    fee_kind="final_value",
                    variable_rate=Decimal("0.1235"),
                    fixed_fee=Decimal("0.30"),
                ),
                rule(
                    marketplace="ebay",
                    fee_kind="regulatory_operating",
                    variable_rate=Decimal("0.0035"),
                ),
                rule(
                    marketplace="ebay",
                    fee_kind="international",
                    variable_rate=Decimal("0.013"),
                ),
            ]
        )

        total, breakdown = book.total_fees(
            marketplace="ebay",
            country="GB",
            category="filters",
            price=Decimal("100.00"),
            on_date=TODAY,
            fee_kinds=("final_value", "regulatory_operating", "international"),
        )

        assert breakdown == {
            "final_value": Decimal("12.65"),
            "regulatory_operating": Decimal("0.35"),
            "international": Decimal("1.30"),
        }
        assert total == Decimal("14.30")
