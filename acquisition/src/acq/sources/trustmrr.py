"""D2 — TrustMRR: processor-verified MRR (Stripe, RevenueCat, LemonSqueezy,
Polar and others). No official API; Apify actors read it without login.

Used two ways, per the brief:

  1. As a **source** — products listed there with a verified figure.
  2. As a **cross-check** — joined against marketplace candidates on domain or
     product name. A match that agrees is the only thing in this pipeline that
     turns UNVERIFIED off. A match that *disagrees* is worth more than no match
     at all: it means the listing's own numbers are contradicted by the
     processor, which is a reason to stop, not a reason to negotiate.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from ..models import Candidate, Listing
from .base import Source, SourceError

APIFY_RUN = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

# How far a verified figure may sit from the listing's own before it counts as
# a disagreement rather than rounding or a month's drift.
AGREEMENT_TOLERANCE = 0.15

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Dropped from the end of a hostname to reach the registrable label:
# "getinvoicehq.io" -> "getinvoicehq", "shop.foo.co.uk" -> "foo".
TLDS = {
    "com", "net", "org", "io", "ai", "app", "co", "dev", "sh", "xyz", "me",
    "us", "uk", "eu", "de", "fr", "nl", "so", "to", "gg", "fyi", "live", "pro",
    "tech", "site", "online", "store", "studio", "design", "page", "link",
    "cloud", "tools", "software", "digital", "agency", "biz", "info",
}

# Vanity prefixes teams put on a domain but never in the product name.
# Stripped only when a substantial stem remains, so "getty" survives intact.
VANITY_PREFIXES = ("get", "try", "use", "join", "my", "the", "go", "with", "app")
MIN_STEM = 4

# A marketplace listing's URL is the *marketplace's* domain, not the product's.
# Folding flippa.com/11500001 to "flippa" would join every Flippa candidate to
# each other and to nothing useful, so these hosts never produce a join key.
MARKETPLACE_HOSTS = {
    "flippa", "acquire", "microns", "trustmrr", "empireflippers", "sideprojectors",
    "tinyacquisitions", "motioninvest", "investorsclub", "latonas", "bizbuysell",
}


def normalise_name(value: str) -> str:
    """Fold a product name or domain to a join key.

    'GetInvoiceHQ.io', 'https://www.getinvoicehq.io/pricing' and 'Invoice HQ'
    all have to land on the same key, or the cross-check silently never matches
    and every candidate stays UNVERIFIED — which looks exactly like TrustMRR
    having no data on it. A join that quietly fails is worse than no join.
    """
    text = (value or "").strip().lower()
    if not text:
        return ""

    looks_like_host = "://" in text or text.startswith("www.") or (
        "." in text and " " not in text.split("/")[0]
    )
    if looks_like_host:
        host = urlparse(text if "://" in text else f"//{text}", scheme="https").netloc
        host = (host or text).split("/")[0].split(":")[0]
        parts = [p for p in host.split(".") if p and p != "www"]
        while len(parts) > 1 and parts[-1] in TLDS:
            parts.pop()
        text = parts[-1] if parts else host

    stem = "".join(p for p in _NON_ALNUM.split(text) if p)
    for prefix in VANITY_PREFIXES:
        if stem.startswith(prefix) and len(stem) - len(prefix) >= MIN_STEM:
            return stem[len(prefix):]
    return stem


@dataclass
class TrustMrrRecord:
    name: str
    mrr: float | None = None
    growth_rate: float | None = None
    asking_price: float | None = None
    multiple: float | None = None
    category: str = ""
    status: str = ""
    url: str = ""
    currency: str = "USD"

    def key(self) -> str:
        keys = join_keys(self.url, self.name)
        return keys[0] if keys else ""


class TrustMrrSource(Source):
    name = "trustmrr"

    def __init__(self, config, session=None, actor: str = "", token: str | None = None) -> None:
        super().__init__(config, session)
        self.actor = actor or os.environ.get("TRUSTMRR_APIFY_ACTOR", "")
        self.token = token or os.environ.get("APIFY_TOKEN", "")

    # -------------------------------------------------------------- as source
    def records(self, limit: int | None = None) -> list[TrustMrrRecord]:
        if not self.actor or not self.token:
            raise SourceError(
                "trustmrr: TRUSTMRR_APIFY_ACTOR and APIFY_TOKEN must both be set")
        payload = self.get_json(APIFY_RUN.format(actor=self.actor),
                                {"token": self.token, "limit": limit or 1000})
        if not isinstance(payload, list):
            raise SourceError("trustmrr: expected a dataset item list")
        return [self.to_record(item) for item in payload]

    def fetch(self, limit: int | None = None) -> list[Listing]:
        out = []
        for r in self.records(limit):
            out.append(Listing(
                source=self.name,
                source_id=r.key() or r.name,
                url=r.url,
                name=r.name,
                category=(r.category or "").lower(),
                revenue_model="subscription",
                currency=r.currency,
                asking_price=r.asking_price,
                mrr=r.mrr,
                stated_multiple=r.multiple,
                has_verified_revenue=True,      # the whole point of the source
                raw=r.__dict__,
            ))
        print(f"{self.name}: {len(out)} processor-verified records")
        return out

    @classmethod
    def to_record(cls, raw: dict) -> TrustMrrRecord:
        return TrustMrrRecord(
            name=raw.get("name", "") or "",
            mrr=cls._num(raw.get("mrr")),
            growth_rate=cls._num(raw.get("growth_rate")),
            asking_price=cls._num(raw.get("asking_price")),
            multiple=cls._num(raw.get("multiple")),
            category=raw.get("category", "") or "",
            status=raw.get("status", "") or "",
            url=raw.get("url", "") or "",
            currency=raw.get("currency", "USD") or "USD",
        )


def join_keys(url: str, name: str) -> list[str]:
    """Keys to try, most specific first: the product's own domain, then its name.

    A marketplace URL contributes nothing — the product domain is not in it.
    """
    keys: list[str] = []
    domain_key = normalise_name(url)
    if domain_key and domain_key not in MARKETPLACE_HOSTS:
        keys.append(domain_key)
    name_key = normalise_name(name)
    if name_key and name_key not in keys:
        keys.append(name_key)
    return keys


def build_index(records: list[TrustMrrRecord]) -> dict[str, TrustMrrRecord]:
    index: dict[str, TrustMrrRecord] = {}
    for r in records:
        for key in join_keys(r.url, r.name):
            index.setdefault(key, r)
    return index


def cross_check(candidates: list[Candidate], records: list[TrustMrrRecord],
                fx=None, tolerance: float = AGREEMENT_TOLERANCE) -> int:
    """Join candidates to verified records on domain or product name.

    Sets `trustmrr_match` to one of: "" (not checked), "none", "agrees",
    "disagrees" — and records the verified MRR in GBP alongside. Returns the
    number of candidates matched.
    """
    index = build_index(records)
    matched = 0
    for c in candidates:
        record = next((index[k] for k in join_keys(c.url, c.name) if k in index), None)
        if record is None:
            c.trustmrr_match = "none"
            continue

        matched += 1
        verified = record.mrr
        if verified is not None and fx is not None:
            verified = fx.convert(verified, record.currency, "GBP")
        c.trustmrr_mrr = verified

        if verified is None or c.mrr is None:
            c.trustmrr_match = "none"
        elif verified <= 0:
            c.trustmrr_match = "disagrees"
        else:
            c.trustmrr_match = ("agrees"
                                if abs(c.mrr - verified) / verified <= tolerance
                                else "disagrees")
    return matched
