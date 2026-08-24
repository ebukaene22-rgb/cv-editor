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

# Positive evidence, strongest first. Only these participate in ranking.
TIERS = ("registration", "vat", "name_address", "name")
CONFIRMING = ("registration", "vat")

# Two NON-evidence outcomes. Both leave a row at candidate_active, and they
# mean opposite things -- so they are first-class values, never a shared
# None:
#
#   no_match               the seller publishes legal details and none match
#                          the source. Evidence AGAINST first-party ownership.
#   legal_info_unavailable no legal block on any sampled listing. Says
#                          nothing about ownership; says the experiment had
#                          no resolving power here.
#
# A candidate population dominated by no_match is a finding. One dominated by
# legal_info_unavailable is an instrument limitation wearing a finding's
# clothes. Reporting them as one number hides which of those you have.
NO_MATCH = "no_match"
UNAVAILABLE = "legal_info_unavailable"

# A third non-evidence outcome, and it must not be folded into UNAVAILABLE.
#
#   not_testable  there was no qualifying active listing to request identity
#                 evidence from. The test was never executable.
#
# UNAVAILABLE now means something precise: listings existed, were sampled,
# and carried no legal block. A dormant or not_detected row has no listing to
# sample at all. Putting those in the same bucket inflates the denominator
# with rows the test never ran on, and makes the identity method look useless
# when it was simply not exercised -- the same failure pattern as before, one
# level up.
NOT_TESTABLE = "not_testable"

NON_EVIDENCE = (NO_MATCH, UNAVAILABLE, NOT_TESTABLE)

# Tiers on which legal identity was actually OBSERVABLE. no_match belongs
# here: contradicting evidence is still evidence the mechanism worked.
OBSERVABLE = TIERS + (NO_MATCH,)


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
        return UNAVAILABLE, "no legal block published on this listing"

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
    return NO_MATCH, ("legal info published but nothing matches the source "
                      "-- evidence against first-party ownership")


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
        if tier in TIERS and (best_tier is None
                              or TIERS.index(tier) < TIERS.index(best_tier)):
            best_tier, best_why = tier, why
    if best_tier:
        return best_tier, best_why
    n = len(observations or [])
    if not any_available:
        return UNAVAILABLE, (f"no legal block on any of {n} sampled listings "
                             f"-- no resolving power here, NOT evidence "
                             f"against ownership")
    return NO_MATCH, (f"legal info published across {n} sampled listings, "
                      f"none matching the source")


def is_confirming(tier):
    """Only registration/VAT may promote a row to confirmed_active."""
    return tier in CONFIRMING


def resolving_power(tiers):
    """
    Summarise a population by what the evidence says AND by whether the
    identity test could run at all.

    Two denominators, deliberately kept apart:

      coverage  = attempted / population
                  how often the identity test was executable
      power     = observable / attempted
                  how often it resolved anything WHEN it ran

    Collapsing these into one "identity confirmation rate" lets population
    composition masquerade as method performance. A DTC arm of 32 dormant +
    18 not_detected + 4 sampled-but-bare + 2 confirmed is not "2/56 = 4%
    confirmation": the test ran on 6 rows and resolved 2 of them. The other
    50 rows are evidence for the INCIDENCE discriminator, and say nothing
    about legal-identity matching.

    -> counts, plus 'attempted', 'observable', 'population', 'coverage'
       and 'power' (None when the denominator is zero).
    """
    out = dict.fromkeys(
        ("confirmed", "corroborated", "supporting", "no_match",
         "unavailable", "not_testable"), 0)
    for t in tiers:
        if t in CONFIRMING:
            out["confirmed"] += 1
        elif t == "name_address":
            out["corroborated"] += 1
        elif t == "name":
            out["supporting"] += 1
        elif t == NO_MATCH:
            out["no_match"] += 1
        elif t == UNAVAILABLE:
            out["unavailable"] += 1
        else:
            out["not_testable"] += 1
    out["population"] = sum(out[k] for k in (
        "confirmed", "corroborated", "supporting", "no_match",
        "unavailable", "not_testable"))
    out["attempted"] = out["population"] - out["not_testable"]
    out["observable"] = (out["confirmed"] + out["corroborated"]
                         + out["supporting"] + out["no_match"])
    out["coverage"] = (out["attempted"] / out["population"]
                       if out["population"] else None)
    out["power"] = (out["observable"] / out["attempted"]
                    if out["attempted"] else None)
    return out
