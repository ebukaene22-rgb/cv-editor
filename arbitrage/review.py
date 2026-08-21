#!/usr/bin/env python3
"""
Terapeak-assisted manual review loop.

eBay Product Research (Terapeak) has the data the APIs will not give us --
actual sold prices, sold counts, sell-through -- but only through a
logged-in dashboard. Automating that dashboard is against eBay's ToS and
brittle besides, so this module deliberately automates everything EXCEPT
Terapeak:

    scan.py review          -> shortlist.csv   (automated columns filled,
                                                manual columns blank)
    ... human fills 3 columns from Product Research, ~1 min/row ...
    scan.py ingest FILE     -> labels stored, joined to frozen features
    scan.py labels          -> what the labeled dataset says so far

Product identity is a FIRST-CLASS STAGE, before sold-price validation.
Manual matching proved unreliable when treated as an implicit step: messy
titles, no visible identifiers, and the temptation to force a fuzzy match
that contaminates the economics. So every row is labeled with match_status
before any sold price counts:

  exact     same brand, product line, product type, and materially
            important variant/size/pack
  close     same product family, a non-critical variant differs
  weak      only broadly similar product
  no_match  no trustworthy equivalent found

Only `exact` feeds profitability. `close` is stored as directional context.
`weak`/`no_match` sold prices are DISCARDED at ingest.

TIMEBOX RULE: 2-3 minutes per row without a trustworthy exact match ->
mark no_match and move on. The batch measures the matching bottleneck; it
does not rescue candidates.

Identifier audit (what the public feeds actually give us): UPC/EAN/GTIN is
structurally absent -- Shopify only exposes `barcode` via the authed Admin
API, so no fuzzy substitute is built. Retailer SKUs cover ~98% of rows and
are style codes on branded stores (Allbirds A11718M080, Gymshark
B5C9W-PCQR-M) that eBay sellers often put in titles/item specifics -- the
sheet surfaces them for use as a secondary search. product_type is captured
for match-rate-by-category reporting.

The point of the exercise is not the verdicts themselves but the LABELED
DATASET: after 100-200 rows we can test which automated signals (spread,
competition, stockouts, markdown depth, brand, region gap) actually predict
a viable trade -- the moment the scanner stops being heuristic.

Feature freezing: every automated signal is persisted into `candidates` at
the moment the sheet is generated. Labels only ever fill in manual columns
on that frozen row. If labels joined against live data instead, features
would drift between shortlisting and labeling and every correlation would
be contaminated by hindsight.
"""
import csv
import io
import re
import sys
import urllib.parse
from datetime import datetime, timezone

