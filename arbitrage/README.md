# Supply-side arbitrage scanner

Findings from probing live sources on 2026-08-20, and a working scanner built on
whatever survived the probe.

## What the probe actually found

The decisive result is that **the two sides of an arbitrage trade have opposite
accessibility**, and it is the reverse of what most guides assume.

| Source | Result from a datacenter IP |
|---|---|
| Shopify `/<domain>/products.json` | **200** — full catalogue, paginated, 250/page |
| WooCommerce `/wp-json/wc/store/v1/products` | **200** on stores that leave the Store API on |
| eBay HTML (incl. sold listings) | **403** |
| eBay Browse / Finding API without a key | **403 / 418** |
| Amazon product pages | **200 but a CAPTCHA body** (~3.8 KB robot check) |
| idealo, geizhals, kelkoo | **403** |
| PriceRunner | 200 |
| FX (`api.frankfurter.dev`) | 200, ECB daily |

So: **demand-side marketplaces are hard-blocked; supply-side storefronts are wide
open.** Scraping Amazon/eBay for resale comps needs residential proxies or a paid
API (Keepa for Amazon history, eBay's own API key — free tier — for sold comps).
Scraping supplier catalogues needs nothing at all.

That inverts the usual strategy. The cheap, durable edge is on the supply side:
finding *what to buy* is free, and you pay only for the comp on *what it sells
for* — one paid lookup on a shortlist, instead of scraping a whole marketplace.

## Why `products.json` is the good one

It is not an unguarded HTML page — it is a documented public endpoint, and per
variant it returns:

| Field | Signal it unlocks |
|---|---|
| `sku` | cross-storefront product matching, no fuzzy title matching needed |
| `price` + `compare_at_price` | clearance depth, in real time |
| `available` | **stock, per variant** — poll it and you get demand |
| `updated_at` | repricing detection |
| `grams` | real landed-cost shipping, not a guess |
| `created_at` | new-product / new-line detection |

`available` is the valuable one. A single scrape shows a price; a *time series* of
`available` shows what actually sells. Polling daily and diffing turns a public
catalogue into a sell-through dataset nobody is selling you.

## The four signals

Measured live across 10 stores / 37,516 variants:

**1. Cross-region gap** — same SKU, different regional storefronts of one brand.
Allbirds US vs UK vs EU vs CA: 2,154 SKUs matched by SKU across regions, median
gap ~25%, **112 pairs above 25% with the buy side actually in stock**, topping out
at 166% (`Tree Topper`: $49 US vs $130 UK). VAT is stripped before comparing —
UK/EU quote tax-inclusive and US/CA do not, so the naive sticker comparison
overstates every gap by ~20%. That correction is the difference between a real
signal and a spreadsheet full of phantom margin.

**2. Clearance depth** — `compare_at_price` vs `price`, in stock only. Found 60–66%
markdowns live on Red Bull Shop, Allbirds CA, Death Wish Coffee.

**3. Sell-out velocity** — variants flipping `available` 1→0 between snapshots.
Real demand, not asking price. Needs two snapshots; the query is verified.

**4. New SKUs** — first appearance of a SKU, for catching a line before it ranks.

## Usage

Stdlib only, no dependencies.

```bash
python3 scan.py stores              # probe which endpoints still serve data
python3 scan.py snapshot            # poll everything into prices.db
python3 scan.py arb --group allbirds --min 25
python3 scan.py clearance --min 45
python3 scan.py sellout             # needs 2+ snapshots
python3 scan.py new
```

`stores.txt` is `platform  domain  currency  region  group` — `region` drives VAT
stripping, `group` ties a brand's regional storefronts together for `arb`.

Run `snapshot` on a daily cron. The price history is the asset: single scrapes are
commodity, and the accumulated series is what nobody else has.

## Honest limits

- **A gap is not a margin.** These numbers are gross. Subtract duty, import VAT,
  marketplace fees (~13% eBay, ~15% Amazon), payment fees, shipping, and a return
  rate. The `grams` field is there so shipping can be modelled rather than guessed.
- **Cross-region retail gaps often aren't tradeable by design.** Brands geo-fence
  checkout, block freight forwarders, and void warranties on grey imports. Treat
  the `arb` output as a lead list to verify by hand, not a signal to act on.
- **SKU match ≠ identical product.** Regional variants differ in packaging, plug
  type, and sizing convention.
- **Scraping vs. ToS.** These endpoints are public and unauthenticated, but polling
  is still on someone's servers — the collectors rate-limit at 0.4 s/page and
  identify over normal HTTP. Marketplace dropshipping rules are a separate matter:
  Amazon prohibits retail-to-marketplace dropshipping where another retailer ships
  to your customer, and eBay restricts it. Supplier-direct with you as seller of
  record is the compliant shape.
- `arb` on a single brand's own storefronts is the *demo*, not the strategy. The
  real use is one supplier catalogue against a different resale venue — which is
  why the sell-side comp needs an API key.

## Next

Wire a resale comp onto the shortlist: eBay Browse API (free key) for sold
comps, or Keepa for Amazon price history. Score `margin × sell-through ×
1/competitor_count` and alert only on the top of that, rather than on raw gap.
