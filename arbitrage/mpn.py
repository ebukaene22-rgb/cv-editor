"""Frozen exact-MPN basket construction and eBay resolver gate."""
import csv
import gzip
import hashlib
import json
import math
import re
import statistics
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


BASKET_FIELDS = [
    "cohort", "source_site", "source_category", "brand", "mpn", "title",
    "source_url", "source_catalogue_lastmod", "source_evidence",
]

LEDGER_FIELDS = BASKET_FIELDS + [
    "audited_at", "ebay_region", "query", "active_total", "returned",
    "inspected", "exact_mpn_items", "exact_brand_mpn_items",
    "coherent_depth", "coherent", "usable_market", "resolution_status",
    "ambiguous_fields", "median_price", "p25_price", "p75_price",
    "p75_p25_ratio", "currency", "item_evidence_json",
]

ECONOMICS_FIELDS = [
    "cohort", "source_category", "brand", "mpn", "title", "source_url",
    "source_verified_at", "source_price_usd", "source_stock",
    "source_shipping_usd", "source_shipping_status",
    "acquisition_floor_usd", "sold_median_usd", "sold_p25_usd",
    "sold_count_90d", "sold_latest_date", "sold_evidence_status",
    "active_coherent_depth", "active_p25_usd",
    "conservative_exit_proxy_usd", "gross_spread_pre_cost_usd",
    "usd_to_gbp", "gross_spread_pre_cost_gbp",
    "gross_margin_pre_cost_pct", "net_contribution_upper_bound_gbp",
    "expected_ebay_fee_usd",
    "outbound_shipping_usd", "return_allowance_usd",
    "net_contribution_gbp", "contribution_margin_pct",
    "expected_monthly_unit_velocity", "expected_monthly_contribution_gbp",
    "economics_status", "unresolved_inputs",
]

MIN_NET_CONTRIBUTION_GBP = 15.0

STRATA = {
    "dishwasher": "appliance", "refrigerator": "appliance",
    "washer": "appliance", "dryer": "appliance",
    "angle-grinder": "tool", "electric-drill": "tool",
    "miter-saw": "tool", "circular-saw": "tool",
    "pressure-washer": "tool", "upright-vacuum": "appliance",
}

BRANDS = {
    "general-electric": "General Electric", "whirlpool": "Whirlpool",
    "frigidaire": "Frigidaire", "maytag": "Maytag",
    "kitchenaid": "KitchenAid", "electrolux": "Electrolux",
    "bosch": "Bosch", "dewalt": "DeWalt", "makita": "Makita",
    "milwaukee": "Milwaukee", "ryobi": "Ryobi",
    "black-and-decker": "Black & Decker", "ridgid": "Ridgid",
    "karcher": "Karcher", "bissell": "Bissell",
}

EXCLUDED_TITLE_WORDS = {
    "discontinued", "obsolete", "screw", "washer", "nut", "bolt",
    "clip", "rivet", "label", "decal", "manual",
}


def _parse_candidate(url, lastmod):
    parts = urllib.parse.urlsplit(url).path.strip("/").split("/")
    if len(parts) != 5 or parts[0] != "parts":
        return None
    _, category, brand_slug, record, slug = parts
    if category not in STRATA or brand_slug not in BRANDS:
        return None
    if not record.startswith("erp") or "-" not in slug:
        return None
    title_slug, mpn = slug.rsplit("-", 1)
    if not re.fullmatch(r"(?=.*\d)[a-z0-9]{5,20}", mpn):
        return None
    words = set(title_slug.split("-"))
    if words & EXCLUDED_TITLE_WORDS:
        return None
    return {
        "cohort": STRATA[category],
        "source_site": "eReplacementParts",
        "source_category": category,
        "brand": BRANDS[brand_slug],
        "mpn": mpn.upper(),
        "title": title_slug.replace("-", " ").title(),
        "source_url": url,
        "source_catalogue_lastmod": lastmod,
        "source_evidence": "manufacturer part number in sitemap product URL",
    }


