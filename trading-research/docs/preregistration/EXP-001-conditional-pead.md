# EXP-001 — Conditional PEAD (Prior-Conflict Earnings Drift)

**Status:** REGISTERED — **BLOCKED on EXP-000** (point-in-time estimates gate)
**Registered at commit:** _(hash of the commit introducing this file)_

## 1. Economic hypothesis

Investors anchor on prior beliefs. An earnings surprise that **contradicts** the
prevailing analyst view receives insufficient initial weight, producing multi-day
drift; surprises that confirm priors are absorbed immediately. The counterparty is
the slow updater — holders with stale bullish views under-reacting to bad news,
and skeptics under-reacting to good news at out-of-favor firms.

## 2. Evidence base

- **Primary:** McCarthy, *Prior-Biased Inference in Asset Prices: The Conditional
  Post-Earnings Announcement Drift*, SSRN 5311906 (June 2025). Reported:
  recommendation-inconsistent strategy ≈ **9.4% abnormal return per annum**
  (note: annualized, not per event); recommendation-consistent ≈ 0.
  `T_paper` = 2025-06 → post-publication sample ≈ 1 year: **record as
  "post-publication evidence unavailable"**, do not interpret.
- **Adversarial:** 2026 event-level expected-return decomposition work disputing
  generic PEAD as abnormal drift. Our falsification benchmark: vanilla SUE-quintile
  PEAD run through the identical pipeline. If vanilla and conditional PEAD are
  indistinguishable in our sample, the conditioning story fails.
- **Explicitly excluded from the primary spec:** the "FQ1 persistence cliff"
  claim (Wang & Zeng) — could not be located/verified as of 2026-08-13. FQ1 is
  relegated to a pre-registered *exploratory* interaction (§8), never a headline.

## 3. Universe and filters (frozen)

US ordinary common stocks (no ADRs, ETFs, REIT-preferreds, SPACs):

- Prior-day close ≥ $5
- Market cap ≥ $1bn
- Trailing 20-day dollar ADV ≥ $10m
- For the short leg: borrow available at entry date, indicated fee ≤ 20%/yr

## 4. Signal definition (frozen)

- `SUE_i = (EPS_actual_i − EPS_consensus_i) / P_{i,t−1}` where consensus is the
  last value observable **before** the announcement timestamp from the
  EXP-000-passing vendor.
- `Prior_i` = z-score of consensus recommendation (positive = bullish), last
  observable before announcement.
- Conflict:
  - `SUE > 0` and `Prior < 30th percentile` → long candidate
  - `SUE < 0` and `Prior > 70th percentile` → short candidate
- Trade the top 20% |SUE| within each conflict bucket, per earnings season.

## 5. Entry and exit (frozen)

- Announcements after prior close / before next open → enter **09:35:00 ET**
  next regular session.
- Marketable limits: buy at `ask × (1 + 5bp)`, short at `bid × (1 − 5bp)`.
  Unfilled after 30 seconds → cancel, no fill, event recorded as missed.
- **Primary horizon: 20 trading days**, exit 15:55 ET. Horizons 5/10/40/60 are
  diagnostics only.
- Sizing: inverse 20-day volatility, max 2% gross weight per name,
  portfolio beta-neutralized. No leverage.

## 6. Costs and survival requirement

Cost ladder per `src/research/execution.py` with: commission 0.5bp/side
(IBKR-tiered proxy), slippage scenarios 0 / 5 / 12.5 bp per side
(≈ 0 / 10 / 25 bp round trip), historical borrow on shorts.

**Survival requirement:** net expectancy > 0 and the pre-registered t-threshold
met at the **25bp-round-trip + borrow** rung, on walk-forward data, with long and
short legs also reported separately.

## 7. Sample design

- Train: earliest clean data → 2018-12-31
- Walk-forward validation: 2019-01-01 → 2022-12-31
- Pre-live validation: 2023-01-01 → 2024-12-31
- **Untouched holdout: 2025-01-01 → latest complete date** (escrowed under
  `data/holdout/`)

## 8. Pre-registered robustness checks (capped — this is the complete list)

1. SUE denominator: consensus-error volatility instead of price.
2. Conflict thresholds 20/80 instead of 30/70.
3. Long-only conflict leg (drops borrow entirely).
4. Exploratory: FQ1 × Conflict interaction (reported, never selected on).
5. Vanilla SUE-quintile PEAD benchmark (falsification control).

## 9. Kill criteria (additional to docs/KILL_CRITERIA.md)

- Post-2018 or post-2022 net alpha ≤ 0 at the survival rung → **kill**.
- Effect concentrated in sub-$1bn names when filters are relaxed → **kill**.
- Recommendation timestamps shown to leak post-announcement information → **kill**
  (and vendor verdict in EXP-000 is reopened).
- > 30% of short-side expected profit consumed by borrow → drop short leg;
  if long-only also fails the survival rung → **kill**.
- Untouched-holdout Sharpe < 0.5 → **kill**.

## 10. Status log

| Date | Commit | Event |
|---|---|---|
| 2026-08-13 | _(this commit)_ | Spec registered; blocked on EXP-000 |
