from __future__ import annotations

from dataclasses import replace
from datetime import date

from ecommerce_os.compliance import (
    BrandAuthorisation,
    FulfilmentMethod,
    SupplierAuthorisation,
    compliance_gate,
)


def gate(auth, **overrides):
    kwargs = dict(
        marketplace="ebay",
        market="GB",
        fulfilment=FulfilmentMethod.SUPPLIER_DROPSHIP,
        as_of=date(2026, 8, 20),
    )
    kwargs.update(overrides)
    return compliance_gate(auth, **kwargs)


class TestBaseline:
    def test_a_fully_authorised_route_passes(self, authorisation):
        assert gate(authorisation).ok

    def test_defaults_are_restrictive(self):
        # A half-completed onboarding form must fail, never pass.
        bare = SupplierAuthorisation(
            supplier_id="s1", canonical_sku_id="cp-1", agreement_start=date(2026, 1, 1)
        )
        result = gate(bare)

        assert not result.ok
        assert "supplier agreement does not authorise resale" in result.failures

    def test_all_failures_are_reported_not_just_the_first(self):
        bare = SupplierAuthorisation(
            supplier_id="s1", canonical_sku_id="cp-1", agreement_start=date(2026, 1, 1)
        )
        assert len(gate(bare).failures) > 5


class TestScopeOfTheAgreement:
    def test_unauthorised_territory_blocks(self, authorisation):
        result = gate(authorisation, market="AE")
        assert not result.ok
        assert "territory AE not authorised" in result.failures

    def test_unauthorised_marketplace_blocks(self, authorisation):
        result = gate(authorisation, marketplace="amazon")
        assert not result.ok
        assert "marketplace amazon not authorised" in result.failures

    def test_expired_agreement_blocks(self, authorisation):
        expired = replace(authorisation, agreement_end=date(2026, 6, 30))
        assert "agreement expired on 2026-06-30" in gate(expired).failures

    def test_agreement_not_yet_in_force_blocks(self, authorisation):
        future = replace(authorisation, agreement_start=date(2026, 12, 1))
        assert not gate(future).ok

    def test_overdue_compliance_review_blocks(self, authorisation):
        stale = replace(authorisation, compliance_review_date=date(2026, 7, 1))
        assert "compliance review overdue since 2026-07-01" in gate(stale).failures


class TestDropshipSpecificDuties:
    def test_resale_rights_alone_do_not_grant_dropship_rights(self, authorisation):
        # "Sure, just email the orders over" is not marketplace fulfilment rights.
        no_dropship = replace(authorisation, dropship_authorised=False)
        result = gate(no_dropship)

        assert not result.ok
        assert "supplier agreement does not authorise direct fulfilment" in result.failures

    def test_supplier_branded_packaging_blocks_dropship(self, authorisation):
        disclosing = replace(authorisation, white_label_packaging=False)
        result = gate(disclosing)

        assert not result.ok
        assert "supplier packaging would disclose a third-party seller" in result.failures

    def test_seller_of_record_must_be_supported(self, authorisation):
        not_sor = replace(authorisation, seller_of_record_supported=False)
        assert not gate(not_sor).ok

    def test_manual_stock_updates_cannot_support_dropship(self, authorisation):
        # Without stock of our own, a live feed is the only thing between us and
        # overselling.
        manual = replace(authorisation, inventory_feed_type="manual")
        result = gate(manual)

        assert not result.ok
        assert any("not machine-readable" in failure for failure in result.failures)

    def test_the_same_supplier_can_still_be_bought_from_in_bulk(self, authorisation):
        # A supplier too unstructured for dropship may be perfectly good for
        # buying a pallet, so the manual-feed rule must not bleed into own-stock.
        manual = replace(
            authorisation, inventory_feed_type="manual", dropship_authorised=False
        )
        assert gate(manual, fulfilment=FulfilmentMethod.OWN_STOCK).ok

    def test_dispatch_sla_beyond_policy_blocks(self, authorisation):
        result = gate(authorisation, max_dispatch_sla_hours=12)
        assert not result.ok
        assert any("exceeds 12h policy" in failure for failure in result.failures)

    def test_undefined_slas_block(self, authorisation):
        undefined = replace(authorisation, dispatch_sla_hours=None, tracking_sla_hours=None)
        failures = gate(undefined).failures

        assert "dispatch SLA is undefined" in failures
        assert "tracking SLA is undefined" in failures


class TestContentAndBrandRights:
    def test_using_supplier_images_without_a_licence_blocks(self, authorisation):
        unlicensed = replace(authorisation, catalogue_content_rights=False)
        result = gate(unlicensed, uses_supplier_content=True)

        assert not result.ok
        assert "no licence for supplier images/copy" in result.failures

    def test_own_content_does_not_need_a_licence(self, authorisation):
        unlicensed = replace(authorisation, catalogue_content_rights=False)
        assert gate(unlicensed, uses_supplier_content=False).ok

    def test_pending_brand_authorisation_blocks_a_gated_brand(self, authorisation):
        pending = replace(authorisation, brand_authorisation=BrandAuthorisation.PENDING)
        result = gate(pending, brand_authorisation_required=True)

        assert not result.ok
        assert "brand authorisation is pending" in result.failures

    def test_not_required_clears(self, authorisation):
        not_required = replace(
            authorisation, brand_authorisation=BrandAuthorisation.NOT_REQUIRED
        )
        assert gate(not_required, brand_authorisation_required=True).ok


class TestReturns:
    def test_no_return_address_blocks_any_fulfilment_method(self, authorisation):
        nowhere = replace(authorisation, return_address_country=None)

        for method in FulfilmentMethod:
            result = gate(nowhere, fulfilment=method)
            assert "no operational return address" in result.failures
