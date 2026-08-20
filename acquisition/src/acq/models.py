"""Candidate record — the single shape every source normalises into.

`Listing` is what a source emits: whatever the marketplace said, in whatever
currency it said it. `Candidate` is what the rule engine reads: GBP, derived
fields computed, provenance retained.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Listing:
    """Raw, source-shaped. No arithmetic has been applied yet."""

    source: str                       # "flippa" | "trustmrr" | "wordpress"
    source_id: str
    url: str = ""
    name: str = ""
    category: str = ""
    revenue_model: str = ""
    platform: str = ""
    currency: str = "USD"

    asking_price: float | None = None
    ttm_revenue: float | None = None
    ttm_costs: float | None = None
    mrr: float | None = None
    monthly_profit: float | None = None
    active_customers: float | None = None   # whatever the listing calls "customers"
    paying_customers: float | None = None   # only when the listing discloses payers separately
    monthly_churn: float | None = None      # fraction, e.g. 0.08
    stated_ltv: float | None = None
    stated_arr: float | None = None         # the seller's own "ARR" claim
    min_customer_price: float | None = None
    age_months: float | None = None
    uniques_per_month: float | None = None

    has_verified_revenue: bool = False
    listing_text: str = ""
    stated_multiple: float | None = None    # the multiple the seller claims
    raw: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        """Dedupe key — source + listing ID, per the playbook's Stage 1 cadence."""
        return f"{self.source}:{self.source_id}"


@dataclass
class Candidate:
    """Normalised to GBP with derived metrics attached."""

    key: str
    source: str
    source_id: str
    url: str = ""
    name: str = ""
    category: str = ""
    revenue_model: str = ""
    platform: str = ""

    # money, all GBP
    asking_price: float | None = None
    ttm_revenue: float | None = None
    ttm_costs: float | None = None
    mrr: float | None = None
    monthly_profit: float | None = None
    stated_ltv: float | None = None
    stated_arr: float | None = None
    min_customer_price: float | None = None

    active_customers: float | None = None
    paying_customers: float | None = None
    monthly_churn: float | None = None
    age_months: float | None = None
    uniques_per_month: float | None = None

    # derived (see §6 of the brief)
    annual_revenue: float | None = None
    annual_profit: float | None = None
    run_rate_arr: float | None = None
    price_to_revenue: float | None = None
    price_to_profit: float | None = None
    payback_months: float | None = None
    arpu: float | None = None
    implied_lifetime: float | None = None
    implied_ltv: float | None = None
    trend_ratio: float | None = None

    # provenance
    original_currency: str = "USD"
    fx_rate: float | None = None
    has_verified_revenue: bool = False
    trustmrr_match: str = ""            # "" | "agrees" | "disagrees" | "none"
    trustmrr_mrr: float | None = None
    listing_text: str = ""
    stated_multiple: float | None = None

    # engine output
    disposition: str = ""               # "reject" | "review"
    rejects: list[dict[str, str]] = field(default_factory=list)
    flags: list[dict[str, str]] = field(default_factory=list)
    fit_score: float = 0.0
    score: float = 0.0

    # lifecycle
    first_seen: str = ""
    last_seen: str = ""
    status: str = "sourced"

    def flag_names(self) -> list[str]:
        return [f["flag"] for f in self.flags]

    def reject_reasons(self) -> list[str]:
        return [r["rule"] for r in self.rejects]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Candidate":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class NeglectCandidate:
    """D3 — a WordPress.org plugin with real users and an absent owner."""

    slug: str
    name: str = ""
    url: str = ""
    author: str = ""
    author_profile: str = ""
    active_installs: int = 0
    last_updated: str = ""
    months_since_update: float = 0.0
    rating: float = 0.0                 # 0-5
    num_ratings: int = 0
    support_threads: int = 0
    support_threads_resolved: int = 0
    support_resolution_rate: float = 0.0
    neglect_score: float = 0.0
    first_seen: str = ""
    last_seen: str = ""
    status: str = "sourced"

    def key(self) -> str:
        return f"wordpress:{self.slug}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NeglectCandidate":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


def stable_id(*parts: str) -> str:
    """Deterministic short ID for sources that don't expose a stable listing ID."""
    digest = hashlib.sha1("|".join(parts).encode()).hexdigest()
    return digest[:12]