import comp as C
import fees as F
import signals as S

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  created_ts    TEXT NOT NULL,
  snapshot_ts   TEXT NOT NULL,
  domain        TEXT NOT NULL,
  product_key   TEXT NOT NULL,
  title         TEXT, vendor TEXT, region TEXT, category TEXT,
  supply_url    TEXT, sku TEXT, ptype TEXT,
  -- frozen supply-side features
  supply_gbp    REAL,     -- cheapest in-stock variant, GBP
  list_gbp      REAL,     -- compare-at price, GBP
  markdown      REAL,     -- 1 - supply/list
  n_variants    INTEGER,  -- in-stock variants under this product
  grams         INTEGER,
  region_gap    REAL,     -- max cross-region price ratio - 1, if known
  -- frozen depletion features
  dep_conf      TEXT, dep_cycles INTEGER, dep_stockouts INTEGER,
  dep_oos_frac  REAL,
  -- frozen active-comp features
  comp_median   REAL, comp_p25 REAL, comp_n INTEGER, comp_synthetic INTEGER,
  active_spread REAL,   -- (median - p25) / median
  -- frozen economics
  est_cm        REAL, est_roi_cost REAL, est_cm_rev REAL,
  seller_country TEXT, fee_tax REAL,
  -- manual identity labels (filled BEFORE sold prices)
  match_status       TEXT,     -- exact | close | weak | no_match
  match_query_used   TEXT,
  match_confidence   REAL,     -- 0-1, reviewer's own confidence
  match_notes        TEXT,
  -- manual labels (from Product Research / Terapeak)
  manual_sold_median REAL,
  manual_sold_90d    INTEGER,
  manual_verdict     TEXT,     -- viable | marginal | dead
  manual_notes       TEXT,
  labeled_ts         TEXT,
  UNIQUE(domain, product_key, snapshot_ts)
);
"""

AUTO_COLS = ["id", "candidate", "sku", "product_type", "supply_url",
             "supply_local", "supply_gbp", "list_gbp", "markdown_pct",
             "est_cm_gbp", "est_roi_cost_pct", "est_cm_rev_pct",
             "active_median_gbp",
             "active_p25_gbp", "active_sellers", "stockout_signal",
             "category", "store", "terapeak_query", "terapeak_url"]
MANUAL_COLS = ["match_status", "match_query_used", "match_confidence",
               "match_notes",
               "manual_sold_median", "manual_sold_90d", "manual_verdict",
               "manual_notes"]
VERDICTS = {"viable", "marginal", "dead"}
MATCH_STATUSES = {"exact", "close", "weak", "no_match"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_title(title):
    """
    Reduce a storefront title to its commercial core -- the tokens a buyer
    would actually type. Discovered the hard way: passing the raw title
    ("Gymshark | Be a visionary. Gymshark VItal Warm Leggings - Base Green
    Marl") to Product Research returns zero sold results every time. The
    tagline, duplicated brand, and colourway all have to go.
    """
    t = title or ""
    # store prefix/suffix segments around pipes: keep the longest segment
    if "|" in t:
        t = max(t.split("|"), key=len)
    # marketing sentences: keep what follows the last full stop that has
    # text after it ("Be a visionary. Gymshark Vital ..." -> "Gymshark
    # Vital ...") -- but don't split decimals or initials
    parts = [p.strip() for p in re.split(r"(?<=[a-z])\.\s+", t) if p.strip()]
    if len(parts) > 1:
        t = parts[-1]
    # variant/colour tails: after "/" and the final " - Colour" segment
    t = re.sub(r"\s*/\s*[^/]*$", "", t)
    if " - " in t:
        t = t.rsplit(" - ", 1)[0]
    t = re.sub(r"[^\w\s-]", " ", t)
    return t


def product_key(row):
    t = clean_title(row["title"])
    words = (row["vendor"] or "").split() + t.split()
    # dedupe repeated tokens case-insensitively, preserve order (kills the
    # "Gymshark ... Gymshark ..." duplication), cap at 7 tokens
    seen, out = set(), []
    for w in words:
        k = w.lower()
        if k not in seen:
            seen.add(k)
            out.append(w)
        if len(out) == 7:
            break
    return " ".join(out)[:80]


def terapeak_url(query):
    # Research dashboard, sold view, last 90 days. Login required -- by design.
    return ("https://www.ebay.co.uk/sh/research?" + urllib.parse.urlencode(
        {"marketplace": "EBAY-GB", "keywords": query, "dayRange": "90",
         "tabName": "SOLD"}))


CAND_CSV = "history/candidates.csv"


def dump_candidates(conn):
    """
    Mirror the candidates table (frozen features + labels) to a committed
    CSV. prices.db is ephemeral and gitignored; the labeled dataset is the
    whole point of this module, so it must survive the container.
    """
    import os
    os.makedirs("history", exist_ok=True)
    cur = conn.execute("SELECT * FROM candidates ORDER BY id")
    cols = [d[0] for d in cur.description]
    with open(CAND_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(cur)


def load_candidates(conn):
    """Restore the candidates table from the committed CSV, if present."""
    import os
    conn.executescript(SCHEMA)
    if not os.path.exists(CAND_CSV):
        return 0
    with open(CAND_CSV, newline="") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames
        rows = [[r[c] if r[c] != "" else None for c in cols] for r in rd]
    conn.executemany(
        f"INSERT OR IGNORE INTO candidates ({','.join(cols)}) "
        f"VALUES ({','.join('?' * len(cols))})", rows)
    conn.commit()
    return len(rows)




class _CheckedWriter:
    """csv.writer that refuses rows whose width differs from the header --
    a short row silently misaligns manual columns in every spreadsheet."""
    def __init__(self, f, ncols):
        self._w = csv.writer(f)
        self._n = ncols

    def writerow(self, row):
        if len(row) != self._n:
            raise ValueError(f"row has {len(row)} fields, header has {self._n}")
        self._w.writerow(row)

# ------------------------------------------------------------------ review

def generate(conn, args, cur_ts, rates):
    """Build the shortlist, freeze features, emit the review CSV."""
    conn.executescript(SCHEMA)
    gbp = rates.get("GBP") or 0.79

    def to_gbp(v, ccy):
        return None if v is None else (v / (rates.get(ccy) or 1.0)) * gbp

    rows = conn.execute("""
        SELECT domain, region, sku, title, vendor, price, compare, currency,
               grams, url, ptype
        FROM obs WHERE ts=? AND available=1 AND price>0
              AND compare IS NOT NULL AND compare > price""",
        (cur_ts,)).fetchall()

    # group variants -> products, keep cheapest in-stock variant
    prods = {}
    for r in rows:
        k = (r["domain"], product_key(r).lower())
        g = to_gbp(r["price"], r["currency"])
        if g is None:
            continue
        p = prods.setdefault(k, {"row": r, "gbp": g, "n": 0,
                                 "key": product_key(r)})
        p["n"] += 1
        if g < p["gbp"]:
            p["row"], p["gbp"] = r, g

    # cross-region gap per product key (same title different domains)
    by_title = {}
    for (dom, kt), p in prods.items():
        by_title.setdefault(kt, []).append(p["gbp"])
    gap = {kt: (max(v) / min(v) - 1) if len(v) > 1 and min(v) > 0 else None
           for kt, v in by_title.items()}

    ranked = sorted(prods.values(),
                    key=lambda p: -(1 - p["row"]["price"] / p["row"]["compare"]))
    ranked = ranked[:args.n * 3]           # headroom: some fail comping

    sig_cache = {}
    ec = C.EbayComp(conn, synthetic=args.synthetic)
    out, skipped_labeled = [], 0
    for p in ranked:
        if len(out) >= args.n:
            break
        r = p["row"]
        kt = product_key(r).lower()
        # skip anything already labeled: review time is the scarce resource
        if conn.execute(
            "SELECT 1 FROM candidates WHERE domain=? AND product_key=? "
            "AND manual_verdict IS NOT NULL", (r["domain"], kt)).fetchone():
            skipped_labeled += 1
            continue
        c = ec.lookup(p["key"], region="GB")
        if not c:
            continue
        med = to_gbp(c["median"], c["currency"])
        p25 = to_gbp(c["p25"], c["currency"])
        cat = F.categorise(r["title"] or "", r["vendor"] or "")
        econ = F.Economics(category=cat, buyer_region="UK",
                           seller_country=args.seller_country,
                           vat_registered=args.vat_registered,
                           duty_rate=args.duty)
        cm, margin, bd = econ.contribution(p["gbp"], med, r["grams"])
        if cm is None or cm < args.min_cm:
            continue
        if r["domain"] not in sig_cache:
            sig_cache[r["domain"]] = S.depletion_signals(conn, r["domain"])
        sig = sig_cache[r["domain"]].get(r["sku"]) or {}
        list_gbp = to_gbp(r["compare"], r["currency"])
        cur = conn.execute("""
            INSERT OR IGNORE INTO candidates
              (created_ts, snapshot_ts, domain, product_key, title, vendor,
               region, category, supply_url, sku, ptype, supply_gbp,
               list_gbp, markdown, n_variants,
               grams, region_gap, dep_conf, dep_cycles, dep_stockouts,
               dep_oos_frac, comp_median, comp_p25, comp_n, comp_synthetic,
               active_spread, est_cm, est_roi_cost, est_cm_rev,
               seller_country, fee_tax)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (now(), cur_ts, r["domain"], kt, r["title"], r["vendor"],
             r["region"], cat, r["url"],
             None if (r["sku"] or "").startswith(("gid:", "wid:")) else r["sku"],
             r["ptype"], p["gbp"], list_gbp,
             1 - r["price"] / r["compare"], p["n"], r["grams"], gap.get(kt),
             sig.get("confidence"), sig.get("cycles"), sig.get("stockouts"),
             sig.get("oos_frac"), med, p25, c["n"],
             1 if c.get("synthetic") else 0,
             (med - p25) / med if med else None, cm, margin,
             bd.get("cm_rev_pct"), args.seller_country, bd.get("fee_tax")))
        if cur.rowcount == 0:      # same product+snapshot already sheeted
            continue
        out.append((cur.lastrowid, p, r, c, med, p25, cm, margin, bd, cat, sig))
    conn.commit()

    header = AUTO_COLS + MANUAL_COLS
    w = _CheckedWriter(open(args.out, "w", newline=""), len(header))
    w.writerow(header)
    for cid, p, r, c, med, p25, cm, margin, bd, cat, sig in out:
        stk = (f"{sig.get('confidence','none')}"
               f"/{sig.get('cycles',0)}cyc/{sig.get('stockouts',0)}so")
        sku = "" if (r["sku"] or "").startswith(("gid:", "wid:")) else (r["sku"] or "")
        w.writerow([cid, p["key"], sku, r["ptype"] or "",
                    r["url"] or f"https://{r['domain']}",
                    f"{r['currency']} {r['price']:.2f}",   # as the store shows it
                    f"{p['gbp']:.2f}",
                    f"{to_gbp(r['compare'], r['currency']):.2f}",
                    f"{(1 - r['price']/r['compare'])*100:.0f}",
                    f"{cm:.2f}", f"{margin*100:.0f}",
                    f"{(bd.get('cm_rev_pct') or 0)*100:.0f}",
                    f"{med:.2f}", f"{p25:.2f}", c["n"], stk, cat,
                    r["domain"], p["key"], terapeak_url(p["key"])]
                   + [""] * len(MANUAL_COLS))
    dump_candidates(conn)
    syn = "  [SYNTHETIC COMPS]" if ec.synthetic else ""
    print(f"wrote {len(out)} candidates -> {args.out}{syn}")
    print(f"frozen features mirrored to {CAND_CSV} -- commit it")
    _, _, probe = F.Economics(seller_country=args.seller_country,
                              vat_registered=args.vat_registered
                              ).contribution(10, 20, 500)
    if probe["fee_tax_note"]:
        print(f"!! {probe['fee_tax_note']}")
    if skipped_labeled:
        print(f"skipped {skipped_labeled} already-labeled products")
    print(f"""
REVIEW RULES (identity first, economics second):
  1. match_status is REQUIRED per reviewed row: exact | close | weak | no_match
     exact = same brand, product line, type, and materially important
     variant/size/pack. When in doubt, it is not exact.
  2. Only `exact` rows may carry manual_sold_median / manual_sold_90d for
     economics. `close` sold data is kept as directional context only.
     weak/no_match sold data is discarded at ingest.
  3. TIMEBOX: 2-3 min without a trustworthy exact match -> no_match, move on.
     This batch measures the matching bottleneck, not rescue rate.
  4. The sku column is the retailer style code -- try it as a second search
     if the title query fails; note what worked in match_query_used.
Then:  scan.py ingest {args.out}""")


