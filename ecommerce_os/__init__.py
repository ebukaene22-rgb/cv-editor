"""Compliant ecommerce operating system — decision engine.

This package is the machine-readable core of the strategy in
``docs/ecommerce-os/strategy.md``: it turns "retailer A is cheaper than
marketplace B" into "a supply relationship I am contractually entitled to use
can reliably generate positive contribution margin through a channel on which
that fulfilment method is permitted".

Nothing here talks to a network. Every module is pure and deterministic so the
gates can be unit-tested and audited before a single listing goes live.
"""

from ecommerce_os.compliance import (
    FulfilmentMethod,
    SupplierAuthorisation,
    compliance_gate,
)
from ecommerce_os.fees import FeeBook, FeeRule, NoFeeRuleError
from ecommerce_os.identity import (
    normalize_brand,
    normalize_gtin,
    normalize_mpn,
    normalize_title,
    parse_pack_count,
)
from ecommerce_os.killswitch import PauseScope, SkuMetrics, SupplierMetrics, evaluate_kill_switches
from ecommerce_os.landed_cost import (
    CostBreakdown,
    LandedCostInputs,
    ReturnProfile,
    VatTreatment,
    contribution_margin,
    expected_return_cost,
)
from ecommerce_os.matching import MatchClass, MatchResult, classify_match
from ecommerce_os.pipeline import ListingCandidate, PublishDecision, evaluate_listing
from ecommerce_os.scoring import PilotGates, ScoreResult, score_opportunity
from ecommerce_os.supply import SupplierPerformance, sellable_stock, supplier_score

__all__ = [
    "CostBreakdown",
    "FeeBook",
    "FeeRule",
    "FulfilmentMethod",
    "LandedCostInputs",
    "ListingCandidate",
    "MatchClass",
    "MatchResult",
    "NoFeeRuleError",
    "PauseScope",
    "PilotGates",
    "PublishDecision",
    "ReturnProfile",
    "ScoreResult",
    "SkuMetrics",
    "SupplierAuthorisation",
    "SupplierMetrics",
    "SupplierPerformance",
    "VatTreatment",
    "classify_match",
    "compliance_gate",
    "contribution_margin",
    "evaluate_kill_switches",
    "evaluate_listing",
    "expected_return_cost",
    "normalize_brand",
    "normalize_gtin",
    "normalize_mpn",
    "normalize_title",
    "parse_pack_count",
    "score_opportunity",
    "sellable_stock",
    "supplier_score",
]
