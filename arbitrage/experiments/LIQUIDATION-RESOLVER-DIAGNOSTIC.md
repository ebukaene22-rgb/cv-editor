# Liquidation resolver diagnostic

Audit time: 2026-08-24
Frozen universe: the same 80 valid-GTIN manifest identities
Market: eBay US active fixed-price listings

## Four passes

| Pass | Retrieval rule | Identities with results | Exact usable markets |
|---|---|---:|---:|
| A | GTIN, no condition filter | 13/80 | 0 |
| B | GTIN, broad NEW/USED filter | 2/80 | 0 |
| C | Exact manufacturer + model, no condition filter | 73/80 | 9 |
| D | Exact manufacturer + model, specific source condition | 44/80 | 3 |

The exact-model resolver accepts only a structured eBay brand match plus an
exact model or MPN field match. Titles are logged for evidence but never used
to accept identity. A usable market still requires coherent details and at
least three exact listings.

## Diagnosis

GTIN retrieval is the primary failure. Sixty-two identities have no GTIN
result but do have model-query results. Broad condition filtering also reduces
GTIN retrieval from 13 identities to two. Model retrieval remains materially
healthier after condition filtering, falling from 73 to 44 identities rather
than to zero.

The deterministic acceptance layer is not universally malformed: ten
identities have a usable exact-model market in at least one model pass. Three
retain at least three coherent listings under the specific source condition:

- Samsung `WA55CG7500AE`: depth 5;
- LG `DLG7001W`: depth 3;
- LG `LDPM6762S`: depth 3.

## Decision

**GTIN RESOLVER KILLED; EXACT-MODEL RESOLVER PASSED TO ECONOMICS.**

The earlier `KILL_EXIT_RESOLUTION` verdict is withdrawn. The source market is
not absent: used-market sellers frequently omit structured GTIN while retaining
structured model identity. Condition semantics explain additional loss but do
not eliminate the exact-model market.

Only the three exact-condition survivors may enter lot economics. The frozen
80, identity rules, and condition rules remain unchanged. Buyer premium,
freight, tax, marketplace fees, outbound postage, expected sellable rate, and
the 15% manifest-accuracy haircut remain unresolved and must be applied before
any max-bid decision.

## Evidence

- `liquidation-resolver-diagnostic.csv.gz`: all four raw result counts, exact
  depths, statuses, dominant category IDs, returned condition IDs, and titles
  for every frozen identity.
