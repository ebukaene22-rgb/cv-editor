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
import math
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


# ------------------------------------------------------------------ fee model

class Fees:
    """
    Landed-cost and net-proceeds model. Defaults are deliberately pessimistic:
    a gap that only clears an optimistic fee model is not a trade.
    """
    def __init__(self, marketplace_pct=0.132, payment_pct=0.029, payment_flat=0.30,
                 ship_per_kg=9.0, ship_base=4.0, duty_pct=0.0, return_rate=0.06):
        self.marketplace_pct = marketplace_pct   # eBay final value fee, typical
        self.payment_pct = payment_pct
        self.payment_flat = payment_flat
        self.ship_per_kg = ship_per_kg
        self.ship_base = ship_base
        self.duty_pct = duty_pct                 # set per lane; 0 is optimistic
        self.return_rate = return_rate

    def landed_cost(self, buy_price, grams):
        kg = (grams or 500) / 1000.0
        ship = self.ship_base + self.ship_per_kg * kg
        return buy_price * (1 + self.duty_pct) + ship

    def net_proceeds(self, sell_price):
        fees = (sell_price * (self.marketplace_pct + self.payment_pct)
                + self.payment_flat)
        return (sell_price - fees) * (1 - self.return_rate)

    def margin(self, buy_price, sell_price, grams):
        cost = self.landed_cost(buy_price, grams)
        if cost <= 0:
            return None, None, None
        net = self.net_proceeds(sell_price)
        return (net - cost) / cost, cost, net


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
        key = hashlib.sha1(f"{mkt}|{query}|{limit}".encode()).hexdigest()
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
        prices, cur = [], None
        for it in d.get("itemSummaries", []) or []:
            p = (it.get("price") or {})
            try:
                prices.append(float(p["value"]))
                cur = cur or p.get("currency")
            except (KeyError, TypeError, ValueError):
                continue
        if not prices:
            return None
        prices.sort()
        return {"median": statistics.median(prices),
                "p25": prices[max(0, len(prices) // 4 - 1)],
                "n": int(d.get("total", len(prices))),
                "currency": cur or "USD", "synthetic": False}

    @staticmethod
    def _synthetic(query, mkt):
        """Deterministic stub so ranking can be tested without a keyset."""
        h = int(hashlib.sha1(f"{mkt}|{query}".encode()).hexdigest()[:8], 16)
        return {"median": 20 + h % 180, "p25": 15 + h % 140,
                "n": 1 + h % 400, "currency": "USD", "synthetic": True}


# ------------------------------------------------------------------ scoring

def sell_through(conn, domain, sku, snapshots=None):
    """
    Fraction of observed intervals in which this variant went 1 -> 0.
    Measured on our own history, which is the only velocity data we have.
    """
    rows = conn.execute(
        "SELECT ts,available FROM obs WHERE domain=? AND sku=? ORDER BY ts",
        (domain, sku)).fetchall()
    if len(rows) < 2:
        return None
    flips = sum(1 for a, b in zip(rows, rows[1:]) if a[1] == 1 and b[1] == 0)
    return flips / (len(rows) - 1)


def score_row(margin, st, competitors):
    """
    margin x velocity / crowding.

    Velocity is unknown until a second snapshot exists; treat unknown as a
    neutral 0.5 rather than 0, or every candidate scores zero on day one.
    Competition is damped with a log: the 40th seller hurts far less than
    the 4th.
    """
    if margin is None or margin <= 0:
        return 0.0
    v = 0.5 if st is None else min(1.0, 0.15 + st * 4)
    return margin * v / math.log(2.718 + (competitors or 0))
