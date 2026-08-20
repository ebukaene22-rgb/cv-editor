"""Risk-adjusted opportunity scoring.

Two stages, deliberately kept apart rather than fused into one arbitrary
formula:

1. **Expected monthly contribution** — demand × conversion × contribution.
2. **Risk adjustment** — discount by match, supplier, availability and
   compliance confidence, then charge for the working capital tied up.

Compliance is not one of the discount factors. It is a prior hard gate: a
listing is either permitted or it is not, and a high enough margin never buys
its way past that.

The pilot gate values below are proposed engineering policy for a first
portfolio, not marketplace rules and not industry standards. Once enough
realised outcomes exist, replace the heuristics with category-specific
posteriors.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ecommerce_os.money import ZERO, money, quantize, rate


@dataclass(frozen=True)
class PilotGates:
    """Minimum bar for an SKU to be worth listing during the pilot."""

    min_contribution_per_order: Decimal = Decimal("5.00")
    min_margin_pct: Decimal = Decimal("0.15")
    min_match_confidence: Decimal = Decimal("0.97")
    min_supplier_reliability: Decimal = Decimal("0.98")
    min_stock_confidence: Decimal = Decimal("0.95")
    max_return_rate: Decimal = Decimal("0.10")
    min_price_observations: int = 3


@dataclass(frozen=True)
class RiskExponents:
    """Tuning knobs, fitted against realised outcomes rather than guessed twice."""

    match: Decimal = Decimal("1")
    supplier: Decimal = Decimal("1")
    availability: Decimal = Decimal("1")
    compliance: Decimal = Decimal("1")
    capital_penalty: Decimal = Decimal("0")


@dataclass(frozen=True)
class Opportunity:
    contribution_per_order: Decimal
    selling_price: Decimal
    monthly_demand: Decimal
    conversion_rate: Decimal
    match_confidence: Decimal
    supplier_reliability: Decimal
    stock_confidence: Decimal
    return_rate: Decimal = ZERO
    compliance_ok: bool = False
    compliance_confidence: Decimal = Decimal("1")
    price_observations: int = 0
    working_capital: Decimal = ZERO


@dataclass(frozen=True)
class ScoreResult:
    rejected: bool
    reasons: tuple[str, ...]
    expected_monthly_contribution: Decimal
    score: Decimal

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return not self.rejected


def _power(base: Decimal, exponent: Decimal) -> Decimal:
    """``base ** exponent`` for a proportion, without leaving Decimal."""
    if exponent == Decimal("1"):
        return base
    if base <= ZERO:
        return ZERO
    return Decimal(str(float(base) ** float(exponent)))


def score_opportunity(
    opportunity: Opportunity,
    gates: PilotGates | None = None,
    exponents: RiskExponents | None = None,
) -> ScoreResult:
    """Apply the pilot gates, then score whatever survives.

    Every failing gate is reported, not just the first, so an operator can see
    whether an SKU is one negotiation away from viable or fundamentally not.
    """
    gates = gates or PilotGates()
    exponents = exponents or RiskExponents()
    reasons: list[str] = []

    if not opportunity.compliance_ok:
        reasons.append("compliance gate not passed")

    contribution = money(opportunity.contribution_per_order)
    price = money(opportunity.selling_price)

    if contribution < money(gates.min_contribution_per_order):
        reasons.append(
            f"contribution {contribution} below minimum {gates.min_contribution_per_order}"
        )

    margin_pct = (contribution / price) if price > ZERO else ZERO
    if margin_pct < money(gates.min_margin_pct):
        reasons.append(
            f"margin {margin_pct:.4f} below minimum {gates.min_margin_pct}"
        )

    if rate(opportunity.match_confidence) < money(gates.min_match_confidence):
        reasons.append(
            f"match confidence {opportunity.match_confidence} below "
            f"{gates.min_match_confidence}"
        )

    if rate(opportunity.supplier_reliability) < money(gates.min_supplier_reliability):
        reasons.append(
            f"supplier reliability {opportunity.supplier_reliability} below "
            f"{gates.min_supplier_reliability}"
        )

    if rate(opportunity.stock_confidence) < money(gates.min_stock_confidence):
        reasons.append(
            f"stock confidence {opportunity.stock_confidence} below "
            f"{gates.min_stock_confidence}"
        )

    if rate(opportunity.return_rate) > money(gates.max_return_rate):
        reasons.append(
            f"return rate {opportunity.return_rate} above {gates.max_return_rate}"
        )

    if opportunity.price_observations < gates.min_price_observations:
        reasons.append(
            f"only {opportunity.price_observations} price observations, need "
            f"{gates.min_price_observations}"
        )

    expected_monthly_contribution = quantize(
        money(opportunity.monthly_demand)
        * rate(opportunity.conversion_rate)
        * contribution
    )

    if reasons:
        return ScoreResult(
            rejected=True,
            reasons=tuple(reasons),
            expected_monthly_contribution=expected_monthly_contribution,
            score=ZERO,
        )

    risk_factor = (
        _power(rate(opportunity.match_confidence), exponents.match)
        * _power(rate(opportunity.supplier_reliability), exponents.supplier)
        * _power(rate(opportunity.stock_confidence), exponents.availability)
        * _power(rate(opportunity.compliance_confidence), exponents.compliance)
        * (Decimal("1") - rate(opportunity.return_rate))
    )

    capital_charge = exponents.capital_penalty * money(opportunity.working_capital)
    score = quantize(expected_monthly_contribution * risk_factor - capital_charge)

    return ScoreResult(
        rejected=False,
        reasons=(),
        expected_monthly_contribution=expected_monthly_contribution,
        score=score,
    )


def stock_transition_delta(
    stocked_profit: Decimal,
    dropship_profit: Decimal,
    holding_cost: Decimal,
    obsolescence_cost: Decimal,
) -> Decimal:
    """ΔP = (P_stocked − P_dropship) − H − O.

    Positive with sufficient demand confidence means the SKU has earned local
    inventory. Dropshipping is a sampling mechanism; stock is what you buy once
    demand uncertainty has fallen far enough to pay for carrying it.
    """
    return quantize(
        money(stocked_profit)
        - money(dropship_profit)
        - money(holding_cost)
        - money(obsolescence_cost)
    )
