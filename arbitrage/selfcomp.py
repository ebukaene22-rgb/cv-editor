#!/usr/bin/env python3
"""
Self-comp detection: reject comps published by the source itself.

The dealer-closeout gate produced this project's first PASSes -- ten of them,
each showing >£90 contribution. Nine were the same artefact: the only eBay
listing for the part was the SOURCE's own eBay store, priced at a fixed
1.2632x markup on its own website price. The gate had measured a seller's
dual-channel fee markup and reported it as spread.

Buying a unit from a dealer's website to undercut that dealer's eBay listing
is not arbitrage. The dealer holds the stock at a lower cost basis by exactly
the markup you are trying to capture, is already in the exit venue, and can
reprice below you at will. And with n=1 the "comp" is one ask by one seller
with no evidence anyone pays it.

Two independent detectors, because each fails differently:

  1. `is_self_comp` -- name matching between the source domain and the eBay
     seller username. Cheap and exact when the store uses its own name.
     It is a LOWER BOUND: a source trading on eBay under an unrelated handle
     is invisible to it.
  2. `fixed_ratio_sellers` -- structural. If one seller's comp price is the
     same constant multiple of the source price across several distinct
     products, that is a channel markup, not a market. Catches renamed
     stores, which detector 1 cannot.

Run both. Detector 2 is the one that generalises.
"""
import re
from collections import defaultdict

# Suffixes a store appends to its eBay handle but not its domain (or vice
# versa). Stripped from both sides before comparison.
_NOISE = ("shop", "store", "storeuk", "direct", "outlet", "online", "sales",
          "ltd", "limited", "llc", "inc", "official", "uk", "gb", "usa", "us",
          "eu", "deals", "trading")

# Below this, a containment match is coincidence rather than identity
# ("it" would otherwise match "itinstock", "digitalworld", "monitors"...).
MIN_CONTAINMENT = 5


def _norm(s):
    """Lowercase alphanumeric core of a domain or username."""
    s = (s or "").strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^www\.", "", s)
    s = s.split("/")[0]
    # drop the TLD and any country second-level ("co.uk", "com.au")
    parts = s.split(".")
    if len(parts) > 1:
        s = parts[0]
    return re.sub(r"[^a-z0-9]", "", s)


def _strip_noise(core):
    """Remove trailing marketing suffixes and digits, but never to nothing."""
    prev = None
    while core != prev:
        prev = core
        for suf in sorted(_NOISE, key=len, reverse=True):
            if core.endswith(suf) and len(core) - len(suf) >= MIN_CONTAINMENT:
                core = core[:-len(suf)]
                break
        stripped = core.rstrip("0123456789")
        if len(stripped) >= MIN_CONTAINMENT:
            core = stripped
    return core


def is_self_comp(source_domain, seller_username):
    """
    -> (bool, reason). True when the eBay seller is, by name, the source.

    A lower bound on self-comping: proves presence, never absence.
    """
    a = _strip_noise(_norm(source_domain))
    b = _strip_noise(_norm(seller_username))
    if not a or not b:
        return False, "insufficient identity"
    if a == b:
        return True, f"seller '{seller_username}' is source '{source_domain}'"
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= MIN_CONTAINMENT and short in long_:
        return True, (f"seller '{seller_username}' contains source core "
                      f"'{short}'")
    return False, "distinct"


def strip_self_comps(items, source_domain):
    """
    items: [{'t','p','s'(seller), ...}] -> (kept, dropped, reasons).

    Items with no seller field are KEPT and counted in `reasons` under
    'unattributed' -- silence about the seller is not evidence of
    independence, and the caller needs to see how much of the comp set
    could not be checked.
    """
    kept, dropped, reasons = [], [], defaultdict(int)
    for it in items:
        seller = it.get("s") or it.get("seller")
        if not seller:
            reasons["unattributed"] += 1
            kept.append(it)
            continue
        hit, why = is_self_comp(source_domain, seller)
        if hit:
            dropped.append(it)
            reasons[why] += 1
        else:
            kept.append(it)
    return kept, dropped, dict(reasons)


def fixed_ratio_sellers(rows, tol=0.005, min_products=3):
    """
    Structural dual-channel detector, blind to names.

    rows: [{'seller','source_price','comp_price','key'}] across a cohort.
    -> {seller: {'ratio','n','keys'}} for sellers whose comp/source ratio is
    constant (within `tol`) over >= `min_products` DISTINCT products.

    A real market does not price N unrelated parts at an identical multiple
    of one dealer's web price. A dealer running two channels does.
    """
    by_seller = defaultdict(list)
    for r in rows:
        try:
            src = float(r["source_price"])
            comp = float(r["comp_price"])
        except (KeyError, TypeError, ValueError):
            continue
        if src <= 0 or comp <= 0:
            continue
        by_seller[r.get("seller") or "?"].append((comp / src, r.get("key")))

    out = {}
    for seller, pairs in by_seller.items():
        buckets = defaultdict(list)
        for ratio, key in pairs:
            placed = False
            for anchor in list(buckets):
                if abs(ratio - anchor) <= tol * anchor:
                    buckets[anchor].append((ratio, key))
                    placed = True
                    break
            if not placed:
                buckets[ratio].append((ratio, key))
        for anchor, members in buckets.items():
            keys = {k for _, k in members if k is not None}
            if len(keys) >= min_products:
                mean = sum(r for r, _ in members) / len(members)
                out[seller] = {"ratio": round(mean, 6), "n": len(keys),
                               "keys": sorted(keys)}
    return out
