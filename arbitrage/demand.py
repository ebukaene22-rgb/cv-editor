#!/usr/bin/env python3
"""
First-party demand signal via Browse `estimatedSoldQuantity`.

Replaces the deleted webpage harvester entirely. eBay's Browse getItem
endpoint returns, per listing:

    estimatedAvailabilities[].estimatedSoldQuantity
    estimatedAvailabilities[].estimatedAvailableQuantity

That is transaction evidence -- units actually sold on a live listing --
obtained through the licensed API we already hold a production keyset for.
No scraping, no disguise, no login.

What it is NOT: a sold-PRICE database. It answers "does this move?", not
"at what price". Product Research (human, login-walled) remains the
valuation oracle. The two are complementary and both are needed.

Caveat carried from eBay's own docs: on a multi-variation listing the sold
quantity can aggregate across variations, so a size/colour we don't care
about can inflate a variant's apparent demand. Listing-level records are
kept raw so this stays visible rather than being averaged away.

Call economy: the BATCH getItems endpoint returns 403 on our keyset (it
needs a higher Buy-API permission tier), so details are fetched one listing
at a time. To keep that cheap, identity filtering runs FIRST on the search
titles we already hold -- only listings that are actually the product cost
a getItem call. A typical candidate spends 3-15 calls against the 5,000/day
limit.
"""
import gzip
import json
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import identity as I

ITEM = "https://api.ebay.com/buy/browse/v1/item/"


def _get(url, token, mkt):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": mkt,
        "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode())


def listing_demand(ec, query, region="GB", limit=50, max_calls=25):
    """
    -> demand evidence over IDENTITY-MATCHED listings, plus raw rows.

    Identity is applied to the search titles before any getItem call, so
    API spend scales with real matches rather than raw result count.
    """
    mkt = ec_marketplace(region)
    raw = ec.lookup(query, region=region, limit=limit)
    if not raw or not raw.get("items"):
        return None
    cands = [it for it in raw["items"]
             if it.get("id") and I.title_matches(query, it["t"])[0]]
    token = ec.token()
    rows, calls = [], 0
    for it in cands[:max_calls]:
        url = ITEM + urllib.parse.quote(it["id"], safe="")
        try:
            d = _get(url, token, mkt)
            calls += 1
        except Exception:
            continue
        ea = (d.get("estimatedAvailabilities") or [{}])[0]
        rows.append({
            "item_id": d.get("itemId"), "title": d.get("title") or it["t"],
            "price": it["p"], "currency": raw["currency"],
            "sold": ea.get("estimatedSoldQuantity"),
            "avail": ea.get("estimatedAvailableQuantity"),
            "cond": d.get("condition"),
            "seller": (d.get("seller") or {}).get("username"),
            "identity_ok": True, "why": "match",
        })
    with_sales = [r for r in rows if (r["sold"] or 0) > 0]
    return {
        "n_raw": len(raw["items"]), "n_identity": len(cands),
        "n_detailed": len(rows), "n_with_sales": len(with_sales),
        "total_sold": sum(r["sold"] or 0 for r in rows),
        "max_sold": max((r["sold"] or 0 for r in rows), default=0),
        "median_price_with_sales": (
            statistics.median([r["price"] for r in with_sales if r["price"]])
            if with_sales else None),
        "calls": calls, "rows": rows,
    }


def ec_marketplace(region):
    import comp as C
    return C.MARKETPLACE.get(region, "EBAY_US")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
