#!/usr/bin/env python3
"""Deterministic identifier coverage and exact-market resolution audit."""
import csv
import gzip
import hashlib
import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone


GTIN_LENGTHS = {8, 12, 13, 14}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

LEDGER_FIELDS = [
    "audited_at", "domain", "group", "region", "category", "source_url",
    "ajax_url", "fetch_status", "fetch_error", "product_id", "variant_id",
    "product_title", "variant_title", "vendor", "source_sku", "barcode_raw",
    "gtin", "gtin_type", "gtin_valid", "source_collision_status",
    "source_identity_status", "price_present", "availability_present",
    "ebay_attempted", "ebay_query_resolved", "ebay_exact_confirmed",
    "ebay_active_total", "ebay_inspected_items", "ebay_exact_items",
    "ebay_coherent", "ebay_usable_market", "ebay_resolution_status",
    "ebay_median_price", "ebay_p25_price", "ebay_p75_price",
    "ebay_currency", "identity_status",
]

RESOLUTION_FIELDS = [
    "audited_at", "gtin", "region", "resolution_status", "active_total",
    "returned_items", "inspected_items", "exact_items", "coherent",
    "usable_market", "ambiguous_fields", "median_price", "p25_price",
    "p75_price", "currency", "item_id", "item_title", "item_gtin",
    "item_exact_gtin", "item_brand", "item_mpn", "item_model", "item_size",
    "item_color", "item_pack", "item_category", "item_lot_size",
    "item_condition", "item_price", "item_currency",
]

COVERAGE_FIELDS = [
    "audited_at", "row_scope", "domain", "group", "region", "category",
    "products_requested", "products_succeeded", "products_failed",
    "variants_total", "variants_with_sku", "sku_coverage_pct",
    "variants_with_barcode", "variants_with_valid_gtin", "gtin_coverage_pct",
    "invalid_barcodes", "unique_valid_gtins", "gtin_collision_groups",
    "gtin_collision_variant_rate_pct", "variants_with_brand",
    "brand_coverage_pct", "variants_with_price", "price_coverage_pct",
    "variants_with_inventory_state", "inventory_coverage_pct",
    "variants_with_explicit_mpn", "mpn_coverage_pct",
    "variants_with_exact_source_identity", "source_identity_coverage_pct",
    "deterministic_identity_coverage_pct", "ebay_gtins_attempted",
    "ebay_gtins_query_resolved", "ebay_query_resolution_rate_pct",
    "ebay_gtins_exact_confirmed", "ebay_exact_confirmation_rate_pct",
    "ebay_gtins_coherent", "ebay_coherence_rate_pct",
    "ebay_gtins_usable_market", "ebay_usable_market_rate_pct",
    "ebay_active_count_median", "ebay_active_count_p25",
    "ebay_active_count_p75", "ebay_exact_price_median",
]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_gtin(value):
    text = "" if value is None else str(value).strip()
    if any(not (ch.isdigit() or ch in " -") for ch in text):
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits if len(digits) in GTIN_LENGTHS else None


def valid_gtin(value):
    digits = normalize_gtin(value)
    if not digits:
        return False
    payload, supplied = digits[:-1], int(digits[-1])
    total = 0
    for index, digit in enumerate(reversed(payload)):
        total += int(digit) * (3 if index % 2 == 0 else 1)
    return (10 - total % 10) % 10 == supplied


def gtin_type(value):
    digits = normalize_gtin(value)
    return {8: "GTIN-8", 12: "UPC-A", 13: "EAN-13", 14: "GTIN-14"}.get(
        len(digits) if digits else 0, "")


def product_ajax_url(source_url):
    if not source_url:
        return None
    parsed = urllib.parse.urlsplit(source_url)
    parts = parsed.path.split("/")
    try:
        marker = parts.index("products")
        handle = parts[marker + 1]
    except (ValueError, IndexError):
        return None
    if not handle:
        return None
    path = "/".join(parts[:marker + 2]).rstrip("/") + ".js"
    path = urllib.parse.quote(path, safe="/%:@")
    return urllib.parse.urlunsplit((parsed.scheme or "https", parsed.netloc,
                                    path, "", ""))


