#!/usr/bin/env python3
"""Bounded experiment tooling for the post-clearance pivots."""
import csv
import gzip
import json
import os
import re
import urllib.parse

import identity as I
import review as R
import signals as S


CONDITION_GRADES = (
    ("certified_refurbished", ("certified refurbished", "pd certified")),
    ("refurbished", ("refurb", "refurbished")),
    ("open_box", ("open box", "openbox")),
    ("factory_second", ("factory 2nd", "factory second", "b-stock", "b stock")),
    ("cosmetic_damage", ("scratch", "dent", "blemish")),
    ("pre_owned", ("pre-owned", "preowned")),
)

BUNDLE_RE = re.compile(
    r"\b(bundle|kit|set|pack|duo|trio|collection|assortment|starter)\b|\d+\s*[- ]?piece",
    re.I,
)


def condition_grade(title):
    text = (title or "").lower()
    for grade, markers in CONDITION_GRADES:
        if any(marker in text for marker in markers):
            return grade
    return None


def _latest_rows(conn):
    """Latest successful observation per domain, not one global timestamp."""
    return conn.execute("""
        SELECT o.* FROM obs o
        JOIN (SELECT domain, MAX(ts) ts FROM obs GROUP BY domain) latest
          ON o.domain=latest.domain AND o.ts=latest.ts
    """).fetchall()


def _to_gbp(value, currency, rates):
    if value is None:
        return None
    gbp = rates.get("GBP") or 0.79
    return value / (rates.get(currency) or 1.0) * gbp


