from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from ecommerce_os.landed_cost import (
    LandedCostInputs,
    ReturnProfile,
    VatTreatment,
    contribution_margin,
    customs_value,
    expected_return_cost,
)
from ecommerce_os.money import money


class TestVatIsThreeDifferentThings:
    def test_collected_vat_is_never_revenue(self, costs):
        # £120 inclusive at 20% is £100 of revenue, not £120.
        assert contribution_margin(costs).net_revenue == Decimal("100.00")

    def test_marketplace_deemed_supplier_also_nets_the_seller_down(self, costs):
        deemed = replace(costs, vat_treatment=VatTreatment.MARKETPLACE_DEEMED_SUPPLIER)
        assert contribution_margin(deemed).net_revenue == Decimal("100.00")

    def test_zero_rated_sale_keeps_the_whole_price(self, costs):
        zero_rated = replace(costs, vat_treatment=VatTreatment.ZERO_RATED)
        assert contribution_margin(zero_rated).net_revenue == Decimal("120.00")

    def test_recoverable_input_vat_is_not_a_cost(self, costs):
        breakdown = contribution_margin(costs)
        assert breakdown.line("non_recoverable_input_vat") == Decimal("0")

    def test_non_recoverable_input_vat_is_a_real_cost(self, costs):
        blocked = replace(costs, input_vat_recoverable=False)
        breakdown = contribution_margin(blocked)

        # 20% of the £48 wholesale cost, straight off the bottom line.
        assert breakdown.line("non_recoverable_input_vat") == Decimal("9.60")
        assert (
            contribution_margin(costs).expected_contribution
            - breakdown.expected_contribution
        ) > Decimal("9.00")


class TestFullBreakdown:
    def test_every_line_is_accounted_for(self, costs):
        breakdown = contribution_margin(costs)

        assert breakdown.lines["product"] == Decimal("48.00")
        assert breakdown.lines["outbound"] == Decimal("7.00")
        # Payment fees are charged on the gross the customer paid, VAT included.
        assert breakdown.lines["payment"] == Decimal("3.78")
        assert breakdown.lines["advertising"] == Decimal("6.00")
        assert breakdown.lines["returns"] == Decimal("1.55")

    def test_headline_spread_overstates_contribution(self, costs):
        # £120 sale on a £48 cost looks like a £72 spread. It is not.
        spread = money(costs.selling_price) - money(costs.supplier_price_ex_vat)
        breakdown = contribution_margin(replace(costs, marketplace_fees=Decimal("12.00")))

        assert spread == Decimal("72.00")
        assert breakdown.expected_contribution == Decimal("21.40")
        assert breakdown.margin_pct == Decimal("0.1783")

    def test_failure_line_is_exactly_the_probability_weighted_form(self, costs):
        priced = replace(costs, marketplace_fees=Decimal("12.00"))
        breakdown = contribution_margin(priced)

        p_fail = money(priced.fulfilment_failure_rate)
        expected = (Decimal("1") - p_fail) * breakdown.contribution_if_fulfilled - (
            p_fail * money(priced.fulfilment_failure_cost)
        )

        assert breakdown.expected_contribution == expected.quantize(Decimal("0.01"))


class TestImportDuty:
    def test_duty_is_charged_on_cif_not_on_goods_alone(self):
        inputs = LandedCostInputs(
            selling_price=Decimal("300.00"),
            supplier_price_ex_vat=Decimal("100.00"),
            vat_treatment=VatTreatment.ZERO_RATED,
            is_import=True,
            insurance=Decimal("5.00"),
            freight=Decimal("20.00"),
            duty_rate=Decimal("0.05"),
        )

        assert customs_value(inputs) == Decimal("125.00")
        assert contribution_margin(inputs).line("duty") == Decimal("6.25")

    def test_domestic_route_pays_no_duty(self, costs):
        assert customs_value(costs) == Decimal("0")
        assert contribution_margin(costs).line("duty") == Decimal("0")

    def test_freight_in_the_wrong_field_understates_duty(self):
        base = dict(
            selling_price=Decimal("300.00"),
            supplier_price_ex_vat=Decimal("100.00"),
            vat_treatment=VatTreatment.ZERO_RATED,
            is_import=True,
            duty_rate=Decimal("0.05"),
        )
        correct = LandedCostInputs(**base, freight=Decimal("20.00"))
        wrong = LandedCostInputs(**base, inbound_shipping=Decimal("20.00"))

        assert contribution_margin(correct).line("duty") > contribution_margin(wrong).line("duty")
        # ...while the inbound cost itself is identical either way.
        assert contribution_margin(correct).line("inbound") == contribution_margin(wrong).line(
            "inbound"
        )


class TestReturnCost:
    def test_is_not_return_rate_times_price(self):
        profile = ReturnProfile(
            return_rate=Decimal("0.10"),
            reverse_logistics_cost=Decimal("5.00"),
            resell_probability=Decimal("0.80"),
            writeoff_cost=Decimal("50.00"),
            handling_cost=Decimal("2.00"),
            nonrefundable_fees=Decimal("3.00"),
        )

        # 0.10 * (5 + 0.2*50 + 2 + 3) = 0.10 * 20 = 2.00
        assert expected_return_cost(profile) == Decimal("2.00")

    def test_resellability_dominates_at_equal_return_rates(self):
        common = dict(
            return_rate=Decimal("0.10"),
            reverse_logistics_cost=Decimal("5.00"),
            writeoff_cost=Decimal("50.00"),
        )
        resellable = ReturnProfile(**common, resell_probability=Decimal("0.95"))
        not_resellable = ReturnProfile(**common, resell_probability=Decimal("0.00"))

        assert expected_return_cost(resellable) == Decimal("0.75")
        assert expected_return_cost(not_resellable) == Decimal("5.50")

    def test_no_returns_costs_nothing(self):
        assert expected_return_cost(ReturnProfile()) == Decimal("0")


class TestGuardrails:
    def test_floats_are_refused_outright(self, costs):
        # Decimal(0.1) is 0.1000000000000000055511151231257827.
        with pytest.raises(TypeError):
            contribution_margin(replace(costs, payment_fee_rate=0.029))

    def test_non_positive_price_is_rejected(self, costs):
        with pytest.raises(ValueError):
            contribution_margin(replace(costs, selling_price=Decimal("0")))

    def test_rate_outside_zero_to_one_is_rejected(self, costs):
        with pytest.raises(ValueError):
            contribution_margin(replace(costs, sale_vat_rate=Decimal("20")))
