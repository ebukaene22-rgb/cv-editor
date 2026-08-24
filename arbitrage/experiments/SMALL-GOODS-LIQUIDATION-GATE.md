# Small-Goods Liquidation Gate

Audit date: 2026-08-24  
Source: Direct Liquidation, US  
Exit market: eBay US active fixed-price listings  
Verdict: **KILL_ECONOMICS for the frozen Wyze parcel cohort**

## Frozen source cohort

The cohort was frozen from 10 distinct live parcel-box manifests before any
eBay query. It contains only small, shippable security and smart-home goods.

- 10 lots
- 138 manifest lines
- 487 units
- 46 deterministic manufacturer + model identities
- 46/46 identities with a valid GTIN
- Frozen CSV SHA-256:
  `55f0fcb2244c50ed1198c4e41ecadf89a6176f5399d9e728db6f01439c786e5e`

The ten lots are supplier-concentrated: 136/138 lines identify Wyze directly,
with one Wyze Labs and one Hualai line. This result therefore applies to the
current Wyze parcel inventory, not to every small-goods liquidation category.

## Resolver gate

The frozen identities were tested without tuning:

| Pass | Identities with results |
|---|---:|
| GTIN, unfiltered | 29/46 |
| GTIN, broad source condition | 15/46 |
| Exact manufacturer + model, unfiltered | 43/46 |
| Exact manufacturer + model, source condition | 39/46 |

Seventeen identities produced a deterministic market in at least one pass.
Four retained at least three exact-condition listings after eBay Taxonomy API
category-name validation:

| Model | eBay category | Coherent depth |
|---|---|---:|
| WLPPO1-1 | Smart Plugs | 4 |
| WYZEC3 | Security Cameras | 5 |
| WYZECGS | Security Cameras | 3 |
| WYZECPAN3 | Security Cameras | 5 |

This is a **resolver pass**. Exact model retrieval works materially better
than GTIN retrieval, and structured product-type coherence does not collapse
the surviving set as it did for whole appliances.

## Economics gate

Only the four resolver survivors were priced. Source ask was allocated to
manifest lines pro rata by extended manifest retail value. The automated
underwriting assumptions were:

- active exact-condition eBay p25 as the exit proxy
- 15% eBay fee
- 10% return allowance
- $10 outbound shipping per usable unit
- 15% manifest/condition accuracy haircut
- minimum required contribution of GBP 15
- USD/GBP: 0.73228

| Model | Active p25 | Allocated ask/unit | Net exit before acquisition | Contribution at ask |
|---|---:|---:|---:|---:|
| WLPPO1-1 | $9.99 | $5.94 | -$2.13 | -$8.07 |
| WYZEC3 | $21.49 | $9.09 | $5.20 | -$3.89 |
| WYZECGS | $15.99 | $10.49 | $1.69 | -$8.80 |
| WYZECPAN3 | $16.89 | $13.99 | $2.27 | -$11.72 |

Buyer premium, inbound freight, and sales tax are still unresolved and can
only make these rows worse. All four have a zero maximum all-in acquisition
price once the GBP 15 contribution requirement is imposed.

## Conclusion

Small, shippable exact-model liquidation fixes the semantic exit-market
failure seen in whole appliances. The current Wyze lots nevertheless fail on
unit economics at the supplier's 35%-of-MSRP ask. Do not build a manual review
queue or tune this cohort. A later category test must use a structurally lower
acquisition ratio, higher-value shippable products, or materially cheaper
fulfilment while preserving the same frozen resolver and taxonomy gates.

## Evidence

- `small-goods-manifest-ledger.csv`: 10 source manifests and all 138 lines.
- `small-goods-universe.csv`: frozen 46-identity source universe.
- `small-goods-resolver-diagnostic.csv.gz`: four-pass resolver evidence.
- `small-goods-economics.csv`: automated underwriting of the four survivors.
