"""Landed cost and contribution margin.

Never rank on gross spread. A scanner showing a £52 "spread" routinely produces
something closer to £10–£20 of economic contribution once tax, duty, fees,
shipping, returns, fulfilment failures and acquisition cost are paid — and
sometimes none at all.

Three distinct things are called "VAT" and only one of them is a cost:

* VAT **collected** on the sale — never ours, whether we remit it or a
  marketplace does as deemed supplier;
* VAT **recoverable** on inputs — a cash-flow item, not a P&L cost;
* VAT that is genuinely **non-recoverable** — a real cost, and the line most
  often forgotten when comparing a domestic route to a cross-border one.

Every output is itemised so that the reconciliation loop can decompose
``CM_actual − CM_predicted`` into fee error, shipping error, tax error, return
error, supplier price error and ad-cost error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from ecommerce_os.money import ZERO, ex_vat, money, quantize, rate


class VatTreatment(Enum):
    """Who accounts for VAT on the sale."""

    SELLER_COLLECTS = "seller_collects"
    MARKETPLACE_DEEMED_SUPPLIER = "marketplace_deemed_supplier"
    ZERO_RATED = "zero_rated"
    OUT_OF_SCOPE = "out_of_scope"

    @property
    def revenue_is_vat_inclusive(self) -> bool:
        return self in (
            VatTreatment.SELLER_COLLECTS,
            VatTreatment.MARKETPLACE_DEEMED_SUPPLIER,
        )


@dataclass(frozen=True)
class ReturnProfile:
    """Expected cost of a return, which is not ``return_rate × price``.

    A locally resellable unopened filter and a compatibility-sensitive part that
    comes back opened have wildly different expected losses at identical return
    rates.
    """

    return_rate: Decimal = ZERO
    reverse_logistics_cost: Decimal = ZERO
    resell_probability: Decimal = ZERO
    writeoff_cost: Decimal = ZERO
    handling_cost: Decimal = ZERO
    nonrefundable_fees: Decimal = ZERO


def expected_return_cost(profile: ReturnProfile) -> Decimal:
    """E[C_return] = p_return × [C_reverse + (1−p_resell)·C_writeoff + C_handling + fees]."""
    p_return = rate(profile.return_rate)
    p_resell = rate(profile.resell_probability)
    per_return = (
        money(profile.reverse_logistics_cost)
        + (Decimal("1") - p_resell) * money(profile.writeoff_cost)
        + money(profile.handling_cost)
        + money(profile.nonrefundable_fees)
    )
    return quantize(p_return * per_return)


@dataclass(frozen=True)
class LandedCostInputs:
    """One fulfilment route for one SKU into one market.

    ``freight`` and ``insurance`` are the international legs that form part of
    the customs value; ``inbound_shipping`` is any further inbound cost that
    does not. Duty is charged on CIF — cost, insurance and freight — so putting
    freight in the wrong field understates duty.
    """

    selling_price: Decimal
    supplier_price_ex_vat: Decimal
    vat_treatment: VatTreatment = VatTreatment.SELLER_COLLECTS
    sale_vat_rate: Decimal = ZERO
    supplier_vat_rate: Decimal = ZERO
    input_vat_recoverable: bool = True
    is_import: bool = False
    freight: Decimal = ZERO
    insurance: Decimal = ZERO
    duty_rate: Decimal = ZERO
    inbound_shipping: Decimal = ZERO
    outbound_shipping: Decimal = ZERO
    marketplace_fees: Decimal = ZERO
    payment_fee_rate: Decimal = ZERO
    payment_fixed_fee: Decimal = ZERO
    advertising_per_order: Decimal = ZERO
    return_profile: ReturnProfile = field(default_factory=ReturnProfile)
    fraud_loss_rate: Decimal = ZERO
    fulfilment_failure_rate: Decimal = ZERO
    fulfilment_failure_cost: Decimal = ZERO


@dataclass(frozen=True)
class CostBreakdown:
    net_revenue: Decimal
    lines: dict[str, Decimal]
    contribution_if_fulfilled: Decimal
    expected_contribution: Decimal
    margin_pct: Decimal

    def line(self, name: str) -> Decimal:
        return self.lines.get(name, ZERO)


def customs_value(inputs: LandedCostInputs) -> Decimal:
    """CIF: goods cost plus insurance plus freight."""
    if not inputs.is_import:
        return ZERO
    return quantize(
        money(inputs.supplier_price_ex_vat) + money(inputs.insurance) + money(inputs.freight)
    )


def contribution_margin(inputs: LandedCostInputs) -> CostBreakdown:
    """Full expected contribution before general corporate overhead."""
    price = money(inputs.selling_price)
    if price <= ZERO:
        raise ValueError("selling_price must be positive")

    sale_vat = rate(inputs.sale_vat_rate)
    if inputs.vat_treatment.revenue_is_vat_inclusive:
        net_revenue = ex_vat(price, sale_vat)
    else:
        net_revenue = price
    net_revenue = quantize(net_revenue)

    lines: dict[str, Decimal] = {}

    lines["product"] = quantize(money(inputs.supplier_price_ex_vat))

    supplier_vat = rate(inputs.supplier_vat_rate)
    lines["non_recoverable_input_vat"] = (
        ZERO
        if inputs.input_vat_recoverable
        else quantize(money(inputs.supplier_price_ex_vat) * supplier_vat)
    )

    lines["duty"] = quantize(rate(inputs.duty_rate) * customs_value(inputs))
    lines["inbound"] = quantize(
        money(inputs.freight) + money(inputs.insurance) + money(inputs.inbound_shipping)
    )
    lines["outbound"] = quantize(money(inputs.outbound_shipping))
    lines["marketplace"] = quantize(money(inputs.marketplace_fees))
    # Payment processors charge on the gross amount the customer paid, VAT
    # included — not on our net revenue.
    lines["payment"] = quantize(
        rate(inputs.payment_fee_rate) * price + money(inputs.payment_fixed_fee)
    )
    lines["advertising"] = quantize(money(inputs.advertising_per_order))
    lines["returns"] = expected_return_cost(inputs.return_profile)

    # A fraudulent order loses the revenue and the goods and the outbound leg.
    goods_at_risk = lines["product"] + lines["non_recoverable_input_vat"] + lines["outbound"]
    lines["fraud"] = quantize(rate(inputs.fraud_loss_rate) * (net_revenue + goods_at_risk))

    contribution_if_fulfilled = quantize(net_revenue - sum(lines.values()))

    # A failed order (supplier stock-out, cancellation) forfeits the whole
    # contribution *and* costs something to clean up. Expressing it as one line
    # keeps the breakdown linear while remaining exactly equivalent to
    #   (1 − p)·contribution − p·failure_cost.
    p_fail = rate(inputs.fulfilment_failure_rate)
    lines["fulfilment_failure"] = quantize(
        p_fail * (contribution_if_fulfilled + money(inputs.fulfilment_failure_cost))
    )

    expected_contribution = quantize(contribution_if_fulfilled - lines["fulfilment_failure"])
    margin_pct = (expected_contribution / price).quantize(Decimal("0.0001"))

    return CostBreakdown(
        net_revenue=net_revenue,
        lines=lines,
        contribution_if_fulfilled=contribution_if_fulfilled,
        expected_contribution=expected_contribution,
        margin_pct=margin_pct,
    )
