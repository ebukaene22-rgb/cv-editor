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

CONDITION_IDS = {
    "new": "1000", "open_box": "1500",
    "certified_refurbished": "2000", "used": "3000",
    "for_parts": "7000",
}


def marketplace_id(region):
    """Return a supported marketplace id; never silently change markets."""
    code = str(region or "").strip().upper()
    if code not in MARKETPLACE:
        supported = ", ".join(sorted(MARKETPLACE))
        raise ValueError(f"unsupported eBay region {region!r}; use {supported}")
    return MARKETPLACE[code]


def canonical_mpn(value):
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


_BRAND_ALIASES = {
    "ge": "generalelectric",
    "blackdecker": "blackanddecker",
    "kitchenaid": "kitchenaid",
}


def canonical_brand(value):
    brand = "".join(ch for ch in str(value or "").lower() if ch.isalnum())
    brand = {
        "lgelectronics": "lg", "lgelectronicsappliance": "lg",
        "samsungelectronics": "samsung", "samsungappliances": "samsung",
        "laskometalproducts": "lasko", "sharpelectronics": "sharp",
        "frigidairecoelectrolux": "frigidaire",
    }.get(brand, brand)
    return _BRAND_ALIASES.get(brand, brand)

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
        mkt = marketplace_id(region)
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
                    min_market_listings=3, condition=None):
        """Search active listings by exact GTIN; never synthesize identity."""
        if self.synthetic:
            raise RuntimeError(
                "exact GTIN resolution requires EBAY_CLIENT_ID and "
                "EBAY_CLIENT_SECRET")
        mkt = marketplace_id(region)
        key = hashlib.sha1(
            f"gtin-v5|{mkt}|{gtin}|{condition}|{limit}|{detail_limit}|"
            f"{min_market_listings}".encode()).hexdigest()
        row = self.conn.execute(
            "SELECT ts,payload FROM comps WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[0] < COMP_TTL:
            self.cache_hits += 1
            return json.loads(row[1])
        out = self._live_gtin(
            gtin, mkt, limit, detail_limit, min_market_listings, condition)
        if out is not None:
            self.conn.execute("INSERT OR REPLACE INTO comps VALUES (?,?,?)",
                              (key, time.time(), json.dumps(out)))
            self.conn.commit()
        return out

    def lookup_mpn(self, brand, mpn, region="US", limit=20,
                   detail_limit=20, min_market_listings=3, condition="new"):
        """Search by brand + MPN and confirm both from item detail fields."""
        return self._lookup_brand_identifier(
            brand, mpn, "mpn", region, limit, detail_limit,
            min_market_listings, condition)

    def lookup_model(self, brand, model, region="US", limit=20,
                     detail_limit=20, min_market_listings=3, condition=None):
        """Search by brand + model and confirm an exact model or MPN field."""
        return self._lookup_brand_identifier(
            brand, model, "model", region, limit, detail_limit,
            min_market_listings, condition)

    def _lookup_brand_identifier(self, brand, identifier, identity_kind,
                                 region, limit, detail_limit,
                                 min_market_listings, condition):
        if self.synthetic:
            raise RuntimeError(
                "exact MPN resolution requires EBAY_CLIENT_ID and "
                "EBAY_CLIENT_SECRET")
        mkt = marketplace_id(region)
        brand_key = canonical_brand(brand)
        identifier_key = canonical_mpn(identifier)
        if not brand_key or not identifier_key:
            raise ValueError("brand and identifier are required")
        key = hashlib.sha1(
            f"{identity_kind}-v4|{mkt}|{brand_key}|{identifier_key}|"
            f"{condition}|{limit}|{detail_limit}|"
            f"{min_market_listings}".encode()).hexdigest()
        row = self.conn.execute(
            "SELECT ts,payload FROM comps WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[0] < COMP_TTL:
            self.cache_hits += 1
            cached = json.loads(row[1])
            if cached.get("identity_rule_version") == 4:
                return cached
            return self._classify_mpn_result(
                brand, identifier, cached.get("items", []), cached.get("n", 0),
                cached.get("returned", 0),
                cached.get("resolution_status") == "API_ERROR",
                min_market_listings, condition, identity_kind)
        out = self._live_mpn(
            brand, identifier, mkt, limit, detail_limit, min_market_listings,
            condition, identity_kind)
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
            "gtin": reported, "exact_gtin": bool(gtin) and reported == gtin,
            "brand": value("brand"), "mpn": value("mpn"),
            "model": value("model"), "size": value("size"),
            "color": value("color", "colour"),
            "pack": value("package quantity", "unit quantity", "number in pack"),
            "category": str(item.get("categoryId") or ""),
            "lot_size": str(item.get("lotSize") or ""),
            "condition": item.get("condition") or "",
            "condition_id": str(item.get("conditionId") or ""),
            "price": amount, "currency": price.get("currency") or "",
        }

    def _live_gtin(self, gtin, mkt, limit, detail_limit,
                   min_market_listings, condition=None):
        params = {"gtin": gtin, "limit": str(limit),
                  "filter": self._search_filter(condition)}
        url = BROWSE + "?" + urllib.parse.urlencode(params)
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
                # Some production keysets can search and get one item but do
                # not have permission for the bulk getItems method.
                for item_id in item_ids[start:start + 20]:
                    item_url = BROWSE_ITEMS + urllib.parse.quote(
                        item_id, safe="")
                    item_data = self._browse_json(item_url, mkt)
                    if item_data is None:
                        detail_failed = True
                    else:
                        details.append(self._item_identity(item_data, gtin))
                continue
            details.extend(self._item_identity(item, gtin)
                           for item in detail_data.get("items", []) or [])

        gtin_items = [item for item in details if item["exact_gtin"]]
        exact_items = [item for item in gtin_items
                       if condition is None or self._condition_matches(
                           item.get("condition"), condition,
                           item.get("condition_id"))]
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
            "exact_gtin_items": len(gtin_items),
            "exact_condition_gtin_items": len(exact_items),
            "condition_family": condition or "unfiltered",
            "coherent_depth": len(exact_items) if coherent else 0,
            "coherent": coherent,
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

    def _live_mpn(self, brand, mpn, mkt, limit, detail_limit,
                  min_market_listings, condition="new", identity_kind="mpn"):
        query = f"{brand} {mpn}"
        params = {"q": query[:100], "limit": str(limit),
                  "filter": self._search_filter(condition)}
        url = BROWSE + "?" + urllib.parse.urlencode(params)
        data = self._browse_json(url, mkt)
        if data is None:
            return None
        summaries = data.get("itemSummaries", []) or []
        item_ids = [item.get("itemId") for item in summaries
                    if item.get("itemId")][:max(0, detail_limit)]
        details = []
        detail_failed = False
        for start in range(0, len(item_ids), 20):
            batch = item_ids[start:start + 20]
            detail_url = BROWSE_ITEMS + "?" + urllib.parse.urlencode({
                "item_ids": ",".join(batch)})
            detail_data = self._browse_json(detail_url, mkt)
            if detail_data is None:
                for item_id in batch:
                    item_url = BROWSE_ITEMS + urllib.parse.quote(
                        item_id, safe="")
                    item_data = self._browse_json(item_url, mkt)
                    if item_data is None:
                        detail_failed = True
                    else:
                        details.append(self._item_identity(item_data, ""))
                continue
            details.extend(self._item_identity(item, "")
                           for item in detail_data.get("items", []) or [])

        return self._classify_mpn_result(
            brand, mpn, details, int(data.get("total", len(summaries))),
            len(summaries), detail_failed, min_market_listings, condition,
            identity_kind)

    @staticmethod
    def _search_filter(condition):
        base = "buyingOptions:{FIXED_PRICE}"
        if condition is None:
            return base
        if condition == "broad_used":
            return base + ",conditions:{USED}"
        if condition == "broad_new":
            return base + ",conditions:{NEW}"
        if condition not in CONDITION_IDS:
            raise ValueError(f"unsupported condition family {condition!r}")
        return base + ",conditionIds:{" + CONDITION_IDS[condition] + "}"

    @staticmethod
    def _condition_matches(value, expected, condition_id=""):
        if expected is None:
            return True
        if expected == "broad_used":
            return str(condition_id or "") in {
                "3000", "4000", "5000", "6000", "7000"}
        if expected == "broad_new":
            return str(condition_id or "") in {"1000", "1500", "1750"}
        if str(condition_id or "") == CONDITION_IDS.get(expected):
            return True
        actual = "".join(ch for ch in str(value or "").casefold()
                         if ch.isalnum())
        if expected == "new":
            return actual == "new"
        if expected == "open_box":
            return "openbox" in actual
        if expected == "certified_refurbished":
            return "certifiedrefurbished" in actual
        if expected == "used":
            return actual.startswith("used")
        raise ValueError(f"unsupported condition family {expected!r}")

    @staticmethod
    def _classify_mpn_result(brand, mpn, details, active_total, returned,
                             detail_failed, min_market_listings,
                             condition="new", identity_kind="mpn"):
        expected_mpn = canonical_mpn(mpn)
        expected_brand = canonical_brand(brand)
        for item in details:
            item["exact_mpn"] = canonical_mpn(item.get("mpn")) == expected_mpn
            item["exact_model"] = canonical_mpn(item.get("model")) == expected_mpn
            item["exact_identifier"] = (item["exact_mpn"] if
                identity_kind == "mpn" else
                item["exact_mpn"] or item["exact_model"])
            item["exact_brand"] = (
                canonical_brand(item["brand"]) == expected_brand)
            item["exact_brand_mpn"] = (
                item["exact_mpn"] and item["exact_brand"])
            item["exact_brand_identifier"] = (
                item["exact_identifier"] and item["exact_brand"])
            item["exact_condition"] = EbayComp._condition_matches(
                item.get("condition"), condition, item.get("condition_id"))
            item["exact_identity"] = (
                item["exact_brand_identifier"] and item["exact_condition"])
        brand_mpn_items = [item for item in details
                           if item["exact_brand_identifier"]]
        exact_items = [item for item in details if item["exact_identity"]]
        ambiguous_fields = []
        for field in ("pack", "lot_size"):
            values = {item[field] for item in exact_items if item[field]}
            if len(values) > 1:
                ambiguous_fields.append(field)
        coherent = bool(exact_items) and not ambiguous_fields
        coherent_depth = len(exact_items) if coherent else 0
        usable = coherent_depth >= min_market_listings
        prices = sorted(item["price"] for item in exact_items
                        if item["price"] is not None)
        p25 = prices[max(0, len(prices) // 4 - 1)] if prices else None
        p75 = (prices[min(len(prices) - 1, 3 * len(prices) // 4)]
               if prices else None)
        if not returned:
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
            "brand": brand, "mpn": mpn, "identity_kind": identity_kind,
            "condition_family": condition or "unfiltered",
            "n": active_total, "returned": returned, "inspected": len(details),
            "exact_mpn_items": sum(item["exact_mpn"] for item in details),
            "exact_model_items": sum(item["exact_model"] for item in details),
            "exact_identifier_items": sum(
                item["exact_identifier"] for item in details),
            "exact_brand_mpn_items": len(brand_mpn_items),
            "coherent_depth": coherent_depth, "coherent": coherent,
            "usable_market": usable, "resolution_status": status,
            "ambiguous_fields": ambiguous_fields,
            "median": statistics.median(prices) if prices else None,
            "p25": p25, "p75": p75,
            "p75_p25_ratio": (p75 / p25 if p25 and p75 else None),
            "currency": next((item["currency"] for item in exact_items
                              if item["currency"]), ""),
            "items": details, "synthetic": False, "identity_rule_version": 4,
        }

    @staticmethod
    def _synthetic(query, mkt):
        """Deterministic stub so ranking can be tested without a keyset."""
        h = int(hashlib.sha1(f"{mkt}|{query}".encode()).hexdigest()[:8], 16)
        return {"median": 20 + h % 180, "p25": 15 + h % 140,
                "n": 1 + h % 400, "currency": "USD", "synthetic": True}
