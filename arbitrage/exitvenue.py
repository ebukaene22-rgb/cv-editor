#!/usr/bin/env python3
"""
Exit-venue overlap: does a source already sell on eBay itself?

`CLOSEOUT-GATE.md` killed dealer closeout because nine of ten PASS comps were
the source's own eBay store. That established that a dual-channel dealer can
manufacture false PASSes. It did not establish how common dual-channel sources
are -- 22 of those 30 rows were one dealer. This measures the base rate over
the sources the project actually scans, before another cohort is spent.

## The API semantics this is built on

Browse's `sellers:{...}` filter fails open, and that had to be pinned down
before anything could be measured:

    unknown handle          -> filter SILENTLY DROPPED, full market returned
                               (`sellers:{zzzznotarealseller99}` + cat 58058
                                -> 9,383,904 results from other sellers)
    real handle, empty cat  -> 0 results, empty item list
                               (`sellers:{itinstock}` + cat 11450 -> 0)
    real handle, has stock  -> only that seller's items
                               (`sellers:{itinstock}` + cat 58058 -> 18,456)

A naive probe reads the first case as "this seller has 9.4M listings". The
useful consequence is the second case: a *zero* in a category holding tens of
millions of listings is proof eBay recognised the name. That gives an
existence test costing one call per candidate handle.

The earlier version of this file searched `q=<brand>` + seller filter instead.
That reported **itinstock -- the one source known for certain to run an eBay
store -- as absent**, because no itinstock listing has "itinstock" in its
title. Categories, not keywords.

## Six outcomes: name morphology is not identity

    confirmed_active   handle with listings AND independent evidence the
                       seller IS the source (storelink.py)
    candidate_active   plausible handle with listings, identity unestablished
    rejected_reseller  name matched only by containment -- an independent
                       reseller trading on the brand name
    dormant            plausible handle, zero listings in probed categories
    not_detected       no plausible handle recognised by eBay
    inconclusive       probe/API failure -- NOTHING is claimed

`confirmed_active` and `candidate_active` are reported separately and never
summed into one "active" figure.

An earlier version collapsed the first two, treating a `suffix` name match as
ownership. It is not: a reseller can register `gymshark-store` exactly as
easily as Gymshark can, and an exact handle can still be coincidence, an
abandoned registration, or an unrelated seller. Handle morphology is evidence
for a candidate, never proof of identity.

The two error costs are not symmetric, which is why presence needs far higher
precision than comp filtering:

    comp filtering     false positive -> discard a valid comp -> a
                       CONSERVATIVE profit estimate. Cheap.
    presence detection false positive -> conclude the source competes in the
                       exit venue -> can invalidate a whole sourcing
                       strategy. Expensive.

`inconclusive` rows are excluded from the denominator, never scored as
absence.

The first full sweep earned that fourth state. It exhausted the daily Browse
quota at ~2,488 calls and the last 21 domains came back all-HTTP-429. An
errored probe was being treated as "handle not real", so quota exhaustion
printed as `not_detected` -- itinstock, with 18,839 live listings confirmed
minutes earlier, reported as absent from the exit venue. Same fail-open shape
as eBay's dropped seller filter and as the self-comp bug: a failure that
renders as a confident negative. A run now aborts once the error rate crosses
`MAX_ERROR_RATE` rather than emitting a mostly-invented CSV.

An earlier version required a listing whose TITLE contained the brand name.
Calibration killed that rule: it marked itinstock -- 18,839 live listings, and
the dealer proven at SKU level to self-comp nine times -- as unattributed,
because a dealer sells Cisco and HPE, not goods branded with its own name.
Brand-in-title separates self-branded DTC stores from dealers reselling third-
party goods, so it is kept as a COLUMN (`brand_in_titles`), not a gate.

## What this cannot see

Both probes key on the store's own name. A source selling on eBay under a
handle unrelated to its domain is invisible to either. In the other
direction, a name match is not ownership: the first sweep credited
`hidie_gymshark` -- a reseller stocking Gymshark -- to gymshark.com. Only
`match_strength` 'exact'/'suffix' hits now count; 'contains' hits are
recorded in `rejected_handles` instead. Calibration found a
live example: reboxed.co.uk, a large UK refurbisher, resolves handles
`reboxed` and `reboxedstore` but shows zero listings across 19 categories --
so its real storefront is either named something else or was missed.

Every number here is a LOWER BOUND. "not_detected" means not detected, never
"not present"; "dormant" may mean "listing under another name".

    python3 -m arbitrage.exitvenue --out arbitrage/experiments/exit-venue-overlap.csv
"""
import argparse
import base64
import concurrent.futures as futures
import csv
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from arbitrage import selfcomp
from arbitrage import storelink