def build_basket(sitemap_path, out_path, size=50):
    """Build a deterministic, category-balanced basket from a sitemap."""
    opener = gzip.open if str(sitemap_path).endswith(".gz") else open
    with opener(sitemap_path, "rb") as stream:
        root = ET.parse(stream).getroot()
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    by_category = {category: [] for category in STRATA}
    for node in root.findall(f"{namespace}url"):
        url = node.findtext(f"{namespace}loc", "").strip()
        lastmod = node.findtext(f"{namespace}lastmod", "").strip()
        row = _parse_candidate(url, lastmod)
        if row:
            by_category[row["source_category"]].append(row)
    quota = math.ceil(size / len(STRATA))
    selected = []
    for category in STRATA:
        rows = sorted(
            by_category[category],
            key=lambda row: hashlib.sha256(
                f"mpn-gate-v1|{row['brand']}|{row['mpn']}".encode()
            ).hexdigest())
        selected.extend(rows[:quota])
    selected = selected[:size]
    if len(selected) != size:
        raise ValueError(f"only {len(selected)} eligible rows for size {size}")
    identities = {(row["brand"], row["mpn"]) for row in selected}
    if len(identities) != len(selected):
        raise ValueError("basket contains duplicate brand + MPN identities")
    with open(out_path, "w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=BASKET_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
    return selected


def basket_checksum(path):
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def read_basket(path):
    with open(path, newline="") as stream:
        rows = list(csv.DictReader(stream))
    missing = [field for field in BASKET_FIELDS
               if not rows or field not in rows[0]]
    if missing:
        raise ValueError("basket missing fields: " + ", ".join(missing))
    identities = []
    for row in rows:
        if not row["brand"].strip() or not row["mpn"].strip():
            raise ValueError("every basket row requires brand and MPN")
        identities.append((row["brand"].casefold(), row["mpn"].casefold()))
    if len(set(identities)) != len(identities):
        raise ValueError("basket contains duplicate brand + MPN identities")
    return rows


def run_audit(ebay, basket_path, ledger_path, region="US", limit=20,
              detail_limit=20, min_market_listings=3):
    rows = read_basket(basket_path)
    audited_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    evidence = []
    for row in rows:
        result = ebay.lookup_mpn(
            row["brand"], row["mpn"], region=region, limit=limit,
            detail_limit=detail_limit,
            min_market_listings=min_market_listings)
        result = result or {"resolution_status": "API_ERROR"}
        evidence.append({
            **row, "audited_at": audited_at, "ebay_region": region,
            "query": f"{row['brand']} {row['mpn']}",
            "active_total": result.get("n", 0),
            "returned": result.get("returned", 0),
            "inspected": result.get("inspected", 0),
            "exact_mpn_items": result.get("exact_mpn_items", 0),
            "exact_brand_mpn_items": result.get("exact_brand_mpn_items", 0),
            "coherent_depth": result.get("coherent_depth", 0),
            "coherent": int(bool(result.get("coherent"))),
            "usable_market": int(bool(result.get("usable_market"))),
            "resolution_status": result.get("resolution_status", "API_ERROR"),
            "ambiguous_fields": ";".join(result.get("ambiguous_fields", [])),
            "median_price": result.get("median") or "",
            "p25_price": result.get("p25") or "",
            "p75_price": result.get("p75") or "",
            "p75_p25_ratio": result.get("p75_p25_ratio") or "",
            "currency": result.get("currency") or "",
            "item_evidence_json": json.dumps(result.get("items", []),
                                               separators=(",", ":")),
        })
    opener = gzip.open if str(ledger_path).endswith(".gz") else open
    with opener(ledger_path, "wt", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(evidence)
    depths = [int(row["coherent_depth"]) for row in evidence]
    usable = sum(int(row["usable_market"]) for row in evidence)
    exact = sum(int(row["exact_brand_mpn_items"]) > 0 for row in evidence)
    return {
        "basket_rows": len(rows), "basket_checksum": basket_checksum(basket_path),
        "active_queries": sum(int(row["active_total"]) > 0 for row in evidence),
        "exact_identities": exact, "usable_markets": usable,
        "usable_rate_pct": 100 * usable / len(rows) if rows else 0,
        "median_coherent_depth": statistics.median(depths) if depths else 0,
        "passed": bool(rows) and usable / len(rows) >= 0.25,
    }


def _read_csv(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", newline="") as stream:
        return list(csv.DictReader(stream))


def run_economics_gate(source_path, resolution_path, out_path, usd_to_gbp):
    """Apply the conservative pre-cost dominance gate to resolver survivors."""
    if usd_to_gbp <= 0:
        raise ValueError("USD-to-GBP rate must be positive")
    source_rows = _read_csv(source_path)
    resolution_rows = [row for row in _read_csv(resolution_path)
                       if row.get("usable_market") == "1"]
    source_by_id = {(row["brand"].casefold(), row["mpn"].casefold()): row
                    for row in source_rows}
    if len(source_by_id) != len(source_rows):
        raise ValueError("source snapshot contains duplicate brand + MPN rows")
    resolution_ids = {
        (row["brand"].casefold(), row["mpn"].casefold())
        for row in resolution_rows}
    if set(source_by_id) != resolution_ids:
        raise ValueError("source snapshot must exactly match resolver survivors")

    output = []
    for market in resolution_rows:
        identity = (market["brand"].casefold(), market["mpn"].casefold())
        source = source_by_id[identity]
        source_price = float(source["source_price_usd"])
        active_p25 = float(market["p25_price"])
        gross_usd = active_p25 - source_price
        gross_gbp = gross_usd * usd_to_gbp
        margin_pct = (100 * gross_usd / active_p25
                      if active_p25 else None)
        rejected = gross_gbp < MIN_NET_CONTRIBUTION_GBP
        status = ("REJECT_PRE_COST_SPREAD_BELOW_15_GBP" if rejected
                  else "BLOCKED_FULL_ECONOMICS_REQUIRED")
        unresolved = [
            "exact_sold_rows", "sold_velocity", "source_shipping_quote",
            "outbound_weight_and_postage", "ebay_us_seller_fee",
            "return_allowance",
        ]
        output.append({
            "cohort": market["cohort"],
            "source_category": market["source_category"],
            "brand": market["brand"], "mpn": market["mpn"],
            "title": market["title"], "source_url": market["source_url"],
            "source_verified_at": source["source_verified_at"],
            "source_price_usd": f"{source_price:.2f}",
            "source_stock": source["source_stock"],
            "source_shipping_usd": source.get("source_shipping_usd", ""),
            "source_shipping_status": source["source_shipping_status"],
            "acquisition_floor_usd": f"{source_price:.2f}",
            "sold_median_usd": "", "sold_p25_usd": "",
            "sold_count_90d": "", "sold_latest_date": "",
            "sold_evidence_status": "UNAVAILABLE_EBAY_AUTH_REQUIRED",
            "active_coherent_depth": market["coherent_depth"],
            "active_p25_usd": f"{active_p25:.2f}",
            "conservative_exit_proxy_usd": f"{active_p25:.2f}",
            "gross_spread_pre_cost_usd": f"{gross_usd:.2f}",
            "usd_to_gbp": f"{usd_to_gbp:.5f}",
            "gross_spread_pre_cost_gbp": f"{gross_gbp:.2f}",
            "gross_margin_pre_cost_pct": (
                f"{margin_pct:.2f}" if margin_pct is not None else ""),
            "net_contribution_upper_bound_gbp": f"{gross_gbp:.2f}",
            "expected_ebay_fee_usd": "", "outbound_shipping_usd": "",
            "return_allowance_usd": "", "net_contribution_gbp": "",
            "contribution_margin_pct": "",
            "expected_monthly_unit_velocity": "",
            "expected_monthly_contribution_gbp": "",
            "economics_status": status,
            "unresolved_inputs": ";".join(unresolved),
        })
    with open(out_path, "w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=ECONOMICS_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    rejected = sum(row["economics_status"].startswith("REJECT")
                   for row in output)
    appliance = [row for row in output if row["cohort"] == "appliance"]
    tool = [row for row in output if row["cohort"] == "tool"]
    return {
        "rows": len(output), "rejected_pre_cost": rejected,
        "cleared_for_full_economics": len(output) - rejected,
        "appliance_cleared": sum(not row["economics_status"].startswith(
            "REJECT") for row in appliance),
        "tool_cleared": sum(not row["economics_status"].startswith(
            "REJECT") for row in tool),
        "precheck_passed": len(output) - rejected >= 4,
    }
