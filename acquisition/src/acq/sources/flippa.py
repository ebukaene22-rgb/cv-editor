"""D2 — Flippa ingestion.

There is no official public API. The site's JSON search endpoint returns
structured listing objects; Apify actors wrap the same data. Both are
undocumented and both will break, so each sits behind `FlippaBackend` and the
source picks one at construction — swapping backends is a config change, not a
rewrite.

Two behaviours that are not optional:

* **Re-filter client-side.** Sponsored listings are injected into results
  outside the requested filter range. Whatever the endpoint was asked for, the
  price band is applied again here on the way out.
* **`has_verified_revenue == false` is the default state below $50k.** Flippa
  does not verify at this level, so absence of verification is not a signal
  about a particular listing — it is the baseline, and the UNVERIFIED flag
  exists to keep it visible rather than to condemn.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from ..extract import apply_to as extract_prose
from ..models import Listing
from .base import Source, SourceError

FLIPPA_SEARCH = "https://flippa.com/v3/listings"
APIFY_RUN = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

# The fields the brief confirms are present on a listing object.
CAPTURE = (
    "id", "title", "property_type", "status", "sale_method", "current_price",
    "buy_it_now_price", "average_revenue", "average_profit", "revenue_per_month",
    "profit_per_month", "business_model", "industry", "uniques_per_month",
    "has_verified_revenue", "has_verified_traffic", "seller_location",
    "established_at", "summary",
)


class FlippaBackend(ABC):
    """Anything that can hand back raw Flippa listing dicts."""

    name = "backend"

    @abstractmethod
    def raw_listings(self, source: "FlippaSource", page_size: int, max_pages: int) -> list[dict]:
        ...


class JsonEndpointBackend(FlippaBackend):
    """The site's own JSON search endpoint."""

    name = "json-endpoint"

    def __init__(self, url: str = FLIPPA_SEARCH) -> None:
        self.url = url

    def raw_listings(self, source: "FlippaSource", page_size: int, max_pages: int) -> list[dict]:
        out: list[dict] = []
        for page in range(1, max_pages + 1):
            params = {
                "filter[property_type]": "website,saas,ecommerce",
                "filter[status]": "open",
                "filter[price][min]": int(source.min_price_native),
                "filter[price][max]": int(source.max_price_native),
                "page[number]": page,
                "page[size]": page_size,
            }
            payload = source.get_json(self.url, params)
            batch = payload.get("data") if isinstance(payload, dict) else payload
            if batch is None:
                raise SourceError("flippa: unexpected response shape (no `data`)")
            if not batch:
                break
            out.extend(batch)
            if len(batch) < page_size:
                break
        return out


class ApifyActorBackend(FlippaBackend):
    """An Apify actor wrapping the same data. Needs APIFY_TOKEN."""

    name = "apify"

    def __init__(self, actor: str, token: str | None = None) -> None:
        self.actor = actor
        self.token = token or os.environ.get("APIFY_TOKEN", "")

    def raw_listings(self, source: "FlippaSource", page_size: int, max_pages: int) -> list[dict]:
        if not self.token:
            raise SourceError("flippa/apify: APIFY_TOKEN is not set")
        payload = source.get_json(
            APIFY_RUN.format(actor=self.actor),
            {"token": self.token, "limit": page_size * max_pages},
        )
        if not isinstance(payload, list):
            raise SourceError("flippa/apify: expected a dataset item list")
        return payload


