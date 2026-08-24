#!/usr/bin/env python3
"""
Supply-side arbitrage scanner.

Polls public storefront catalogue endpoints, stores every observation in a
SQLite time-series, and derives four signals from the history:

  clearance  deep compare_at_price discounts that are still in stock
  sellout    variants that flipped available -> unavailable between snapshots
  arb        same SKU priced differently across regional storefronts
  new        SKUs appearing for the first time

Stdlib only. Two sources are supported, both of which serve JSON to anonymous
clients by design:

  shopify  <domain>/products.json          (paginated, 250/page)
  woo      <domain>/wp-json/wc/store/v1/products

Usage:
    python3 scan.py snapshot            # poll every store in stores.txt
    python3 scan.py clearance --min 40
    python3 scan.py sellout
    python3 scan.py arb --group allbirds --min 25
    python3 scan.py new
    python3 scan.py stores              # coverage report
"""
import argparse
import gzip
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("ARBITRAGE_DB", os.path.join(HERE, "prices.db"))
STORES = os.path.join(HERE, "stores.txt")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

# Consumer prices are quoted tax-inclusive in the UK/EU and tax-exclusive in
# the US/CA. Comparing the sticker prices directly overstates the gap by the
# VAT rate, so divide it out before comparing.
VAT = {"US": 1.00, "CA": 1.00, "GB": 1.20, "EU": 1.21, "AU": 1.10}

SCHEMA = """
CREATE TABLE IF NOT EXISTS obs (
  ts        TEXT NOT NULL,
  domain    TEXT NOT NULL,
  grp       TEXT,
  region    TEXT,
  sku       TEXT NOT NULL,
  title     TEXT,
  vendor    TEXT,
  price     REAL,
  compare   REAL,
  currency  TEXT,
  available INTEGER,
  grams     INTEGER,
  url       TEXT,
  ptype     TEXT,
  PRIMARY KEY (ts, domain, sku)
);
CREATE INDEX IF NOT EXISTS ix_sku    ON obs(sku);
CREATE INDEX IF NOT EXISTS ix_domain ON obs(domain, ts);
CREATE TABLE IF NOT EXISTS fx (ts TEXT PRIMARY KEY, rates TEXT);
"""


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-GB,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8", "replace"))


