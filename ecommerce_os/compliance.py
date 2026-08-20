"""Compliance as data, not as a document somebody remembers to check.

Every supplier × SKU × marketplace combination carries an explicit
authorisation record. A listing is not publishable because it is profitable; it
is publishable because a supply relationship we are contractually entitled to
use permits this product, on this channel, into this territory, by this
fulfilment method.

Compliance is a **hard gate**, never a probabilistic discount in the score. A
90%-likely-compliant listing is not worth 90% of the margin; it is worth an
account suspension.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

# Feed mechanisms that a machine can trust for live stock. "Email the orders
# over" is a fine way to buy a pallet and a terrible way to run dropship.
MACHINE_READABLE_FEEDS = frozenset({"api", "sftp", "csv", "xml", "json", "edi"})


class FulfilmentMethod(Enum):
    SUPPLIER_DROPSHIP = "supplier_dropship"
    OWN_STOCK = "own_stock"
    THIRD_PARTY_LOGISTICS = "third_party_logistics"
    MARKETPLACE_FULFILLED = "marketplace_fulfilled"  # FBA / FBN

    @property
    def requires_dropship_rights(self) -> bool:
        return self is FulfilmentMethod.SUPPLIER_DROPSHIP


class BrandAuthorisation(Enum):
    AUTHORISED = "authorised"
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    REFUSED = "refused"

    @property
    def clears(self) -> bool:
        return self in (BrandAuthorisation.AUTHORISED, BrandAuthorisation.NOT_REQUIRED)


@dataclass(frozen=True)
class SupplierAuthorisation:
    """What a written supply agreement actually entitles us to do.

    Defaults are deliberately restrictive. An authorisation record built from a
    partially completed onboarding form should fail the gate, not pass it.
    """

    supplier_id: str
    canonical_sku_id: str
    agreement_start: date
    resale_authorised: bool = False
    dropship_authorised: bool = False
    territories: frozenset[str] = field(default_factory=frozenset)
    marketplaces: frozenset[str] = field(default_factory=frozenset)
    seller_of_record_supported: bool = False
    white_label_packaging: bool = False
    catalogue_content_rights: bool = False
    brand_authorisation: BrandAuthorisation = BrandAuthorisation.PENDING
    return_address_country: str | None = None
    warranty_owner: str | None = None
    dispatch_sla_hours: int | None = None
    tracking_sla_hours: int | None = None
    inventory_feed_type: str = "manual"
    inventory_feed_frequency_minutes: int | None = None
    agreement_end: date | None = None
    compliance_review_date: date | None = None


@dataclass(frozen=True)
class GateResult:
    ok: bool
    failures: tuple[str, ...]

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return self.ok


def compliance_gate(
    auth: SupplierAuthorisation,
    *,
    marketplace: str,
    market: str,
    fulfilment: FulfilmentMethod,
    as_of: date,
    brand_authorisation_required: bool = False,
    uses_supplier_content: bool = False,
    max_dispatch_sla_hours: int | None = None,
) -> GateResult:
    """Return every reason this combination may not be listed.

    All failures are collected rather than short-circuited, so an operator sees
    the full remediation list in one pass instead of fixing one blocker per day.
    """
    failures: list[str] = []
    marketplace = marketplace.strip().lower()
    market = market.strip().upper()

    if not auth.resale_authorised:
        failures.append("supplier agreement does not authorise resale")

    if as_of < auth.agreement_start:
        failures.append(f"agreement does not start until {auth.agreement_start.isoformat()}")
    if auth.agreement_end is not None and as_of > auth.agreement_end:
        failures.append(f"agreement expired on {auth.agreement_end.isoformat()}")

    if auth.compliance_review_date is not None and as_of > auth.compliance_review_date:
        failures.append(
            f"compliance review overdue since {auth.compliance_review_date.isoformat()}"
        )

    if market not in {t.strip().upper() for t in auth.territories}:
        failures.append(f"territory {market} not authorised")

    if marketplace not in {m.strip().lower() for m in auth.marketplaces}:
        failures.append(f"marketplace {marketplace} not authorised")

    if brand_authorisation_required and not auth.brand_authorisation.clears:
        failures.append(f"brand authorisation is {auth.brand_authorisation.value}")

    if uses_supplier_content and not auth.catalogue_content_rights:
        failures.append("no licence for supplier images/copy")

    if fulfilment.requires_dropship_rights:
        failures.extend(_dropship_failures(auth, max_dispatch_sla_hours))

    if auth.return_address_country is None:
        failures.append("no operational return address")

    return GateResult(ok=not failures, failures=tuple(failures))


def _dropship_failures(
    auth: SupplierAuthorisation, max_dispatch_sla_hours: int | None
) -> list[str]:
    """Extra conditions that only bite when the supplier ships to the customer."""
    failures: list[str] = []

    if not auth.dropship_authorised:
        failures.append("supplier agreement does not authorise direct fulfilment")

    # We must remain the only seller the buyer ever sees.
    if not auth.seller_of_record_supported:
        failures.append("supplier cannot support us as sole seller of record")
    if not auth.white_label_packaging:
        failures.append("supplier packaging would disclose a third-party seller")

    # Without stock of our own, live inventory is the only thing standing
    # between us and overselling.
    if auth.inventory_feed_type.strip().lower() not in MACHINE_READABLE_FEEDS:
        failures.append(
            f"inventory feed '{auth.inventory_feed_type}' is not machine-readable"
        )
    if auth.inventory_feed_frequency_minutes is None:
        failures.append("inventory feed frequency is undefined")

    if auth.dispatch_sla_hours is None:
        failures.append("dispatch SLA is undefined")
    elif max_dispatch_sla_hours is not None and auth.dispatch_sla_hours > max_dispatch_sla_hours:
        failures.append(
            f"dispatch SLA {auth.dispatch_sla_hours}h exceeds "
            f"{max_dispatch_sla_hours}h policy"
        )

    if auth.tracking_sla_hours is None:
        failures.append("tracking SLA is undefined")

    return failures
