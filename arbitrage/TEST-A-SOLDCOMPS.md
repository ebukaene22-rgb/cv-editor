# Test A — structured sold data (SoldComps) — 2026-08-23

Retrospective benchmark: 18 labelled products -> their individual sold rows
-> OUR identity matcher -> recomputed sold median -> scored against the
human verdicts we already hold. ~22 of the 100/month free requests used.

## The data source works

`GET api.sold-comps.com/v1/scrape` returns real, recent, machine-readable
sold rows: `soldPrice`, `endedAt`, `condition`, `sellerUsername`, `epid`,
shipping, totals. Many rows dated within 1-3 days of the query. This is
genuinely the sold data eBay's own APIs will not give us.

Not used: their optional `X-eBay-Cookies` header, which forwards your own
logged-in eBay session. Their docs say "the risk is yours alone" -- that is
the seller-account exposure we have declined throughout.

## The benchmark result: NOT usable as-is

| metric | value |
|---|---|
| median absolute error vs verified sold price (n=11) | **32%** |
| their raw median's error, same rows | 52% |
| within 10% / 20% / 30% | 1/11, 3/11, 4/11 |
| products returning zero matched rows | 2/18 |

Applying our matcher improves on their aggregate (32% vs 52%) but 32% is
unusable against 20-30% target margins. Worse, **errors skew upward on the
known failures** -- Percale 20->36, Eddy 52->85, Ridge 56->212 -- which is
precisely the direction that manufactures false positives.

## The cause is OUR identity matcher, not their data

The worst outlier explains everything. For "Ridge Daily Driver Kit" our
matcher accepted 31 of 44 rows, including:

    $1098  Power Stop K6375 Z23 Daily Driver Brake Pad and Rotor Kit
    $ 705  Power Stop K8171 Z23 Daily Driver Brake Pad ...
    $ 606  Power Stop K6560 Z23 Daily Driver Brake Pad ...

Car brake pads, matched to a wallet, because "daily/driver/kit" are
ordinary words and the query carries no numeric model core to require.
Same mechanism as Capers (sunglasses named after a foodstuff).

Note the inverse: the two known winners scored the two BEST errors --
SuitCase -3% (£30 vs £31), Cashmere -13% (£52 vs £60) -- because
"SuitCase MacBook 16-inch" and "Heathered Cashmere" are distinctive.

`epid` does not rescue this: coverage is 25/44 on Ridge (all brake pads)
and 2/40 on the SuitCase. The canonical ID is absent exactly where it is
needed.

## Conclusion

The missing sold-data layer was **not hiding a profitable market**. With
real transaction prices in hand, the failures remain failures and the
valuation error is dominated by product identity.

Identity is now conclusively the binding constraint, and it is
name-dependent in a way that is not fixable by better data purchasing:

- **distinctive names** (SuitCase MacBook 16-inch, Heathered Cashmere,
  IceFlow 40oz) -> sold data lands within ~3-17%.
- **ordinary-word names** (Daily Driver, Capers, Beechwood Spatulas)
  -> unsalvageable at any price, from any source.

The actionable change is therefore not a better matcher but a **hard
exclusion**: products whose identity cannot be pinned deterministically
should leave the funnel before valuation, not be scored badly inside it.
That shrinks the addressable universe substantially -- which is itself the
finding.
