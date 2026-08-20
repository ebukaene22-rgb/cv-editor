"""Entity resolution between supplier catalogue rows and canonical products.

Trained and tuned for **precision first**. A false positive does not merely add
noise — it invents an arbitrage opportunity that does not exist, and the loss is
realised at the moment a customer orders the wrong pack size.

The weighting here is the Python twin of the candidate-generation SQL in
``schema/004_matching.sql``, so an offline evaluation on labelled pairs predicts
what the database will actually do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Mapping

from ecommerce_os.identity import (
    normalize_brand,
    normalize_gtin,
    normalize_mpn,
    normalize_title,
    parse_pack_count,
)

# Component weights. They sum to 1.00 and deliberately give pack agreement more
# weight than brand: brand is usually right and rarely discriminating, pack size
# is the field that silently destroys margin.
W_TITLE = Decimal("0.45")
W_BRAND = Decimal("0.25")
W_PACK = Decimal("0.30")

SCORE_GTIN = Decimal("1.00")
SCORE_BRAND_MPN = Decimal("0.96")

AUTO_MATCH_THRESHOLD = Decimal("0.97")
REVIEW_THRESHOLD = Decimal("0.85")

# Attributes that must not disagree, whatever the identifiers claim. A UK and a
# UAE variant of "the same" product are not interchangeable stock.
CRITICAL_ATTRIBUTES = ("voltage", "plug_type", "size", "colour_family", "region")


class MatchClass(Enum):
    """What the system is allowed to do with a candidate pair."""

    DETERMINISTIC = "deterministic"  # verified GTIN + critical attributes agree
    VERY_HIGH = "very_high"  # brand + exact MPN + pack agreement
    HIGH = "high"  # model score >= 0.97
    MEDIUM = "medium"  # 0.85 - 0.97, human review
    LOW = "low"  # < 0.85, reject
    CONFLICT = "conflict"  # identifiers agree but attributes contradict

    @property
    def auto_matchable(self) -> bool:
        return self in (MatchClass.DETERMINISTIC, MatchClass.VERY_HIGH, MatchClass.HIGH)


@dataclass(frozen=True)
class ProductRecord:
    """A normalised view of one product, from either side of the match."""

    title: str | None = None
    brand: str | None = None
    mpn: str | None = None
    gtin: str | None = None
    pack_count: int | None = None
    condition: str = "new"
    category: str | None = None
    attributes: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_raw(
        cls,
        title: str | None = None,
        brand: str | None = None,
        mpn: str | None = None,
        gtin: str | int | None = None,
        pack_count: int | None = None,
        condition: str = "new",
        category: str | None = None,
        attributes: Mapping[str, str] | None = None,
    ) -> "ProductRecord":
        """Normalise a raw feed row.

        When ``pack_count`` is not supplied explicitly it is inferred from the
        title — but an explicit feed value always wins, because a supplier that
        states pack size in a structured field is more trustworthy than a regex.
        """
        return cls(
            title=normalize_title(title),
            brand=normalize_brand(brand),
            mpn=normalize_mpn(mpn),
            gtin=normalize_gtin(gtin),
            pack_count=pack_count if pack_count is not None else parse_pack_count(title),
            condition=(condition or "new").strip().lower(),
            category=(category or "").strip().lower() or None,
            attributes={
                key.strip().lower(): str(value).strip().lower()
                for key, value in (attributes or {}).items()
                if value is not None and str(value).strip()
            },
        )


@dataclass(frozen=True)
class MatchResult:
    score: Decimal
    match_class: MatchClass
    identifier_score: Decimal
    title_score: Decimal
    brand_score: Decimal
    pack_score: Decimal
    conflicts: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def auto_matchable(self) -> bool:
        return self.match_class.auto_matchable


def trigram_similarity(left: str | None, right: str | None) -> Decimal:
    """Jaccard similarity over trigram sets, mirroring PostgreSQL ``pg_trgm``.

    ``pg_trgm`` pads each word with two leading spaces and one trailing space
    before extracting 3-grams, so the same pair of strings scores identically
    here and in the candidate-generation query.
    """
    left_grams = _trigrams(left)
    right_grams = _trigrams(right)
    if not left_grams or not right_grams:
        return Decimal("0")
    intersection = len(left_grams & right_grams)
    union = len(left_grams | right_grams)
    return (Decimal(intersection) / Decimal(union)).quantize(Decimal("0.0001"))


def _trigrams(text: str | None) -> set[str]:
    if not text:
        return set()
    grams: set[str] = set()
    for word in text.split():
        padded = f"  {word} "
        for index in range(len(padded) - 2):
            grams.add(padded[index : index + 3])
    return grams


def _find_conflicts(source: ProductRecord, canonical: ProductRecord) -> tuple[str, ...]:
    """Attributes where both sides state a value and the values disagree.

    Silence is not disagreement: a missing attribute on either side is unknown,
    not a conflict. Only asserted contradictions quarantine a pair.
    """
    conflicts: list[str] = []

    if (
        source.pack_count is not None
        and canonical.pack_count is not None
        and source.pack_count != canonical.pack_count
    ):
        conflicts.append("pack_count")

    if source.condition != canonical.condition:
        conflicts.append("condition")

    if source.category and canonical.category and source.category != canonical.category:
        conflicts.append("category")

    for attribute in CRITICAL_ATTRIBUTES:
        left = source.attributes.get(attribute)
        right = canonical.attributes.get(attribute)
        if left and right and left != right:
            conflicts.append(attribute)

    return tuple(conflicts)


def classify_match(source: ProductRecord, canonical: ProductRecord) -> MatchResult:
    """Score and classify one candidate pair."""
    reasons: list[str] = []
    conflicts = _find_conflicts(source, canonical)

    gtin_agrees = bool(source.gtin and canonical.gtin and source.gtin == canonical.gtin)
    mpn_agrees = bool(
        source.mpn
        and canonical.mpn
        and source.mpn == canonical.mpn
        and source.brand
        and source.brand == canonical.brand
    )

    if gtin_agrees:
        identifier_score = SCORE_GTIN
        reasons.append("gtin agreement")
    elif mpn_agrees:
        identifier_score = SCORE_BRAND_MPN
        reasons.append("brand + mpn agreement")
    else:
        identifier_score = Decimal("0")

    title_score = trigram_similarity(source.title, canonical.title)
    brand_score = (
        Decimal("1") if source.brand and source.brand == canonical.brand else Decimal("0")
    )
    # NULL pack on either side scores zero, exactly as the SQL does. The effect
    # is intentional: text similarity alone tops out at 0.70 and can never reach
    # the 0.97 auto-match bar without corroborating pack or identifier evidence.
    pack_agrees = (
        source.pack_count is not None
        and canonical.pack_count is not None
        and source.pack_count == canonical.pack_count
    )
    pack_score = Decimal("1") if pack_agrees else Decimal("0")

    weighted = W_TITLE * title_score + W_BRAND * brand_score + W_PACK * pack_score
    score = max(identifier_score, weighted).quantize(Decimal("0.0001"))

    # An identifier that agrees while a critical attribute contradicts is the
    # most dangerous signal in the system: it looks deterministic and is wrong.
    # Quarantine for a human rather than resolving it either way.
    if identifier_score > 0 and conflicts:
        reasons.append(f"identifier agrees but {', '.join(conflicts)} conflict")
        return MatchResult(
            score=score,
            match_class=MatchClass.CONFLICT,
            identifier_score=identifier_score,
            title_score=title_score,
            brand_score=brand_score,
            pack_score=pack_score,
            conflicts=conflicts,
            reasons=tuple(reasons),
        )

    if gtin_agrees and not conflicts:
        match_class = MatchClass.DETERMINISTIC
    elif mpn_agrees and pack_agrees and not conflicts:
        match_class = MatchClass.VERY_HIGH
    elif conflicts:
        # No identifier corroboration and an outright contradiction: reject
        # regardless of how similar the marketing copy happens to be.
        reasons.append(f"attribute conflict: {', '.join(conflicts)}")
        match_class = MatchClass.LOW
    elif score >= AUTO_MATCH_THRESHOLD:
        match_class = MatchClass.HIGH
    elif score >= REVIEW_THRESHOLD:
        match_class = MatchClass.MEDIUM
        reasons.append("below auto-match threshold; queued for human review")
    else:
        match_class = MatchClass.LOW
        reasons.append("insufficient evidence")

    return MatchResult(
        score=score,
        match_class=match_class,
        identifier_score=identifier_score,
        title_score=title_score,
        brand_score=brand_score,
        pack_score=pack_score,
        conflicts=conflicts,
        reasons=tuple(reasons),
    )
