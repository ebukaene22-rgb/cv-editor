"""D4 — normalisation and derived metrics.

Everything the rule engine reads is computed here, once, in GBP. Where a figure
has to be inferred rather than read (run-rate standing in for a missing TTM, the
seller's own "ARR" standing in for a missing MRR), the substitution is recorded
on the candidate so a flag can point at it later.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .fx import FxRates
from .models import Candidate, Listing

MONEY_FIELDS = (
    "asking_price", "ttm_revenue", "ttm_costs", "mrr", "monthly_profit",
    "stated_ltv", "stated_arr", "min_customer_price", "stated_monthly_costs",
)


def _div(num: float | None, den: float | None) -> float | None:
    """Guarded division — None in, None out; never a ZeroDivisionError and never
    an infinity that would sail past a `> threshold` comparison as False."""
    if num is None or den is None or den == 0:
        return None
    return num / den


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def normalise(listing: Listing, fx: FxRates, target: str = "GBP") -> Candidate:
    cur = (listing.currency or "USD").upper()
    rate = fx.rate(cur, target)

    c = Candidate(
        key=listing.key(),
        source=listing.source,
        source_id=listing.source_id,
        url=listing.url,
        name=listing.name,
        category=(listing.category or "").strip().lower(),
        revenue_model=(listing.revenue_model or "").strip().lower(),
        platform=(listing.platform or "").strip().lower(),
        active_customers=listing.active_customers,
        paying_customers=listing.paying_customers,
        monthly_churn=listing.monthly_churn,
        age_months=listing.age_months,
        uniques_per_month=listing.uniques_per_month,
        original_currency=cur,
        fx_rate=rate,
        has_verified_revenue=bool(listing.has_verified_revenue),
        listing_text=listing.listing_text or "",
        stated_multiple=listing.stated_multiple,
        first_seen=now_iso(),
        last_seen=now_iso(),
    )
    for field in MONEY_FIELDS:
        value = getattr(listing, field)
        setattr(c, field, None if value is None else value * rate)

    derive(c)
    return c


def derive(c: Candidate) -> Candidate:
    """Compute §6 derived fields in place. Safe to re-run after an edit."""
    # Revenue basis. TTM is the honest figure; run-rate is what a listing reaches
    # for when TTM is unflattering, so falling back to it is recorded, not hidden.
    c.run_rate_arr = (c.mrr * 12) if c.mrr is not None else c.stated_arr
    c.annual_revenue = c.ttm_revenue if c.ttm_revenue is not None else c.run_rate_arr

    if c.mrr is None and c.ttm_revenue is not None:
        c.mrr = c.ttm_revenue / 12

    if c.annual_revenue is not None and c.ttm_costs is not None:
        c.annual_profit = c.annual_revenue - c.ttm_costs
    if c.monthly_profit is None and c.annual_profit is not None:
        c.monthly_profit = c.annual_profit / 12

    c.price_to_revenue = _div(c.asking_price, c.annual_revenue)
    c.price_to_profit = _div(c.asking_price, c.annual_profit)
    c.payback_months = _div(c.asking_price, c.monthly_profit)
    # ARPU is per *paying* customer. A listing that quotes a user count and a
    # payer count gets measured against the payers; one that quotes a single
    # blended "customers" figure gets measured against that, which is precisely
    # how an inflated count surfaces as an impossible ARPU.
    billable = c.paying_customers if c.paying_customers is not None else c.active_customers
    c.arpu = _div(c.mrr, billable)
    c.implied_lifetime = _div(1.0, c.monthly_churn)
    c.implied_ltv = (
        c.arpu * c.implied_lifetime
        if c.arpu is not None and c.implied_lifetime is not None
        else None
    )
    c.trend_ratio = _div(c.run_rate_arr, c.ttm_revenue)
    return c