class FlippaSource(Source):
    name = "flippa"

    def __init__(self, config, session=None, backend: FlippaBackend | None = None,
                 native_currency: str = "USD", fx=None) -> None:
        super().__init__(config, session)
        self.backend = backend or JsonEndpointBackend()
        self.native_currency = native_currency
        self.fx = fx

    # The endpoint filters in its own currency; the config band is GBP.
    @property
    def min_price_native(self) -> float:
        return self._to_native(self.cfg["budget.min_price_gbp"])

    @property
    def max_price_native(self) -> float:
        return self._to_native(self.cfg["budget.max_price_gbp"])

    def _to_native(self, gbp: float) -> float:
        if self.fx is None or self.native_currency == "GBP":
            return gbp
        return gbp * self.fx.rate("GBP", self.native_currency)

    def fetch(self, limit: int | None = None, page_size: int = 100,
              max_pages: int = 10) -> list[Listing]:
        raw = self.backend.raw_listings(self, page_size, max_pages)
        listings = [self.to_listing(item) for item in raw]
        listings = [l for l in listings if l is not None]

        kept = [l for l in listings if self._in_band(l)]
        dropped = len(listings) - len(kept)
        print(f"{self.name}: {len(listings)} listings via {self.backend.name}")
        if dropped:
            # Sponsored slots are the usual cause, but the filter is unconditional:
            # anything outside the band is out of the tier, however it got here.
            print(f"{self.name}: dropped {dropped} outside the £"
                  f"{self.cfg['budget.min_price_gbp']:,}–£{self.cfg['budget.max_price_gbp']:,} "
                  f"band before screening (sponsored slots and mis-tiered listings)")
        print(f"{self.name}: {len(kept)} in band")
        return kept[:limit] if limit else kept

    def _in_band(self, listing: Listing) -> bool:
        """Client-side re-filter. A listing with no price at all is kept — the
        rule engine will surface it as DATA_INCOMPLETE rather than the source
        deciding silently."""
        if listing.asking_price is None:
            return True
        return self.min_price_native <= listing.asking_price <= self.max_price_native

    @classmethod
    def to_listing(cls, raw: dict, currency: str = "USD",
                   read_prose: bool = True) -> Listing | None:
        """Map one raw listing.

        `read_prose` fills customer count, churn, stated LTV and entry price from
        the `summary` text. The endpoint does not return any of them, and without
        them LTV_IMPLAUSIBLE and CUSTOMER_COUNT_INFLATED can never fire on a live
        pull. Endpoint values always win; prose only fills gaps.
        """
        listing_id = raw.get("id")
        if listing_id is None:
            return None
        get = cls._num

        price = get(raw.get("buy_it_now_price")) or get(raw.get("current_price"))
        monthly_revenue = get(raw.get("revenue_per_month"))
        monthly_profit = get(raw.get("profit_per_month"))
        ttm_revenue = get(raw.get("average_revenue"))
        if ttm_revenue is None and monthly_revenue is not None:
            ttm_revenue = monthly_revenue * 12
        annual_profit = get(raw.get("average_profit"))
        if monthly_profit is None and annual_profit is not None:
            monthly_profit = annual_profit / 12

        ttm_costs = None
        if ttm_revenue is not None and annual_profit is not None:
            ttm_costs = ttm_revenue - annual_profit

        listing = Listing(
            source="flippa",
            source_id=str(listing_id),
            url=raw.get("listing_url") or f"https://flippa.com/{listing_id}",
            name=raw.get("title", "") or "",
            category=(raw.get("industry") or raw.get("property_type") or "").strip().lower(),
            revenue_model=(raw.get("business_model") or "").strip().lower(),
            currency=raw.get("currency", currency) or currency,
            asking_price=price,
            ttm_revenue=ttm_revenue,
            ttm_costs=ttm_costs,
            mrr=monthly_revenue,
            monthly_profit=monthly_profit,
            uniques_per_month=get(raw.get("uniques_per_month")),
            age_months=cls._age_months(raw.get("established_at")),
            has_verified_revenue=bool(raw.get("has_verified_revenue")),
            listing_text=raw.get("summary", "") or "",
            stated_multiple=get(raw.get("multiple")),
            raw={k: raw.get(k) for k in CAPTURE if k in raw},
        )
        if read_prose:
            extract_prose(listing)
        return listing

    @staticmethod
    def _age_months(established_at) -> float | None:
        """`established_at` arrives as an ISO timestamp, a date, or a bare year."""
        if not established_at:
            return None
        text = str(established_at).strip().replace("Z", "+0000")
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                when = datetime.strptime(text, fmt)
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return round(max(0.0, (datetime.now(timezone.utc) - when).days / 30.44), 1)
        return None