# ------------------------------------------------------------------ ingest

def ingest(conn, path):
    conn.executescript(SCHEMA)
    ok = bad = blank = 0
    errors = []
    discarded_sold = 0
    with open(path, newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            ms = (row.get("match_status") or "").strip().lower().replace("-", "_")
            verdict = (row.get("manual_verdict") or "").strip().lower()
            touched = ms or verdict or (row.get("manual_sold_median") or "").strip()
            if not touched:
                blank += 1
                continue
            if not ms:
                errors.append(f"  line {i}: reviewed but match_status missing "
                              f"(one of {sorted(MATCH_STATUSES)})")
                bad += 1
                continue
            if ms not in MATCH_STATUSES:
                errors.append(f"  line {i}: match_status '{ms}' not in "
                              f"{sorted(MATCH_STATUSES)}")
                bad += 1
                continue
            if verdict and verdict not in VERDICTS:
                errors.append(f"  line {i}: verdict '{verdict}' not in "
                              f"{sorted(VERDICTS)}")
                bad += 1
                continue
            try:
                cid = int(row["id"])
            except (KeyError, ValueError):
                errors.append(f"  line {i}: missing/invalid id")
                bad += 1
                continue
            def num(k, cast=float):
                v = (row.get(k) or "").strip().replace("£", "").replace(",", "")
                return cast(v) if v else None
            try:
                sold_med = num("manual_sold_median")
                sold_90 = num("manual_sold_90d", int)
                mconf = num("match_confidence")
            except ValueError:
                errors.append(f"  line {i}: non-numeric sold/confidence fields")
                bad += 1
                continue
            if mconf is not None and mconf > 1:
                mconf = mconf / 100.0          # accept 0-100 as well as 0-1
            # identity gate: sold prices only survive exact/close matches
            if ms in ("weak", "no_match") and (sold_med or sold_90):
                sold_med = sold_90 = None
                discarded_sold += 1
            n = conn.execute("""
                UPDATE candidates SET match_status=?, match_query_used=?,
                  match_confidence=?, match_notes=?,
                  manual_sold_median=?, manual_sold_90d=?,
                  manual_verdict=?, manual_notes=?, labeled_ts=?
                WHERE id=?""",
                (ms, (row.get("match_query_used") or "").strip() or None,
                 mconf, (row.get("match_notes") or "").strip() or None,
                 sold_med, sold_90, verdict or None,
                 (row.get("manual_notes") or "").strip() or None,
                 now(), cid)).rowcount
            if n:
                ok += 1
            else:
                errors.append(f"  line {i}: id {cid} not in candidates")
                bad += 1
    conn.commit()
    dump_candidates(conn)
    print(f"labeled {ok} rows  ({blank} left blank, {bad} rejected)")
    if discarded_sold:
        print(f"  {discarded_sold} weak/no_match rows had sold prices -- "
              "discarded (identity gate)")
    print(f"labels mirrored to {CAND_CSV} -- commit it")
    for e in errors[:10]:
        print(e)


# ------------------------------------------------------------------ labels

def report(conn):
    conn.executescript(SCHEMA)
    rows = conn.execute("SELECT * FROM candidates "
                        "WHERE match_status IS NOT NULL").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    if not rows:
        print(f"no labels yet ({total} candidates sheeted).")
        return
    n = len(rows)

    # 1+2: match distribution
    from collections import Counter, defaultdict
    dist = Counter(r["match_status"] for r in rows)
    print(f"MATCH DISTRIBUTION  ({n} reviewed of {total} sheeted)")
    for st in ("exact", "close", "weak", "no_match"):
        c = dist.get(st, 0)
        print(f"  {st:<9} {c:>4}  {c/n*100:5.1f}%")

    # 3: viability conditional on exact
    exact = [r for r in rows if r["match_status"] == "exact"]
    print(f"\nVIABILITY | EXACT MATCH")
    if not exact:
        print("  no exact matches yet -- economics has no denominator")
    else:
        v = Counter(r["manual_verdict"] or "unjudged" for r in exact)
        for k in ("viable", "marginal", "dead", "unjudged"):
            if v.get(k):
                print(f"  {k:<9} {v[k]:>4}  {v[k]/len(exact)*100:5.1f}%")
        judged = [r for r in exact if r["manual_verdict"]]
        if judged:
            vr = sum(1 for r in judged if r["manual_verdict"] == "viable")
            print(f"  -> P(viable | exact, judged) = {vr}/{len(judged)} "
                  f"= {vr/len(judged)*100:.0f}%")
        pairs = [(r["comp_median"], r["manual_sold_median"]) for r in exact
                 if r["comp_median"] and r["manual_sold_median"]
                 and not r["comp_synthetic"]]
        if pairs:
            ratios = sorted(s / a for a, s in pairs)
            print(f"  sold/asking ratio (exact only, n={len(pairs)}): "
                  f"median {ratios[len(ratios)//2]:.2f}")

    # 4: exact-match rate by store and category
    def by(key, label):
        g = defaultdict(lambda: [0, 0])
        for r in rows:
            g[r[key] or "?"][0] += 1
            if r["match_status"] == "exact":
                g[r[key] or "?"][1] += 1
        print(f"\nEXACT-MATCH RATE BY {label}")
        for k, (tot, ex) in sorted(g.items(), key=lambda x: -x[1][0]):
            print(f"  {str(k)[:34]:<34} n={tot:<4} exact {ex/tot*100:4.0f}%")
    by("domain", "STORE")
    by("ptype", "PRODUCT TYPE (source feed)")

    # 5: are missing identifiers driving match failure?
    print(f"\nIDENTIFIERS vs MATCH FAILURE")
    has = [r for r in rows if r["sku"]]
    no = [r for r in rows if not r["sku"]]
    for lbl, grp in (("has retailer sku", has), ("no sku", no)):
        if grp:
            ex = sum(1 for r in grp if r["match_status"] == "exact")
            nm = sum(1 for r in grp if r["match_status"] == "no_match")
            print(f"  {lbl:<18} n={len(grp):<4} exact {ex/len(grp)*100:4.0f}%  "
                  f"no_match {nm/len(grp)*100:4.0f}%")
    print("  (UPC/EAN/GTIN structurally absent from public Shopify feeds --"
          "\n   the only identifier available is the retailer style code)")

    fails = [r for r in rows if r["match_status"] in ("weak", "no_match")
             and r["match_notes"]]
    if fails:
        print(f"\n  failure notes ({len(fails)}):")
        for r in fails[:8]:
            print(f"    [{r['match_status']}] {(r['title'] or '')[:38]}: "
                  f"{r['match_notes'][:60]}")

    if n < 100:
        print(f"\n{100 - n} more labels before rates here are worth "
              "believing; small-n percentages are noise with confidence.")
