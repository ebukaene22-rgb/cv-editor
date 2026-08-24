# Pivot experiments

These sheets execute the bounded experiments selected after the broad
clearance-arbitrage post-mortem. They are evidence ledgers, not buy lists.

## Scarcity

`scarcity-measurement.csv.gz` is the full calendar-normalised SKU ledger.
`scarcity-review.csv` contains the first 20 unique products with a completed
source cycle or a new replenishment. Fill the marketplace and economics fields.

Pass only if at least 10% are exact-identity, marketplace-scarce opportunities
and at least one survives full contribution economics.

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