OAUTH = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"
MARKETPLACE = {"US": "EBAY_US", "GB": "EBAY_GB", "EU": "EBAY_DE",
               "CA": "EBAY_CA", "AU": "EBAY_AU"}

# Browse accepts exactly ONE category_id per request (two -> errorId 12030).
# Clothing: tens of millions of listings on every marketplace probed, so a
# zero here is unambiguous evidence the seller filter was honoured.
EXISTENCE_CAT = "11450"

# Root categories swept for a confirmed handle's inventory, ordered by how
# likely the project's sources are to sit in them.
INVENTORY_CATS = [
    ("11450", "Clothing/Shoes"),      ("58058", "Computers/Networking"),
    ("293",   "Consumer Electronics"), ("11700", "Home & Garden"),
    ("26395", "Health & Beauty"),      ("888",   "Sporting Goods"),
    ("15032", "Mobile/Comms"),         ("12576", "Business/Industrial"),
    ("625",   "Cameras & Photo"),      ("220",   "Toys & Hobbies"),
    ("281",   "Jewellery & Watches"),  ("1249",  "Video Games"),
]

# Handle variants a brand plausibly registers.
SUFFIXES = ("", "-uk", "uk", "-us", "us", "official", "-official",
            "_official", "store", "-store", "shop", "-shop",
            "outlet", "-outlet", "direct")

WORKERS = 8

# Abort rather than emit a CSV whose negatives are really API failures.
MAX_ERROR_RATE = 0.25


def brand_core(domain):
    """'www.stanley1913.com' -> 'stanley1913'; 'uk.foo.co.uk' -> 'foo'."""
    d = re.sub(r"^(www|uk|us|eu|ca|au|shop|store)\.", "",
               domain.strip().lower())
    return d.split(".")[0]


def brand_terms(domain):
    """Tokens that mark a listing as belonging to this brand."""
    core = brand_core(domain)
    m = re.match(r"^([a-z]+?)(\d+)$", core)
    if m:
        return {core, m.group(1)}
    return {core}


def brand_query(domain):
    core = brand_core(domain)
    m = re.match(r"^([a-z]+?)(\d+)$", core)
    return f"{m.group(1)} {m.group(2)}" if m else core


class Browse:
    def __init__(self):
        cid = os.environ.get("EBAY_CLIENT_ID")
        sec = os.environ.get("EBAY_CLIENT_SECRET")
        if not (cid and sec):
            raise SystemExit("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET required")
        self._auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
        self._tok, self._exp, self.calls = None, 0, 0
        self._lock = threading.Lock()      # probes run concurrently

    def token(self):
        with self._lock:
            if self._tok and time.time() < self._exp - 60:
                return self._tok
            return self._refresh()

    def _refresh(self):
        body = urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": SCOPE}).encode()
        req = urllib.request.Request(OAUTH, data=body, headers={
            "Authorization": f"Basic {self._auth}",
            "Content-Type": "application/x-www-form-urlencoded"})
        d = json.loads(urllib.request.urlopen(req, timeout=30).read())
        self._tok = d["access_token"]
        self._exp = time.time() + int(d.get("expires_in", 7200))
        return self._tok

    def search(self, params, mkt, retries=3):
        url = BROWSE + "?" + urllib.parse.urlencode(params)
        for attempt in range(retries):
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {self.token()}",
                "X-EBAY-C-MARKETPLACE-ID": mkt})
            try:
                with self._lock:
                    self.calls += 1
                return json.loads(
                    urllib.request.urlopen(req, timeout=30).read())
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 503) and attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return {"_error": f"HTTP {e.code}"}
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return {"_error": repr(e)[:100]}
        return {"_error": "retries exhausted"}


