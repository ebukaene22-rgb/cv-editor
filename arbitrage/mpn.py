"""Frozen exact-MPN basket construction and eBay resolver gate."""
import csv
import gzip
import hashlib
import json
import math
import re
import statistics
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser


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

USED_SOURCE_FIELDS = [
    "brand", "mpn", "source_category", "source_vendor", "brand_match_rule",
    "source_condition", "condition_family", "source_price_usd",
    "source_available", "source_sku", "source_url", "source_verified_at",
    "market_status", "market_depth", "market_p25_usd", "currency",
    "gross_spread_pre_cost_usd", "gross_spread_pre_cost_gbp",
    "economics_status", "unresolved_inputs",
]

BRAND_FAMILIES = {
    "electrolux": {"electrolux", "frigidaire"},
    "whirlpool": {"whirlpool", "maytag"},
}

SOURCE_CONDITIONS = {
    "New": "new",
    "Like New / Open Box": "open_box",
    "Certified Refurbished": "certified_refurbished",
    "Used Part - A Condition Grade": "used",
}

MANIFEST_FIELDS = [
    "source", "lot_id", "lot_url", "lot_ask_price_usd", "lot_units",
    "lot_condition", "manifest_accuracy_risk_pct", "line_manufacturer",
    "line_title", "line_category", "line_model", "line_condition",
    "line_upc", "line_quantity",
    "line_retail_price_usd", "frozen_brand", "frozen_mpn",
    "identity_status", "audited_at",
]

LIQUIDATION_EXIT_FIELDS = [
    "model", "manufacturer", "gtin", "source_conditions",
    "condition_family", "manifest_lot_count", "manifest_quantity",
    "audited_at", "ebay_region", "active_total", "returned", "inspected",
    "exact_gtin_items", "exact_condition_gtin_items", "coherent_depth",
    "usable_market", "resolution_status", "median_price", "p25_price",
    "p75_price", "currency", "economics_status", "unresolved_inputs",
]

RESOLVER_DIAGNOSTIC_FIELDS = [
    "model", "manufacturer", "gtin", "source_categories", "source_conditions",
    "specific_condition", "broad_condition", "audited_at", "ebay_region",
    "gtin_unfiltered_count", "gtin_condition_count",
    "model_unfiltered_count", "model_condition_count",
    "gtin_unfiltered_exact_depth", "gtin_condition_exact_depth",
    "model_unfiltered_exact_depth", "model_condition_exact_depth",
    "gtin_unfiltered_status", "gtin_condition_status",
    "model_unfiltered_status", "model_condition_status",
    "dominant_category_id", "dominant_category_name",
    "category_identity_coherent", "returned_condition_ids",
    "returned_titles_json", "diagnostic_classification",
    "deterministic_market_found", "economics_eligible",
]

LIQUIDATION_UNIVERSE_FIELDS = [
    "model", "manufacturers", "titles", "categories", "upcs",
    "valid_gtins", "lot_count", "manifest_line_count", "total_quantity",
    "conditions", "lot_ids", "lot_urls", "first_seen_at",
]

LIQUIDATION_ECONOMICS_FIELDS = [
    "model", "manufacturer", "source_categories", "source_conditions",
    "condition_family", "manifest_lot_count", "manifest_quantity",
    "market_depth", "active_p25_usd", "allocated_ask_per_unit_usd",
    "ebay_fee_rate", "return_allowance_rate", "outbound_shipping_usd",
    "manifest_usable_probability", "expected_net_exit_pre_acquisition_usd",
    "expected_contribution_at_ask_usd", "expected_contribution_at_ask_gbp",
    "contribution_margin_at_ask_pct", "required_profit_gbp",
    "max_all_in_acquisition_per_manifest_unit_usd", "economics_status",
    "unresolved_lot_costs",
]

_COMPONENT_CATEGORY_WORDS = {
    "accessory", "accessories", "part", "parts", "mount", "mounts",
    "bracket", "brackets", "cable", "cables", "adapter", "adapters",
}

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


def _canonical_text(value):
    return "".join(ch for ch in str(value or "").casefold()
                   if ch.isalnum())


