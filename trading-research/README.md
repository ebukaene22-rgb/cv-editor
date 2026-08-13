# Trading Research Platform

A pre-registered, execution-first research programme for testing a small number of
economically motivated short-horizon trading hypotheses. This is **not** a trading bot.
It is the machinery for killing bad ideas cheaply before they see real money.

## Operating principles

1. **Point-in-time or it doesn't exist.** Every signal input must have been observable
   at the decision timestamp. Any experiment that needs data not available at decision
   time is killed immediately (look-ahead bias).
2. **The cost ladder, always.** Every result is reported at five rungs:
   gross (mid-to-mid) → bid/ask spread → +commission → +slippage → +borrow.
   A strategy that is only profitable above the bottom rung is an academic result,
   not an alpha strategy.
3. **Pre-registration by commit hash.** An experiment spec is committed to
   `docs/preregistration/` *before* its backtest runs. The git commit hash is the
   tamper-proof registration. Changing a spec after seeing results requires a new
   experiment ID and an explicit note of what was learned.
4. **Holdout escrow.** Data from 2025-01-01 onward lives under `data/holdout/` and is
   never read by any experiment until the spec is frozen and all in-sample /
   walk-forward work is complete. See `data/holdout/README.md`.
5. **Kill criteria are honored.** The universal kill framework is in
   `docs/KILL_CRITERIA.md`. Per-experiment criteria are in each spec. A killed
   experiment stays killed; resurrection requires a new registered spec.
6. **Cluster your errors.** Trades sharing an announcement date, rebalance event, or
   calendar day are not independent. All summary statistics use cluster bootstrap
   (`src/research/stats.py`).

## Layout

```
trading-research/
├── docs/
│   ├── KILL_CRITERIA.md            Universal kill framework
│   └── preregistration/
│       ├── TEMPLATE.md             Spec template — copy for each new experiment
│       ├── EXP-000-vendor-pit-audit.md   Phase 1 gate: is retail point-in-time
│       │                                 estimates data trustworthy?
│       └── EXP-001-conditional-pead.md   First strategy spec (blocked on EXP-000)
├── src/research/
│   ├── execution.py                Pessimistic fills + the cost ladder
│   ├── stats.py                    Cluster bootstrap, Sharpe with CI
│   └── engine.py                   Event-study backtest engine
├── scripts/
│   └── audit_vendor_pit.py         Runnable scorer for the EXP-000 audit
├── tests/                          stdlib unittest — zero dependencies
└── data/
    └── holdout/                    Escrowed. Do not read. See its README.
```

## Running tests

No third-party dependencies are required:

```bash
cd trading-research
python3 -m unittest discover -s tests -v
```

## Status

- **Phase 1 (feasibility spike): in progress.** EXP-000 (vendor point-in-time audit)
  is registered and is the gate for everything downstream. EXP-001 (conditional PEAD)
  is registered but blocked on EXP-000's outcome.
- No backtest has been run. No results exist. That is intentional: specs freeze first.

## Source papers (verified to exist, 2026-08)

- McCarthy — *Prior-Biased Inference in Asset Prices: The Conditional Post-Earnings
  Announcement Drift* (SSRN 5311906). Recommendation-inconsistent PEAD ≈ 9.4%/yr.
- Baltussen, Da & Soebhag — *End-of-Day Reversal* (SSRN 5039009). NOTE: headline
  long-short decile figure is ~0.24%/day in the final half-hour, not "a few bps" —
  read the paper's cost section before trusting either number.
- *Index-tracking rigidity and arbitrage opportunities in MSCI index reconstitutions*
  (Pacific-Basin Finance Journal, 2025). 56 markets, 2006–2023.
- Greenwood & Sammon — *The Disappearing Index Effect* (adversarial counterpoint).
- FINRA Regulatory Notice 26-10 — intraday margin framework replacing the PDT rule,
  effective 2026-06-04, broker phase-in through 2027-10-20. Verify per-broker behavior.
