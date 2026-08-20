"""Marketplace fee rules.

Fees are category-, country-, price-band- and date-dependent, and marketplaces
restate them regularly. They also *stack*: a single eBay sale can attract a
final value fee, a regulatory operating fee and an international fee at once.

Hard-coding "about 15%" into an arbitrage model is the fastest way to build a
portfolio of confidently unprofitable SKUs. This module therefore has no
default: an unpriceable combination raises rather than guesses, and the caller
is expected to either load the rule or refuse to list the SKU.

Where a marketplace exposes a fee-estimate API, prefer it and record the
estimate as an observation — those estimates are not guaranteed to equal the
fee actually charged, so the reconciliation loop still has to compare predicted
against settled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ecommerce_os.money import ZERO, money, quantize

ANY = "*"


class NoFeeRuleError(LookupError):
    """Raised when no fee rule covers a combination. Never silently defaulted."""


class AmbiguousFeeRuleError(LookupError):
    """Raised when two equally specific rules both apply — a data error."""


@dataclass(frozen=True)
class FeeRule:
    """One fee line for one slice of the catalogue over one date range."""

    marketplace: str
    country: str
    category: str
    fee_kind: str
    variable_rate: Decimal
    fixed_fee: Decimal
    effective_from: date
    effective_to: date | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    schedule_version: str = "unversioned"
    # Where this rate was read from, mirroring marketplace_fee_rule.source_ref.
    source_ref: str | None = None

    def covers(self, *, price: Decimal, on_date: date) -> bool:
        if on_date < self.effective_from:
            return False
        if self.effective_to is not None and on_date > self.effective_to:
            return False
        if self.price_min is not None and price < self.price_min:
            return False
        # Bands are half-open at the top so adjacent bands never both match.
        if self.price_max is not None and price >= self.price_max:
            return False
        return True

    @property
    def specificity(self) -> tuple[int, int, int]:
        """Higher is more specific: exact category, exact country, priced band."""
        return (
            0 if self.category == ANY else 1,
            0 if self.country == ANY else 1,
            1 if (self.price_min is not None or self.price_max is not None) else 0,
        )

    def compute(self, price: Decimal) -> Decimal:
        return quantize(self.variable_rate * price + self.fixed_fee)


@dataclass
class FeeBook:
    """A versioned collection of fee rules."""

    rules: list[FeeRule]

    def __init__(self, rules: list[FeeRule] | None = None) -> None:
        self.rules = list(rules or [])

    def add(self, rule: FeeRule) -> None:
        self.rules.append(rule)

    def resolve(
        self,
        *,
        fee_kind: str,
        marketplace: str,
        country: str,
        category: str,
        price: Decimal,
        on_date: date,
    ) -> FeeRule:
        """Find the single most specific applicable rule, or raise."""
        price = money(price)
        applicable = [
            rule
            for rule in self.rules
            if rule.fee_kind == fee_kind
            and rule.marketplace == marketplace
            and rule.country in (country, ANY)
            and rule.category in (category, ANY)
            and rule.covers(price=price, on_date=on_date)
        ]
        if not applicable:
            raise NoFeeRuleError(
                f"no {fee_kind} fee rule for {marketplace}/{country}/{category} "
                f"at {price} on {on_date.isoformat()}"
            )

        applicable.sort(key=lambda rule: rule.specificity, reverse=True)
        best = applicable[0]
        if len(applicable) > 1 and applicable[1].specificity == best.specificity:
            raise AmbiguousFeeRuleError(
                f"{len(applicable)} equally specific {fee_kind} rules for "
                f"{marketplace}/{country}/{category} at {price}"
            )
        return best

    def total_fees(
        self,
        *,
        marketplace: str,
        country: str,
        category: str,
        price: Decimal,
        on_date: date,
        fee_kinds: tuple[str, ...],
    ) -> tuple[Decimal, dict[str, Decimal]]:
        """Sum every required fee kind, itemised.

        Every kind in ``fee_kinds`` must resolve. If a marketplace charges a
        regulatory operating fee in this country, omitting it from the book is
        not the same as it being zero.
        """
        breakdown: dict[str, Decimal] = {}
        total = ZERO
        for kind in fee_kinds:
            rule = self.resolve(
                fee_kind=kind,
                marketplace=marketplace,
                country=country,
                category=category,
                price=money(price),
                on_date=on_date,
            )
            amount = rule.compute(money(price))
            breakdown[kind] = amount
            total += amount
        return quantize(total), breakdown
