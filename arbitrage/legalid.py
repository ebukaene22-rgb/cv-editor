#!/usr/bin/env python3
"""
Identity confirmation from business seller legal information.

`storelink.py` route one -- the brand's own site linking to its eBay store --
measured nearly empty: gymshark, rokform, fromourplace and itinstock link no
eBay store across 4-7 pages each, and itinstock runs 18,839 listings. Route
two is this one.

eBay collects business details from business sellers and surfaces them through
its business-details/profile infrastructure; Browse's **detailed item
resource** (`getItem`) exposes them as `seller.sellerLegalInfo`, carrying
fields such as `name`, `registrationNumber`, `vatDetails`, legal address, and
contact details. Ordinary `item_summary/search` results do not carry it.

Deliberately NOT claimed here: that UK/EU law requires every field to be
embedded visibly in each listing body. The defensible statement is the one
above -- eBay collects the details and the detailed item resource exposes
them.

## Evidence hierarchy

    registration  company registration number matches the source's own
                  -> CONFIRMED. The strongest automated attribution available.
    vat           VAT number matches after normalisation
                  -> CONFIRMED.
    name_address  legal business name AND address both match
                  -> strong, but below the two above: names and addresses
                     need fuzzy normalisation and fuzzy matching invites the
                     false positives presence detection cannot afford.
    name          legal business name alone -> SUPPORTING, not conclusive.
    (none)        handle morphology and branded titles -> candidate only.

## Absence is not refutation

`sellerLegalInfo` fields are conditional. A seller lacking one, or an
individual (non-business) account, yields `legal_info_unavailable` -- an
evidence state, never evidence the route does not work or that the seller is
not the source. Sample SEVERAL listings before concluding a field is missing:
one item not carrying a field is not the field being unavailable.

That distinction is the fifth instance of this project's recurring failure
shape -- a failure rendering as a confident negative -- caught before it was
built rather than after.
"""
import re

# --- normalisation --------------------------------------------------------

def norm_vat(v):
    """
    'GB 483 890 250' / 'gb483890250' -> 'GB483890250'.

    Country prefix is preserved when present but not invented: a bare
    '483890250' normalises to '483890250' and still matches a prefixed value
    via `vat_match`, because sources routinely publish it either way.
    """
    if not v:
        return ""
    s = re.sub(r"[^A-Za-z0-9]", "", str(v)).upper()
    return s


def vat_match(a, b):
    """True when two VAT numbers agree, with or without a country prefix."""
    a, b = norm_vat(a), norm_vat(b)
    if not a or not b:
        return False
    if a == b:
        return True
    strip = lambda s: re.sub(r"^[A-Z]{2}", "", s)
    return bool(strip(a)) and strip(a) == strip(b)


def norm_company(n):
    """
    UK company numbers are 8 characters and zero-padded: '3708416' and
    '03708416' are the same company. Pad plain-numeric values to 8.
    """
    if not n:
        return ""
    s = re.sub(r"[^A-Za-z0-9]", "", str(n)).upper()
    if s.isdigit():
        return s.zfill(8)
    # prefixed forms (SC/NI/OC...) keep the prefix, pad the numeric tail
    m = re.match(r"^([A-Z]{2})(\d+)$", s)
    if m:
        return m.group(1) + m.group(2).zfill(6)
    return s


def company_match(a, b):
    a, b = norm_company(a), norm_company(b)
    return bool(a) and a == b


_SUFFIX = re.compile(
    r"\b(ltd|limited|llp|llc|plc|inc|incorporated|co|company|"
    r"holdings?|group|uk|gb|international|intl)\b", re.I)


def norm_name(n):
    """Lowercase alphanumeric core with corporate suffixes removed."""
    if not n:
        return ""
    s = _SUFFIX.sub(" ", str(n).lower())
    return re.sub(r"[^a-z0-9]", "", s)


def name_match(a, b):
    a, b = norm_name(a), norm_name(b)
    if not a or not b or min(len(a), len(b)) < 4:
        return False
    return a == b or a in b or b in a


def norm_postcode(s):
    if not s:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", str(s)).upper()


# --- evidence -------------------------------------------------------------

TIERS = ("registration", "vat", "name_address", "name")
CONFIRMING = ("registration", "vat")


def extract(item):
    """
    Pull the legal block out of a Browse getItem payload.

    -> dict with name / registrationNumber / vat / postcode / account_type,
    plus `available` False when the seller carries no legal info at all.
    """
    seller = (item or {}).get("seller") or {}
    legal = seller.get("sellerLegalInfo") or {}
    addr = legal.get("legalAddress") or {}
    vat = ""
    details = legal.get("vatDetails") or []
    if isinstance(details, dict):
        details = [details]
    for d in details:
        vat = vat or (d or {}).get("vatId") or ""
    return {
        "available": bool(legal),
        "name": legal.get("name") or legal.get("legalContactFirstName") or "",
        "registrationNumber": legal.get("registrationNumber") or "",
        "vat": vat,
        "postcode": addr.get("postalCode") or "",
        "account_type": seller.get("sellerAccountType") or "",
        "username": seller.get("username") or "",
    }


def evaluate(observed, expected):
    """
    Compare a seller's legal block against what the source publishes.

    observed: output of `extract`.
    expected: {'registrationNumber','vat','name','postcode'} from the source's
              own site.
    -> (tier, reason). tier is one of TIERS or None.

    A None tier with `observed['available']` False means the evidence was not
    published, NOT that the seller is a different entity. Callers must render
    that as `legal_info_unavailable`, never as a rejection.
    """
    if not observed or not observed.get("available"):
        return None, "legal_info_unavailable"

    if company_match(observed.get("registrationNumber"),
                     expected.get("registrationNumber")):
        return "registration", (
            f"company registration {observed['registrationNumber']} matches "
            f"the source's published number")

    if vat_match(observed.get("vat"), expected.get("vat")):
        return "vat", (f"VAT {observed['vat']} matches the source's "
                       f"published number")

    nm = name_match(observed.get("name"), expected.get("name"))
    if nm and norm_postcode(observed.get("postcode")) and \
            norm_postcode(observed.get("postcode")) == \
            norm_postcode(expected.get("postcode")):
        return "name_address", (f"legal name '{observed['name']}' and postcode "
                                f"both match")
    if nm:
        return "name", (f"legal name '{observed['name']}' matches, address "
                        f"unconfirmed -- supporting evidence only")
    return None, ("legal info published but nothing matches the source -- "
                  "likely a different entity")


def best_of(observations, expected):
    """
    Evaluate SEVERAL listings and keep the strongest evidence found.

    Fields are conditional, so one item lacking a value is not the value being
    unavailable. Only when EVERY sampled item carries no legal block at all is
    the result `legal_info_unavailable`.
    """
    best_tier, best_why, any_available = None, "", False
    for obs in observations or []:
        if obs.get("available"):
            any_available = True
        tier, why = evaluate(obs, expected)
        if tier and (best_tier is None
                     or TIERS.index(tier) < TIERS.index(best_tier)):
            best_tier, best_why = tier, why
    if best_tier:
        return best_tier, best_why
    if not any_available:
        return None, (f"legal_info_unavailable across "
                      f"{len(observations or [])} sampled listings")
    return None, "legal info published but nothing matched the source"


def is_confirming(tier):
    """Only registration/VAT may promote a row to confirmed_active."""
    return tier in CONFIRMING
