# Roadmap

Each phase ends at a decision gate. Passing the gate is the only way forward;
failing it triggers the written fallback, not improvisation.

## Phase 1 — Feasibility spike (2–4 weeks, ~$100–300 data trials)

- Read the three primary papers end-to-end; extract actual numbers, universes,
  cost treatments into `docs/paper-notes/` (resolve the EOD-reversal magnitude
  discrepancy: ~24bp/day headline vs "few bps" claims elsewhere).
- Run **EXP-000**: audit one retail estimates vendor (Zacks via Intrinio /
  Nasdaq Data Link, or FMP) for point-in-time integrity.

**Gate:** EXP-000 verdict.
- PASS → EXP-001 (conditional PEAD) proceeds as first strategy build.
- FAIL → conditional PEAD is downgraded; re-rank with MSCI reconstitution and
  earnings tonal inconsistency as leaders (their inputs — official index
  announcements, press releases, transcripts — are public with timestamps).

## Phase 2 — Pre-registration + shared infrastructure (4–8 weeks)

- Freeze the leader's spec (already drafted as EXP-001; amend only via new ID).
- Build out: point-in-time event calendar loader, NBBO execution simulator
  (aggressive fills only), cost-ladder reporting, cluster-bootstrap stats.
  Skeletons exist in `src/research/`; this phase connects real data.
- Escrow holdout data (2025-01-01 onward) under `data/holdout/`.

**Gate:** spec committed BEFORE first backtest run; infrastructure tests green.

## Phase 3 — First experiment + kill decision

- Walk-forward design: train ≤2018 · validate 2019–2022 · pre-live 2023–2024 ·
  untouched holdout 2025–2026.
- Report the full cost ladder, clustered CIs, and every kill criterion verdict.

**Gate:** survives its own pre-registered kill criteria → Phase 4. Otherwise:
document the kill, move to the next registered spec. A kill is a success of
the programme, not a failure.

## Phase 4 — Paper trading (3–6 months)

- IBKR paper (or Alpaca) with full execution logging: decision NBBO, submission,
  acknowledgement, fill timestamps and prices, effective/realized spread.
- Compare live fill distribution against simulator assumptions; recalibrate.

**Gate:** live fills within pre-registered tolerance of simulated fills AND
paper P&L consistent with backtest CI → Phase 5.

## Phase 5 — Small live capital

- Size so total loss is tuition. Scale only on live evidence, never backtest.

## Standing constraints

- Expected value honesty: on $10k–250k, even full success is a few $k–$20k/yr
  against substantial skilled time + data costs + short-term capital gains tax.
  The justification is education, infrastructure optionality, and a small chance
  of durable edge — not income replacement.
- Correlation audit: several candidates are secretly "provide liquidity into
  selling." Report portfolio behavior in Mar-2020 / 2022-style stress windows,
  not just standalone Sharpes.
