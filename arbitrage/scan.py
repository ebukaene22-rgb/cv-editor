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
DB = os.path.join(HERE, "prices.db")
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
    ex = sub.add_parser("export")
    ex.set_defaults(fn=cmd_export)
    rb = sub.add_parser("rebuild")
    rb.set_defaults(fn=cmd_rebuild)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
