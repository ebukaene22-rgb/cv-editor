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
python3 scan.py funnel --synthetic  # survival funnel; drop --synthetic with a keyset
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

## Economics (`fees.py`)

The original fee model (flat 13.2% + separate 2.9% + $0.30 payment fee) was
wrong in three ways at once: it charged a payment-processing fee that eBay's
managed payments folds into the FVF (inflating costs), used one universal FVF
where business rates are category-dependent 6.9%–14.9% (wrong in either
direction), and ignored VAT on fees, the 0.35% regulatory operating fee,
international fees, and FVF-on-postage (understating costs). Biased both ways
is worse than pessimistic — it can't be corrected for.

The replacement computes contribution per order:

```
CM = Revenue − SupplierCost − InboundShip − Duty − OutboundShip
   − FVF(category) − PerOrderFee(£0.30/£0.40) − RegFee(0.35%)
   − IntlFee(region) − AdFee − VAT-on-fees(if unregistered)
   − ExpectedReturnCost
```

Two margins are reported, answering different questions: **CM/revenue**
(the underlying economics of the sales business) and **ROI on invested
cost** (how hard working capital works per cycle). GMROI comes later — it
needs turn time, which doesn't exist until something has sold.

Tax on eBay's own fees is a **seller-profile input, not a constant**: it
depends on where the selling entity is established, not on the marketplace
site. `fees.fee_tax_for()` knows GB (20%, reclaimable if VAT-registered)
and AE (5%, flagged UNVERIFIED until checked against a real eBay invoice);
unknown jurisdictions get 0 plus a warning that propagates to every report.
Commands default to `--seller-country AE`.

`fees.categorise()` maps titles into FVF bands, falling back to the
*higher* default band when unsure.

## Availability telemetry (`signals.py`)

An `available` 1→0 flip does **not** mean a sale — it can be a manual edit, a
withdrawal, a reallocation, or a feed change. So nothing here is called
sell-through. The measured quantity is **availability depletion**:

- one 1→0 flip = weak evidence (indistinguishable from withdrawal)
- a **replenishment cycle** (0→1→0) = strong evidence — withdrawals don't restock
- repeated cycles = demand intensity

Two confounders are controlled: store-wide flips (>25% of a store's SKUs
flipping in one snapshot = feed artefact, discounted) and disappearance from
the feed (delisted ≠ sold, excluded).

## Ranking

The prototype `margin × velocity ÷ log(competitors)` formula is gone — it
mixed incommensurable quantities and couldn't be sanity-checked against
money. The score is now directly interpretable:

```
E[monthly contribution] = E[monthly orders] × E[contribution/order]
score = E[monthly contribution] × MatchConf × SupplyConf − CapitalCost
```

Competitor count feeds the demand estimate (share-of-market shrinks with
crowding) instead of being an arbitrary divisor. `expected_monthly_orders` is
a structured estimator with visible assumptions, not a fitted model — fitting
one requires sales outcomes that don't exist until the thing has been traded.

## The review loop (`scan.py review / ingest / labels`)

Sold-price truth lives in eBay Product Research (Terapeak): real sold
prices, 90-day sold counts, sell-through — dashboard-only, login-walled,
and deliberately **not automated** (ToS, brittleness, and no need: at 10–30
candidates/day manual lookup is fine).

```bash
python3 scan.py review -n 30          # -> shortlist.csv + frozen features
# fill 3 columns per row from Product Research (~1 min each)
python3 scan.py ingest shortlist.csv  # labels stored against frozen features
python3 scan.py labels                # what the dataset says so far
```

The sheet carries every automated signal (supply cost, markdown, est CM,
ROI-on-cost, CM/revenue, active median/p25/sellers, stockout signal, a
prefilled Terapeak deep link) and three blank columns: `manual_sold_median`,
`manual_sold_90d`, `manual_verdict` (viable/marginal/dead).

**Features are frozen at sheet time** into the `candidates` table; ingest
only fills manual columns on the frozen row. Labels joined against live
data would drift between shortlisting and labeling and contaminate every
correlation. Already-labeled products are skipped on the next `review` —
review minutes are the scarce resource.

The product is the labeled dataset: after 100–200 rows, `labels` shows
viable-rate by frozen signal (depletion cycles, competition, markdown
depth, spread, region gap) against the base rate, plus the sold/asking
ratio that calibrates every future active-comp estimate. That's the moment
the scanner stops being heuristic and starts being learnable. Under n=100
the report says "noise" and means it.

## The funnel (`scan.py funnel`)

The experiment that matters: how much of the observed universe survives real
economics. Prints the distribution, not the top ten — a top-ten list looks
good from any distribution.

```bash
export EBAY_CLIENT_ID=... EBAY_CLIENT_SECRET=...    # free keyset
python3 scan.py funnel -n 300
python3 scan.py funnel -n 300 --synthetic           # no keyset: machinery test
```

Stages are labelled REAL / SYNTH so a stub run can't masquerade as market
evidence. Reports: survival by stage, contribution percentiles (median / P75
/ P90), survivor counts at £5/£10/£15, survivor rate by category, store
concentration (a shortlist 90% inside one store is one bet, not a
portfolio), and depletion-confidence vs competitor count once enough
snapshots exist.

Comps are cached for 6 h and looked up **once per product, not per variant** —
eight sizes of one shoe are one trade and one call. That keeps a scan inside
the free 5,000 calls/day quota.

## Next

- Swap the Browse median for a real sold-comp source if a Keepa key or an
  approved Insights keyset becomes available — the `EbayComp.lookup` contract
  (`median`, `p25`, `n`) is what the scorer depends on, so it is a drop-in.
- Per-lane duty rates rather than one global `--duty`.
- Alert on rank changes rather than absolute rank, once the series is long
  enough for that to mean anything.
