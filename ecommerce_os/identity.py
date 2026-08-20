"""Product identity normalisation.

The identity hierarchy the matcher relies on:

    GTIN > (brand + MPN) > (brand + model + variant) > attributes > text > semantic

GTIN is the strongest *readily available* identifier, not an infallible one — a
single external identifier can map to several marketplace catalogue entries, so
identifier agreement still has to survive attribute validation downstream (see
:mod:`ecommerce_os.matching`).
"""

from __future__ import annotations

import re
import unicodedata

# Words that carry no discriminating power in a product title and only inflate
# trigram similarity between genuinely different products.
_TITLE_NOISE = {
    "brand",
    "genuine",
    "new",
    "official",
    "original",
    "uk",
    "with",
    "for",
    "the",
    "and",
}

_PACK_MULTIPLIER = re.compile(
    r"(?<![\w.])(\d{1,3})\s*[x×]\s*(\d{1,3})\s*(?:-|\s)?(?:pack|pk|pcs?|pieces?)\b",
    re.IGNORECASE,
)
_PACK_OF = re.compile(r"\bpack\s+of\s+(\d{1,4})\b", re.IGNORECASE)
_PACK_SUFFIX = re.compile(
    r"(?<![\w.])(\d{1,4})\s*(?:-|\s)?(?:pack|pk|pcs|pieces|count|ct)\b", re.IGNORECASE
)
_PACK_X_PREFIX = re.compile(r"(?<![\w.])[x×]\s*(\d{1,4})(?![\w.])", re.IGNORECASE)


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_gtin(raw: str | int | None) -> str | None:
    """Normalise any GTIN-8/12/13/14 to zero-padded GTIN-14 form.

    Returns ``None`` when the value is absent, not a plausible GTIN length, or
    fails the GS1 mod-10 check digit. A GTIN that fails its own check digit is
    worse than no GTIN — it is a typo that would otherwise be treated as
    deterministic proof of identity.
    """
    if raw is None:
        return None

    digits = re.sub(r"\D", "", str(raw))
    if len(digits) not in (8, 12, 13, 14):
        return None

    padded = digits.zfill(14)
    if not _check_digit_valid(padded):
        return None
    return padded


def _check_digit_valid(gtin14: str) -> bool:
    body, check = gtin14[:-1], int(gtin14[-1])
    # GS1 mod-10: weights alternate 3,1,3,1... reading right-to-left from the
    # digit adjacent to the check digit.
    total = 0
    for index, char in enumerate(reversed(body)):
        weight = 3 if index % 2 == 0 else 1
        total += int(char) * weight
    return (10 - total % 10) % 10 == check


def gtin_check_digit(body: str) -> int:
    """Compute the GS1 check digit for a GTIN body (i.e. without check digit)."""
    digits = re.sub(r"\D", "", body).zfill(13)
    total = 0
    for index, char in enumerate(reversed(digits)):
        weight = 3 if index % 2 == 0 else 1
        total += int(char) * weight
    return (10 - total % 10) % 10


def normalize_brand(raw: str | None) -> str | None:
    """Casefold, de-accent and strip corporate suffixes from a brand name."""
    if not raw:
        return None
    text = _strip_accents(str(raw)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    text = re.sub(
        r"\b(ltd|limited|inc|incorporated|gmbh|bv|sarl|plc|llc|co|corp|corporation)\b",
        " ",
        text,
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_mpn(raw: str | None) -> str | None:
    """Reduce an MPN to its comparable core: uppercase alphanumerics only.

    Manufacturer part numbers are written inconsistently across feeds
    (``ABC-123``, ``abc 123``, ``ABC123``) and the separators carry no meaning.
    """
    if not raw:
        return None
    text = re.sub(r"[^A-Za-z0-9]+", "", str(raw)).upper()
    # A one or two character "MPN" is almost always a feed artefact, not a part
    # number, and would collide across the entire catalogue.
    return text if len(text) >= 3 else None


def normalize_title(raw: str | None) -> str | None:
    """Normalise a title for trigram similarity."""
    if not raw:
        return None
    text = _strip_accents(str(raw)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [tok for tok in text.split() if tok and tok not in _TITLE_NOISE]
    return " ".join(tokens) or None


def parse_pack_count(raw: str | None) -> int | None:
    """Extract a pack quantity from a title.

    Pack-size identity is the single most expensive matching failure in retail
    arbitrage: a *3 pack* and a *6 pack* of the same product share almost every
    token, so text similarity celebrates the match and the P&L pays for it.

    Handles ``3 pack``, ``pack of 24``, ``3-pack``, ``x3`` and the compound
    ``2 x 3 pack`` (which is six units, not two and not three).
    """
    if not raw:
        return None
    text = str(raw)

    compound = _PACK_MULTIPLIER.search(text)
    if compound:
        return int(compound.group(1)) * int(compound.group(2))

    for pattern in (_PACK_OF, _PACK_SUFFIX, _PACK_X_PREFIX):
        found = pattern.search(text)
        if found:
            value = int(found.group(1))
            if value > 0:
                return value
    return None
