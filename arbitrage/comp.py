#!/usr/bin/env python3
"""
Resale comparables + margin scoring.

Supply-side scanning (scan.py) tells you what is cheap and what is moving.
This module answers the other half: what does it resell for, and how many
people are already selling it.

Comp source is the eBay Browse API. Two things to be clear about:

  * Browse returns ACTIVE listings only. eBay's sold-comps API (Marketplace
    Insights, 90-day sales history) is a Limited Release keyset that eBay
    does not currently grant to new applicants, and the sold-listing web UI
    blocks datacenter IPs. So "what it actually sold for" is not obtainable
    here.
  * That is survivable, because velocity does not have to come from eBay.
    scan.py already measures it directly on the supply side: a variant
    flipping available 1 -> 0 is a real unit leaving a real shelf. Browse
    supplies price and competition; the time series supplies demand.

Credentials (free keyset from developer.ebay.com):
    export EBAY_CLIENT_ID=...
    export EBAY_CLIENT_SECRET=...

Without them, `score` runs in --synthetic mode: the comp layer is replaced by
a deterministic stub so the fee model and ranking can still be exercised.
Synthetic rows are labelled and must not be traded on.
"""
import base64
import gzip
import hashlib
import json
import os
import sqlite3
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

OAUTH = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"

# eBay marketplace ids by the region codes used in stores.txt
MARKETPLACE = {"US": "EBAY_US", "GB": "EBAY_GB", "EU": "EBAY_DE",
               "CA": "EBAY_CA", "AU": "EBAY_AU"}

COMP_TTL = 6 * 3600          # seconds; comps are cached to stay inside quota

COMP_SCHEMA = """
CREATE TABLE IF NOT EXISTS comps (
  key TEXT PRIMARY KEY, ts REAL, payload TEXT
);
"""



# ------------------------------------------------------------------ comp client

class EbayComp:
    def __init__(self, conn, synthetic=False):
        self.conn = conn
        self.conn.executescript(COMP_SCHEMA)
        self.synthetic = synthetic
        self._tok = None
        self._tok_exp = 0
        self.calls = 0
        self.cache_hits = 0
        cid = os.environ.get("EBAY_CLIENT_ID")
        sec = os.environ.get("EBAY_CLIENT_SECRET")
        if not (cid and sec):
            self.synthetic = True
        self._auth = (base64.b64encode(f"{cid}:{sec}".encode()).decode()
                      if cid and sec else None)

    # -- oauth -------------------------------------------------------------
    def token(self):
        if self._tok and time.time() < self._tok_exp - 60:
            return self._tok
        body = urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": SCOPE}).encode()
        req = urllib.request.Request(OAUTH, data=body, headers={
            "Authorization": f"Basic {self._auth}",
            "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode())
        self._tok = d["access_token"]
        self._tok_exp = time.time() + int(d.get("expires_in", 7200))
        return self._tok

    # -- comp --------------------------------------------------------------
    def lookup(self, query, region="US", limit=50):
        """
        -> {'median','p25','n','currency','synthetic'} or None.

        `n` is the active-listing count for the query: the competition term.
        `median` is an ASKING price, not a realised sale price.
        """
        mkt = MARKETPLACE.get(region, "EBAY_US")
        key = hashlib.sha1(f"v3|{mkt}|{query}|{limit}".encode()).hexdigest()
        row = self.conn.execute(
            "SELECT ts,payload FROM comps WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[0] < COMP_TTL:
            self.cache_hits += 1
            return json.loads(row[1])

        out = (self._synthetic(query, mkt) if self.synthetic
               else self._live(query, mkt, limit))
        if out is not None:
            self.conn.execute("INSERT OR REPLACE INTO comps VALUES (?,?,?)",
                              (key, time.time(), json.dumps(out)))
            self.conn.commit()
        return out

    def _live(self, query, mkt, limit):
        url = BROWSE + "?" + urllib.parse.urlencode({
            "q": query[:100], "limit": str(limit),
            "filter": "buyingOptions:{FIXED_PRICE},conditions:{NEW}"})
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.token()}",
            "X-EBAY-C-MARKETPLACE-ID": mkt,
            "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                d = json.loads(raw.decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2)
            return None
        except Exception:
            return None
        self.calls += 1
        items, cur = [], None
        for it in d.get("itemSummaries", []) or []:
            p = (it.get("price") or {})
            try:
                items.append({"t": it.get("title") or "",
                              "p": float(p["value"]),
                              "id": it.get("itemId")})
                cur = cur or p.get("currency")
            except (KeyError, TypeError, ValueError):
                continue
        if not items:
            return None
        prices = sorted(i["p"] for i in items)
        return {"median": statistics.median(prices),
                "p25": prices[max(0, len(prices) // 4 - 1)],
                "n": int(d.get("total", len(prices))),
                "currency": cur or "USD", "synthetic": False,
                "items": items,
                "ids": [i["id"] for i in items if i.get("id")]}

    @staticmethod
    def _synthetic(query, mkt):
        """Deterministic stub so ranking can be tested without a keyset."""
        h = int(hashlib.sha1(f"{mkt}|{query}".encode()).hexdigest()[:8], 16)
        return {"median": 20 + h % 180, "p25": 15 + h % 140,
                "n": 1 + h % 400, "currency": "USD", "synthetic": True}


