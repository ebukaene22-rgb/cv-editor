"""The publish decision.

    publishable = economic_gate
                  and match_gate
                  and supplier_gate
                  and marketplace_gate
                  and product_compliance_gate
                  and inventory_gate

This is the difference between an arbitrage script and an operating system. An
SKU is never published because ``expected_profit > 0``; it is published because
every gate independently said yes, and any one of them can say no on its own.

The evaluation is total rather than short-circuiting — including for missing fee
rules, which are reported as a blocker rather than raised — so a batch run
produces a complete remediation list instead of failing one SKU at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from ecommerce_os.compliance import (
    FulfilmentMethod,
    GateResult,
    SupplierAuthorisation,
    compliance_gate,
)
from ecommerce_os.fees import FeeBook
from ecommerce_os.landed_cost import CostBreakdown, LandedCostInputs, contribution_margin
from ecommerce_os.matching import MatchResult, ProductRecord, classify_match
from ecommerce_os.money import ZERO, money
from ecommerce_os.scoring import (
    Opportunity,
    PilotGates,
    RiskExponents,
    ScoreResult,
    score_opportunity,
)
from ecommerce_os.supply import (
    SupplierPerformance,
    feed_is_stale,
    sellable_stock,
    supplier_score,
)

# How much confidence a stale feed costs us. A starting heuristic, to be
# replaced by the observed relationship between feed age and oversell rate once
# there are enough cancellations to fit one.
STALE_FEED_CONFIDENCE_MULTIPLIER = Decimal("0.5")


@dataclass(frozen=True)
class ListingCandidate:
    canonical_sku_id: str
    marketplace: str
    market: str
    category: str
    fulfilment: FulfilmentMethod
    authorisation: SupplierAuthorisation
    source_product: ProductRecord
    canonical_product: ProductRecord
    costs: LandedCostInputs
    supplier_performance: SupplierPerformance
    supplier_qty: int
    feed_age_minutes: int
    monthly_demand: Decimal = ZERO
    conversion_rate: Decimal = ZERO
    price_observations: int = 0
    working_capital: Decimal = ZERO
    brand_authorisation_required: bool = False
    uses_supplier_content: bool = False
    fee_kinds: tuple[str, ...] = ("referral",)


@dataclass(frozen=True)
class PublishDecision:
    publishable: bool
    blockers: tuple[str, ...]
    match: MatchResult
    compliance: GateResult
    sellable_qty: int
    breakdown: CostBreakdown | None
    score: ScoreResult | None
    fee_breakdown: dict[str, Decimal] = field(default_factory=dict)

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return self.publishable


def stock_confidence(
    performance: SupplierPerformance,
    feed_age_minutes: int,
    expected_frequency_minutes: int | None,
) -> Decimal:
    """How much we believe the stock number we are about to promise against."""
    confidence = money(performance.feed_accuracy)
    if feed_is_stale(feed_age_minutes, expected_frequency_minutes):
        confidence *= STALE_FEED_CONFIDENCE_MULTIPLIER
    return confidence.quantize(Decimal("0.0001"))


def evaluate_listing(
    candidate: ListingCandidate,
    *,
    fee_book: FeeBook,
    as_of: date,
    gates: PilotGates | None = None,
    exponents: RiskExponents | None = None,
    max_dispatch_sla_hours: int | None = None,
) -> PublishDecision:
    """Run every gate and return a decision that explains itself."""
    gates = gates or PilotGates()
    blockers: list[str] = []

    compliance = compliance_gate(
        candidate.authorisation,
        marketplace=candidate.marketplace,
        market=candidate.market,
        fulfilment=candidate.fulfilment,
        as_of=as_of,
        brand_authorisation_required=candidate.brand_authorisation_required,
        uses_supplier_content=candidate.uses_supplier_content,
        max_dispatch_sla_hours=max_dispatch_sla_hours,
    )
    blockers.extend(f"compliance: {reason}" for reason in compliance.failures)

    match = classify_match(candidate.source_product, candidate.canonical_product)
    if not match.auto_matchable:
        blockers.append(
            f"match: {match.match_class.value} (score {match.score}) — "
            f"{'; '.join(match.reasons) or 'not eligible for automatic listing'}"
        )

    reliability = supplier_score(candidate.supplier_performance)
    available = sellable_stock(
        candidate.supplier_qty, candidate.feed_age_minutes, reliability
    )
    if available <= 0:
        blockers.append(
            f"inventory: no sellable stock after buffering "
            f"({candidate.supplier_qty} raw, feed {candidate.feed_age_minutes}m old)"
        )

    # Fees are resolved before the economics so that a missing rule blocks the
    # listing instead of being quietly treated as zero.
    breakdown: CostBreakdown | None = None
    fee_breakdown: dict[str, Decimal] = {}
    try:
        total_fees, fee_breakdown = fee_book.total_fees(
            marketplace=candidate.marketplace,
            country=candidate.market,
            category=candidate.category,
            price=candidate.costs.selling_price,
            on_date=as_of,
            fee_kinds=candidate.fee_kinds,
        )
    except LookupError as exc:
        blockers.append(f"fees: {exc}")
    else:
        breakdown = contribution_margin(
            replace(candidate.costs, marketplace_fees=total_fees)
        )

    score: ScoreResult | None = None
    if breakdown is not None:
        score = score_opportunity(
            Opportunity(
                contribution_per_order=breakdown.expected_contribution,
                selling_price=candidate.costs.selling_price,
                monthly_demand=candidate.monthly_demand,
                conversion_rate=candidate.conversion_rate,
                match_confidence=match.score,
                supplier_reliability=reliability,
                stock_confidence=stock_confidence(
                    candidate.supplier_performance,
                    candidate.feed_age_minutes,
                    candidate.authorisation.inventory_feed_frequency_minutes,
                ),
                return_rate=candidate.costs.return_profile.return_rate,
                compliance_ok=compliance.ok,
                price_observations=candidate.price_observations,
                working_capital=candidate.working_capital,
            ),
            gates=gates,
            exponents=exponents,
        )
        blockers.extend(
            f"economics: {reason}"
            for reason in score.reasons
            # The compliance gate already reported itself in full above.
            if reason != "compliance gate not passed"
        )

    return PublishDecision(
        publishable=not blockers,
        blockers=tuple(blockers),
        match=match,
        compliance=compliance,
        sellable_qty=available,
        breakdown=breakdown,
        score=score,
        fee_breakdown=fee_breakdown,
    )


__all__ = [
    "ListingCandidate",
    "PublishDecision",
    "evaluate_listing",
    "stock_confidence",
]