def fetch_product(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json,text/plain,*/*",
        "Accept-Encoding": "gzip", "Accept-Language": "en-GB,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8", "replace"))


def _write(path, fields, rows):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    opener = gzip.open if path.endswith(".gz") else open
    mode = "wt" if path.endswith(".gz") else "w"
    with opener(path, mode, newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields,
                                extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pct(numerator, denominator):
    return numerator / denominator * 100.0 if denominator else 0.0


def _distribution(values):
    values = sorted(values)
    if not values:
        return "", "", ""
    return (f"{statistics.median(values):.2f}",
            f"{values[max(0, len(values) // 4 - 1)]:.2f}",
            f"{values[min(len(values) - 1, 3 * len(values) // 4)]:.2f}")


def _latest_products(conn, platform_by_domain, only_domain=None):
    latest = conn.execute("""
        SELECT o.* FROM obs o
        JOIN (SELECT domain, MAX(ts) ts FROM obs GROUP BY domain) x
          ON o.domain=x.domain AND o.ts=x.ts
        WHERE o.url IS NOT NULL
        ORDER BY o.domain, o.url
    """).fetchall()
    products = {}
    for row in latest:
        domain = row["domain"]
        if only_domain and domain != only_domain:
            continue
        if platform_by_domain.get(domain) != "shopify":
            continue
        ajax = product_ajax_url(row["url"])
        if not ajax:
            continue
        key = (domain, ajax)
        products.setdefault(key, {
            "domain": domain, "group": row["grp"] or "",
            "region": row["region"] or "", "category": row["ptype"] or "",
            "source_url": row["url"].split("?", 1)[0], "ajax_url": ajax,
        })
    return products


def _stable_sample(products, sample_per_store):
    by_domain = defaultdict(list)
    for product in products.values():
        key = hashlib.sha1(
            f"{product['domain']}|{product['ajax_url']}".encode()).hexdigest()
        by_domain[product["domain"]].append((key, product))
    selected = []
    for domain in sorted(by_domain):
        ranked = sorted(by_domain[domain], key=lambda item: item[0])
        selected.extend(product for _, product in ranked[:sample_per_store])
    return selected


def _variant_rows(product, data, audited_at):
    variants = data.get("variants") or []
    rows = []
    for variant in variants:
        raw = variant.get("barcode")
        normalized = normalize_gtin(raw)
        is_valid = valid_gtin(raw)
        rows.append({
            "audited_at": audited_at, **product, "fetch_status": "ok",
            "fetch_error": "", "product_id": data.get("id") or "",
            "variant_id": variant.get("id") or "",
            "product_title": data.get("title") or "",
            "variant_title": variant.get("title") or "",
            "vendor": data.get("vendor") or "",
            "source_sku": (variant.get("sku") or "").strip(),
            "barcode_raw": "" if raw is None else str(raw),
            "gtin": normalized or "", "gtin_type": gtin_type(raw),
            "gtin_valid": int(is_valid), "source_collision_status": "",
            "source_identity_status": "",
            "price_present": int(variant.get("price") is not None),
            "availability_present": int("available" in variant),
            "ebay_attempted": 0, "ebay_query_resolved": 0,
            "ebay_exact_confirmed": 0, "ebay_active_total": "",
            "ebay_inspected_items": "", "ebay_exact_items": "",
            "ebay_coherent": 0, "ebay_usable_market": 0,
            "ebay_resolution_status": "NOT_ATTEMPTED",
            "ebay_median_price": "", "ebay_p25_price": "",
            "ebay_p75_price": "", "ebay_currency": "",
            "identity_status": "REJECT",
        })
    return rows


def _classify_source_identity(rows):
    members = defaultdict(set)
    for row in rows:
        if row.get("fetch_status") == "ok" and row.get("gtin_valid"):
            members[(row["domain"], row["gtin"])].add(
                (row["ajax_url"], row["variant_id"]))
    for row in rows:
        if row.get("fetch_status") != "ok":
            continue
        if not row.get("barcode_raw"):
            row["source_collision_status"] = "NOT_APPLICABLE"
            row["source_identity_status"] = "REJECT_MISSING_IDENTIFIER"
        elif not row.get("gtin_valid"):
            row["source_collision_status"] = "NOT_APPLICABLE"
            row["source_identity_status"] = "REJECT_INVALID_GTIN"
        elif len(members[(row["domain"], row["gtin"])]) > 1:
            row["source_collision_status"] = "COLLISION"
            row["source_identity_status"] = "REJECT_SOURCE_COLLISION"
        else:
            row["source_collision_status"] = "UNIQUE_WITHIN_STORE"
            row["source_identity_status"] = "EXACT_SOURCE"


def _resolution_rows(results, audited_at, region):
    rows = []
    for gtin, result in sorted(results.items()):
        result = result or {}
        base = {
            "audited_at": audited_at, "gtin": gtin, "region": region,
            "resolution_status": result.get("resolution_status", "API_ERROR"),
            "active_total": result.get("n", ""),
            "returned_items": result.get("returned", ""),
            "inspected_items": result.get("inspected", ""),
            "exact_items": result.get("exact_gtin_items", ""),
            "coherent": int(bool(result.get("coherent"))),
            "usable_market": int(bool(result.get("usable_market"))),
            "ambiguous_fields": ",".join(result.get("ambiguous_fields", [])),
            "median_price": result.get("median") or "",
            "p25_price": result.get("p25") or "",
            "p75_price": result.get("p75") or "",
            "currency": result.get("currency") or "",
        }
        items = result.get("items") or [None]
        for item in items:
            item = item or {}
            rows.append({
                **base, "item_id": item.get("id", ""),
                "item_title": item.get("title", ""),
                "item_gtin": item.get("gtin", ""),
                "item_exact_gtin": int(bool(item.get("exact_gtin"))),
                "item_brand": item.get("brand", ""),
                "item_mpn": item.get("mpn", ""),
                "item_model": item.get("model", ""),
                "item_size": item.get("size", ""),
                "item_color": item.get("color", ""),
                "item_pack": item.get("pack", ""),
                "item_category": item.get("category", ""),
                "item_lot_size": item.get("lot_size", ""),
                "item_condition": item.get("condition", ""),
                "item_price": item.get("price", ""),
                "item_currency": item.get("currency", ""),
            })
    return rows


def _resolve_ebay(rows, ebay, region, max_lookups, detail_limit,
                  min_market_listings):
    gtins = {row["gtin"] for row in rows
             if row.get("source_identity_status") == "EXACT_SOURCE"}
    gtins = sorted(gtins, key=lambda gtin: hashlib.sha1(gtin.encode()).hexdigest())
    results = {}
    for gtin in gtins[:max_lookups]:
        result = ebay.lookup_gtin(
            gtin, region=region, detail_limit=detail_limit,
            min_market_listings=min_market_listings)
        results[gtin] = result
    for row in rows:
        gtin = row.get("gtin", "")
        if gtin not in results:
            continue
        result = results[gtin]
        row["ebay_attempted"] = 1
        row["ebay_query_resolved"] = int(bool(result and result.get("n", 0)))
        row["ebay_exact_confirmed"] = int(bool(
            result and result.get("exact_gtin_items", 0)))
        row["ebay_active_total"] = result.get("n", 0) if result else 0
        row["ebay_inspected_items"] = (
            result.get("inspected", 0) if result else 0)
        row["ebay_exact_items"] = (
            result.get("exact_gtin_items", 0) if result else 0)
        row["ebay_coherent"] = int(bool(result and result.get("coherent")))
        row["ebay_usable_market"] = int(bool(
            result and result.get("usable_market")))
        row["ebay_resolution_status"] = (
            result.get("resolution_status", "API_ERROR")
            if result else "API_ERROR")
        row["ebay_median_price"] = result.get("median") or "" if result else ""
        row["ebay_p25_price"] = result.get("p25") or "" if result else ""
        row["ebay_p75_price"] = result.get("p75") or "" if result else ""
        row["ebay_currency"] = result.get("currency") or "" if result else ""
        row["identity_status"] = (
            "EXACT" if result and result.get("resolution_status") in
            {"EXACT_USABLE", "EXACT_SHALLOW"} else "REJECT")
    return results


def _audit_store(products, fetcher, timeout, delay, audited_at, retries):
    ledger, fetches = [], []
    for index, product in enumerate(products):
        try:
            for attempt in range(retries + 1):
                try:
                    data = fetcher(product["ajax_url"], timeout=timeout)
                    break
                except urllib.error.HTTPError as error:
                    if error.code != 429 or attempt == retries:
                        raise
                    retry_after = error.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else 2 ** attempt
                    time.sleep(min(max(wait, 1), 30))
            ledger.extend(_variant_rows(product, data, audited_at))
            fetches.append({"domain": product["domain"],
                            "category": product["category"], "status": "ok"})
        except Exception as error:
            fetches.append({"domain": product["domain"],
                            "category": product["category"], "status": "error"})
            ledger.append({
                "audited_at": audited_at, **product, "fetch_status": "error",
                "fetch_error": f"{type(error).__name__}: {str(error)[:160]}",
            })
        if delay and index + 1 < len(products):
            time.sleep(delay)
    return ledger, fetches


def _coverage_row(rows, product_fetches, audited_at, scope, domain,
                  group="", region="", category=""):
    variants = [row for row in rows if row["fetch_status"] == "ok"]
    total = len(variants)
    with_sku = sum(bool(row["source_sku"]) for row in variants)
    with_barcode = sum(bool(row["barcode_raw"]) for row in variants)
    with_gtin = sum(bool(row["gtin_valid"]) for row in variants)
    invalid = sum(bool(row["barcode_raw"]) and not row["gtin_valid"]
                  for row in variants)
    with_brand = sum(bool(row["vendor"]) for row in variants)
    with_price = sum(bool(row["price_present"]) for row in variants)
    with_inventory = sum(bool(row["availability_present"]) for row in variants)
    with_source_identity = sum(
        row["source_identity_status"] == "EXACT_SOURCE" for row in variants)

    identities = defaultdict(set)
    for row in variants:
        if row["gtin_valid"]:
            identities[row["gtin"]].add((row["ajax_url"], row["variant_id"]))
    collisions = {gtin: members for gtin, members in identities.items()
                  if len(members) > 1}
    colliding_variants = sum(len(members) for members in collisions.values())

    attempted = {row["gtin"] for row in variants if row["ebay_attempted"]}
    query_resolved = {row["gtin"] for row in variants
                      if row["ebay_query_resolved"]}
    exact_confirmed = {row["gtin"] for row in variants
                       if row["ebay_exact_confirmed"]}
    coherent = {row["gtin"] for row in variants if row["ebay_coherent"]}
    usable = {row["gtin"] for row in variants if row["ebay_usable_market"]}
    attempted_rows = {}
    for row in variants:
        if row["ebay_attempted"]:
            attempted_rows.setdefault(row["gtin"], row)
    active_counts = [int(row["ebay_active_total"] or 0)
                     for row in attempted_rows.values()
                     if row["ebay_query_resolved"]]
    exact_prices = [float(row["ebay_median_price"])
                    for row in attempted_rows.values()
                    if row["ebay_median_price"] not in ("", None)]
    active_median, active_p25, active_p75 = _distribution(active_counts)
    fetches = product_fetches if scope == "store_total" else []
    return {
        "audited_at": audited_at, "row_scope": scope, "domain": domain,
        "group": group, "region": region, "category": category,
        "products_requested": len(fetches),
        "products_succeeded": sum(f["status"] == "ok" for f in fetches),
        "products_failed": sum(f["status"] != "ok" for f in fetches),
        "variants_total": total, "variants_with_sku": with_sku,
        "sku_coverage_pct": f"{_pct(with_sku, total):.2f}",
        "variants_with_barcode": with_barcode,
        "variants_with_valid_gtin": with_gtin,
        "gtin_coverage_pct": f"{_pct(with_gtin, total):.2f}",
        "invalid_barcodes": invalid, "unique_valid_gtins": len(identities),
        "gtin_collision_groups": len(collisions),
        "gtin_collision_variant_rate_pct": f"{_pct(colliding_variants, total):.2f}",
        "variants_with_brand": with_brand,
        "brand_coverage_pct": f"{_pct(with_brand, total):.2f}",
        "variants_with_price": with_price,
        "price_coverage_pct": f"{_pct(with_price, total):.2f}",
        "variants_with_inventory_state": with_inventory,
        "inventory_coverage_pct": f"{_pct(with_inventory, total):.2f}",
        # Shopify Ajax provides SKU and barcode, not an explicit MPN field.
        "variants_with_explicit_mpn": 0, "mpn_coverage_pct": "0.00",
        "variants_with_exact_source_identity": with_source_identity,
        "source_identity_coverage_pct": f"{_pct(with_source_identity, total):.2f}",
        "deterministic_identity_coverage_pct": f"{_pct(with_source_identity, total):.2f}",
        "ebay_gtins_attempted": len(attempted),
        "ebay_gtins_query_resolved": len(query_resolved),
        "ebay_query_resolution_rate_pct": f"{_pct(len(query_resolved), len(attempted)):.2f}",
        "ebay_gtins_exact_confirmed": len(exact_confirmed),
        "ebay_exact_confirmation_rate_pct": f"{_pct(len(exact_confirmed), len(attempted)):.2f}",
        "ebay_gtins_coherent": len(coherent),
        "ebay_coherence_rate_pct": f"{_pct(len(coherent), len(attempted)):.2f}",
        "ebay_gtins_usable_market": len(usable),
        "ebay_usable_market_rate_pct": f"{_pct(len(usable), len(attempted)):.2f}",
        "ebay_active_count_median": active_median,
        "ebay_active_count_p25": active_p25,
        "ebay_active_count_p75": active_p75,
        "ebay_exact_price_median": (
            f"{statistics.median(exact_prices):.2f}" if exact_prices else ""),
    }


def run_audit(conn, stores, out_path, ledger_path, sample_per_store=5,
              delay=0.15, timeout=20, only_domain=None, ebay=None,
              ebay_region="GB", max_ebay_lookups=100, fetcher=None,
              workers=4, retries=2, ebay_detail_limit=50,
              min_market_listings=3, resolution_path=None):
    audited_at = now()
    platform = {store["domain"]: store["platform"] for store in stores}
    products = _latest_products(conn, platform, only_domain=only_domain)
    selected = _stable_sample(products, sample_per_store)
    fetcher = fetcher or fetch_product
    ledger, fetches = [], []
    by_domain = defaultdict(list)
    for product in selected:
        by_domain[product["domain"]].append(product)
    store_batches = [by_domain[domain] for domain in sorted(by_domain)]

    def audit_store(batch):
        return _audit_store(batch, fetcher, timeout, delay, audited_at, retries)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for store_ledger, store_fetches in pool.map(audit_store, store_batches):
            ledger.extend(store_ledger)
            fetches.extend(store_fetches)

    _classify_source_identity(ledger)
    results = {}
    if ebay is not None:
        results = _resolve_ebay(
            ledger, ebay, ebay_region, max_ebay_lookups, ebay_detail_limit,
            min_market_listings)
    if resolution_path:
        _write(resolution_path, RESOLUTION_FIELDS,
               _resolution_rows(results, audited_at, ebay_region))

    coverage = []
    domains = sorted({product["domain"] for product in selected})
    for domain in domains:
        domain_rows = [row for row in ledger if row["domain"] == domain]
        domain_fetches = [row for row in fetches if row["domain"] == domain]
        first = next((row for row in domain_rows), {})
        coverage.append(_coverage_row(
            domain_rows, domain_fetches, audited_at, "store_total", domain,
            first.get("group", ""), first.get("region", ""), ""))
        categories = sorted({row.get("category", "") for row in domain_rows
                             if row.get("fetch_status") == "ok"})
        for category in categories:
            category_rows = [row for row in domain_rows
                             if row.get("category", "") == category]
            coverage.append(_coverage_row(
                category_rows, [], audited_at, "category", domain,
                first.get("group", ""), first.get("region", ""), category))

    coverage.sort(key=lambda row: (
        0 if row["row_scope"] == "store_total" else 1,
        -float(row["deterministic_identity_coverage_pct"]),
        row["domain"], row["category"]))
    _write(out_path, COVERAGE_FIELDS, coverage)
    _write(ledger_path, LEDGER_FIELDS, ledger)
    totals = {
        "domains": len(domains), "products_requested": len(selected),
        "products_succeeded": sum(row["status"] == "ok" for row in fetches),
        "variants": sum(row.get("fetch_status") == "ok" for row in ledger),
        "valid_gtins": sum(bool(row.get("gtin_valid")) for row in ledger),
        "coverage_rows": len(coverage), "ledger_rows": len(ledger),
        "ebay_gtins_attempted": len(results),
        "ebay_gtins_query_resolved": sum(
            bool(result and result.get("n")) for result in results.values()),
        "ebay_gtins_coherent": sum(
            bool(result and result.get("coherent"))
            for result in results.values()),
        "ebay_gtins_usable_market": sum(
            bool(result and result.get("usable_market"))
            for result in results.values()),
    }
    totals["gtin_coverage_pct"] = _pct(totals["valid_gtins"], totals["variants"])
    return totals
