from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from ecommerce_os.killswitch import (
    PauseScope,
    SkuMetrics,
    SkuThresholds,
    SupplierMetrics,
    SupplierThresholds,
    evaluate_kill_switches,
)

HEALTHY_SKU = SkuMetrics(
    feed_age_minutes=30,
    expected_contribution=Decimal("12.00"),
    supplier_price_change_pct=Decimal("0.01"),
    cancellation_rate=Decimal("0.005"),
    tracking_failure_rate=Decimal("0.005"),
    return_rate=Decimal("0.05"),
)

HEALTHY_SUPPLIER = SupplierMetrics(
    fill_rate=Decimal("0.99"),
    on_time_dispatch_rate=Decimal("0.98"),
    tracking_validity_rate=Decimal("0.99"),
)


def rules(sku=None, supplier=None, **kwargs) -> set[str]:
    triggers = evaluate_kill_switches(sku=sku, supplier=supplier, **kwargs)
    return {trigger.rule for trigger in triggers}


class TestHealthyStateKeepsSelling:
    def test_nothing_fires_when_everything_is_fine(self):
        assert evaluate_kill_switches(sku=HEALTHY_SKU, supplier=HEALTHY_SUPPLIER) == ()


class TestSkuPauses:
    def test_stale_stock_feed_pauses(self):
        assert "stale_stock_feed" in rules(sku=replace(HEALTHY_SKU, feed_age_minutes=240))

    def test_supplier_price_increase_beyond_tolerance_pauses(self):
        stung = replace(HEALTHY_SKU, supplier_price_change_pct=Decimal("0.12"))
        assert "supplier_price_increase" in rules(sku=stung)

    def test_negative_contribution_pauses(self):
        assert "contribution_below_minimum" in rules(
            sku=replace(HEALTHY_SKU, expected_contribution=Decimal("-0.50"))
        )

    def test_cancellation_and_tracking_spikes_pause(self):
        spiking = replace(
            HEALTHY_SKU,
            cancellation_rate=Decimal("0.09"),
            tracking_failure_rate=Decimal("0.08"),
        )
        assert {"cancellation_spike", "tracking_failure_spike"} <= rules(sku=spiking)

    def test_a_changed_match_invalidates_the_listing_premise(self):
        assert "match_record_changed" in rules(
            sku=replace(HEALTHY_SKU, match_record_changed=True)
        )

    def test_identifier_conflict_pauses(self):
        assert "identifier_conflict" in rules(sku=replace(HEALTHY_SKU, identifier_conflict=True))

    def test_recall_pauses_regardless_of_economics(self):
        recalled = replace(
            HEALTHY_SKU, recall_or_safety_flag=True, expected_contribution=Decimal("500")
        )
        assert "product_recall" in rules(sku=recalled)

    def test_marketplace_policy_flag_pauses(self):
        assert "marketplace_policy_flag" in rules(
            sku=replace(HEALTHY_SKU, marketplace_policy_flag=True)
        )

    def test_triggers_are_scoped_to_the_sku(self):
        triggers = evaluate_kill_switches(sku=replace(HEALTHY_SKU, feed_age_minutes=999))
        assert all(t.scope is PauseScope.SKU for t in triggers)

    def test_thresholds_are_tunable(self):
        tolerant = SkuThresholds(max_feed_age_minutes=1440)
        stale = replace(HEALTHY_SKU, feed_age_minutes=240)

        assert "stale_stock_feed" not in rules(sku=stale, sku_thresholds=tolerant)


class TestSupplierPauses:
    def test_fill_rate_below_floor_pauses_the_whole_supplier(self):
        assert "fill_rate" in rules(
            supplier=replace(HEALTHY_SUPPLIER, fill_rate=Decimal("0.90"))
        )

    def test_late_dispatch_pauses(self):
        assert "on_time_dispatch" in rules(
            supplier=replace(HEALTHY_SUPPLIER, on_time_dispatch_rate=Decimal("0.80"))
        )

    def test_prolonged_feed_outage_pauses(self):
        assert "prolonged_feed_outage" in rules(
            supplier=replace(HEALTHY_SUPPLIER, feed_outage_minutes=1440)
        )

    def test_any_third_party_packaging_incident_pauses(self):
        # Zero tolerance: one disclosed parcel is a policy problem, not a rate.
        assert "packaging_disclosure" in rules(
            supplier=replace(HEALTHY_SUPPLIER, unbranded_packaging_incidents=1)
        )

    def test_expired_agreement_pauses(self):
        expired = replace(HEALTHY_SUPPLIER, agreement_end=date(2026, 1, 1))
        assert "agreement_expired" in rules(supplier=expired, as_of=date(2026, 8, 20))

    def test_agreement_still_in_force_does_not_pause(self):
        live = replace(HEALTHY_SUPPLIER, agreement_end=date(2027, 1, 1))
        assert "agreement_expired" not in rules(supplier=live, as_of=date(2026, 8, 20))

    def test_supplier_triggers_are_scoped_to_the_supplier(self):
        triggers = evaluate_kill_switches(
            supplier=replace(HEALTHY_SUPPLIER, fill_rate=Decimal("0.10"))
        )
        assert all(t.scope is PauseScope.SUPPLIER for t in triggers)

    def test_thresholds_are_tunable(self):
        strict = SupplierThresholds(min_fill_rate=Decimal("0.995"))
        assert "fill_rate" in rules(supplier=HEALTHY_SUPPLIER, supplier_thresholds=strict)


class TestFailClosed:
    def test_every_trigger_carries_an_explanation(self):
        triggers = evaluate_kill_switches(
            sku=replace(HEALTHY_SKU, feed_age_minutes=9999, identifier_conflict=True),
            supplier=replace(HEALTHY_SUPPLIER, fill_rate=Decimal("0.10")),
        )

        assert len(triggers) >= 3
        assert all(trigger.rule and trigger.detail for trigger in triggers)
