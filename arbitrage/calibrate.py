#!/usr/bin/env python3
"""
Realised-price proxy calibration -- evaluates alternative active-market
proxies against human-verified sold medians. Analysis only; the funnel is
unchanged pending results review.

Caveats stated up front:
 - Active distributions are re-fetched at analysis time, not shortlist
   time (raw listings were not archived). Days of drift.
 - "Sold-observed" rows have genuinely observed sold prices; rows whose
   realised value was inferred from retail availability are excluded.
 - n≈9. Everything here is a directional read, not a fitted model.
"""
import sys, statistics
sys.path.insert(0, ".")
import scan, comp as C, identity as I

# (product, query, evidence_market, verified_sold_gbp)
CASES = [
 ("TS SuitCase 16",      "Twelve South SuitCase for MacBook 16-inch Pro", "GB", 31.15),
 ("Cashmere King",       "Brooklinen Heathered Cashmere Pillowcases King", "US", 60.0),
 ("Classic Percale Std", "Brooklinen Classic Percale Pillowcase Set Standard", "US", 20.0),
 ("Eddy Cardigan",       "Taylor Stitch Eddy Cardigan Merino", "US", 51.8),
 ("W Dasher NZ",         "Allbirds Women s Dasher NZ", "US", 58.6),
 ("M Dasher NZ",         "Allbirds Men s Dasher NZ", "US", 58.6),
 ("Ridge Daily Driver",  "Ridge Daily Driver Kit", "US", 55.5),
 ("Satechi 100W GaN",    "Satechi 100W USB-C PD Compact GaN Charger", "GB", 49.7),
 ("IceFlow 40oz",        "Stanley IceFlow Tumbler Fast Flow Lid 40", "GB", 38.73),
]

def proxies(kept):
    kept = sorted(kept)
    n = len(kept)
    def pct(p):
        k = (n - 1) * p
        lo, hi = int(k), min(int(k) + 1, n - 1)
        return kept[lo] + (kept[hi] - kept[lo]) * (k - lo)
    trimmed = kept[max(1, n//10):n - max(1, n//10)] if n >= 4 else kept
    return {
        "median": statistics.median(kept),
        "0.75xmedian": 0.75 * statistics.median(kept),
        "min": kept[0],
        "p10": pct(.10), "p20": pct(.20), "p25": pct(.25),
        "cheap3": statistics.median(kept[:3]),
        "cheap5": statistics.median(kept[:5]) if n >= 3 else statistics.median(kept),
        "trimmed": statistics.median(trimmed),
    }

def main():
    conn = scan.db()
    rates = scan.fx_rates(conn)
    gbp = rates.get("GBP")
    ec = C.EbayComp(conn)
    rows = []
    for name, q, mkt, sold in CASES:
        c = ec.lookup(q, region=mkt, limit=50)
        if not c or not c.get("items"):
            print(f"  !! no listings for {name}")
            continue
        kept = [it["p"] for it in c["items"] if I.title_matches(q, it["t"])[0]]
        if not kept:
            print(f"  !! zero clean listings for {name} ({len(c['items'])} raw)")
            continue
        fx = (rates.get(c["currency"]) or 1.0) / gbp
        kept_gbp = [p / fx for p in kept]
        disp = (max(kept_gbp) - min(kept_gbp)) / statistics.median(kept_gbp) if len(kept_gbp) > 1 else 0
        rows.append((name, sold, kept_gbp, disp))
    names = list(proxies([1, 2, 3]).keys())
    err = {k: [] for k in names}
    print(f"\n{'case':<20}{'sold':>7}{'n':>4}{'disp':>6}", "".join(f"{k:>12}" for k in names))
    for name, sold, kept, disp in rows:
        P = proxies(kept)
        print(f"{name:<20}{sold:>7.1f}{len(kept):>4}{disp:>6.1f}",
              "".join(f"{P[k]:>12.1f}" for k in names))
        for k in names:
            err[k].append((P[k] - sold) / sold)
    print(f"\n{'PROXY':<14}{'MAPE':>7}{'bias':>8}{'<=10%':>7}{'<=20%':>7}{'<=30%':>7}")
    for k in names:
        e = err[k]
        mape = statistics.median([abs(x) for x in e]) * 100
        bias = statistics.median(e) * 100
        w = lambda t: sum(1 for x in e if abs(x) <= t) * 100 // len(e)
        print(f"{k:<14}{mape:>6.0f}%{bias:>+7.0f}%{w(.10):>6}%{w(.20):>6}%{w(.30):>6}%")
    return rows

if __name__ == "__main__":
    main()
