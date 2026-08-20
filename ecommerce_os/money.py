"""Money helpers.

Every monetary value in this package is a :class:`decimal.Decimal`. Floats are
banned: a 0.1% rounding drift on fee estimates is enough to flip a marginal SKU
from "list" to "don't list", and the whole point of the economics engine is that
predicted contribution can be reconciled against accounting reality.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

Numeric = Union[Decimal, int, str]

CENT = Decimal("0.01")
ZERO = Decimal("0")


def money(value: Numeric) -> Decimal:
    """Coerce to Decimal without ever routing through binary floating point.

    Floats are rejected rather than silently converted, because ``Decimal(0.1)``
    is ``0.1000000000000000055511151231257827``.
    """
    if isinstance(value, float):
        raise TypeError(
            "float is not accepted for monetary values; pass a str or Decimal "
            f"(got {value!r})"
        )
    return Decimal(value)


def quantize(value: Decimal) -> Decimal:
    """Round to two decimal places, half-up, the way an invoice does."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def rate(value: Numeric) -> Decimal:
    """Coerce a rate/probability and assert it is a sane proportion."""
    dec = money(value)
    if not (ZERO <= dec <= Decimal("1")):
        raise ValueError(f"rate must be within [0, 1], got {dec}")
    return dec


def ex_vat(gross: Decimal, vat_rate: Decimal) -> Decimal:
    """Strip VAT out of a tax-inclusive amount."""
    return gross / (Decimal("1") + vat_rate)
