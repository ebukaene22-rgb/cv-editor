# Exact-MPN manifested-liquidation gate

Audit time: 2026-08-24 11:27 UTC
Demand universe: the same 16 exact-MPN eBay resolver survivors
Source: Direct Liquidation live appliance-accessories lots

## Method

The audit parses each lot's structured line-level manifest and compares its
manufacturer and model fields against the frozen demand universe. Titles are
not used as identity evidence. Each line also records quantity, condition,
UPC, stated retail price, lot ask price, and the marketplace's stated manifest
accuracy risk.

The coverage gate requires at least three frozen MPN identities. A minimum of
10 manifested lots is required before a zero-match result can be treated as a
source-class kill. Any matching line would then proceed to:

`quantity -> condition scenario -> conservative exit -> fees/freight/risk -> max all-in bid`

## Current sample

| Metric | Result |
|---|---:|
| Live manifested lots | 10 |
| Distinct manifest lines | 91 |
| Total units | 114 |
| Frozen MPN matches | 0 |
| Rows with usable model ID | 88/91 (96.7%) |
| Rows with valid GTIN | 85/91 (93.4%) |
| Minimum sample reached | Yes |

The sample deliberately includes the original two appliance-accessory lots and
eight additional multi-unit appliance lots. The added manifests cover laundry,
refrigerators, freezers, dishwashers, ovens, and related goods. None of the 91
line models is in the frozen 16-MPN replacement-parts demand universe.

Direct Liquidation states that the manifest may vary by up to 15% of units and
that mixed customer returns are untested, may be incomplete, and are sold as
is. The ledger records a 15% accuracy-risk input; it does not invent a sellable
rate or freight quote.

## Decision

**KILL_FROZEN_UNIVERSE_INTERSECTION / CHANGE_UNIVERSE CANDIDATE.**

The pre-registered 10-lot stop has been reached with zero frozen matches, so
the replacement-parts universe does not proceed to liquidation economics on
this source. There is no basis for max-bid calculations because none of its
demand identities occurs in the sampled supply.

This is not a kill of manifested liquidation generally. Identity quality is
strong: 96.7% of lines expose a usable model and 93.4% expose a check-digit-valid
GTIN. The deterministic unmatched identities are preserved separately in
`mpn-manifest-unmatched-identities.csv`. That supports a controlled
`CHANGE_UNIVERSE` experiment around exact finished-appliance models, without
retroactively tuning the completed frozen-parts gate.

The 15% manifest-accuracy haircut remains mandatory in any later max-bid test.

## Evidence

- `mpn-manifest-ledger.csv`: all 91 structured manifest lines.
- `mpn-manifest-unmatched-identities.csv`: 83 deterministic unmatched model
  identities, kept separate from the frozen universe.
- Live lot 944526:
  <https://www.directliquidation.com/p/944526-1-pallet-24-pcs-accessories-kitchen-and-dining-fans-untested-customer-returns-panasonic-midea-sharp-electronics-broan/944526>
- Live lot 943722:
  <https://www.directliquidation.com/p/943722-1-pallet-1-pcs-accessories-major-retailer/943722>

The `mpn-manifest-audit` command accepts one or more Direct Liquidation product
URLs and writes a new line-level ledger.
