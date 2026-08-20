from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from ecommerce_os.scoring import (
    Opportunity,
    PilotGates,
    RiskExponents,
    score_opportunity,
    stock_transition_delta,
)


def viable(**overrides) -> Opportunity:
    """An opportunity that clears every pilot gate, before overrides."""
    base = Opportunity(
        contribution_per_order=Decimal("20.00"),
        selling_price=Decimal("100.00"),
        monthly_demand=Decimal("50"),
        conversion_rate=Decimal("1"),
        match_confidence=Decimal("1"),
        supplier_reliability=Decimal("0.99"),
        stock_confidence=Decimal("0.99"),
        return_rate=Decimal("0.05"),
        compliance_ok=True,
        price_observations=5,
    )
    return replace(base, **overrides)


class TestComplianceIsNotNegotiable:
    def test_a_huge_margin_never_buys_past_the_compliance_gate(self):
        result = score_opportunity(
            viable(compliance_ok=False, contribution_per_order=Decimal("500.00"))
        )

        assert result.rejected
        assert result.score == Decimal("0")
        assert "compliance gate not passed" in result.reasons

    def test_compliance_is_a_gate_not_a_discount(self):
        # It must not appear as a factor that merely shrinks the score.
        clean = score_opportunity(viable())
        assert not clean.rejected and clean.score > 0


class TestPilotGates:
    def test_thin_absolute_contribution_is_rejected(self):
        result = score_opportunity(viable(contribution_per_order=Decimal("4.00")))
        assert result.rejected
        assert any("below minimum" in reason for reason in result.reasons)

    def test_thin_percentage_margin_is_rejected(self):
        # £20 on a £1,000 sale clears the absolute floor and fails the ratio.
        result = score_opportunity(viable(selling_price=Decimal("1000.00")))
        assert result.rejected
        assert any("margin" in reason for reason in result.reasons)

    def test_uncertain_match_is_rejected(self):
        result = score_opportunity(viable(match_confidence=Decimal("0.90")))
        assert result.rejected
        assert any("match confidence" in reason for reason in result.reasons)

    def test_unreliable_supplier_is_rejected(self):
        result = score_opportunity(viable(supplier_reliability=Decimal("0.90")))
        assert result.rejected

    def test_high_return_rate_is_rejected(self):
        result = score_opportunity(viable(return_rate=Decimal("0.25")))
        assert result.rejected

    def test_too_few_price_observations_is_rejected(self):
        # One scrape is a rumour, not a price.
        result = score_opportunity(viable(price_observations=1))
        assert result.rejected
        assert any("price observations" in reason for reason in result.reasons)

    def test_every_failing_gate_is_reported(self):
        result = score_opportunity(
            viable(
                contribution_per_order=Decimal("1.00"),
                match_confidence=Decimal("0.5"),
                supplier_reliability=Decimal("0.5"),
                price_observations=0,
            )
        )
        assert len(result.reasons) >= 4

    def test_gates_are_tunable_per_category(self):
        lenient = PilotGates(min_match_confidence=Decimal("0.85"))
        assert not score_opportunity(viable(match_confidence=Decimal("0.90")), lenient).rejected


class TestRiskAdjustment:
    def test_expected_monthly_contribution_is_demand_times_conversion_times_margin(self):
        result = score_opportunity(
            viable(monthly_demand=Decimal("400"), conversion_rate=Decimal("0.25"))
        )
        # 400 * 0.25 * 20.00
        assert result.expected_monthly_contribution == Decimal("2000.00")

    def test_score_is_discounted_below_raw_contribution(self):
        result = score_opportunity(viable())
        assert result.score < result.expected_monthly_contribution

    def test_reliability_lowers_the_score_at_equal_margin(self):
        # A £25-margin product with poor fulfilment is not worth more than a
        # £15-margin product that actually ships.
        reliable = score_opportunity(
            viable(contribution_per_order=Decimal("15.00"), return_rate=Decimal("0.01"))
        )
        unreliable = score_opportunity(
            viable(
                contribution_per_order=Decimal("25.00"),
                supplier_reliability=Decimal("0.985"),
                return_rate=Decimal("0.09"),
            ),
            PilotGates(min_supplier_reliability=Decimal("0.98")),
        )

        assert unreliable.expected_monthly_contribution > reliable.expected_monthly_contribution
        assert unreliable.score < unreliable.expected_monthly_contribution

    def test_working_capital_is_charged_when_the_penalty_is_set(self):
        opportunity = viable(working_capital=Decimal("1000.00"))
        free = score_opportunity(opportunity)
        charged = score_opportunity(
            opportunity, exponents=RiskExponents(capital_penalty=Decimal("0.02"))
        )

        assert free.score - charged.score == Decimal("20.00")

    def test_exponents_sharpen_the_discount(self):
        opportunity = viable(supplier_reliability=Decimal("0.98"))
        mild = score_opportunity(opportunity)
        harsh = score_opportunity(opportunity, exponents=RiskExponents(supplier=Decimal("4")))

        assert harsh.score < mild.score


class TestStockTransition:
    def test_stock_wins_only_after_carrying_costs(self):
        delta = stock_transition_delta(
            stocked_profit=Decimal("30.00"),
            dropship_profit=Decimal("20.00"),
            holding_cost=Decimal("3.00"),
            obsolescence_cost=Decimal("2.00"),
        )
        assert delta == Decimal("5.00")

    def test_a_marginal_uplift_does_not_justify_inventory(self):
        delta = stock_transition_delta(
            stocked_profit=Decimal("22.00"),
            dropship_profit=Decimal("20.00"),
            holding_cost=Decimal("3.00"),
            obsolescence_cost=Decimal("2.00"),
        )
        assert delta < Decimal("0")
