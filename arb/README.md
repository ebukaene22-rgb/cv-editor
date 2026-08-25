# Arbitrage Pilot Instruments

Zero-capital measurement tools implementing `research/final-program.md`.
Nothing here trades or spends. Both exist to answer one question each,
prospectively, before any of the ~$13k reserve moves:

| Instrument | Question it answers | Capital unlock gate |
|---|---|---|
| `japan/` | Are there enough executable ≥35%-markup buys per month, at FINAL prices? | realized ROI ≥ 20% over ≥10 terminal items, cycle ≤ 45 days, capacity ≥ 2× |
| `cs2/` | Do underpriced listings survive long enough for a human to buy them? | ≥100 candidates AND median net edge ≥ 7% on 5-minute survivors |

## Day-0 human checklist (has lead time — start before touching the tools)

1. **eBay + Payoneer**: open the eBay seller account, complete Emirates ID
   verification, link Payoneer (USD payouts only — no PayPal for UAE sellers).
   Check the fresh account's selling limits.
2. **License path**: price a Dubai E-Trader-class license vs full trade license
   before assuming the worst-case overhead. Needed for commercial volume.
3. **CSFloat rails**: complete one small end-to-end loop — deposit → buy → sell
   → payout landed in your actual UAE account (KYC included). If this stalls,
   the CS2 lane dies regardless of what the recorder finds.
4. Review CSFloat's ToS for API use (the recorder is read-only and rate-limited,
   and performs no Steam interaction — keep it that way).

## Japan corridor (`japan/`)

```
# 1. Fill comps.csv from eBay Terapeak SOLD data (p25, not best comp)
# 2. Compute the ceiling bid per model:
python3 japan/model.py max-bid --sale-usd 200 --weight small --category watches
# 3. Sanity-check any candidate before bidding:
python3 japan/model.py evaluate --hammer-jpy 9000 --sale-usd 200 --category watches
# 4. Log EVERY candidate when first seen, and every outcome:
python3 japan/oplog.py add --model "SEIKO SARB033" --source yahoo \
    --first-price-jpy 9000 --expected-sale-usd 200 --state spread_positive
python3 japan/oplog.py update <id> --state purchased --final-price-jpy 9500
python3 japan/oplog.py update <id> --state completed_profit --landed-usd 95 --net-usd 41
python3 japan/oplog.py stats
```

Rules encoded from the program: route defaults to **direct-from-Japan**
(`--route dubai` shows the +10.25% cost of transiting the UAE); the fee stack is
the corrected one (FVF incl. processing + $0.40 + intl surcharge + Payoneer FX +
5% return reserve); a candidate that can't be underwritten is logged with an
`*_unknown` state, never guessed. First 20–30 trades: tested/working inventory
only, no ジャンク.

Early lesson already visible in the model: fixed costs make low-ASP items
unworkable — a $180-exit item supports a max bid of only ~¥8,300. Prefer
$200–400 exits.

## CS2 recorder (`cs2/`)

```
export CSFLOAT_API_KEY=...   # csfloat.com profile -> developer tab
python3 cs2/recorder.py once            # smoke test
python3 cs2/recorder.py run --minutes 240   # collect (run daily for ~2 weeks)
python3 cs2/analyze.py                  # survival table + live gate verdict
```

Edit `families` in `cs2/config.json` to the 3–5 skin families under study.
Reference price = rolling same-family median (float-adjusted analysis can be
layered on the stored `float_value` later). The analyzer's gate line is the
decision: no PASS, no live capital — and a PASS unlocks only the $500
diagnostic, not the old $5k plan.
