# Unit-Value Floor

Status: **CORE PRE-RESOLUTION RULE**  
Adopted: 2026-08-24

## Rule

Every physical-product experiment must screen unit value before identity
enrichment, marketplace resolution, or mechanism scoring.

- Default expected exit floor: **GBP 50**
- Preferred expected exit band: **GBP 75-200**
- Default bounded cohort band: **GBP 50-200**
- Required net contribution: **GBP 15 per unit**

The GBP 50 screen is a necessary condition, not evidence of profitability.
Before marketplace resolution, expected exit may only be represented by a
labelled source-side proxy such as explicit reference retail. It must never be
reported as an observed resale value. The marketplace's exact-condition p25
replaces the proxy once resolution runs.

## Economic Basis

For source cost `S`, outbound fulfilment `F`, proportional fees `f`, returns
allowance `r`, and target contribution `T`, the minimum required exit is:

```text
minimum_exit = (S + F + T) / (1 - f - r)
```

Assuming a strong 40% buy-to-exit ratio, an AE seller, 12.9% final-value fee,
per-order and regulatory fees, and 6% returns, the approximate floors are:

| Target contribution | Ship GBP 3 | Ship GBP 5 | Ship GBP 8 |
|---|---:|---:|---:|
| GBP 5 | GBP 24 | GBP 29 | GBP 35 |
| GBP 10 | GBP 35 | GBP 40 | GBP 46 |
| GBP 15 | GBP 46 | GBP 51 | GBP 57 |
| GBP 20 | GBP 57 | GBP 61 | GBP 68 |
| GBP 25 | GBP 68 | GBP 72 | GBP 79 |

These are scenario thresholds, not universal impossibility bounds: a lower
acquisition ratio lowers the required exit. They show why GBP 50 is a sensible
default screen under ordinary sourcing and small-parcel fulfilment.

## Wyze Evidence

The small-goods cohort contained 136/138 manifest lines from Wyze. Its four
resolved exit markets had active p25 values of $9.99-$21.49 against $10
outbound shipping. Fulfilment alone consumed roughly 47-100% of revenue before
fees. `KILL_ECONOMICS` is decisive for that cohort but weak evidence against
liquidation generally because the unit values were structurally unsuitable.

## Consequences

- Clearance, fitment, small-goods liquidation, and multipack decomposition
  results must be interpreted through unit value rather than as four wholly
  independent mechanism failures.
- Bundle decomposition applies the floor independently to every child because
  splitting into `N` components multiplies fulfilment by `N`.
- Whole-appliance liquidation remains excluded for product-type, freight,
  storage, and handling reasons even though its unit values are high.

## Ordering

1. Verify current availability, source price, and explicit condition.
2. Apply the GBP 50-200 unit-value proxy band.
3. Freeze the cohort and checksum it.
4. Resolve exact model/MPN and structured brand.
5. Enforce condition, product-type, and category coherence.
6. Replace the proxy with exact-condition active p25.
7. Apply fees, shipping, returns, source shipping, and acquisition cost.
8. Require at least GBP 15 contribution per unit.

Rows below the floor are `REJECT_UNIT_VALUE_PRE_RESOLUTION`. A source universe
that cannot provide the requested frozen cohort is
`INSUFFICIENT_SOURCE_COHORT`, not a failed arbitrage mechanism.
