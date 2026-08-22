#!/usr/bin/env python3
"""
Comp identity filtering -- built from the labeled failure modes of the first
verified cohort.

Manual verification showed the comp stage failing four distinct ways, all of
them visible in listing TITLES the old code discarded:

  set_mismatch   GBP 1.93 single camp spoon comped against 12-piece cutlery
                 sets ("Set", "12 Pc", "4 person")
  bundle         Fellow "lid system" comped against full mug+lids bundles
  adjacent       Goal Zero "Basecamp 4" ask median polluted by Yeti power
                 stations matching on the brand tokens
  aspirational   asks far above the brand's own list price (nobody pays more
                 than the manufacturer charges for an in-stock product)

This module scores each returned listing against the query and the known
supply-side list price, keeps only listings that plausibly ARE the product,
and recomputes the comp stats over the kept set. Active asks remain a
FILTERING signal -- the haircut and manual sold validation still apply after
this. Tightening identity and discounting price are different corrections
for different failure modes.
"""
import re
import statistics

STOP = {"the", "a", "an", "of", "for", "with", "and", "in", "on", "by", "to",
        "new", "i", "ii"}
# words that signal multi-unit/bundle listings
SET_WORDS = {"set", "pack", "pcs", "piece", "pieces", "bundle", "lot",
             "pairs", "combo"}
# supply-side title markers meaning the buy leg is NOT new-in-box
CONDITION_MARKERS = ("open box", "openbox", "refurb", "pd certified",
                     "factory 2nd", "factory second", "b-stock", "b stock",
                     "pre-owned", "preowned", "last call", "final sale",
                     "blemished", "scratch", "dent")


UNITS = ("w", "watt", "watts", "inch", "in", "oz", "ml", "l", "ft", "cm",
         "mm", "qt", "gb", "tb", "pc")


def tokens(s):
    return [t for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", (s or "").lower())
            if t not in STOP]


def numeric_cores(toks):
    """'16-inch' -> {'16'}; '100w' -> {'100'}; '3-in-1' -> {'3','1'}.
    Units and separators vary wildly across listing titles; the digits are
    the identity."""
    cores = set()
    for t in toks:
        for m in re.findall(r"\d+(?:\.\d+)?", t):
            cores.add(m)
    return cores


def condition_flag(supply_title):
    t = (supply_title or "").lower()
    return next((m for m in CONDITION_MARKERS if m in t), None)


def title_matches(query, listing_title):
    """
    Does this listing plausibly refer to the queried product?

      * every NUMERIC/model token in the query must appear (numbers carry
        identity: 100W, 16-inch, 200X, 3-in-1)
      * >= 60% of the remaining distinctive tokens must appear
      * a set-word in the listing but not the query -> reject (set/multipack
        contamination); same in reverse (query wants a set, listing is one
        unit)
    """
    q = tokens(query)
    lt = set(tokens(listing_title))
    if not q or not lt:
        return False, "empty"
    q_cores = numeric_cores(q)
    l_cores = numeric_cores(lt)
    for n in q_cores:
        if n not in l_cores:
            return False, f"model number '{n}' missing"
    rest = [t for t in q if not any(ch.isdigit() for ch in t)]
    if rest:
        hit = sum(1 for t in rest if t in lt)
        if hit / len(rest) < 0.75:
            return False, f"only {hit}/{len(rest)} tokens match"
    qs = set(q)
    listing_sets = lt & SET_WORDS
    query_sets = qs & SET_WORDS
    if listing_sets - query_sets:
        return False, f"set-word {sorted(listing_sets - query_sets)} not in query"
    if query_sets - listing_sets:
        return False, "query is a set, listing is not"
    # "Rack + Perfect Pot", "Wallet + KeyCase": a joined bundle the query
    # didn't ask for
    if ("+" in listing_title or " w/ " in listing_title.lower()) \
            and "+" not in query:
        return False, "bundle marker (+) not in query"
    return True, None


def clean_comp(comp, query, list_gbp=None, fx=1.0, msrp_ceiling=1.35):
    """
    comp: raw lookup result carrying `items` [(title, price)].
    -> filtered comp dict + rejection accounting, or None if nothing survives.

    The brand list price is used as a FLAG, not a filter: a cleaned median
    above list marks a scarcity premium (discontinued/sold-out at source),
    which manual verification showed is where the genuine opportunities
    live -- the earlier version rejected those comps as "aspirational" and
    thereby rejected the one confirmed-good candidate. Bundles are caught
    by title structure instead.
    """
    items = comp.get("items")
    if not items:                      # cache from before v2, or synthetic
        return dict(comp, filtered=False)
    kept, rejects = [], {}
    for it in items:
        ok, why = title_matches(query, it["t"])
        if ok:
            kept.append(it["p"])
        else:
            rejects[why.split("'")[0].strip()] = \
                rejects.get(why.split("'")[0].strip(), 0) + 1
    if not kept:
        return None
    kept.sort()
    med = statistics.median(kept)
    scarcity = bool(list_gbp) and med > list_gbp * fx * msrp_ceiling
    return {"median": med,
            "p25": kept[max(0, len(kept) // 4 - 1)],
            "n": len(kept),            # verified-identity count, not eBay total
            "n_raw": len(items), "rejected": rejects,
            "scarcity_premium": scarcity,
            "currency": comp["currency"], "synthetic": comp.get("synthetic", False),
            "filtered": True}
