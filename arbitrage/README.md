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

Python 3.9+, stdlib only, no dependencies, no install step.

```bash
python3 scan.py stores              # probe which endpoints still serve data
python3 scan.py snapshot            # poll everything into prices.db
python3 scan.py arb --group allbirds --min 25
python3 scan.py clearance --min 45
python3 scan.py sellout             # needs 2+ snapshots
python3 scan.py new
python3 scan.py score --synthetic   # rank; drop --synthetic with a keyset
```

Daily collection:

```cron
17 6 * * *  cd /path/to/arbitrage && /usr/bin/python3 scan.py snapshot >> scan.log 2>&1
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

## The comp layer (`comp.py`)

Supply-side scanning says what is cheap and what is moving. `score` answers the
other half — what it resells for, and how crowded that resale is.

**Sold-price data is not obtainable for free, and this is worth being precise
about.** eBay's sold comps live in the Marketplace Insights API (90-day sales
history), which is a Limited Release keyset that eBay does not currently grant
to new applicants. The free Browse API returns *active listings only and
explicitly no sold data*. The sold-listing web UI (`LH_Sold=1`) does show it,
but 403s from a datacenter IP. So "what it actually sold for" is off the table
without a paid provider (Keepa for Amazon history) or residential proxies.

That is survivable, because velocity does not have to come from eBay:

| Term | Source |
|---|---|
| resale price | eBay Browse API — median **asking** price, free keyset |
| competition | Browse `total` — active listings for the query, free |
| **velocity** | **our own time series** — `available` 1→0 flips from `sellout` |

A variant flipping out of stock is a real unit leaving a real shelf. That is a
better demand signal than an asking price anyway, and it is the part nobody
can sell you — it only exists if you have been polling.

Ranking is `margin × velocity ÷ log(e + competitors)`. Competition is damped
because the 40th seller hurts far less than the 4th. Velocity is unknown until
a second snapshot exists and is treated as a neutral 0.5 rather than 0, or
every candidate would score zero on day one.

Margin runs through a deliberately pessimistic fee model (`comp.Fees`):
marketplace fee 13.2%, payment 2.9% + $0.30, shipping derived from the `grams`
field, configurable duty, 6% return rate. A gap that only clears an optimistic
fee model is not a trade.

```bash
export EBAY_CLIENT_ID=...  EBAY_CLIENT_SECRET=...   # free keyset
python3 scan.py score --min-margin 0.25 --duty 0.12
python3 scan.py score --synthetic                   # no keyset: stub comps
```

Comps are cached for 6 h and looked up **once per product, not per variant** —
eight sizes of one shoe are one trade and one call. That keeps a scan inside
the free 5,000 calls/day quota.

Without credentials `score` runs `--synthetic`: deterministic stub comps so the
fee model and ranking are still exercisable. Those rows are labelled and must
not be traded on.

## Next

- Swap the Browse median for a real sold-comp source if a Keepa key or an
  approved Insights keyset becomes available — the `EbayComp.lookup` contract
  (`median`, `p25`, `n`) is what the scorer depends on, so it is a drop-in.
- Per-lane duty rates rather than one global `--duty`.
- Alert on rank changes rather than absolute rank, once the series is long
  enough for that to mean anything.
