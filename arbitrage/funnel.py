#!/usr/bin/env python3
"""
Empirical funnel: how much of the observed supply universe survives contact
with real economics?

Prints the whole distribution, not the top ten. A top-ten list is guaranteed
to look good regardless of whether the business works -- it is the tail of
any distribution. The survivor counts and percentiles are the thing that
actually discriminates between "this can support a business" and "this is a
handful of flukes".

Stages are labelled REAL or ESTIMATED. Supply-side stages come from observed
data. Demand-side stages need eBay comps; without a keyset they run on
synthetic stubs and are marked as such, because a funnel built on stub comps
measures the machinery, not the market.
"""
import re
import statistics
from collections import defaultdict

import comp as C
import fees as F
import signals as S


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


from review import product_key  # shared: funnel and review must agree on identity


def run(conn, args, cur_ts, rates):
    gbp_per_usd = rates.get("GBP") or 0.79

    def to_gbp(v, ccy):
        if v is None:
            return None
        return (v / (rates.get(ccy) or 1.0)) * gbp_per_usd

    # ---------------------------------------------------- stage 1: universe
    total_variants = conn.execute(
        "SELECT COUNT(*) FROM obs WHERE ts=?", (cur_ts,)).fetchone()[0]
    stores = conn.execute(
        "SELECT COUNT(DISTINCT domain) FROM obs WHERE ts=?", (cur_ts,)
    ).fetchone()[0]

    rows = conn.execute("""
        SELECT domain, region, sku, title, vendor, price, compare, currency,
               grams
        FROM obs WHERE ts=? AND available=1 AND price > 0""",
        (cur_ts,)).fetchall()

    # -------------------------------------------- stage 2: anomaly + dedupe
    anomalous = [r for r in rows
                 if r["compare"] and r["compare"] > r["price"]
                 and (1 - r["price"] / r["compare"]) >= args.min_discount]

    best = {}
    for r in anomalous:
        k = (r["domain"], product_key(r).lower())
        g = to_gbp(r["price"], r["currency"])
        if g and (k not in best or g < best[k][0]):
            best[k] = (g, product_key(r), r)
    products = list(best.values())
    products.sort(key=lambda x: -(1 - x[2]["price"] / x[2]["compare"]))
    products = products[:args.n]

    # ------------------------------------------- availability telemetry
    sig_by_store = {}
    for dom in {r["domain"] for _, _, r in products}:
        sig_by_store[dom] = S.depletion_signals(conn, dom)

    # ------------------------------------------------- stage 3+: economics
    ec = C.EbayComp(conn, synthetic=args.synthetic)
    recs = []
    for buy_gbp, q, r in products:
        c = ec.lookup(q, region=r["region"] or "GB")
        if not c:
            continue
        sell_gbp = to_gbp(c["median"], c["currency"])
        cat = F.categorise(r["title"] or "", r["vendor"] or "")
        econ = F.Economics(category=cat, buyer_region="UK",
                           seller_country=args.seller_country,
                           vat_registered=args.vat_registered,
                           duty_rate=args.duty, ad_rate=args.ad,
                           postage_charged=args.postage)
        cm, margin, bd = econ.contribution(buy_gbp, sell_gbp, r["grams"])
        if cm is None:
            continue
        sig = sig_by_store.get(r["domain"], {}).get(r["sku"])
        share = S.share_from_competition(c["n"])
        eo = S.expected_monthly_orders(sig, share_of_market=share)
        score = S.opportunity_score(eo, cm, args.match_conf, args.supply_conf)
        recs.append({"cm": cm, "margin": margin, "bd": bd, "cat": cat, "comp_n": c["n"],
                     "buy": buy_gbp, "sell": sell_gbp, "sig": sig,
                     "exp_orders": eo, "score": score, "row": r,
                     "synthetic": c.get("synthetic", False)})

    # ------------------------------------------------------------- report
    syn = ec.synthetic
    tag = "  [SYNTHETIC COMPS - measures machinery, not market]" if syn else ""
    print(f"\n{'='*78}\nFUNNEL{tag}\n{'='*78}")
    _, _, probe = F.Economics(
        seller_country=args.seller_country,
        vat_registered=args.vat_registered).contribution(10, 20, 500)
    print(f"snapshot {cur_ts}   stores={stores}   "
          f"seller={args.seller_country} vat_reg={args.vat_registered} "
          f"fee_tax={probe['fee_tax']:.0%}  duty={args.duty:.0%}  "
          f"ad={args.ad:.0%}")
    if probe["fee_tax_note"]:
        print(f"  !! {probe['fee_tax_note']}")
    print()

    matched = len(recs)
    m15 = [r for r in recs if r["margin"] is not None and r["margin"] >= 0.15]
    cm5 = [r for r in m15 if r["cm"] >= 5]
    cm10 = [r for r in m15 if r["cm"] >= 10]
    cm15 = [r for r in m15 if r["cm"] >= 15]
    uncrowded = [r for r in cm5 if r["comp_n"] <= args.max_competitors]
    with_signal = [r for r in uncrowded
                   if r["sig"] and r["sig"]["confidence"] in
                   ("moderate", "strong")]

    def line(label, n, prev, real):
        rate = f"{n/prev*100:5.1f}%" if prev else "    -"
        print(f"  {label:<44} {n:>7,}  {rate}   {real}")

    print(f"  {'STAGE':<44} {'N':>7}  {'SURV':>5}   BASIS")
    print("  " + "-" * 74)
    line("observed variants (in stock)", len(rows), None, "REAL")
    line(f"anomalous (>={args.min_discount:.0%} off list)",
         len(anomalous), len(rows), "REAL")
    line("unique candidate products (deduped)", len(best), len(anomalous), "REAL")
    line("sampled for comping", len(products), len(best), "REAL")
    basis = "SYNTH" if syn else "REAL"
    line("with a plausible resale match", matched, len(products), basis)
    line("contribution margin >= 15% on cost", len(m15), matched, basis)
    line("contribution >= GBP 5/order", len(cm5), len(m15), basis)
    line(f"competitors <= {args.max_competitors}", len(uncrowded), len(cm5), basis)
    line("with moderate+ depletion evidence", len(with_signal),
         len(uncrowded), "REAL" if not syn else "MIXED")

    if not recs:
        print("\n  no records survived comping.")
        return

    cms = [r["cm"] for r in recs]
    print(f"\n  CONTRIBUTION PER ORDER (GBP, all {len(recs)} comped)")
    print(f"    median {pct(cms,.5):7.2f}   P75 {pct(cms,.75):7.2f}   "
          f"P90 {pct(cms,.9):7.2f}   max {max(cms):7.2f}")
    revs = [r["bd"]["cm_rev_pct"] for r in recs if r["bd"].get("cm_rev_pct") is not None]
    rois = [r["bd"]["roi_cost"] for r in recs if r["bd"].get("roi_cost") is not None]
    if revs and rois:
        print(f"    CM/revenue median {pct(revs,.5)*100:5.1f}%   "
              f"ROI-on-cost median {pct(rois,.5)*100:5.1f}%")
    neg = sum(1 for x in cms if x <= 0)
    print(f"    negative or zero: {neg:,} of {len(cms):,} "
          f"({neg/len(cms)*100:.0f}%)")

    print(f"\n  SURVIVORS BY CONTRIBUTION THRESHOLD (of {matched} matched)")
    for lbl, s in (("GBP  5", cm5), ("GBP 10", cm10), ("GBP 15", cm15)):
        print(f"    >= {lbl}: {len(s):>5,}  ({len(s)/matched*100:4.1f}%)")

    print(f"\n  SURVIVOR RATE BY CATEGORY (>=15% margin AND >=GBP5)")
    by_cat = defaultdict(lambda: [0, 0])
    for r in recs:
        by_cat[r["cat"]][0] += 1
        if r in cm5:
            by_cat[r["cat"]][1] += 1
    print(f"    {'category':<14} {'comped':>7} {'survive':>8} {'rate':>7} "
          f"{'med CM':>8}")
    for cat, (tot, sv) in sorted(by_cat.items(), key=lambda x: -x[1][0]):
        med = pct([r["cm"] for r in recs if r["cat"] == cat], .5)
        print(f"    {cat:<14} {tot:>7,} {sv:>8,} {sv/tot*100:>6.1f}% "
              f"{med:>8.2f}")

    print(f"\n  CONCENTRATION (are opportunities one store's artefact?)")
    by_store = defaultdict(int)
    for r in cm5:
        by_store[r["row"]["domain"]] += 1
    if by_store:
        tot = sum(by_store.values())
        for dom, n in sorted(by_store.items(), key=lambda x: -x[1])[:8]:
            print(f"    {dom:<34} {n:>5,}  {n/tot*100:5.1f}% of survivors")
        top = max(by_store.values()) / tot
        print(f"    -> top store holds {top:.0%} of survivors"
              + ("  ** concentrated: treat as one bet, not a portfolio **"
                 if top > 0.5 else ""))

    print(f"\n  DEPLETION SIGNAL vs COMPETITION")
    buckets = defaultdict(list)
    for r in recs:
        conf = r["sig"]["confidence"] if r["sig"] else "no-data"
        buckets[conf].append(r["comp_n"])
    for conf in ("strong", "moderate", "weak", "none", "no-data"):
        if conf in buckets:
            v = buckets[conf]
            print(f"    {conf:<9} n={len(v):>5,}  median competitors "
                  f"{pct(v,.5):>8,.0f}")
    if len({c for c in buckets if c != 'no-data'}) <= 1:
        print("    -> single bucket: needs more snapshots before this "
              "relationship is measurable")

    print(f"\n  TOP BY EXPECTED MONTHLY CONTRIBUTION (GBP)")
    ranked = [r for r in recs if r["score"] is not None]
    ranked.sort(key=lambda r: -r["score"])
    if not ranked:
        print("    none scoreable: expected-orders needs >=2 snapshots with "
              "a replenishment cycle")
    else:
        print(f"    {'E[cont]':>9} {'E[ord]':>7} {'CM':>7} {'comp':>6}  PRODUCT")
        for r in ranked[:10]:
            print(f"    {r['score']:>9.2f} {r['exp_orders']:>7.1f} "
                  f"{r['cm']:>7.2f} {r['comp_n']:>6,}  "
                  f"{(r['row']['title'] or '')[:34]}")

    print(f"\n  api calls={ec.calls}  cache hits={ec.cache_hits}")
    if syn:
        print("  Comps synthetic: stages 5+ are NOT evidence about the "
              "market.\n  Set EBAY_CLIENT_ID/EBAY_CLIENT_SECRET and rerun.")
    print()