def source_brand_match(demand_brand, source_vendor):
    demand = _canonical_text(demand_brand)
    source = _canonical_text(source_vendor)
    if demand == "generalelectric":
        demand = "ge"
    if source == "generalelectric":
        source = "ge"
    if demand == source:
        return "EXACT_BRAND"
    if any(demand in family and source in family
           for family in BRAND_FAMILIES.values()):
        return "CORPORATE_BRAND_FAMILY"
    return ""


def _source_part_number(body):
    match = re.search(r"Part Number:</strong>\s*([^<]+)", body or "", re.I)
    return match.group(1).strip() if match else ""


def _source_products(mpn, timeout=20):
    query = urllib.parse.urlencode({
        "q": mpn, "resources[type]": "product", "resources[limit]": "10",
    })
    url = "https://neuapplianceparts.com/search/suggest.json?" + query
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return (json.load(response).get("resources", {}).get("results", {})
                .get("products", []))


def _source_product_detail(handle, timeout=20):
    url = f"https://neuapplianceparts.com/products/{handle}.js"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def run_used_source_audit(ebay, resolution_path, out_path, usd_to_gbp,
                          region="US", min_market_listings=3, timeout=20):
    """Test a structured used/open-box source against condition-matched comps."""
    if usd_to_gbp <= 0:
        raise ValueError("USD-to-GBP rate must be positive")
    demand = [row for row in _read_csv(resolution_path)
              if row.get("usable_market") == "1"]
    verified_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = []
    matched_identities = set()
    available_identities = set()
    for row in demand:
        expected_mpn = _canonical_text(row["mpn"])
        for product in _source_products(row["mpn"], timeout):
            if _canonical_text(_source_part_number(product.get("body"))) != expected_mpn:
                continue
            brand_rule = source_brand_match(row["brand"], product.get("vendor"))
            if not brand_rule:
                continue
            matched_identities.add((row["brand"], row["mpn"]))
            detail = _source_product_detail(product["handle"], timeout)
            for variant in detail.get("variants", []):
                condition = SOURCE_CONDITIONS.get(variant.get("title"))
                if not condition or not variant.get("available"):
                    continue
                available_identities.add((row["brand"], row["mpn"]))
                price = float(variant["price"]) / 100
                market = ebay.lookup_mpn(
                    row["brand"], row["mpn"], region=region, limit=20,
                    detail_limit=20, min_market_listings=min_market_listings,
                    condition=condition) or {"resolution_status": "API_ERROR"}
                p25 = market.get("p25")
                spread_usd = p25 - price if p25 is not None else None
                spread_gbp = (spread_usd * usd_to_gbp
                              if spread_usd is not None else None)
                if not market.get("usable_market"):
                    status = "REJECT_CONDITION_MARKET_DEPTH"
                elif spread_gbp < MIN_NET_CONTRIBUTION_GBP:
                    status = "REJECT_PRE_COST_SPREAD_BELOW_15_GBP"
                else:
                    status = "BLOCKED_FULL_ECONOMICS_REQUIRED"
                output.append({
                    "brand": row["brand"], "mpn": row["mpn"],
                    "source_category": row["source_category"],
                    "source_vendor": product.get("vendor") or "",
                    "brand_match_rule": brand_rule,
                    "source_condition": variant.get("title") or "",
                    "condition_family": condition,
                    "source_price_usd": f"{price:.2f}",
                    "source_available": "1", "source_sku": variant.get("sku") or "",
                    "source_url": ("https://neuapplianceparts.com/products/" +
                                   product["handle"]),
                    "source_verified_at": verified_at,
                    "market_status": market.get("resolution_status", "API_ERROR"),
                    "market_depth": market.get("coherent_depth", 0),
                    "market_p25_usd": f"{p25:.2f}" if p25 is not None else "",
                    "currency": market.get("currency") or "",
                    "gross_spread_pre_cost_usd": (
                        f"{spread_usd:.2f}" if spread_usd is not None else ""),
                    "gross_spread_pre_cost_gbp": (
                        f"{spread_gbp:.2f}" if spread_gbp is not None else ""),
                    "economics_status": status,
                    "unresolved_inputs": (
                        "source_shipping_quote;outbound_postage;ebay_fee;"
                        "return_allowance;sold_velocity"),
                })
    with open(out_path, "w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=USED_SOURCE_FIELDS,
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    viable = sum(row["economics_status"] ==
                 "BLOCKED_FULL_ECONOMICS_REQUIRED" for row in output)
    return {
        "demand_rows": len(demand), "matched_identities": len(matched_identities),
        "available_identities": len(available_identities),
        "available_variants": len(output), "condition_markets": sum(
            row["market_status"] == "EXACT_USABLE" for row in output),
        "pre_cost_candidates": viable, "source_gate_passed": viable >= 3,
    }


def run_liquidation_coverage_gate(coverage_path, resolution_path):
    """Validate title-search snapshots; this is not a manifest-content gate."""
    demand = [row for row in _read_csv(resolution_path)
              if row.get("usable_market") == "1"]
    demand_ids = {row["mpn"].casefold() for row in demand}
    coverage = _read_csv(coverage_path)
    sources = {row["source"] for row in coverage}
    for source in sources:
        observed = {row["mpn"].casefold() for row in coverage
                    if row["source"] == source}
        if observed != demand_ids:
            raise ValueError(
                f"{source} snapshot must exactly match resolver survivors")
    matched_ids = {row["mpn"].casefold() for row in coverage
                   if int(row["exact_search_results"]) > 0}
    return {
        "demand_rows": len(demand), "sources": len(sources),
        "searches": len(coverage), "matched_identities": len(matched_ids),
        "source_gate_passed": len(matched_ids) >= 3,
    }


class _ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() == "script":
            self.in_script = True
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag.casefold() == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.scripts[-1] += data


def parse_direct_liquidation_page(html):
    """Extract the structured lot and line-level manifest from a product page."""
    marker = "window.__INITIAL_STATE__ = "
    parser = _ScriptCollector()
    parser.feed(html)
    script = next((item for item in parser.scripts if marker in item), None)
    if script is None:
        raise ValueError("Direct Liquidation page has no initial state")
    state = json.JSONDecoder().raw_decode(script.split(marker, 1)[1])[0]
    product = (state.get("__SSR_STATE__", {}).get("single-product", {})
               .get("product"))
    if not product or not isinstance(product.get("products"), list):
        raise ValueError("Direct Liquidation page has no line-level manifest")
    return product


def _fetch_text(url, timeout=30):
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "text/html",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def run_manifest_audit(urls, resolution_path, out_path, timeout=30):
    """Match real line-level liquidation manifests to the frozen MPN set."""
    demand = [row for row in _read_csv(resolution_path)
              if row.get("usable_market") == "1"]
    demand_by_mpn = {_canonical_text(row["mpn"]): row for row in demand}
    audited_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = []
    lot_ids = set()
    exact_ids = set()
    for url in urls:
        lot = parse_direct_liquidation_page(_fetch_text(url, timeout))
        lot_id = str(lot.get("masterSku") or lot.get("sku") or "")
        if not lot_id or lot_id in lot_ids:
            raise ValueError("manifest lots require unique lot IDs")
        lot_ids.add(lot_id)
        for line in lot["products"]:
            model = _canonical_text(line.get("model"))
            frozen = demand_by_mpn.get(model)
            if not frozen:
                status = "NOT_IN_FROZEN_UNIVERSE"
            else:
                brand_rule = source_brand_match(
                    frozen["brand"], line.get("manufacturer"))
                status = ("EXACT_FROZEN_MPN" if brand_rule
                          else "MPN_BRAND_MISMATCH")
                if brand_rule:
                    exact_ids.add(model)
            output.append({
                "source": "Direct Liquidation", "lot_id": lot_id,
                "lot_url": url,
                "lot_ask_price_usd": f"{float(lot.get('price') or 0):.2f}",
                "lot_units": lot.get("units") or "",
                "lot_condition": lot.get("condition") or "",
                "manifest_accuracy_risk_pct": "15",
                "line_manufacturer": line.get("manufacturer") or "",
                "line_title": line.get("title") or "",
                "line_category": line.get("category") or "",
                "line_model": line.get("model") or "",
                "line_condition": line.get("condition") or "",
                "line_upc": line.get("upc") or "",
                "line_quantity": line.get("quantity") or "",
                "line_retail_price_usd": (
                    f"{float(line.get('retailPrice') or 0):.2f}"),
                "frozen_brand": frozen["brand"] if frozen else "",
                "frozen_mpn": frozen["mpn"] if frozen else "",
                "identity_status": status, "audited_at": audited_at,
            })
    with open(out_path, "w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS,
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    return {
        "lots": len(lot_ids), "manifest_lines": len(output),
        "manifest_units": sum(int(row["line_quantity"]) for row in output),
        "matched_identities": len(exact_ids),
        "coverage_gate_passed": len(exact_ids) >= 3,
        "sample_sufficient": len(lot_ids) >= 10,
    }


def freeze_liquidation_universe(manifest_path, out_path):
    """Freeze deterministic brand+model identities from a manifest ledger."""
    rows = _read_csv(manifest_path)
    groups = defaultdict(list)
    for row in rows:
        model = _canonical_text(row.get("line_model"))
        manufacturer = _canonical_text(row.get("line_manufacturer"))
        category = row.get("line_category", "")
        if not model or not manufacturer or not category:
            continue
        groups[model].append(row)
    output = []
    ambiguous = 0
    for model_key, members in sorted(groups.items()):
        manufacturers = sorted({row["line_manufacturer"].strip()
                                for row in members})
        canonical_manufacturers = {
            re.sub(r"(?:labs?|inc|llc|corp|corporation)$", "",
                   _canonical_text(value)) for value in manufacturers}
        if len(canonical_manufacturers) != 1:
            ambiguous += 1
            continue
        upcs = sorted({re.sub(r"\D", "", row.get("line_upc", ""))
                       for row in members if row.get("line_upc")})
        from identifiers import valid_gtin
        valid_gtins = [value for value in upcs if valid_gtin(value)]
        output.append({
            "model": members[0]["line_model"].strip(),
            "manufacturers": manufacturers[0],
            "titles": ";".join(sorted({row["line_title"].strip()
                                        for row in members})),
            "categories": ";".join(sorted({row["line_category"].strip()
                                             for row in members})),
            "upcs": ";".join(upcs), "valid_gtins": ";".join(valid_gtins),
            "lot_count": len({row["lot_id"] for row in members}),
            "manifest_line_count": len(members),
            "total_quantity": sum(int(row["line_quantity"] or 0)
                                  for row in members),
            "conditions": ";".join(sorted({row["line_condition"].strip()
                                             for row in members})),
            "lot_ids": ";".join(sorted({row["lot_id"] for row in members})),
            "lot_urls": ";".join(sorted({row["lot_url"] for row in members})),
            "first_seen_at": min(row["audited_at"] for row in members),
        })
    with open(out_path, "w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LIQUIDATION_UNIVERSE_FIELDS,
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    return {
        "manifest_lines": len(rows), "identities": len(output),
        "valid_gtin_identities": sum(bool(row["valid_gtins"])
                                     for row in output),
        "ambiguous_models": ambiguous, "checksum": basket_checksum(out_path),
    }


def _liquidation_condition_family(conditions):
    values = {value.strip() for value in conditions.split(";") if value.strip()}
    if "Untested Customer Returns" in values:
        return "for_parts"
    if "Used" in values:
        return "used"
    if values & {"Open Box Like New", "Like New"}:
        return "open_box"
    if values & {"GRADE A", "GRADE B", "GRADE C", "GRADE D"}:
        return "used"
    if values & {"New", "BRAND NEW"}:
        return "new"
    raise ValueError(f"unsupported liquidation conditions {conditions!r}")


def category_identity_coherent(source_categories, ebay_category_name):
    """Reject exact-model hits whose category represents another object."""
    ebay_words = set(re.findall(r"[a-z]+", ebay_category_name.casefold()))
    ebay_is_component = bool(ebay_words & _COMPONENT_CATEGORY_WORDS)
    source_leaves = [value.rsplit("->", 1)[-1].strip().casefold()
                     for value in source_categories.split(";") if value]
    source_words = set()
    for leaf in source_leaves:
        source_words.update(re.findall(r"[a-z]+", leaf))
    source_is_component = bool(source_words & _COMPONENT_CATEGORY_WORDS)
    return not (ebay_is_component and not source_is_component)


def run_liquidation_exit_audit(ebay, universe_path, out_path, region="US",
                               min_market_listings=3):
    """Resolve the frozen liquidation-first GTIN universe by source condition."""
    universe = [row for row in _read_csv(universe_path)
                if row.get("valid_gtins")]
    audited_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = []
    for row in universe:
        gtins = row["valid_gtins"].split(";")
        gtin = min(gtins, key=lambda value: (len(value), value))
        condition = _liquidation_condition_family(row["conditions"])
        result = ebay.lookup_gtin(
            gtin, region=region, limit=10, detail_limit=10,
            min_market_listings=min_market_listings,
            condition=condition) or {"resolution_status": "API_ERROR"}
        usable = bool(result.get("usable_market"))
        output.append({
            "model": row["model"], "manufacturer": row["manufacturers"],
            "gtin": gtin, "source_conditions": row["conditions"],
            "condition_family": condition,
            "manifest_lot_count": row["lot_count"],
            "manifest_quantity": row["total_quantity"],
            "audited_at": audited_at, "ebay_region": region,
            "active_total": result.get("n", 0),
            "returned": result.get("returned", 0),
            "inspected": result.get("inspected", 0),
            "exact_gtin_items": result.get("exact_gtin_items", 0),
            "exact_condition_gtin_items": result.get(
                "exact_condition_gtin_items", 0),
            "coherent_depth": result.get("coherent_depth", 0),
            "usable_market": int(usable),
            "resolution_status": result.get("resolution_status", "API_ERROR"),
            "median_price": result.get("median") or "",
            "p25_price": result.get("p25") or "",
            "p75_price": result.get("p75") or "",
            "currency": result.get("currency") or "",
            "economics_status": ("READY_FOR_LOT_ECONOMICS" if usable
                                 else "REJECT_EXIT_RESOLUTION"),
            "unresolved_inputs": ("sold_velocity;condition_sellable_rate;"
                                  "buyer_premium;freight;sales_tax;ebay_fee;"
                                  "outbound_postage;manifest_accuracy_haircut"),
        })
    opener = gzip.open if str(out_path).endswith(".gz") else open
    with opener(out_path, "wt", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LIQUIDATION_EXIT_FIELDS,
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    usable = sum(row["usable_market"] for row in output)
    return {
        "identities": len(output), "usable_markets": usable,
        "usable_rate_pct": 100 * usable / len(output) if output else 0,
        "advance_economics": usable >= 3,
    }


def _diagnostic_items(result):
    return (result or {}).get("items", []) or []


def _diagnostic_count(result):
    return int((result or {}).get("n", 0))


def _diagnostic_depth(result):
    return int((result or {}).get("coherent_depth", 0))


def _diagnostic_status(result):
    return (result or {}).get("resolution_status", "API_ERROR")


def run_liquidation_resolver_diagnostic(ebay, universe_path, out_path,
                                        region="US", min_market_listings=3):
    """Decompose GTIN, model, and condition effects over the frozen universe."""
    universe = [row for row in _read_csv(universe_path)
                if row.get("valid_gtins")]
    audited_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = []
    for row in universe:
        gtin = min(row["valid_gtins"].split(";"),
                   key=lambda value: (len(value), value))
        specific = _liquidation_condition_family(row["conditions"])
        broad = "broad_new" if specific == "open_box" else "broad_used"
        kwargs = {"region": region, "limit": 10, "detail_limit": 5,
                  "min_market_listings": min_market_listings}
        pass_a = ebay.lookup_gtin(gtin, condition=None, **kwargs)
        pass_b = ebay.lookup_gtin(gtin, condition=broad, **kwargs)
        pass_c = ebay.lookup_model(
            row["manufacturers"], row["model"], condition=None, **kwargs)
        pass_d = ebay.lookup_model(
            row["manufacturers"], row["model"], condition=specific, **kwargs)
        all_items = []
        for result in (pass_a, pass_b, pass_c, pass_d):
            all_items.extend(_diagnostic_items(result))
        model_items = [item for result in (pass_d, pass_c)
                       for item in _diagnostic_items(result)
                       if item.get("exact_identity")]
        categories = [item.get("category") for item in model_items
                      if item.get("category")]
        dominant = (max(set(categories), key=categories.count)
                    if categories else "")
        category_name = ebay.category_name(dominant, region=region)
        category_coherent = bool(category_name) and category_identity_coherent(
            row["categories"], category_name)
        condition_ids = sorted({str(item.get("condition_id"))
                                for item in all_items
                                if item.get("condition_id")})
        titles = list(dict.fromkeys(
            item.get("title") for item in all_items if item.get("title")))
        a_count, b_count = _diagnostic_count(pass_a), _diagnostic_count(pass_b)
        c_count, d_count = _diagnostic_count(pass_c), _diagnostic_count(pass_d)
        deterministic_market = any(
            (result or {}).get("usable_market")
            for result in (pass_a, pass_b, pass_c, pass_d))
        economics_eligible = bool(
            (pass_d or {}).get("usable_market") and category_coherent)
        if a_count == 0 and c_count == 0:
            classification = "LIKELY_MISSING_EXIT_MARKET"
        elif a_count == 0 and c_count > 0:
            classification = "GTIN_RETRIEVAL_FAILURE"
        elif a_count > 0 and b_count == 0:
            classification = "GTIN_CONDITION_FILTER_FAILURE"
        elif c_count > 0 and d_count == 0:
            classification = "MODEL_CONDITION_FILTER_FAILURE"
        elif (_diagnostic_depth(pass_a) == 0 and
              _diagnostic_depth(pass_c) == 0):
            classification = "IDENTITY_COHERENCE_REJECTION"
        else:
            classification = "DETERMINISTIC_MARKET_FOUND"
        output.append({
            "model": row["model"], "manufacturer": row["manufacturers"],
            "gtin": gtin, "source_categories": row["categories"],
            "source_conditions": row["conditions"],
            "specific_condition": specific, "broad_condition": broad,
            "audited_at": audited_at, "ebay_region": region,
            "gtin_unfiltered_count": a_count,
            "gtin_condition_count": b_count,
            "model_unfiltered_count": c_count,
            "model_condition_count": d_count,
            "gtin_unfiltered_exact_depth": _diagnostic_depth(pass_a),
            "gtin_condition_exact_depth": _diagnostic_depth(pass_b),
            "model_unfiltered_exact_depth": _diagnostic_depth(pass_c),
            "model_condition_exact_depth": _diagnostic_depth(pass_d),
            "gtin_unfiltered_status": _diagnostic_status(pass_a),
            "gtin_condition_status": _diagnostic_status(pass_b),
            "model_unfiltered_status": _diagnostic_status(pass_c),
            "model_condition_status": _diagnostic_status(pass_d),
            "dominant_category_id": dominant,
            "dominant_category_name": category_name,
            "category_identity_coherent": int(category_coherent),
            "returned_condition_ids": ";".join(condition_ids),
            "returned_titles_json": json.dumps(titles, separators=(",", ":")),
            "diagnostic_classification": classification,
            "deterministic_market_found": int(deterministic_market),
            "economics_eligible": int(economics_eligible),
        })
    opener = gzip.open if str(out_path).endswith(".gz") else open
    with opener(out_path, "wt", newline="") as stream:
        writer = csv.DictWriter(stream,
                                fieldnames=RESOLVER_DIAGNOSTIC_FIELDS,
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    return {
        "identities": len(output),
        "gtin_unfiltered_hits": sum(
            int(row["gtin_unfiltered_count"]) > 0 for row in output),
        "gtin_condition_hits": sum(
            int(row["gtin_condition_count"]) > 0 for row in output),
        "model_unfiltered_hits": sum(
            int(row["model_unfiltered_count"]) > 0 for row in output),
        "model_condition_hits": sum(
            int(row["model_condition_count"]) > 0 for row in output),
        "deterministic_markets": sum(
            int(row["deterministic_market_found"]) for row in output),
        "economics_eligible": sum(
            int(row["economics_eligible"]) for row in output),
    }


def run_liquidation_economics(ebay, universe_path, diagnostic_path,
                              manifest_path, out_path, usd_to_gbp,
                              fee_rate=0.15, return_rate=0.10,
                              outbound_shipping=10.0,
                              manifest_risk=0.15,
                              required_profit_gbp=15.0, region="US"):
    """Underwrite only category-coherent exact-condition survivors."""
    if not 0 < usd_to_gbp or not 0 <= manifest_risk < 1:
        raise ValueError("invalid FX rate or manifest risk")
    universe = {_canonical_text(row["model"]): row
                for row in _read_csv(universe_path)}
    eligible = [row for row in _read_csv(diagnostic_path)
                if row.get("economics_eligible") == "1"]
    manifests = _read_csv(manifest_path)
    lot_retail = defaultdict(float)
    for row in manifests:
        lot_retail[row["lot_id"]] += (
            float(row["line_retail_price_usd"] or 0) *
            int(row["line_quantity"] or 0))
    allocated = defaultdict(float)
    quantities = defaultdict(int)
    for row in manifests:
        key = _canonical_text(row["line_model"])
        total = lot_retail[row["lot_id"]]
        quantity = int(row["line_quantity"] or 0)
        if key not in universe or total <= 0 or quantity <= 0:
            continue
        line_retail = float(row["line_retail_price_usd"] or 0) * quantity
        allocated[key] += float(row["lot_ask_price_usd"] or 0) * line_retail / total
        quantities[key] += quantity
    output = []
    required_profit_usd = required_profit_gbp / usd_to_gbp
    usable_probability = 1 - manifest_risk
    for diagnostic in eligible:
        key = _canonical_text(diagnostic["model"])
        source = universe[key]
        condition = _liquidation_condition_family(source["conditions"])
        result = ebay.lookup_model(
            source["manufacturers"], source["model"], region=region,
            limit=10, detail_limit=5, min_market_listings=3,
            condition=condition) or {}
        p25 = result.get("p25")
        quantity = quantities[key]
        ask_per_unit = allocated[key] / quantity if quantity else 0
        if p25 is None or not result.get("usable_market"):
            net_exit = contribution = max_acquisition = None
            status = "REJECT_MARKET_CHANGED"
        else:
            p25 = float(p25)
            net_exit = usable_probability * (
                p25 * (1 - fee_rate - return_rate) - outbound_shipping)
            contribution = net_exit - ask_per_unit
            max_acquisition = max(0.0, net_exit - required_profit_usd)
            margin = contribution / p25 * 100 if p25 else 0
            status = ("VIABLE_AT_ALLOCATED_ASK" if
                      contribution * usd_to_gbp >= required_profit_gbp and
                      margin >= 20 else "REJECT_CONTRIBUTION_GATE")
        output.append({
            "model": source["model"],
            "manufacturer": source["manufacturers"],
            "source_categories": source["categories"],
            "source_conditions": source["conditions"],
            "condition_family": condition,
            "manifest_lot_count": source["lot_count"],
            "manifest_quantity": quantity,
            "market_depth": result.get("coherent_depth", 0),
            "active_p25_usd": f"{p25:.2f}" if p25 is not None else "",
            "allocated_ask_per_unit_usd": f"{ask_per_unit:.2f}",
            "ebay_fee_rate": f"{fee_rate:.4f}",
            "return_allowance_rate": f"{return_rate:.4f}",
            "outbound_shipping_usd": f"{outbound_shipping:.2f}",
            "manifest_usable_probability": f"{usable_probability:.4f}",
            "expected_net_exit_pre_acquisition_usd": (
                f"{net_exit:.2f}" if net_exit is not None else ""),
            "expected_contribution_at_ask_usd": (
                f"{contribution:.2f}" if contribution is not None else ""),
            "expected_contribution_at_ask_gbp": (
                f"{contribution * usd_to_gbp:.2f}"
                if contribution is not None else ""),
            "contribution_margin_at_ask_pct": (
                f"{contribution / p25 * 100:.2f}"
                if contribution is not None and p25 else ""),
            "required_profit_gbp": f"{required_profit_gbp:.2f}",
            "max_all_in_acquisition_per_manifest_unit_usd": (
                f"{max_acquisition:.2f}" if max_acquisition is not None else ""),
            "economics_status": status,
            "unresolved_lot_costs": "buyer_premium;inbound_freight;sales_tax",
        })
    with open(out_path, "w", newline="") as stream:
        writer = csv.DictWriter(stream,
                                fieldnames=LIQUIDATION_ECONOMICS_FIELDS,
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    viable = sum(row["economics_status"] == "VIABLE_AT_ALLOCATED_ASK"
                 for row in output)
    return {"rows": len(output), "viable": viable,
            "advance": viable >= 3}
