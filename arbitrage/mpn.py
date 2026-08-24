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
