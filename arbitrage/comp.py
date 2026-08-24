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
import urllib.error
from datetime import datetime, timezone

OAUTH = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE = "https://api.ebay.com/buy/browse/v1/item_summary/search"
BROWSE_ITEMS = "https://api.ebay.com/buy/browse/v1/item/"
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

    def lookup_gtin(self, gtin, region="GB", limit=50, detail_limit=50,
                    min_market_listings=3):
        """Search active listings by exact GTIN; never synthesize identity."""
        if self.synthetic:
            raise RuntimeError(
                "exact GTIN resolution requires EBAY_CLIENT_ID and "
                "EBAY_CLIENT_SECRET")
        mkt = MARKETPLACE.get(region, "EBAY_GB")
        key = hashlib.sha1(
            f"gtin-v2|{mkt}|{gtin}|{limit}|{detail_limit}|"
            f"{min_market_listings}".encode()).hexdigest()
        row = self.conn.execute(
            "SELECT ts,payload FROM comps WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[0] < COMP_TTL:
            self.cache_hits += 1
            return json.loads(row[1])
        out = self._live_gtin(
            gtin, mkt, limit, detail_limit, min_market_listings)
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

    def _browse_json(self, url, mkt):
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.token()}",
            "X-EBAY-C-MARKETPLACE-ID": mkt,
            "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode())
        except urllib.error.HTTPError as error:
            if error.code == 429:
                time.sleep(2)
            return None
        except Exception:
            return None
        self.calls += 1
        return data

    @staticmethod
    def _item_identity(item, gtin):
        reported = "".join(ch for ch in str(item.get("gtin") or "")
                           if ch.isdigit())
        aspects = {}
        for aspect in item.get("localizedAspects", []) or []:
            name = str(aspect.get("name") or "").strip().lower()
            value = str(aspect.get("value") or "").strip().lower()
            if name and value:
                aspects[name] = value

        def value(*names):
            for name in names:
                direct = item.get(name)
                if direct not in (None, ""):
                    return str(direct).strip().lower()
                if name.lower() in aspects:
                    return aspects[name.lower()]
            return ""

        price = item.get("price") or {}
        try:
            amount = float(price["value"])
        except (KeyError, TypeError, ValueError):
            amount = None
        return {
            "id": item.get("itemId") or "", "title": item.get("title") or "",
            "gtin": reported, "exact_gtin": reported == gtin,
            "brand": value("brand"), "mpn": value("mpn"),
            "model": value("model"), "size": value("size"),
            "color": value("color", "colour"),
            "pack": value("package quantity", "unit quantity", "number in pack"),
            "category": str(item.get("categoryId") or ""),
            "lot_size": str(item.get("lotSize") or ""),
            "condition": item.get("condition") or "",
            "price": amount, "currency": price.get("currency") or "",
        }

    def _live_gtin(self, gtin, mkt, limit, detail_limit,
                   min_market_listings):
        url = BROWSE + "?" + urllib.parse.urlencode({
            "gtin": gtin, "limit": str(limit),
            "filter": "buyingOptions:{FIXED_PRICE},conditions:{NEW}"})
        data = self._browse_json(url, mkt)
        if data is None:
            return None
        summaries = data.get("itemSummaries", []) or []
        item_ids = [item.get("itemId") for item in summaries
                    if item.get("itemId")][:max(0, detail_limit)]
        details = []
        detail_failed = False
        for start in range(0, len(item_ids), 20):
            detail_url = BROWSE_ITEMS + "?" + urllib.parse.urlencode({
                "item_ids": ",".join(item_ids[start:start + 20])})
            detail_data = self._browse_json(detail_url, mkt)
            if detail_data is None:
                detail_failed = True
                continue
            details.extend(self._item_identity(item, gtin)
                           for item in detail_data.get("items", []) or [])

        exact_items = [item for item in details if item["exact_gtin"]]
        ambiguous_fields = []
        for field in ("brand", "mpn", "model", "size", "color", "pack",
                      "category", "lot_size"):
            values = {item[field] for item in exact_items if item[field]}
            if len(values) > 1:
                ambiguous_fields.append(field)
        all_inspected_exact = bool(details) and len(exact_items) == len(details)
        coherent = all_inspected_exact and not ambiguous_fields
        usable = coherent and len(exact_items) >= min_market_listings
        prices = sorted(item["price"] for item in exact_items
                        if item["price"] is not None)
        if not summaries:
            status = "NOT_FOUND"
        elif detail_failed:
            status = "API_ERROR"
        elif not exact_items:
            status = "UNCONFIRMED"
        elif not coherent:
            status = "AMBIGUOUS"
        elif usable:
            status = "EXACT_USABLE"
        else:
            status = "EXACT_SHALLOW"
        return {
            "gtin": gtin, "n": int(data.get("total", len(summaries))),
            "returned": len(summaries), "inspected": len(details),
            "exact_gtin_items": len(exact_items), "coherent": coherent,
            "usable_market": usable, "resolution_status": status,
            "ambiguous_fields": ambiguous_fields,
            "median": statistics.median(prices) if prices else None,
            "p25": prices[max(0, len(prices) // 4 - 1)] if prices else None,
            "p75": prices[min(len(prices) - 1, 3 * len(prices) // 4)]
            if prices else None,
            "currency": next((item["currency"] for item in exact_items
                              if item["currency"]), ""),
            "items": details, "synthetic": False,
        }

    @staticmethod
    def _synthetic(query, mkt):
        """Deterministic stub so ranking can be tested without a keyset."""
        h = int(hashlib.sha1(f"{mkt}|{query}".encode()).hexdigest()[:8], 16)
        return {"median": 20 + h % 180, "p25": 15 + h % 140,
                "n": 1 + h % 400, "currency": "USD", "synthetic": True}
