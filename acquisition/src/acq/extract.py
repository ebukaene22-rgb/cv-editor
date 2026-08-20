"""Pull the figures the endpoint doesn't return out of the listing prose.

Flippa's confirmed field list carries price, revenue, profit, traffic and dates.
It does not carry a customer count, a churn rate, a stated LTV, or an entry
price — which are precisely the inputs `LTV_IMPLAUSIBLE` and
`CUSTOMER_COUNT_INFLATED` need. On a live pull those two rules would never fire,
and a rule that cannot run looks exactly like a rule that ran and found nothing.

Those numbers are in the `summary` field, written by the seller in prose. This
module reads them out deterministically. It is conservative on purpose: a
missed figure leaves a rule unevaluated, which the coverage report will say out
loud, whereas a wrong figure fires a flag against a number the seller never
gave. Ambiguity therefore returns None.

Extracted values are marked on the candidate as prose-derived, so a flag raised
from one can be read with that in mind.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# "1,000 customers", "62 paying stores", "44 agency accounts", "90 paying users".
# Up to two intervening words ("agency accounts", "small business customers"),
# but no punctuation, so a match cannot run across a sentence boundary.
_CUSTOMERS = re.compile(
    r"(?<![$£€])(?<![$£€]\s)"          # a money amount is a price, not a count
    r"\b([\d,]+(?:\.\d+)?\s*[kK]?)\s+"
    r"(?:[a-zA-Z][a-zA-Z-]*\s+){0,2}"
    r"(customers?|subscribers?|users?|accounts?|stores?|venues?|agencies|teams?|"
    r"members?|clients?|sites?|shops?|businesses)\b",
    re.IGNORECASE)

# Words that mean the number is traffic, not a stated customer base. Note that
# "users" is deliberately NOT here: a headline user count presented as a customer
# base is the exact conflation CUSTOMER_COUNT_INFLATED exists to catch, so it has
# to be captured, not filtered out. Traffic already arrives as uniques_per_month.
_NON_PAYING = ("visitor", "signup", "sign-up", "registered", "free", "trial",
               "unique", "install", "download", "follower", "waitlist",
               "page view", "pageview", "impression", "email list",
               "per customer", "per user", "per account", "ltv", "lifetime value")

# "8% monthly churn", "churn is 8%", "monthly churn of 8%"
_CHURN = re.compile(
    r"(?:(?:monthly\s+)?churn(?:\s+rate)?(?:\s+is|\s+of|\s*[:=])?\s*([\d.]+)\s*%)"
    r"|(?:([\d.]+)\s*%\s*(?:monthly\s+)?churn)",
    re.IGNORECASE)

# "$7,200 LTV", "LTV is $7,200", "lifetime value of $7,200"
_LTV = re.compile(
    r"(?:(?:ltv|lifetime\s+value)(?:\s+is|\s+of|\s*[:=])?\s*[$£€]?\s*([\d,]+(?:\.\d+)?)\s*[kK]?)"
    r"|(?:[$£€]\s*([\d,]+(?:\.\d+)?)\s*[kK]?\s*(?:ltv|lifetime\s+value))",
    re.IGNORECASE)

# Words near a price that mean it is an outgoing, not a plan price.
_COST_WORDS = ("cost", "spend", "hosting", "server", "api", "bill", "expense",
               "infra", "fee", "overhead", "profit", "revenue", "mrr", "arr")

# "plans from $5/mo", "starts at $9 per month", "$19/month plans"
_MIN_PRICE_EXPLICIT = re.compile(
    r"(?:from|starting\s+at|starts\s+at|plans\s+from|as\s+low\s+as)\s*"
    r"[$£€]\s*([\d,]+(?:\.\d+)?)\s*(?:/|\s*per\s*)?\s*(?:mo|month)?",
    re.IGNORECASE)
_MIN_PRICE_BARE = re.compile(
    r"[$£€]\s*([\d,]+(?:\.\d+)?)\s*/\s*(?:mo|month)\b",
    re.IGNORECASE)

# "costs are low, around $90/mo for the SERP API", "hosting runs $40/mo",
# "under $40/mo in API spend", "$200 a month in servers". Accepted only when a
# cost word sits nearby — the same shape with no cost word is a plan price.
_MONTHLY_COST = re.compile(
    r"[$£€]\s*([\d,]+(?:\.\d+)?)\s*(?:/\s*(?:mo|month)\b|\s*(?:per|a)\s+month\b)",
    re.IGNORECASE)

# A paying count stated separately from a headline count: "33 payers",
# "only 33 of them pay", "33 paid subscribers".
_PAYERS = re.compile(
    r"\b([\d,]+)\s+(?:of\s+(?:them|which|these)\s+)?"
    r"(?:pay\b|payers?\b|paid\s+(?:customers?|subscribers?|users?|accounts?)\b|"
    r"paying\s+(?:customers?|subscribers?|users?|accounts?)\b)",
    re.IGNORECASE)


@dataclass
class Extracted:
    active_customers: float | None = None
    paying_customers: float | None = None
    monthly_churn: float | None = None
    stated_ltv: float | None = None
    min_customer_price: float | None = None
    stated_monthly_costs: float | None = None
    sources: dict[str, str] = field(default_factory=dict)   # field -> matched phrase

    def any(self) -> bool:
        return bool(self.sources)


def _to_number(text: str) -> float | None:
    text = (text or "").strip().replace(",", "")
    multiplier = 1.0
    if text and text[-1] in "kK":
        multiplier, text = 1_000.0, text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _context(haystack: str, match: re.Match, width: int = 40) -> str:
    start = max(0, match.start() - width)
    return haystack[start:match.end() + width].strip()


def _first_group(match: re.Match) -> str | None:
    return next((g for g in match.groups() if g), None)


def extract(text: str) -> Extracted:
    """Read customer count, churn, stated LTV and entry price out of prose."""
    out = Extracted()
    if not (text or "").strip():
        return out

    # --- customer count -----------------------------------------------------
    # Take the largest plausible count that is not qualified by a
    # non-paying word. Sellers lead with their biggest number, and that is the
    # one CUSTOMER_COUNT_INFLATED is meant to test.
    best: tuple[float, str] | None = None
    for m in _CUSTOMERS.finditer(text):
        window = text[max(0, m.start() - 30):m.end() + 10].lower()
        if any(word in window for word in _NON_PAYING):
            continue
        value = _to_number(m.group(1))
        if value is None or value <= 0:
            continue
        if best is None or value > best[0]:
            best = (value, _context(text, m))
    if best:
        out.active_customers, out.sources["active_customers"] = best

    m = _PAYERS.search(text)
    if m:
        value = _to_number(m.group(1))
        if value is not None and value > 0:
            out.paying_customers, out.sources["paying_customers"] = value, _context(text, m)

    # --- churn --------------------------------------------------------------
    m = _CHURN.search(text)
    if m:
        value = _to_number(_first_group(m) or "")
        # A churn rate above 100% is a parse error, not a business.
        if value is not None and 0 < value <= 100:
            out.monthly_churn, out.sources["monthly_churn"] = value / 100.0, _context(text, m)

    # --- stated LTV ---------------------------------------------------------
    m = _LTV.search(text)
    if m:
        raw = _first_group(m) or ""
        value = _to_number(raw + ("k" if re.search(rf"{re.escape(raw)}\s*[kK]", m.group(0)) else ""))
        if value is not None and value > 0:
            out.stated_ltv, out.sources["stated_ltv"] = value, _context(text, m)

    # --- stated monthly cost ------------------------------------------------
    # Deliberately kept apart from `ttm_costs`. A prose figure is good enough to
    # make a flag's evidence accurate and to sanity-check a margin; it is not
    # good enough to drive a hard reject on payback.
    for m in _MONTHLY_COST.finditer(text):
        window = text[max(0, m.start() - 45):m.end() + 30].lower()
        if not any(word in window for word in _COST_WORDS):
            continue
        if any(word in window for word in ("profit", "revenue", "mrr", "arr")):
            continue        # "$600/mo profit" is not a cost
        value = _to_number(m.group(1))
        if value is not None and value > 0:
            out.stated_monthly_costs, out.sources["stated_monthly_costs"] = (
                value, _context(text, m))
            break

    # --- entry price --------------------------------------------------------
    # "plans from $5/mo" names itself as a plan price and needs no guard.
    m = _MIN_PRICE_EXPLICIT.search(text)
    if m and (value := _to_number(m.group(1))) and value > 0:
        out.min_customer_price, out.sources["min_customer_price"] = value, _context(text, m)
    else:
        # A bare "$90/mo" could be anything. Only take it when nothing nearby
        # says it is an outgoing.
        for m in _MIN_PRICE_BARE.finditer(text):
            window = text[max(0, m.start() - 40):m.end() + 20].lower()
            if any(word in window for word in _COST_WORDS):
                continue    # "$90/mo for the SERP API" is a cost, not a plan
            value = _to_number(m.group(1))
            if value is not None and value > 0:
                out.min_customer_price, out.sources["min_customer_price"] = (
                    value, _context(text, m))
                break

    return out


def apply_to(listing, text: str | None = None) -> Extracted:
    """Fill only the fields the source left empty. An endpoint figure always
    beats a prose figure — prose is the fallback, never the override."""
    found = extract(text if text is not None else listing.listing_text)
    for name in ("active_customers", "paying_customers", "monthly_churn",
                 "stated_ltv", "min_customer_price", "stated_monthly_costs"):
        value = getattr(found, name)
        if value is not None and getattr(listing, name, None) is None:
            setattr(listing, name, value)
    if found.any():
        listing.raw.setdefault("prose_extracted", found.sources)
    return found
