#!/usr/bin/env python3
"""
SoldComps client -- structured eBay sold rows (Test A).

Third-party provider; obtains sold listings that eBay's own APIs do not
expose. We take their INDIVIDUAL ROWS and apply our own identity matcher
rather than trusting their aggregates -- their median is over whatever
their keyword search returned, which is exactly the contamination problem
we already measured on eBay's own search.

Provenance caveat kept visible: this is a scraping-derived service
(distributed via Apify/RapidAPI), so continuity is not guaranteed and it
must not become a load-bearing dependency without a fallback.

NOT USED: their optional X-eBay-Cookies header, which forwards your own
logged-in eBay session for extra fields. Their docs say "the risk is yours
alone" -- that is exactly the seller-account exposure we have declined
throughout.
"""
import json
import os
import statistics
import urllib.parse
import urllib.request

API = "https://api.sold-comps.com/v1/scrape"
SITE = {"GB": "ebay.co.uk", "US": "ebay.com", "EU": "ebay.de"}


def fetch(keyword, region="GB", count=200, condition=None):
    key = os.environ.get("SOLDCOMPS_API_KEY")
    if not key:
        raise RuntimeError("SOLDCOMPS_API_KEY not set")
    q = {"keyword": keyword, "count": str(count),
         "ebaySite": SITE.get(region, "ebay.com")}
    if condition:
        q["condition"] = condition
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q),
                                 headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rows(payload):
    out = []
    for it in payload.get("items", []) or []:
        p = it.get("soldPrice")
        if p is None:
            continue
        try:
            p = float(p)
        except (TypeError, ValueError):
            continue
        out.append({"title": it.get("title") or "", "price": p,
                    "currency": it.get("soldCurrency"),
                    "ended": (it.get("endedAt") or "")[:10],
                    "cond": it.get("condition"), "epid": it.get("epid"),
                    "item_id": it.get("itemId"),
                    "ship": it.get("shippingPrice"),
                    "total": it.get("totalPrice")})
    return out


def summarise(matched):
    if not matched:
        return None
    ps = sorted(r["price"] for r in matched)
    return {"n": len(ps), "median": statistics.median(ps),
            "p25": ps[max(0, len(ps) // 4 - 1)], "min": ps[0], "max": ps[-1],
            "newest": max((r["ended"] for r in matched), default=""),
            "with_epid": sum(1 for r in matched if r.get("epid"))}
