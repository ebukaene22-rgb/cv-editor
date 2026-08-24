# Deterministic identity audit

## Result

The 2026-08-24 panel sampled five products from each of 68 Shopify stores in
the latest rebuilt observation snapshot. Of 340 requested product endpoints,
321 succeeded and exposed 1,247 variants.

| Measure | Result |
| --- | ---: |
| Variants with a valid GTIN | 827 / 1,247 (66.32%) |
| Strict source-eligible variants | 807 / 1,247 (64.72%) |
| Unique source-eligible GTINs | 795 |
| Variants with any barcode | 956 / 1,247 (76.66%) |
| Present but invalid barcodes | 129 |
| Stores with 100% valid-GTIN coverage | 28 / 68 |
| Stores with 0% valid-GTIN coverage | 10 / 68 |
| GTIN collision groups | 4 |

This overturns the assumption that the current source universe is uniformly
identifier-blind. It supports a targeted exact-identity pilot, especially in
the 28 fully covered stores. It does not establish marketplace demand, resale
price, fees, stock depth, or contribution margin.

After collision rejection and regional duplicate consolidation, the live eBay
gate therefore starts from 795 unique eligible GTINs rather than all 827 valid
variant identifiers.

## Interpretation

Treat a valid, unique GTIN as deterministic product evidence, not as a buy
signal. Manual review classified all four within-store collisions as malformed
source data: three MOFT identifiers span incompatible phone/color variants and
one Death Wish Coffee identifier spans four pack counts. The pipeline now marks
all such variants `REJECT_SOURCE_COLLISION` before marketplace lookup. Reuse
across regional storefronts in the same brand group remains eligible because it
can represent the same trade item sold in multiple regions.

The Shopify Ajax response does not expose an explicit MPN field, so MPN
coverage is reported as zero rather than inferred from SKU or title text. The
single configured WooCommerce store is outside this Shopify-specific audit.

The resolver records both whether a GTIN query returns listings and whether
item-detail records explicitly confirm the same GTIN. Search summaries alone
are not treated as confirmation because eBay's `ItemSummary` schema does not
expose GTIN. Inspected results are `EXACT` only when every detail confirms the
queried GTIN and brand/model/variant identity fields do not conflict;
everything else is `REJECT`.

## Exact eBay GB gate

The 2026-08-24 live gate selected 100 of the 795 eligible GTINs by stable hash
and searched new, fixed-price listings on `EBAY_GB`. Every returned listing was
then inspected through the item-detail endpoint.

| Measure | Result |
| --- | ---: |
| GTIN queries with active results | 7 / 100 (7%) |
| GTINs with any explicit exact confirmation | 2 / 100 (2%) |
| GTINs coherent across all returned listings | 1 / 100 (1%) |
| GTINs with at least 3 coherent listings | 0 / 100 (0%) |
| Active-listing count among resolved queries | median 1; range 1-2 |
| Exact-item price median across confirmed GTINs | GBP 110.10 |

Of the seven query-resolved GTINs, five were `UNCONFIRMED` because item details
did not report a GTIN, one was `AMBIGUOUS` because only one of two returned
items confirmed the queried GTIN, and one was `EXACT_SHALLOW` with a single
listing. There were no API errors in the final evidence.

**Decision: exact-market resolver gate FAILED for eBay GB.** Source identity
remains a passed infrastructure gate, but this sample does not support a usable
deterministic source-to-eBay-GB market at the preregistered depth. Bundle
monetisation remains blocked; unconfirmed search hits must not be promoted to
exact identity.

## Evidence

- `identity-coverage.csv`: store and category aggregates, including failures,
  invalid identifiers, collisions, and optional eBay resolution rates.
- `identity-ledger.csv.gz`: one row per returned variant plus one row per failed
  endpoint, with source URL, raw barcode, normalized GTIN, and validation state.
- `identifier-collisions.csv`: manual classification of within-store source
  collisions and the encoded handling decision.
- `ebay-resolution-ledger.csv.gz`: one row per inspected eBay item when the
  credentialed resolver is enabled.

The sample is stable: products are ranked by a hash of domain and product URL,
then the first five per store are selected. Rebuilding from a newer observation
snapshot can change the eligible product universe and should produce a newly
dated audit rather than silently replacing this result.
