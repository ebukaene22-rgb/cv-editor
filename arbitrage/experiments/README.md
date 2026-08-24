# Pivot experiments

These sheets execute the bounded experiments selected after the broad
clearance-arbitrage post-mortem. They are evidence ledgers, not buy lists.

## Scarcity

`scarcity-measurement.csv.gz` is the full calendar-normalised SKU ledger.
`scarcity-review.csv` contains the first 20 unique products with a completed
source cycle or a new replenishment. Fill the marketplace and economics fields.

Pass only if at least 10% are exact-identity, marketplace-scarce opportunities
and at least one survives full contribution economics.

## Deterministic identity

`identity-coverage.csv` is the store/category coverage matrix and
`identity-ledger.csv.gz` is the variant-level evidence. The audit samples a
stable five-product panel per Shopify storefront, validates GTIN check digits,
and rejects GTINs reused across variants within one store. The four manually
reviewed collisions are classified in `identifier-collisions.csv`. Read
`IDENTITY-AUDIT.md` before using the result as a sourcing filter.

Regenerate it from a rebuilt database with:

```bash
python3 scan.py identity-audit
```

Add `--resolve-ebay` only when `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` are
set. A bounded live gate that inspects up to 50 returned listings per GTIN is:

```bash
python3 scan.py identity-audit --resolve-ebay \
  --max-ebay-lookups 100 --ebay-detail-limit 50 \
  --min-market-listings 3
```

The resolver batches item details through eBay `getItems`, writes inspected
listing evidence to `ebay-resolution-ledger.csv.gz`, and never replaces exact
marketplace confirmation with synthetic data.

## Open box and refurbished

`openbox-cohort.csv` contains 30 in-stock products whose source titles state a
secondary condition. Verify the exact model and match the resale condition
before entering sold evidence.

Pass at 3/30 robust opportunities with contribution margin at least 15% and
median verification time no more than 8 minutes.

## Bundles

`bundle-cohort.csv` contains 20 kits, sets, or multipacks. Record the component
mapping as JSON and calculate separate fulfilment and fees. A component is not
identified merely because its generic description looks similar.

Pass at 70% deterministic component maps and 2/20 opportunities with at least
15% contribution after separate fulfilment.

## Liquidation

Fill `liquidation-manifest.csv` from one real manifested lot, then run:

```bash
python3 scan.py liquidation experiments/liquidation-manifest.csv \
  --bid BID_GBP --freight FREIGHT_GBP --testing TESTING_GBP \
  --disposal DISPOSAL_GBP
```

The lot passes only with at least 70% deterministic identity by stated value,
80% manifest value coverage, 20% expected contribution, and no uncertain line
controlling more than 25% of the positive recovery pool.

Regenerate the passive and active sheets from a rebuilt database with:

```bash
python3 scan.py measure
python3 scan.py openbox-cohort
python3 scan.py bundle-cohort
python3 scan.py liquidation-template
```