def _write(path, fields, rows):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    opener = gzip.open if path.endswith(".gz") else open
    mode = "wt" if path.endswith(".gz") else "w"
    with opener(path, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sold_url(query):
    return "https://www.ebay.co.uk/sch/i.html?" + urllib.parse.urlencode({
        "_nkw": query, "LH_Sold": "1", "LH_Complete": "1"
    })


def _signal_cache(conn):
    return {domain: S.depletion_signals(conn, domain)
            for (domain,) in conn.execute("SELECT DISTINCT domain FROM obs")}


def _regional_states(conn):
    """Exact-SKU availability asymmetry at each group's latest shared poll."""
    out = {}
    groups = [r[0] for r in conn.execute(
        "SELECT DISTINCT grp FROM obs WHERE grp IS NOT NULL")]
    for grp in groups:
        snapshots = conn.execute("""
            SELECT ts, COUNT(DISTINCT domain) domains
            FROM obs WHERE grp=? GROUP BY ts HAVING domains >= 2
            ORDER BY ts DESC LIMIT 1
        """, (grp,)).fetchone()
        if not snapshots:
            continue
        ts = snapshots[0]
        book = {}
        for sku, domain, region, available in conn.execute(
                "SELECT sku,domain,region,available FROM obs WHERE grp=? AND ts=?",
                (grp, ts)):
            book.setdefault(sku, []).append((domain, region, available))
        for sku, states in book.items():
            if len({s[1] for s in states}) < 2:
                continue
            available = sum(s[2] for s in states)
            out[(grp, sku)] = {
                "regional_ts": ts,
                "regional_regions": len({s[1] for s in states}),
                "regional_in_stock": available,
                "regional_gap": int(0 < available < len(states)),
            }
    return out


def write_measurement(conn, out_path, review_path, review_n=20):
    sigs = _signal_cache(conn)
    regional = _regional_states(conn)
    latest = {(r["domain"], r["sku"]): r for r in _latest_rows(conn)}
    rows = []
    for domain, by_sku in sigs.items():
        for sku, sig in by_sku.items():
            row = latest.get((domain, sku))
            if not row:
                continue
            rec = {
                "domain": domain, "group": row["grp"] or "",
                "region": row["region"] or "", "sku": sku,
                "title": row["title"] or "", "vendor": row["vendor"] or "",
                "url": row["url"] or "",
                "latest_available": row["available"], **sig,
            }
            rec.update(regional.get((row["grp"], sku), {}))
            rows.append(rec)

    fields = [
        "domain", "group", "region", "sku", "title", "url",
        "latest_available", "first_seen", "last_seen", "n_obs", "sku_days",
        "coverage", "stockouts", "restocks", "cycles", "cycles_per_30d",
        "in_stock_days", "out_of_stock_days", "oos_frac", "delisted",
        "price_changes", "price_stability", "confidence", "regional_ts",
        "regional_regions", "regional_in_stock", "regional_gap",
    ]
    _write(out_path, fields, rows)

    eligible = [r for r in rows if r["latest_available"] and
                (r["cycles"] or r["restocks"])]
    eligible.sort(key=lambda r: (
        -r["cycles"], -r["restocks"], -r["stockouts"],
        -(r.get("regional_gap") or 0), -r["coverage"], r["title"]))
    review_rows = []
    seen_products = set()
    for r in eligible:
        query = R.product_key(r)
        product = (r["domain"], query.lower())
        if product in seen_products:
            continue
        seen_products.add(product)
        i = len(review_rows) + 1
        review_rows.append({
            "id": i, "candidate": r["title"], "sku": r["sku"],
            "source_url": r["url"], "source_cycles": r["cycles"],
            "source_restocks": r["restocks"],
            "source_depletions": r["stockouts"],
            "cycles_per_30d": r["cycles_per_30d"],
            "coverage": r["coverage"], "regional_gap": r.get("regional_gap", 0),
            "market_query": query, "sold_search_url": _sold_url(query),
            "exact_identity": "", "market_current_stock": "",
            "market_est_sold_qty": "", "market_competitors": "",
            "market_condition": "", "estimated_cm_pct": "",
            "verification_minutes": "", "verdict": "", "notes": "",
        })
        if len(review_rows) >= review_n:
            break
    review_fields = [
        "id", "candidate", "sku", "source_url", "source_cycles",
        "source_restocks", "source_depletions", "cycles_per_30d", "coverage",
        "regional_gap", "market_query", "sold_search_url", "exact_identity",
        "market_current_stock", "market_est_sold_qty", "market_competitors",
        "market_condition", "estimated_cm_pct", "verification_minutes",
        "verdict", "notes",
    ]
    _write(review_path, review_fields, review_rows)

    sku_days = sum(r["sku_days"] for r in rows)
    totals = {name: sum(r[name] for r in rows)
              for name in ("stockouts", "restocks", "cycles")}
    totals["sku_days"] = sku_days
    totals["rows"] = len(rows)
    totals["review_rows"] = len(review_rows)
    for name in ("stockouts", "restocks", "cycles"):
        totals[name + "_per_10k_sku_days"] = (
            totals[name] / sku_days * 10000 if sku_days else 0.0)
    return totals


def write_openbox_cohort(conn, rates, out_path, limit=30):
    sigs = _signal_cache(conn)
    candidates = {}
    for row in _latest_rows(conn):
        grade = condition_grade(row["title"])
        if not grade or not row["available"] or not row["price"]:
            continue
        key = (row["domain"], R.product_key(row).lower())
        buy = _to_gbp(row["price"], row["currency"], rates)
        discount = (1 - row["price"] / row["compare"]
                    if row["compare"] and row["compare"] > row["price"] else 0)
        signal = sigs.get(row["domain"], {}).get(row["sku"], {})
        candidate = {"row": row, "grade": grade, "buy": buy,
                     "discount": discount, "signal": signal}
        if key not in candidates or buy < candidates[key]["buy"]:
            candidates[key] = candidate
    ranked = sorted(candidates.values(), key=lambda x: (
        -x["signal"].get("cycles", 0), -x["discount"], x["buy"]))[:limit]
    rows = []
    for i, item in enumerate(ranked, 1):
        row, sig = item["row"], item["signal"]
        query = f"{R.product_key(row)} {item['grade'].replace('_', ' ')}"
        rows.append({
            "id": i, "candidate": row["title"], "sku": row["sku"],
            "product_type": row["ptype"] or "", "source_url": row["url"] or "",
            "source_condition": item["grade"], "source_currency": row["currency"],
            "source_price": row["price"], "source_gbp": f"{item['buy']:.2f}",
            "source_discount_pct": f"{item['discount'] * 100:.1f}",
            "source_cycles": sig.get("cycles", 0), "market_query": query,
            "sold_search_url": _sold_url(query), "exact_model": "",
            "condition_match": "", "manual_sold_median_gbp": "",
            "manual_sold_90d": "", "estimated_cm_gbp": "",
            "estimated_cm_pct": "", "verification_minutes": "",
            "verdict": "", "notes": "",
        })
    fields = list(rows[0]) if rows else [
        "id", "candidate", "sku", "product_type", "source_url",
        "source_condition", "source_currency", "source_price", "source_gbp",
        "source_discount_pct", "source_cycles", "market_query",
        "sold_search_url", "exact_model", "condition_match",
        "manual_sold_median_gbp", "manual_sold_90d", "estimated_cm_gbp",
        "estimated_cm_pct", "verification_minutes", "verdict", "notes",
    ]
    _write(out_path, fields, rows)
    return len(rows)


def write_bundle_cohort(conn, rates, out_path, limit=20):
    candidates = {}
    for row in _latest_rows(conn):
        if not row["available"] or not row["price"] or not BUNDLE_RE.search(row["title"] or ""):
            continue
        if I.condition_flag(row["title"]):
            continue
        key = (row["domain"], R.product_key(row).lower())
        buy = _to_gbp(row["price"], row["currency"], rates)
        discount = (1 - row["price"] / row["compare"]
                    if row["compare"] and row["compare"] > row["price"] else 0)
        candidate = {"row": row, "buy": buy, "discount": discount}
        if key not in candidates or buy < candidates[key]["buy"]:
            candidates[key] = candidate
    ranked = sorted(candidates.values(), key=lambda x: (-x["discount"], x["buy"]))[:limit]
    rows = []
    for i, item in enumerate(ranked, 1):
        row = item["row"]
        rows.append({
            "id": i, "candidate": row["title"], "sku": row["sku"],
            "source_url": row["url"] or "", "source_gbp": f"{item['buy']:.2f}",
            "bundle_marker": BUNDLE_RE.search(row["title"]).group(0),
            "component_map_json": "", "component_identity_coverage_pct": "",
            "component_revenue_gbp": "", "separate_fulfilment_gbp": "",
            "marketplace_fees_gbp": "", "expected_returns_gbp": "",
            "estimated_cm_gbp": "", "estimated_cm_pct": "",
            "verification_minutes": "", "verdict": "", "notes": "",
        })
    fields = list(rows[0]) if rows else [
        "id", "candidate", "sku", "source_url", "source_gbp", "bundle_marker",
        "component_map_json", "component_identity_coverage_pct",
        "component_revenue_gbp", "separate_fulfilment_gbp",
        "marketplace_fees_gbp", "expected_returns_gbp", "estimated_cm_gbp",
        "estimated_cm_pct", "verification_minutes", "verdict", "notes",
    ]
    _write(out_path, fields, rows)
    return len(rows)


LIQUIDATION_FIELDS = [
    "line_id", "title", "quantity", "stated_retail_each_gbp",
    "deterministic_identity", "expected_resale_each_gbp", "sellable_rate",
    "fulfilment_each_gbp", "notes",
]


def write_liquidation_template(path):
    _write(path, LIQUIDATION_FIELDS, [])


def underwrite_liquidation(path, bid, freight, testing=0.0, disposal=0.0,
                           fee_rate=0.15):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    retail_total = identified_value = covered_value = revenue = fulfilment = 0.0
    uncertain_positive = []
    for row in rows:
        qty = float(row.get("quantity") or 0)
        retail = float(row.get("stated_retail_each_gbp") or 0)
        line_retail = qty * retail
        retail_total += line_retail
        identified = str(row.get("deterministic_identity") or "").strip().lower() in {
            "1", "true", "yes", "y"
        }
        if identified:
            identified_value += line_retail
        resale_text = row.get("expected_resale_each_gbp") or ""
        if not resale_text:
            continue
        covered_value += line_retail
        resale = float(resale_text)
        sellable = float(row.get("sellable_rate") or 0)
        sold_units = qty * max(0.0, min(1.0, sellable))
        line_revenue = sold_units * resale
        line_fulfilment = sold_units * float(row.get("fulfilment_each_gbp") or 0)
        revenue += line_revenue
        fulfilment += line_fulfilment
        line_contribution = line_revenue * (1 - fee_rate) - line_fulfilment
        if not identified and line_contribution > 0:
            uncertain_positive.append(line_contribution)
    fees = revenue * fee_rate
    contribution = revenue - fees - fulfilment - bid - freight - testing - disposal
    positive_pool = max(0.0, revenue - fees - fulfilment)
    return {
        "manifest_lines": len(rows), "stated_retail_gbp": retail_total,
        "identity_coverage_pct": identified_value / retail_total * 100 if retail_total else 0,
        "manifest_value_coverage_pct": covered_value / retail_total * 100 if retail_total else 0,
        "expected_revenue_gbp": revenue, "marketplace_fees_gbp": fees,
        "fulfilment_gbp": fulfilment, "bid_gbp": bid, "freight_gbp": freight,
        "testing_gbp": testing, "disposal_gbp": disposal,
        "expected_contribution_gbp": contribution,
        "expected_contribution_pct": contribution / revenue * 100 if revenue else 0,
        "largest_uncertain_profit_share_pct": (
            max(uncertain_positive, default=0) / positive_pool * 100
            if positive_pool else 0),
    }


def print_underwriting(result):
    print(json.dumps(result, indent=2, sort_keys=True))
    passes = (
        result["identity_coverage_pct"] >= 70 and
        result["manifest_value_coverage_pct"] >= 80 and
        result["expected_contribution_pct"] >= 20 and
        result["largest_uncertain_profit_share_pct"] <= 25
    )
    print("PASS" if passes else "FAIL")
    return passes