def fx_rates(conn):
    """Live USD-base rates, cached for the day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute("SELECT rates FROM fx WHERE ts=?", (today,)).fetchone()
    if row:
        return json.loads(row["rates"])
    rates = {"USD": 1.0}
    try:
        d = get("https://api.frankfurter.dev/v1/latest?base=USD")
        rates.update(d["rates"])
    except Exception as e:
        print(f"  ! FX fetch failed ({e}); assuming parity", file=sys.stderr)
    conn.execute("INSERT OR REPLACE INTO fx VALUES (?,?)", (today, json.dumps(rates)))
    conn.commit()
    return rates


# ---------------------------------------------------------------- collectors

def shopify(domain, pages=4):
    """Yield variant dicts from a public Shopify catalogue."""
    for page in range(1, pages + 1):
        try:
            d = get(f"https://{domain}/products.json?limit=250&page={page}")
        except Exception as e:
            if page == 1:
                raise
            print(f"    page {page}: {e}", file=sys.stderr)
            return
        prods = d.get("products", [])
        if not prods:
            return
        for p in prods:
            for v in p.get("variants", []):
                sku = (v.get("sku") or "").strip() or f"gid:{v['id']}"
                try:
                    price = float(v["price"])
                except (TypeError, ValueError, KeyError):
                    continue
                cmp_ = v.get("compare_at_price")
                try:
                    cmp_ = float(cmp_) if cmp_ else None
                except ValueError:
                    cmp_ = None
                yield {
                    "sku": sku,
                    "title": f"{p['title']} / {v.get('title','')}".strip(" /"),
                    "vendor": p.get("vendor"),
                    "price": price,
                    "compare": cmp_,
                    "available": 1 if v.get("available") else 0,
                    "grams": v.get("grams"),
                    "url": (f"https://{domain}/products/{p['handle']}"
                            f"?variant={v['id']}" if p.get("handle") else None),
                    "ptype": p.get("product_type") or None,
                }
        time.sleep(0.4)


def woo(domain, pages=4):
    """Yield variant dicts from a public WooCommerce Store API."""
    for page in range(1, pages + 1):
        try:
            items = get(f"https://{domain}/wp-json/wc/store/v1/products"
                        f"?per_page=100&page={page}")
        except Exception as e:
            if page == 1:
                raise
            return
        if not items:
            return
        for p in items:
            pr = p.get("prices") or {}
            minor = 10 ** int(pr.get("currency_minor_unit", 2) or 2)
            try:
                price = float(pr["price"]) / minor
            except (TypeError, ValueError, KeyError):
                continue
            reg = pr.get("regular_price")
            try:
                reg = float(reg) / minor if reg else None
            except ValueError:
                reg = None
            cats = p.get("categories") or []
            yield {
                "url": p.get("permalink"),
                "ptype": cats[0].get("name") if cats else None,
                "sku": (p.get("sku") or "").strip() or f"wid:{p['id']}",
                "title": re.sub(r"<[^>]+>", "", p.get("name", ""))[:160],
                "vendor": None,
                "price": price,
                "compare": reg if reg and reg > price else None,
                "available": 1 if p.get("is_in_stock") else 0,
                "grams": None,
            }
        time.sleep(0.4)


COLLECTORS = {"shopify": shopify, "woo": woo}


def load_stores():
    """stores.txt: platform<TAB>domain<TAB>currency<TAB>region<TAB>group"""
    out = []
    if not os.path.exists(STORES):
        sys.exit(f"missing {STORES}")
    for ln in open(STORES):
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        f = [x.strip() for x in re.split(r"\t+|\s{2,}", ln)]
        if len(f) < 4:
            continue
        out.append({"platform": f[0], "domain": f[1], "currency": f[2],
                    "region": f[3], "group": f[4] if len(f) > 4 else None})
    return out


def cmd_snapshot(args):
    conn = db()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ok = fail = total = 0
    for s in load_stores():
        fn = COLLECTORS.get(s["platform"])
        if not fn:
            continue
        try:
            rows = list(fn(s["domain"], pages=args.pages))
        except Exception as e:
            print(f"  x {s['domain']:<34} {type(e).__name__}: {e}")
            fail += 1
            continue
        seen = {}
        for r in rows:                       # first observation of a SKU wins
            seen.setdefault(r["sku"], r)
        conn.executemany(
            "INSERT OR REPLACE INTO obs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(ts, s["domain"], s["group"], s["region"], r["sku"], r["title"],
              r["vendor"], r["price"], r["compare"], s["currency"],
              r["available"], r["grams"], r.get("url"), r.get("ptype"))
             for r in seen.values()])
        conn.commit()
        instock = sum(r["available"] for r in seen.values())
        print(f"  + {s['domain']:<34} {len(seen):>5} skus  "
              f"{instock/max(len(seen),1)*100:>3.0f}% in stock")
        ok += 1
        total += len(seen)
    print(f"\nsnapshot {ts}: {ok} stores ok, {fail} failed, {total:,} variant rows")


def latest_two(conn, domain=None):
    q = "SELECT DISTINCT ts FROM obs"
    p = ()
    if domain:
        q += " WHERE domain=?"
        p = (domain,)
    ts = [r["ts"] for r in conn.execute(q + " ORDER BY ts DESC LIMIT 2", p)]
    return (ts + [None, None])[:2]


def cmd_clearance(args):
    conn = db()
    cur, _ = latest_two(conn)
    if not cur:
        sys.exit("no snapshots yet - run: scan.py snapshot")
    rows = conn.execute("""
        SELECT domain, title, price, compare, currency,
               (1 - price/compare)*100 AS pct
        FROM obs
        WHERE ts=? AND compare IS NOT NULL AND compare > price
              AND price > 0 AND available=1
        ORDER BY pct DESC LIMIT ?""", (cur, args.limit)).fetchall()
    rows = [r for r in rows if r["pct"] >= args.min]
    print(f"in-stock clearance >= {args.min:.0f}%  ({cur})\n")
    print(f"{'OFF':>5}  {'NOW':>9}  {'WAS':>9}  {'STORE':<26} PRODUCT")
    print("-" * 104)
    for r in rows:
        print(f"{r['pct']:4.0f}%  {r['price']:9.2f}  {r['compare']:9.2f}  "
              f"{r['domain'][:26]:<26} {r['title'][:40]}")
    if not rows:
        print("(nothing above threshold)")


def cmd_sellout(args):
    """Variants that went available -> unavailable: real demand, not asking price."""
    conn = db()
    cur, prev = latest_two(conn)
    if not prev:
        sys.exit("need 2 snapshots - run scan.py snapshot again later")
    rows = conn.execute("""
        SELECT a.domain, a.title, a.price, a.currency
        FROM obs a JOIN obs b ON a.sku=b.sku AND a.domain=b.domain
        WHERE a.ts=? AND b.ts=? AND b.available=1 AND a.available=0
        ORDER BY a.price DESC LIMIT ?""", (cur, prev, args.limit)).fetchall()
    print(f"sold out between {prev} and {cur}\n")
    print(f"{'PRICE':>9}  {'STORE':<26} PRODUCT")
    print("-" * 92)
    for r in rows:
        print(f"{r['price']:9.2f}  {r['domain'][:26]:<26} {r['title'][:46]}")
    print(f"\n{len(rows)} variants sold out this interval")


def cmd_arb(args):
    """Same SKU, different regional storefronts, VAT- and FX-normalised."""
    conn = db()
    cur, _ = latest_two(conn)
    if not cur:
        sys.exit("no snapshots yet")
    rates = fx_rates(conn)
    q = "SELECT * FROM obs WHERE ts=?"
    p = [cur]
    if args.group:
        q += " AND grp=?"
        p.append(args.group)
    book = {}
    for r in conn.execute(q, p):
        rate = rates.get(r["currency"])
        if not rate or not r["price"]:
            continue
        usd = r["price"] / rate / VAT.get(r["region"], 1.0)
        book.setdefault(r["sku"], []).append((usd, r))
    out = []
    for sku, obs in book.items():
        if len(obs) < 2:
            continue
        lo = min(obs, key=lambda x: x[0])
        hi = max(obs, key=lambda x: x[0])
        if lo[0] <= 0 or not lo[1]["available"]:
            continue                          # unbuyable buy-side is not a trade
        gap = (hi[0] - lo[0]) / lo[0] * 100
        if gap >= args.min:
            out.append((gap, lo, hi))
    out.sort(key=lambda x: -x[0])
    print(f"cross-region gaps >= {args.min:.0f}%, buy-side in stock, "
          f"VAT-stripped, USD  ({cur})\n")
    print(f"{'GAP':>6}  {'BUY':<20} {'SELL':<20} {'BUY$':>8} {'SELL$':>8}  PRODUCT")
    print("-" * 112)
    for gap, lo, hi in out[:args.limit]:
        print(f"{gap:5.0f}%  {lo[1]['domain'][:20]:<20} {hi[1]['domain'][:20]:<20} "
              f"{lo[0]:8.2f} {hi[0]:8.2f}  {lo[1]['title'][:34]}")
    print(f"\n{len(out)} tradeable pairs "
          f"({len([b for b in book.values() if len(b)>1]):,} SKUs matched across regions)")


def cmd_new(args):
    conn = db()
    cur, prev = latest_two(conn)
    if not prev:
        sys.exit("need 2 snapshots")
    rows = conn.execute("""
        SELECT domain, title, price, currency FROM obs
        WHERE ts=? AND sku NOT IN (SELECT sku FROM obs WHERE ts=?)
        ORDER BY domain LIMIT ?""", (cur, prev, args.limit)).fetchall()
    print(f"new SKUs since {prev}\n")
    for r in rows:
        print(f"{r['price']:9.2f} {r['currency']}  {r['domain'][:26]:<26} {r['title'][:44]}")
    print(f"\n{len(rows)} new")


def cmd_stores(args):
    """Probe every store and report which endpoints actually serve data."""
    ok = 0
    for s in load_stores():
        fn = COLLECTORS.get(s["platform"])
        try:
            n = len(list(fn(s["domain"], pages=1)))
            print(f"  {'OK ' if n else 'EMPTY'} {s['domain']:<34} {n:>5} variants")
            ok += bool(n)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code:<4} {s['domain']:<34} blocked")
        except Exception as e:
            print(f"  ERR      {s['domain']:<34} {type(e).__name__}")
    print(f"\n{ok} reachable")




def cmd_funnel(args):
    """Empirical survival funnel with corrected UK economics."""
    import funnel as FN
    conn = db()
    cur, _ = latest_two(conn)
    if not cur:
        sys.exit("no snapshots yet")
    FN.run(conn, args, cur, fx_rates(conn))



def cmd_review(args):
    """Emit a Terapeak review sheet; freeze features into `candidates`."""
    import review as RV
    conn = db()
    cur, _ = latest_two(conn)
    if not cur:
        sys.exit("no snapshots yet")
    RV.generate(conn, args, cur, fx_rates(conn))


def cmd_ingest(args):
    """Read a filled review sheet back in as labels."""
    import review as RV
    conn = db()
    RV.load_candidates(conn)      # container is ephemeral; restore first
    RV.ingest(conn, args.file)


def cmd_labels(args):
    """What the labeled dataset says so far."""
    import review as RV
    conn = db()
    RV.load_candidates(conn)
    RV.report(conn)


def cmd_measure(args):
    """Write calendar-normalised scarcity measurements and the event review gate."""
    import experiments as E
    conn = db()
    totals = E.write_measurement(conn, args.out, args.review_out, args.review_n)
    print(f"measurement: {totals['rows']:,} active SKU histories -> {args.out}")
    print(f"scarcity review: {totals['review_rows']} rows -> {args.review_out}")
    print(f"SKU-days: {totals['sku_days']:,.1f}")
    for name in ("stockouts", "restocks", "cycles"):
        rate = totals[name + "_per_10k_sku_days"]
        print(f"{name}: {totals[name]:,} ({rate:.2f} per 10k SKU-days)")


def cmd_identity_audit(args):
    """Measure exact identifier coverage; optionally resolve GTINs on eBay."""
    import identifiers as ID
    conn = db()
    ebay = None
    if args.resolve_ebay:
        import comp as C
        ebay = C.EbayComp(conn)
        if ebay.synthetic:
            sys.exit("--resolve-ebay requires EBAY_CLIENT_ID and EBAY_CLIENT_SECRET")
    totals = ID.run_audit(
        conn, load_stores(), args.out, args.ledger_out,
        sample_per_store=args.sample_per_store, delay=args.delay,
        timeout=args.timeout, only_domain=args.only_domain, ebay=ebay,
        ebay_region=args.ebay_region,
        max_ebay_lookups=args.max_ebay_lookups, workers=args.workers,
        retries=args.retries, ebay_detail_limit=args.ebay_detail_limit,
        min_market_listings=args.min_market_listings,
        resolution_path=args.ebay_ledger_out if args.resolve_ebay else None)
    print(f"identity audit: {totals['domains']} stores, "
          f"{totals['products_succeeded']}/{totals['products_requested']} "
          f"product endpoints succeeded")
    print(f"variants: {totals['variants']:,}; valid GTINs: "
          f"{totals['valid_gtins']:,} ({totals['gtin_coverage_pct']:.2f}%)")
    print(f"coverage matrix -> {args.out}")
    print(f"evidence ledger -> {args.ledger_out}")
    if args.resolve_ebay:
        print(f"eBay: {totals['ebay_gtins_query_resolved']}/"
              f"{totals['ebay_gtins_attempted']} queries resolved; "
              f"{totals['ebay_gtins_coherent']} coherent; "
              f"{totals['ebay_gtins_usable_market']} usable markets")
        print(f"eBay evidence -> {args.ebay_ledger_out}")


def cmd_mpn_basket(args):
    """Freeze a deterministic exact-MPN cohort from a source sitemap."""
    import mpn as M
    rows = M.build_basket(args.sitemap, args.out, args.n)
    print(f"exact-MPN basket: {len(rows)} rows -> {args.out}")
    print(f"basket sha256: {M.basket_checksum(args.out)}")


def cmd_mpn_audit(args):
    """Run the pre-registered exact brand + MPN eBay resolver gate."""
    import comp as C
    import mpn as M
    conn = db()
    ebay = C.EbayComp(conn)
    if ebay.synthetic:
        sys.exit("mpn-audit requires EBAY_CLIENT_ID and EBAY_CLIENT_SECRET")
    totals = M.run_audit(
        ebay, args.basket, args.out, region=args.ebay_region,
        limit=args.limit, detail_limit=args.detail_limit,
        min_market_listings=args.min_market_listings)
    verdict = "PASS" if totals["passed"] else "KILL"
    print(f"basket: {totals['basket_rows']} frozen identities; "
          f"sha256 {totals['basket_checksum']}")
    print(f"active: {totals['active_queries']}/{totals['basket_rows']}; "
          f"exact brand+MPN: {totals['exact_identities']}/"
          f"{totals['basket_rows']}; usable depth: "
          f"{totals['usable_markets']}/{totals['basket_rows']} "
          f"({totals['usable_rate_pct']:.2f}%)")
    print(f"median coherent depth: {totals['median_coherent_depth']}; "
          f"pre-registered 25% gate: {verdict}")
    print(f"evidence -> {args.out}")


def cmd_mpn_economics(args):
    """Apply the frozen 16-row conservative acquisition economics gate."""
    import mpn as M
    conn = db()
    rate = args.usd_to_gbp or fx_rates(conn).get("GBP")
    if not rate:
        sys.exit("USD-to-GBP rate unavailable; pass --usd-to-gbp")
    totals = M.run_economics_gate(
        args.source, args.resolution, args.out, rate)
    verdict = ("ADVANCE_FULL_ECONOMICS" if totals["precheck_passed"]
               else "KILL_SOURCE")
    print(f"economics cohort: {totals['rows']} resolver survivors")
    print(f"pre-cost rejects: {totals['rejected_pre_cost']}; "
          f"cleared for full economics: {totals['cleared_for_full_economics']}")
    print(f"appliance cleared: {totals['appliance_cleared']}; "
          f"tool cleared: {totals['tool_cleared']}")
    print(f"four-SKU £15 contribution gate: {verdict}")
    print(f"evidence -> {args.out}")


def cmd_mpn_source_audit(args):
    """Test the frozen MPN demand set against a structured secondary source."""
    import comp as C
    import mpn as M
    conn = db()
    ebay = C.EbayComp(conn)
    if ebay.synthetic:
        sys.exit("mpn-source-audit requires eBay credentials")
    rate = args.usd_to_gbp or fx_rates(conn).get("GBP")
    if not rate:
        sys.exit("USD-to-GBP rate unavailable; pass --usd-to-gbp")
    totals = M.run_used_source_audit(
        ebay, args.resolution, args.out, rate, region=args.ebay_region,
        min_market_listings=args.min_market_listings, timeout=args.timeout)
    verdict = "ADVANCE_FULL_ECONOMICS" if totals["source_gate_passed"] else "KILL_SOURCE"
    print(f"frozen demand: {totals['demand_rows']} identities; exact source matches: "
          f"{totals['matched_identities']}; available identities: "
          f"{totals['available_identities']}")
    print(f"available condition variants: {totals['available_variants']}; "
          f"usable condition markets: {totals['condition_markets']}; "
          f"pre-cost candidates: {totals['pre_cost_candidates']}")
    print(f"three-SKU source gate: {verdict}")
    print(f"evidence -> {args.out}")


def cmd_mpn_liquidation_coverage(args):
    """Summarize title-search discovery evidence, not manifest contents."""
    import mpn as M
    totals = M.run_liquidation_coverage_gate(args.coverage, args.resolution)
    verdict = "TITLE_MATCHES_FOUND" if totals["source_gate_passed"] else "TITLE_SEARCH_INCONCLUSIVE"
    print(f"liquidation title-search screen: {totals['searches']} searches across "
          f"{totals['sources']} sources")
    print(f"matched frozen identities: {totals['matched_identities']}/"
          f"{totals['demand_rows']}; three-SKU gate: {verdict}")


def cmd_mpn_manifest_audit(args):
    """Audit real line-level liquidation manifests against frozen MPNs."""
    import mpn as M
    totals = M.run_manifest_audit(
        args.urls, args.resolution, args.out, timeout=args.timeout)
    if not totals["sample_sufficient"]:
        verdict = "INSUFFICIENT_MANIFEST_SAMPLE"
    elif totals["coverage_gate_passed"]:
        verdict = "ADVANCE_LOT_ECONOMICS"
    else:
        verdict = "KILL_FROZEN_UNIVERSE_INTERSECTION"
    print(f"manifest audit: {totals['lots']} lots, "
          f"{totals['manifest_lines']} lines, {totals['manifest_units']} units")
    print(f"matched frozen identities: {totals['matched_identities']}; "
          f"verdict: {verdict}")
    print(f"evidence -> {args.out}")


def cmd_liquidation_exit_audit(args):
    """Resolve the frozen liquidation-first GTIN universe on eBay."""
    import comp as C
    import mpn as M
    ebay = C.EbayComp(db())
    if ebay.synthetic:
        sys.exit("liquidation-exit-audit requires eBay credentials")
    totals = M.run_liquidation_exit_audit(
        ebay, args.universe, args.out, region=args.ebay_region,
        min_market_listings=args.min_market_listings)
    verdict = ("ADVANCE_LOT_ECONOMICS" if totals["advance_economics"]
               else "KILL_EXIT_RESOLUTION")
    print(f"liquidation-first universe: {totals['identities']} valid-GTIN identities")
    print(f"usable exact condition markets: {totals['usable_markets']}/"
          f"{totals['identities']} ({totals['usable_rate_pct']:.2f}%); "
          f"verdict: {verdict}")
    print(f"evidence -> {args.out}")


def cmd_liquidation_resolver_diagnostic(args):
    """Run four frozen passes to isolate GTIN, model, and condition failures."""
    import comp as C
    import mpn as M
    ebay = C.EbayComp(db())
    if ebay.synthetic:
        sys.exit("liquidation-resolver-diagnostic requires eBay credentials")
    totals = M.run_liquidation_resolver_diagnostic(
        ebay, args.universe, args.out, region=args.ebay_region,
        min_market_listings=args.min_market_listings)
    print(f"resolver diagnostic: {totals['identities']} frozen identities")
    print(f"A GTIN unfiltered: {totals['gtin_unfiltered_hits']}; "
          f"B GTIN broad-condition: {totals['gtin_condition_hits']}; "
          f"C model unfiltered: {totals['model_unfiltered_hits']}; "
          f"D model condition: {totals['model_condition_hits']}")
    print(f"deterministic markets: {totals['deterministic_markets']}")
    print(f"category-coherent exact-condition markets eligible for economics: "
          f"{totals['economics_eligible']}")
    print(f"evidence -> {args.out}")


def cmd_openbox_cohort(args):
    """Generate the bounded condition-matched open-box/refurb review sheet."""
    import experiments as E
    conn = db()
    n = E.write_openbox_cohort(conn, fx_rates(conn), args.out, args.n)
    print(f"open-box/refurb cohort: {n}/{args.n} rows -> {args.out}")


def cmd_bundle_cohort(args):
    """Generate bundle candidates with explicit component-mapping fields."""
    import experiments as E
    conn = db()
    n = E.write_bundle_cohort(conn, fx_rates(conn), args.out, args.n)
    print(f"bundle cohort: {n}/{args.n} rows -> {args.out}")


def cmd_liquidation_template(args):
    """Create the input contract for one manifested-lot paper exercise."""
    import experiments as E
    E.write_liquidation_template(args.out)
    print(f"liquidation manifest template -> {args.out}")


def cmd_liquidation(args):
    """Conservatively underwrite a filled liquidation manifest."""
    import experiments as E
    result = E.underwrite_liquidation(
        args.file, args.bid, args.freight, args.testing, args.disposal,
        args.fee_rate)
    E.print_underwriting(result)



def cmd_export(args):
    """Export snapshots to history/*.csv.gz -- the git-friendly archive."""
    import csv, gzip
    conn = db()
    os.makedirs("history", exist_ok=True)
    cols = ["ts","domain","grp","region","sku","title","vendor","price",
            "compare","currency","available","grams","url","ptype"]
    n = 0
    for (ts,) in conn.execute("SELECT DISTINCT ts FROM obs ORDER BY ts"):
        path = os.path.join("history", ts.replace(":", "") + ".csv.gz")
        if os.path.exists(path):
            continue
        with gzip.open(path, "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(conn.execute(
                f"SELECT {','.join(cols)} FROM obs WHERE ts=?", (ts,)))
        n += 1
        print(f"  wrote {path}")
    print(f"exported {n} snapshot(s)")


def cmd_rebuild(args):
    """Rebuild prices.db from history/*.csv.gz."""
    import csv, gzip, glob as g
    conn = db()
    have = {t for (t,) in conn.execute("SELECT DISTINCT ts FROM obs")}
    n = rows = 0
    for path in sorted(g.glob("history/*.csv.gz")):
        with gzip.open(path, "rt", newline="") as f:
            rd = csv.DictReader(f)
            batch = [(r["ts"], r["domain"], r["grp"] or None,
                      r["region"] or None, r["sku"], r["title"], r["vendor"],
                      float(r["price"]) if r["price"] else None,
                      float(r["compare"]) if r["compare"] else None,
                      r["currency"], int(r["available"]),
                      int(r["grams"]) if r["grams"] else None,
                      r.get("url") or None, r.get("ptype") or None)
                     for r in rd]
        if batch and batch[0][0] in have:
            continue
        conn.executemany(
            "INSERT INTO obs (ts,domain,grp,region,sku,title,vendor,price,"
            "compare,currency,available,grams,url,ptype) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            batch)
        n += 1
        rows += len(batch)
    conn.commit()
    print(f"loaded {n} snapshot(s), {rows:,} rows")



def cmd_recomp(args):
    """
    Instrumentation only (no funnel logic): re-fetch fresh clean comp
    distributions for every frozen shortlist candidate and append a
    timestamped record to history/comp-track.csv. Feeds the ask-decay
    diagnostic: median ask at t+1/3/5/7 days after source markdown.
    """
    import csv as _csv
    import comp as C, identity as I, review as RV
    conn = db()
    RV.load_candidates(conn)
    cur, _ = latest_two(conn)
    rates = fx_rates(conn)
    gbp = rates.get("GBP") or 0.79
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cands = conn.execute(
        "SELECT DISTINCT product_key, region, list_gbp, sku, domain "
        "FROM candidates").fetchall()
    # bust the cache for exactly these keys so the fetch is genuinely fresh
    ec = C.EbayComp(conn)
    out_path = os.path.join("history", "comp-track.csv")
    new_file = not os.path.exists(out_path)
    f = open(out_path, "a", newline="")
    w = _csv.writer(f)
    if new_file:
        w.writerow(["ts", "product_key", "region", "n_clean", "n_raw",
                    "min_gbp", "p10_gbp", "p25_gbp", "cheap3_gbp",
                    "median_gbp", "source_price_now_gbp", "source_ref_gbp",
                    "first_markdown_ts"])
    n_ok = 0
    for c in cands:
        q, region = c["product_key"], c["region"] or "GB"
        import hashlib
        mkt = C.MARKETPLACE.get(region, "EBAY_US")
        key = hashlib.sha1(f"v2|{mkt}|{q}|50".encode()).hexdigest()
        conn.execute("DELETE FROM comps WHERE key=?", (key,))
        raw = ec.lookup(q, region=region, limit=50)
        if not raw or not raw.get("items"):
            continue
        kept = sorted(it["p"] for it in raw["items"]
                      if I.title_matches(q, it["t"])[0])
        if not kept:
            continue
        fx = (rates.get(raw["currency"]) or 1.0) / gbp
        kg = [p / fx for p in kept]
        def pct(p):
            k = (len(kg) - 1) * p
            lo, hi = int(k), min(int(k) + 1, len(kg) - 1)
            return kg[lo] + (kg[hi] - kg[lo]) * (k - lo)
        import statistics as st
        src_now = first_md = None
        if c["sku"]:
            r = conn.execute(
                "SELECT price, currency FROM obs WHERE ts=? AND sku=? AND domain=?",
                (cur, c["sku"], c["domain"])).fetchone()
            if r:
                src_now = (r["price"] / (rates.get(r["currency"]) or 1.0)) * gbp
            r2 = conn.execute(
                "SELECT MIN(ts) FROM obs WHERE sku=? AND domain=? AND "
                "compare IS NOT NULL AND compare > price",
                (c["sku"], c["domain"])).fetchone()
            first_md = r2[0] if r2 else None
        w.writerow([ts, q, region, len(kg), len(raw["items"]),
                    f"{kg[0]:.2f}", f"{pct(.10):.2f}", f"{pct(.25):.2f}",
                    f"{st.median(kg[:3]):.2f}", f"{st.median(kg):.2f}",
                    f"{src_now:.2f}" if src_now else "",
                    f"{c['list_gbp']:.2f}" if c["list_gbp"] else "",
                    first_md or ""])
        n_ok += 1
        time.sleep(0.3)
    f.close()
    print(f"comp-track: {n_ok}/{len(cands)} candidates recorded at {ts} "
          f"(api calls={ec.calls})")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot"); s.add_argument("--pages", type=int, default=4); s.set_defaults(fn=cmd_snapshot)
    s = sub.add_parser("clearance"); s.add_argument("--min", type=float, default=40); s.add_argument("--limit", type=int, default=40); s.set_defaults(fn=cmd_clearance)
    s = sub.add_parser("sellout"); s.add_argument("--limit", type=int, default=40); s.set_defaults(fn=cmd_sellout)
    s = sub.add_parser("arb"); s.add_argument("--group"); s.add_argument("--min", type=float, default=25); s.add_argument("--limit", type=int, default=40); s.set_defaults(fn=cmd_arb)
    s = sub.add_parser("new"); s.add_argument("--limit", type=int, default=40); s.set_defaults(fn=cmd_new)
    s = sub.add_parser("stores"); s.set_defaults(fn=cmd_stores)
    f = sub.add_parser("funnel")
    f.add_argument("-n", type=int, default=300, help="products to comp")
    f.add_argument("--min-discount", type=float, default=0.10)
    f.add_argument("--max-competitors", type=int, default=150)
    f.add_argument("--duty", type=float, default=0.0)
    f.add_argument("--ad", type=float, default=0.0, help="promoted listings rate")
    f.add_argument("--postage", type=float, default=0.0, help="postage charged to buyer")
    f.add_argument("--seller-country", default="AE",
                   help="where the selling entity is established (fee-tax regime)")
    f.add_argument("--vat-registered", action="store_true", default=False)
    f.add_argument("--match-conf", type=float, default=0.6,
                   help="P(title-matched comp is the same product)")
    f.add_argument("--supply-conf", type=float, default=0.5,
                   help="P(supplier will actually sell to us at this price)")
    f.add_argument("--synthetic", action="store_true")
    f.add_argument("--sold-ratio", type=float, default=0.60,
                   help="PROVISIONAL sold/ask haircut on active comps")
    f.add_argument("--strict-identity", action="store_true", default=True,
                   help="title/set/MSRP comp filtering + condition gate")
    f.add_argument("--no-strict-identity", dest="strict_identity",
                   action="store_false")
    f.add_argument("--only-group", default=None,
                   help="draw the cohort from one stores.txt group only")
    f.add_argument("--skip-cats", default="",
                   help="comma-separated categories to exclude, e.g. clothing,shoes")
    f.set_defaults(fn=cmd_funnel)
    r = sub.add_parser("review")
    r.add_argument("-n", type=int, default=30, help="shortlist size")
    r.add_argument("--out", default="shortlist.csv")
    r.add_argument("--min-cm", type=float, default=5.0, help="min est GBP contribution")
    r.add_argument("--duty", type=float, default=0.0)
    r.add_argument("--seller-country", default="AE",
                   help="where the selling entity is established (fee-tax regime)")
    r.add_argument("--vat-registered", action="store_true", default=False)
    r.add_argument("--synthetic", action="store_true")
    r.add_argument("--only-group", default=None)
    r.set_defaults(fn=cmd_review)
    g = sub.add_parser("ingest")
    g.add_argument("file")
    g.set_defaults(fn=cmd_ingest)
    lb = sub.add_parser("labels")
    lb.set_defaults(fn=cmd_labels)
    m = sub.add_parser("measure")
    m.add_argument("--out", default="experiments/scarcity-measurement.csv.gz")
    m.add_argument("--review-out", default="experiments/scarcity-review.csv")
    m.add_argument("--review-n", type=int, default=20)
    m.set_defaults(fn=cmd_measure)
    ia = sub.add_parser("identity-audit")
    ia.add_argument("--sample-per-store", type=int, default=5)
    ia.add_argument("--out", default="experiments/identity-coverage.csv")
    ia.add_argument("--ledger-out", default="experiments/identity-ledger.csv.gz")
    ia.add_argument("--only-domain")
    ia.add_argument("--delay", type=float, default=0.15)
    ia.add_argument("--timeout", type=int, default=20)
    ia.add_argument("--workers", type=int, default=4)
    ia.add_argument("--retries", type=int, default=2)
    ia.add_argument("--resolve-ebay", action="store_true")
    ia.add_argument("--ebay-region", default="GB")
    ia.add_argument("--max-ebay-lookups", type=int, default=100)
    ia.add_argument("--ebay-detail-limit", type=int, default=50)
    ia.add_argument("--min-market-listings", type=int, default=3)
    ia.add_argument("--ebay-ledger-out",
                    default="experiments/ebay-resolution-ledger.csv.gz")
    ia.set_defaults(fn=cmd_identity_audit)
    mb = sub.add_parser("mpn-basket")
    mb.add_argument("sitemap")
    mb.add_argument("-n", type=int, default=50)
    mb.add_argument("--out", default="experiments/mpn-basket.csv")
    mb.set_defaults(fn=cmd_mpn_basket)
    ma = sub.add_parser("mpn-audit")
    ma.add_argument("--basket", default="experiments/mpn-basket.csv")
    ma.add_argument("--out", default="experiments/mpn-resolution-ledger.csv.gz")
    ma.add_argument("--ebay-region", default="US")
    ma.add_argument("--limit", type=int, default=20)
    ma.add_argument("--detail-limit", type=int, default=20)
    ma.add_argument("--min-market-listings", type=int, default=3)
    ma.set_defaults(fn=cmd_mpn_audit)
    me = sub.add_parser("mpn-economics")
    me.add_argument("--source",
                    default="experiments/mpn-source-snapshot.csv")
    me.add_argument("--resolution",
                    default="experiments/mpn-resolution-ledger.csv.gz")
    me.add_argument("--out", default="experiments/mpn-economics-ledger.csv")
    me.add_argument("--usd-to-gbp", type=float)
    me.set_defaults(fn=cmd_mpn_economics)
    ms = sub.add_parser("mpn-source-audit")
    ms.add_argument("--resolution",
                    default="experiments/mpn-resolution-ledger.csv.gz")
    ms.add_argument("--out", default="experiments/mpn-used-source-ledger.csv")
    ms.add_argument("--ebay-region", default="US")
    ms.add_argument("--min-market-listings", type=int, default=3)
    ms.add_argument("--usd-to-gbp", type=float)
    ms.add_argument("--timeout", type=int, default=20)
    ms.set_defaults(fn=cmd_mpn_source_audit)
    ml = sub.add_parser("mpn-liquidation-coverage")
    ml.add_argument("--coverage",
                    default="experiments/mpn-liquidation-coverage.csv")
    ml.add_argument("--resolution",
                    default="experiments/mpn-resolution-ledger.csv.gz")
    ml.set_defaults(fn=cmd_mpn_liquidation_coverage)
    mm = sub.add_parser("mpn-manifest-audit")
    mm.add_argument("urls", nargs="+")
    mm.add_argument("--resolution",
                    default="experiments/mpn-resolution-ledger.csv.gz")
    mm.add_argument("--out", default="experiments/mpn-manifest-ledger.csv")
    mm.add_argument("--timeout", type=int, default=30)
    mm.set_defaults(fn=cmd_mpn_manifest_audit)
    le = sub.add_parser("liquidation-exit-audit")
    le.add_argument("--universe",
                    default="experiments/mpn-manifest-unmatched-identities.csv")
    le.add_argument("--out",
                    default="experiments/liquidation-exit-resolution.csv.gz")
    le.add_argument("--ebay-region", default="US")
    le.add_argument("--min-market-listings", type=int, default=3)
    le.set_defaults(fn=cmd_liquidation_exit_audit)
    ld = sub.add_parser("liquidation-resolver-diagnostic")
    ld.add_argument("--universe",
                    default="experiments/mpn-manifest-unmatched-identities.csv")
    ld.add_argument("--out",
                    default="experiments/liquidation-resolver-diagnostic.csv.gz")
    ld.add_argument("--ebay-region", default="US")
    ld.add_argument("--min-market-listings", type=int, default=3)
    ld.set_defaults(fn=cmd_liquidation_resolver_diagnostic)
    ob = sub.add_parser("openbox-cohort")
    ob.add_argument("-n", type=int, default=30)
    ob.add_argument("--out", default="experiments/openbox-cohort.csv")
    ob.set_defaults(fn=cmd_openbox_cohort)
    bu = sub.add_parser("bundle-cohort")
    bu.add_argument("-n", type=int, default=20)
    bu.add_argument("--out", default="experiments/bundle-cohort.csv")
    bu.set_defaults(fn=cmd_bundle_cohort)
    lt = sub.add_parser("liquidation-template")
    lt.add_argument("--out", default="experiments/liquidation-manifest.csv")
    lt.set_defaults(fn=cmd_liquidation_template)
    lu = sub.add_parser("liquidation")
    lu.add_argument("file")
    lu.add_argument("--bid", type=float, required=True)
    lu.add_argument("--freight", type=float, required=True)
    lu.add_argument("--testing", type=float, default=0.0)
    lu.add_argument("--disposal", type=float, default=0.0)
    lu.add_argument("--fee-rate", type=float, default=0.15)
    lu.set_defaults(fn=cmd_liquidation)
    rc = sub.add_parser("recomp")
    rc.set_defaults(fn=cmd_recomp)
    ex = sub.add_parser("export")
    ex.set_defaults(fn=cmd_export)
    rb = sub.add_parser("rebuild")
    rb.set_defaults(fn=cmd_rebuild)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
