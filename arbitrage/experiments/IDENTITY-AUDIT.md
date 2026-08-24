# Deterministic identity audit

## Result

The 2026-08-24 panel sampled five products from each of 68 Shopify stores in
the latest rebuilt observation snapshot. Of 340 requested product endpoints,
321 succeeded and exposed 1,247 variants.

| Measure | Result |
| --- | ---: |
| Variants with a valid GTIN | 827 / 1,247 (66.32%) |
| Variants with any barcode | 956 / 1,247 (76.66%) |
| Present but invalid barcodes | 129 |
| Stores with 100% valid-GTIN coverage | 28 / 68 |
| Stores with 0% valid-GTIN coverage | 10 / 68 |
| GTIN collision groups | 4 |

This overturns the assumption that the current source universe is uniformly
identifier-blind. It supports a targeted exact-identity pilot, especially in
the 28 fully covered stores. It does not establish marketplace demand, resale
price, fees, stock depth, or contribution margin.

## Interpretation

Treat a valid, unique GTIN as deterministic product evidence, not as a buy
signal. Four GTINs were reused across multiple source variants; these require
manual model/pack-size review and must not be joined automatically.

The Shopify Ajax response does not expose an explicit MPN field, so MPN
coverage is reported as zero rather than inferred from SKU or title text. The
single configured WooCommerce store is outside this Shopify-specific audit.

The committed run did not query eBay because API credentials were unavailable.
The optional resolver records both whether a GTIN query returns listings and
whether returned listing data explicitly confirms the same GTIN. Those are
separate measures by design.

## Evidence

- `identity-coverage.csv`: store and category aggregates, including failures,
  invalid identifiers, collisions, and optional eBay resolution rates.
- `identity-ledger.csv.gz`: one row per returned variant plus one row per failed
  endpoint, with source URL, raw barcode, normalized GTIN, and validation state.

The sample is stable: products are ranked by a hash of domain and product URL,
then the first five per store are selected. Rebuilding from a newer observation
snapshot can change the eligible product universe and should produce a newly
dated audit rather than silently replacing this result.
