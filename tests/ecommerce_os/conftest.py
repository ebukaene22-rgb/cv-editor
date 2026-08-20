"""Shared fixtures: a supplier and a route that are deliberately *fully* compliant.

Individual tests break one thing at a time from this baseline, which keeps each
test about a single gate rather than about assembling twenty fields correctly.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ecommerce_os.compliance import BrandAuthorisation, SupplierAuthorisation
from ecommerce_os.fees import ANY, FeeBook, FeeRule
from ecommerce_os.landed_cost import LandedCostInputs, ReturnProfile, VatTreatment
from ecommerce_os.supply import SupplierPerformance

TODAY = date(2026, 8, 20)


@pytest.fixture
def today() -> date:
    return TODAY


@pytest.fixture
def authorisation() -> SupplierAuthorisation:
    return SupplierAuthorisation(
        supplier_id="dist-uk-001",
        canonical_sku_id="cp-1001",
        agreement_start=date(2026, 1, 1),
        agreement_end=date(2027, 1, 1),
        compliance_review_date=date(2026, 12, 1),
        resale_authorised=True,
        dropship_authorised=True,
        territories=frozenset({"GB"}),
        marketplaces=frozenset({"ebay"}),
        seller_of_record_supported=True,
        white_label_packaging=True,
        catalogue_content_rights=True,
        brand_authorisation=BrandAuthorisation.AUTHORISED,
        return_address_country="GB",
        warranty_owner="manufacturer",
        dispatch_sla_hours=24,
        tracking_sla_hours=24,
        inventory_feed_type="api",
        inventory_feed_frequency_minutes=60,
    )


@pytest.fixture
def fee_book() -> FeeBook:
    return FeeBook(
        [
            FeeRule(
                marketplace="ebay",
                country="GB",
                category=ANY,
                fee_kind="referral",
                variable_rate=Decimal("0.10"),
                fixed_fee=Decimal("0"),
                effective_from=date(2026, 1, 1),
                schedule_version="2026-01",
            )
        ]
    )


@pytest.fixture
def performance() -> SupplierPerformance:
    return SupplierPerformance(
        fill_rate=Decimal("0.99"),
        on_time_dispatch_rate=Decimal("0.99"),
        valid_tracking_rate=Decimal("0.99"),
        feed_accuracy=Decimal("0.99"),
        return_resolution_quality=Decimal("0.99"),
        non_defect_rate=Decimal("0.99"),
    )


@pytest.fixture
def return_profile() -> ReturnProfile:
    return ReturnProfile(
        return_rate=Decimal("0.05"),
        reverse_logistics_cost=Decimal("4.00"),
        resell_probability=Decimal("0.50"),
        writeoff_cost=Decimal("48.00"),
        handling_cost=Decimal("1.00"),
        nonrefundable_fees=Decimal("2.00"),
    )


@pytest.fixture
def costs(return_profile: ReturnProfile) -> LandedCostInputs:
    """A £120 VAT-inclusive UK sale on a £48 wholesale cost."""
    return LandedCostInputs(
        selling_price=Decimal("120.00"),
        supplier_price_ex_vat=Decimal("48.00"),
        vat_treatment=VatTreatment.SELLER_COLLECTS,
        sale_vat_rate=Decimal("0.20"),
        supplier_vat_rate=Decimal("0.20"),
        input_vat_recoverable=True,
        outbound_shipping=Decimal("7.00"),
        payment_fee_rate=Decimal("0.029"),
        payment_fixed_fee=Decimal("0.30"),
        advertising_per_order=Decimal("6.00"),
        return_profile=return_profile,
        fulfilment_failure_rate=Decimal("0.01"),
        fulfilment_failure_cost=Decimal("5.00"),
    )
