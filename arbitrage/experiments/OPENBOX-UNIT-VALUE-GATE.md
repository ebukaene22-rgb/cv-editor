# Open-Box Unit-Value Gate

Audit date: 2026-08-24  
Verdict: **INSUFFICIENT_SOURCE_COHORT**

The open-box/refurb experiment was reset to require a GBP 50-200 source-side
exit-value proxy before identity work. The proxy is explicit reference retail
where available, otherwise source price; it is not marketplace evidence.

The latest successful snapshot from every monitored domain contained five
available products with explicit secondary-condition titles. Only one cleared
the new band:

| Source | Product | Condition | Source GBP | Exit proxy GBP |
|---|---|---|---:|---:|
| Goal Zero | Yeti 200X | Open box | 104.69 | 161.06 |

The generated cohort is therefore 1/30 and is not sent to eBay resolution.
Older Peak Design rows were not reused because they are absent from the latest
available snapshot.

Frozen CSV SHA-256:
`83609e6e28a3eed6e95b84f639f7764e2e263c6981daf8a97edcb389cd101fd6`

Public-source discovery also shows that suitable feeds exist but the present
coverage is too narrow to freeze 30 without padding: Canon's official US
refurbished-camera catalogue currently reports 12 products in stock across all
price levels, while NETGEAR's direct Imperfect Box range is small and is
factory-sealed new inventory rather than open-box/refurbished inventory.

Next work is source-universe expansion. The 30-row cohort must remain frozen,
condition-explicit, currently purchasable, exact-model capable, compact, and
inside the unit-value proxy band before any eBay API calls are spent.
