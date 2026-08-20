"""UK marketplace fee rules, February 2026 rate card — SEARCH-VERIFIED.

Collected 2026-08-20 by web search from secondary sources plus eBay's own
seller-centre rate-card announcement surfaced in results. Status:
**search-verified, not primary-confirmed** — confirm against the marketplace's
own fee page or fee-estimate API before these drive live listing decisions.
Sources are cited per rule in ``source_ref``.

Conventions:

* Rates are **ex-VAT**. Both marketplaces add 20% VAT on their fees; for a
  VAT-registered seller that VAT is recoverable input tax, so the ex-VAT rate
  is the true economic cost and is what belongs in the landed-cost model.
* eBay computes its percentage fees on the **total sale amount including VAT
  and postage** — which is exactly the ``price`` the FeeBook is called with, so
  no adjustment is needed.
* Amazon UK rates below are **effective rates**: base referral rate × 1.02 for
  the UK Digital Services Tax pass-through reported by fee guides (e.g. 15% →
  15.3% effective). Encoded as a single rule per category because the FeeBook
  computes percentages of price, not fees-on-fees.
* eBay's per-order fixed fee is banded by order value: £0.30 under £10, £0.40
  at £10 and above (raised from £0.30 in February 2026). Encoded as the
  ``order_fixed`` fee kind with a half-open band boundary at £10.
* Secondary sources disagree slightly on the regulatory operating fee
  (0.32%–0.42% quoted); 0.35% is the figure most sources state and is encoded
  here. This is exactly the kind of drift primary confirmation exists to catch.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ecommerce_os.fees import ANY, FeeBook, FeeRule

COLLECTED_ON = date(2026, 8, 20)
_EFFECTIVE = date(2026, 2, 1)  # February 2026 rate card
_VERSION = "2026-02-search-verified"

_EBAY_SRC = (
    "search 2026-08-20: ebay.co.uk/sellercentre fees + "
    "valueaddedresource.net (Feb 2026 UK FVF rise) + dashvue.co.uk fee guide"
)
_AMZN_SRC = (
    "search 2026-08-20: aboutamazon.eu 2026 fee update + "
    "profit-scanner.com / axivelo.app UK referral tables (DST pass-through)"
)


def uk_fee_book_2026() -> FeeBook:
    """FeeBook covering the categories the parts thesis actually trades in."""
    rules = [
        # ---- eBay UK, business sellers, Feb 2026 rate card ----
        FeeRule(
            marketplace="ebay",
            country="GB",
            category="business_industrial",
            fee_kind="final_value",
            variable_rate=Decimal("0.125"),  # Business, Office & Industrial
            fixed_fee=Decimal("0"),
            effective_from=_EFFECTIVE,
            schedule_version=_VERSION,
            source_ref=_EBAY_SRC,
        ),
        FeeRule(
            marketplace="ebay",
            country="GB",
            category=ANY,
            fee_kind="final_value",
            variable_rate=Decimal("0.128"),  # most-categories standard rate
            fixed_fee=Decimal("0"),
            effective_from=_EFFECTIVE,
            schedule_version=_VERSION,
            source_ref=_EBAY_SRC,
        ),
        FeeRule(
            marketplace="ebay",
            country="GB",
            category=ANY,
            fee_kind="regulatory_operating",
            variable_rate=Decimal("0.0035"),  # sources quote 0.32%-0.42%
            fixed_fee=Decimal("0"),
            effective_from=_EFFECTIVE,
            schedule_version=_VERSION,
            source_ref=_EBAY_SRC,
        ),
        # Per-order fixed fee, banded at £10 (half-open boundary: £10 pays 40p).
        FeeRule(
            marketplace="ebay",
            country="GB",
            category=ANY,
            fee_kind="order_fixed",
            variable_rate=Decimal("0"),
            fixed_fee=Decimal("0.30"),
            price_max=Decimal("10.00"),
            effective_from=_EFFECTIVE,
            schedule_version=_VERSION,
            source_ref=_EBAY_SRC,
        ),
        FeeRule(
            marketplace="ebay",
            country="GB",
            category=ANY,
            fee_kind="order_fixed",
            variable_rate=Decimal("0"),
            fixed_fee=Decimal("0.40"),
            price_min=Decimal("10.00"),
            effective_from=_EFFECTIVE,
            schedule_version=_VERSION,
            source_ref=_EBAY_SRC,
        ),
        # ---- Amazon UK, effective rates incl. 2% DST pass-through ----
        FeeRule(
            marketplace="amazon",
            country="GB",
            category="business_industrial_scientific",
            fee_kind="referral",
            variable_rate=Decimal("0.1224"),  # 12% x 1.02
            fixed_fee=Decimal("0"),
            effective_from=_EFFECTIVE,
            schedule_version=_VERSION,
            source_ref=_AMZN_SRC,
        ),
        FeeRule(
            marketplace="amazon",
            country="GB",
            category="home_kitchen",
            fee_kind="referral",
            variable_rate=Decimal("0.153"),  # 15% x 1.02
            fixed_fee=Decimal("0"),
            effective_from=_EFFECTIVE,
            schedule_version=_VERSION,
            source_ref=_AMZN_SRC,
        ),
    ]
    return FeeBook(rules)


EBAY_UK_FEE_KINDS = ("final_value", "regulatory_operating", "order_fixed")
AMAZON_UK_FEE_KINDS = ("referral",)