def seller_probe(api, handle, cat, mkt, limit=50):
    """
    One category, one seller. -> (state, total, titles)

    state is 'honoured' (filter applied -- the handle is real), 'dropped'
    (unknown handle), or 'error'.
    """
    d = api.search({"category_ids": cat, "limit": str(limit),
                    "filter": "sellers:{%s}" % handle}, mkt)
    if "_error" in d:
        return "error", None, []
    items = d.get("itemSummaries") or []
    total = int(d.get("total") or 0)
    if not items:
        # zero in a category this large means the filter WAS applied
        return "honoured", 0, []
    sellers = {((i.get("seller") or {}).get("username") or "").lower()
               for i in items}
    if sellers != {handle.lower()}:
        return "dropped", None, []
    return "honoured", total, [i.get("title") or "" for i in items]


def probe_domain(api, domain, region, verbose=True, confirm=True):
    core = brand_core(domain)
    terms = brand_terms(domain)
    mkt = MARKETPLACE.get(region, "EBAY_US")
    row = {"domain": domain, "region": region, "brand_core": core,
           "marketplace": mkt}
    notes = []

    # --- 1. which candidate handles does eBay recognise? ------------------
    # A dropped-filter probe scans the whole category (~4.3s server-side), so
    # these run concurrently; eBay's quota is per-day, not per-second.
    real, errors, rejected = [], 0, []
    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        jobs = {pool.submit(seller_probe, api, core + suf, EXISTENCE_CAT,
                            mkt, 1): core + suf for suf in SUFFIXES}
        for fut in futures.as_completed(jobs):
            handle = jobs[fut]
            state, _, _ = fut.result()
            if state == "honoured":
                real.append(handle)
            elif state == "error":
                errors += 1
                notes.append(f"{handle}:error")
    real.sort(key=len)

    # --- 2. discovery: handles the enumerator never guessed ---------------
    d = api.search({"q": brand_query(domain)[:100], "limit": "200"}, mkt)
    if "_error" in d:
        notes.append("discovery:" + d["_error"])
    else:
        for it in d.get("itemSummaries") or []:
            s = (it.get("seller") or {}).get("username")
            if not s or s.lower() in {h.lower() for h in real}:
                continue
            # Only 'exact'/'suffix' may count as the source's own store.
            # A 'contains' hit is normally a reseller leading with its own
            # name ('hidie_gymshark'), and crediting its stock to the brand
            # would invent presence rather than measure it.
            strength, why = selfcomp.match_strength(domain, s)
            if strength in ("exact", "suffix"):
                real.append(s)
            elif strength == "contains":
                rejected.append(f"{s}({strength})")

    # --- 3. inventory + brand attribution for each real handle ------------
    total_listings, attributed, where, sample = 0, False, [], ""
    probes = [(h, c, lbl) for h in real for c, lbl in INVENTORY_CATS]
    with futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        jobs = {pool.submit(seller_probe, api, h, c, mkt): (h, lbl)
                for h, c, lbl in probes}
        for fut in futures.as_completed(jobs):
            _, label = jobs[fut]
            state, n, titles = fut.result()
            if state == "error":
                errors += 1
            if state != "honoured" or not n:
                continue
            total_listings += n
            where.append(f"{label}:{n}")
            for t in titles:
                if any(term in t.lower() for term in terms):
                    attributed = True
                    sample = sample or t[:90]
                    break
    where.sort()

    # An errored probe proves nothing. Never let an API failure render as
    # absence -- that is what reported itinstock as not_detected.
    if errors and not total_listings:
        row["present"] = "inconclusive"
    elif not real:
        row["present"] = ("rejected_reseller" if rejected else "not_detected")
    elif total_listings > 0:
        confirmed = ""
        if confirm:
            linked, _, _ = storelink.brand_ebay_handles(domain)
            for h in real:
                ok, why = storelink.confirms(domain, h, linked=linked)
                if ok:
                    confirmed = why
                    break
        row["present"] = "confirmed_active" if confirmed else "candidate_active"
        row["identity_evidence"] = confirmed
    else:
        row["present"] = "dormant"
    row["errors"] = errors

    row["brand_in_titles"] = "yes" if attributed else "no"
    row["rejected_handles"] = "|".join(rejected)
    row["handles"] = "|".join(real)
    row["listings"] = total_listings
    row["categories"] = ";".join(where[:6])
    row["sample_title"] = sample
    row["notes"] = ";".join(notes)
    if verbose:
        print(f"  {domain:32} {row['present']:13} "
              f"{row['handles'][:30]:30} {total_listings:>8}",
              file=sys.stderr, flush=True)
    return row


