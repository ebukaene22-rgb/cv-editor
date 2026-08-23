#!/usr/bin/env python3
"""
Local sold-counter harvester -- STANDALONE DIAGNOSTIC, not funnel-integrated.

Runs on a residential machine with a real browser (eBay's search pages
block datacenter IPs; sold COUNTERS on active listings are visible without
login, unlike the sold-history view). Extracts per-listing "N sold"
transaction evidence for a fixed target list and writes an auditable CSV.

Ground rules (non-negotiable):
  - headed Chrome (channel="chrome"), fresh logged-OUT profile
  - never a profile where any eBay account is signed in
  - human pacing: 4-8s between queries, one results page per query
  - target list only (~20 products), never bulk crawling

Usage (from arbitrage/ with the Playwright venv active):
  python harvest_sold.py                 # harvests targets-sold-harvest.csv
  python harvest_sold.py --market US     # ebay.com instead of ebay.co.uk
"""
import csv
import random
import re
import sys
import time
from datetime import datetime, timezone

import identity as I

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("pip install playwright && playwright install chrome")

MARKETS = {"GB": "https://www.ebay.co.uk", "US": "https://www.ebay.com"}
SOLD_RE = re.compile(r"([\d,]+)\+?\s*sold", re.I)
PRICE_RE = re.compile(r"[£$]\s?([\d,]+\.?\d*)")


def parse_cards(page):
    cards = page.query_selector_all("li.s-item, .s-item")
    out = []
    for c in cards:
        txt = c.inner_text()
        if not txt or "Shop on eBay" in txt:
            continue
        t = c.query_selector(".s-item__title")
        p = c.query_selector(".s-item__price")
        title = t.inner_text().strip() if t else ""
        m = PRICE_RE.search(p.inner_text() if p else txt)
        price = float(m.group(1).replace(",", "")) if m else None
        sm = SOLD_RE.search(txt)
        sold = int(sm.group(1).replace(",", "")) if sm else 0
        cond = "new" if re.search(r"brand new|new with|new \(", txt, re.I) else \
               ("used" if re.search(r"pre-owned|used", txt, re.I) else "?")
        if title and price:
            out.append({"title": title, "price": price, "sold": sold,
                        "cond": cond, "raw": txt.replace("\n", " | ")[:300]})
    return out


def main():
    market = "US" if "--market US" in " ".join(sys.argv) else None
    targets = list(csv.DictReader(open("targets-sold-harvest.csv")))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out = csv.writer(open(f"history/sold-counters-{ts}.csv", "w", newline=""))
    out.writerow(["ts", "product", "query", "market", "listing_title",
                  "price_local", "sold_count", "condition",
                  "identity_match", "match_reason", "raw_snippet"])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        ctx = browser.new_context()      # fresh profile: logged out by construction
        page = ctx.new_page()
        for t in targets:
            mkt = market or t.get("market") or "GB"
            url = (f"{MARKETS[mkt]}/sch/i.html?_nkw="
                   + t["query"].replace(" ", "+") + "&_sop=12")
            try:
                page.goto(url, timeout=45000)
                page.wait_for_timeout(2500)
                cards = parse_cards(page)
            except Exception as e:
                print(f"  !! {t['product']}: {type(e).__name__}")
                continue
            n_sold_evid = 0
            for card in cards[:25]:
                ok, why = I.title_matches(t["query"], card["title"])
                out.writerow([ts, t["product"], t["query"], mkt,
                              card["title"], card["price"], card["sold"],
                              card["cond"], "yes" if ok else "no",
                              why or "match", card["raw"]])
                if ok and card["sold"] > 0:
                    n_sold_evid += 1
            print(f"  {t['product'][:38]:<40} {len(cards):>3} cards, "
                  f"{n_sold_evid} identity-matched with sold>0")
            time.sleep(random.uniform(4, 8))
        browser.close()
    print(f"\nwrote history/sold-counters-{ts}.csv -- commit and push it")


if __name__ == "__main__":
    main()
