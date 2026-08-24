# Exact-MPN manifested-liquidation gate

Audit time: 2026-08-24 11:19 UTC  
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
| Live manifested lots | 2 |
| Distinct manifest lines | 18 |
| Total units | 25 |
| Frozen MPN matches | 0 |
| Minimum sample reached | No |

One lot contains 24 mixed-condition units across 17 models at a USD 1,080.30
ask price. The other contains one like-new Samsung pedestal at USD 153. None
of the 18 line models is in the frozen 16-MPN demand universe.

Direct Liquidation states that the manifest may vary by up to 15% of units and
that mixed customer returns are untested, may be incomplete, and are sold as
is. The ledger records a 15% accuracy-risk input; it does not invent a sellable
rate or freight quote.

## Decision

**INSUFFICIENT_MANIFEST_SAMPLE.**

There is no basis for lot economics because there are no frozen-identity
matches. There is also no basis for killing manifested liquidation after only
two lots. Continue accumulating actual appliance-parts manifests until either:

- at least three frozen identities appear and can enter lot economics; or
- at least 10 relevant lots have been audited with fewer than three matches.

This is the first acquisition test in the project that directly measures
forced-disposal inventory at line level.

## Evidence

- `mpn-manifest-ledger.csv`: 18 structured manifest lines.
- Live lot 944526:
  <https://www.directliquidation.com/p/944526-1-pallet-24-pcs-accessories-kitchen-and-dining-fans-untested-customer-returns-panasonic-midea-sharp-electronics-broan/944526>
- Live lot 943722:
  <https://www.directliquidation.com/p/943722-1-pallet-1-pcs-accessories-major-retailer/943722>

The `mpn-manifest-audit` command accepts one or more Direct Liquidation product
URLs and writes a new line-level ledger.