def read_stores(path):
    out = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        if len(f) >= 4:
            out.append((f[1], f[3]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", default="arbitrage/stores.txt")
    ap.add_argument("--extra", default="", help="comma-separated extra domains")
    ap.add_argument("--extra-region", default="GB")
    ap.add_argument("--out",
                    default="arbitrage/experiments/exit-venue-overlap.csv")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true",
                    help="keep resolved rows in --out, re-probe only "
                         "inconclusive/missing ones")
    a = ap.parse_args(argv)

    doms = read_stores(a.stores)
    for d in [x.strip() for x in a.extra.split(",") if x.strip()]:
        # "domain:REGION" -- serverpartdeals probed on EBAY_GB returned 1
        # listing; it is a US seller and belongs on EBAY_US.
        dom, _, reg = d.partition(":")
        doms.append((dom, reg or a.extra_region))
    if a.limit:
        doms = doms[:a.limit]

    prior = {}
    if a.resume and os.path.exists(a.out):
        for r in csv.DictReader(open(a.out)):
            if r.get("present") not in (None, "", "inconclusive"):
                prior[r["domain"]] = r
        print(f"resume: {len(prior)} rows already resolved", file=sys.stderr)

    api = Browse()
    todo = [(d, r) for d, r in doms if d not in prior]
    print(f"probing {len(todo)} domains", file=sys.stderr)
    rows, errored = [], 0
    for d, r in doms:
        if d in prior:
            rows.append(prior[d])
            continue
        row = probe_domain(api, d, r)
        rows.append(row)
        errored += 1 if row["present"] == "inconclusive" else 0
        done = len(rows) - len(prior)
        if done >= 8 and errored / done > MAX_ERROR_RATE:
            print(f"\nABORT: {errored}/{done} domains inconclusive -- the API "
                  f"is failing, not the sources. Partial results written; "
                  f"re-run with --resume.", file=sys.stderr)
            for d2, r2 in doms[len(rows):]:
                rows.append({"domain": d2, "region": r2,
                             "present": "inconclusive", "notes": "not probed"})
            break

    cols = ["domain", "region", "brand_core", "marketplace", "present",
            "brand_in_titles", "identity_evidence", "handles",
            "rejected_handles", "listings", "categories", "errors",
            "sample_title", "notes"]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})

    import collections
    tally = collections.Counter(r["present"] for r in rows)
    inc = tally["inconclusive"]
    resolved = len(rows) - inc
    print("", file=sys.stderr)
    for state in ("confirmed_active", "candidate_active", "rejected_reseller",
                  "dormant", "not_detected", "inconclusive"):
        print(f"  {state:18} {tally[state]:>4}", file=sys.stderr)
    if resolved:
        print(f"\nCONFIRMED active : {tally['confirmed_active']}/{resolved} "
              f"({tally['confirmed_active']/resolved:.1%})", file=sys.stderr)
        print(f"CANDIDATE active : {tally['candidate_active']}/{resolved} "
              f"({tally['candidate_active']/resolved:.1%})  "
              f"-- identity NOT established", file=sys.stderr)
    print("all figures are LOWER BOUNDS on presence", file=sys.stderr)
    if inc:
        print(f"INCONCLUSIVE (API errors, excluded): {inc} "
              f"-- re-run with --resume", file=sys.stderr)
    print(f"eBay calls: {api.calls}  ->  {a.out}", file=sys.stderr)
    return rows


if __name__ == "__main__":
    main()
