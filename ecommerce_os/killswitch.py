"""Automatic pause rules.

The production philosophy in one line:

    **It should be easier for the system to stop selling than to accidentally sell.**

Automated commerce needs deliberate failure modes. Every rule here is
fail-closed: missing or unmeasurable data pauses the listing rather than
assuming the best, because the cost asymmetry is brutal — a paused SKU forgoes
some margin, an unpaused broken SKU generates cancellations, defects and
account-health damage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from ecommerce_os.money import ZERO, money, rate


class PauseScope(Enum):
    SKU = "sku"
    SUPPLIER = "supplier"


@dataclass(frozen=True)
class PauseTrigger:
    scope: PauseScope
    rule: str
    detail: str


@dataclass(frozen=True)
class SkuThresholds:
    max_feed_age_minutes: int = 180
    max_supplier_price_increase_pct: Decimal = Decimal("0.05")
    min_expected_contribution: Decimal = Decimal("0.01")
    max_cancellation_rate: Decimal = Decimal("0.02")
    max_tracking_failure_rate: Decimal = Decimal("0.02")
    max_return_rate: Decimal = Decimal("0.15")


@dataclass(frozen=True)
class SupplierThresholds:
    min_fill_rate: Decimal = Decimal("0.95")
    min_on_time_dispatch_rate: Decimal = Decimal("0.95")
    max_feed_outage_minutes: int = 720
    max_unbranded_packaging_incidents: int = 0
    min_tracking_validity_rate: Decimal = Decimal("0.95")


@dataclass(frozen=True)
class SkuMetrics:
    feed_age_minutes: int
    expected_contribution: Decimal
    supplier_price_change_pct: Decimal = ZERO
    cancellation_rate: Decimal = ZERO
    tracking_failure_rate: Decimal = ZERO
    return_rate: Decimal = ZERO
    match_record_changed: bool = False
    identifier_conflict: bool = False
    marketplace_policy_flag: bool = False
    recall_or_safety_flag: bool = False


@dataclass(frozen=True)
class SupplierMetrics:
    fill_rate: Decimal
    on_time_dispatch_rate: Decimal
    tracking_validity_rate: Decimal
    feed_outage_minutes: int = 0
    unbranded_packaging_incidents: int = 0
    agreement_end: date | None = None


def evaluate_kill_switches(
    *,
    sku: SkuMetrics | None = None,
    supplier: SupplierMetrics | None = None,
    as_of: date | None = None,
    sku_thresholds: SkuThresholds | None = None,
    supplier_thresholds: SupplierThresholds | None = None,
) -> tuple[PauseTrigger, ...]:
    """Return every pause that should fire. Empty means keep selling."""
    triggers: list[PauseTrigger] = []
    if sku is not None:
        triggers.extend(_sku_triggers(sku, sku_thresholds or SkuThresholds()))
    if supplier is not None:
        triggers.extend(
            _supplier_triggers(supplier, supplier_thresholds or SupplierThresholds(), as_of)
        )
    return tuple(triggers)


def _sku_triggers(m: SkuMetrics, t: SkuThresholds) -> list[PauseTrigger]:
    out: list[PauseTrigger] = []

    def pause(rule: str, detail: str) -> None:
        out.append(PauseTrigger(PauseScope.SKU, rule, detail))

    if m.feed_age_minutes > t.max_feed_age_minutes:
        pause(
            "stale_stock_feed",
            f"feed is {m.feed_age_minutes}m old, limit {t.max_feed_age_minutes}m",
        )

    if money(m.supplier_price_change_pct) > money(t.max_supplier_price_increase_pct):
        pause(
            "supplier_price_increase",
            f"cost up {m.supplier_price_change_pct}, tolerance "
            f"{t.max_supplier_price_increase_pct}",
        )

    if money(m.expected_contribution) < money(t.min_expected_contribution):
        pause(
            "contribution_below_minimum",
            f"expected contribution {m.expected_contribution}",
        )

    if rate(m.cancellation_rate) > money(t.max_cancellation_rate):
        pause("cancellation_spike", f"cancellation rate {m.cancellation_rate}")

    if rate(m.tracking_failure_rate) > money(t.max_tracking_failure_rate):
        pause("tracking_failure_spike", f"tracking failure rate {m.tracking_failure_rate}")

    if rate(m.return_rate) > money(t.max_return_rate):
        pause("return_rate_out_of_control", f"return rate {m.return_rate}")

    # The following are binary facts, not rates: any one of them invalidates the
    # premise the listing was created on.
    if m.match_record_changed:
        pause("match_record_changed", "canonical match was edited or re-resolved")
    if m.identifier_conflict:
        pause("identifier_conflict", "GTIN/MPN conflict detected against canonical record")
    if m.marketplace_policy_flag:
        pause("marketplace_policy_flag", "marketplace raised a policy flag")
    if m.recall_or_safety_flag:
        pause("product_recall", "recall or safety flag on this product")

    return out


def _supplier_triggers(
    m: SupplierMetrics, t: SupplierThresholds, as_of: date | None
) -> list[PauseTrigger]:
    out: list[PauseTrigger] = []

    def pause(rule: str, detail: str) -> None:
        out.append(PauseTrigger(PauseScope.SUPPLIER, rule, detail))

    if rate(m.fill_rate) < money(t.min_fill_rate):
        pause("fill_rate", f"fill rate {m.fill_rate} below {t.min_fill_rate}")

    if rate(m.on_time_dispatch_rate) < money(t.min_on_time_dispatch_rate):
        pause(
            "on_time_dispatch",
            f"on-time dispatch {m.on_time_dispatch_rate} below {t.min_on_time_dispatch_rate}",
        )

    if m.feed_outage_minutes > t.max_feed_outage_minutes:
        pause(
            "prolonged_feed_outage",
            f"feed unavailable for {m.feed_outage_minutes}m",
        )

    if m.unbranded_packaging_incidents > t.max_unbranded_packaging_incidents:
        pause(
            "packaging_disclosure",
            f"{m.unbranded_packaging_incidents} incidents of third-party packaging",
        )

    if rate(m.tracking_validity_rate) < money(t.min_tracking_validity_rate):
        pause(
            "tracking_validity",
            f"valid tracking {m.tracking_validity_rate} below {t.min_tracking_validity_rate}",
        )

    if as_of is not None and m.agreement_end is not None and as_of > m.agreement_end:
        pause("agreement_expired", f"agreement ended {m.agreement_end.isoformat()}")

    return out
