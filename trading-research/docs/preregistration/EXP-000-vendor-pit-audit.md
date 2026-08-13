# EXP-000 — Vendor Point-in-Time Estimates Audit

**Status:** REGISTERED
**Registered at commit:** _(hash of the commit introducing this file)_
**Blocked on:** nothing — this is the Phase 1 gate for EXP-001 and all
estimate-dependent experiments.

## 1. Objective

Determine whether a retail-accessible analyst-estimates vendor provides genuinely
**point-in-time** consensus EPS and recommendation data — i.e., "consensus as of
date X" reflects only information available on date X, with no backfill of later
revisions and no post-announcement contamination.

This is not a strategy. It is a data-integrity experiment whose outcome re-ranks
the strategy queue. If no vendor passes, conditional PEAD (EXP-001) is downgraded
and the programme leads with MSCI reconstitution and earnings tonal inconsistency,
whose raw inputs are public with native timestamps.

## 2. Candidate vendors (audit in this order, stop at first PASS)

1. Zacks consensus via Nasdaq Data Link or Intrinio (quarterly EPS history to 1982).
2. Financial Modeling Prep analyst estimates endpoints.

## 3. Sample design (frozen)

- **N = 50 earnings events**, drawn before any vendor data is inspected.
- Stratification: 2 events per quarter, 2021Q1–2024Q4 (32 events), plus 18 events
  split evenly across three cap buckets ($1–5bn, $5–50bn, >$50bn) sampled from
  2019–2020. US common stocks only, price ≥ $5, cap ≥ $1bn at event date.
- Selection: deterministic — rank each stratum's eligible events by ticker
  alphabetically and take the first k. No discretion.
- The sample list is committed to `data/exp000/sample_events.csv` **before** any
  vendor query is run.

## 4. Ground truth

For each sampled event, capture independent evidence of the pre-announcement
consensus:

- Wayback Machine snapshots of public estimate pages (Yahoo Finance, Zacks.com,
  StreetInsider) dated in the window [announcement − 10 days, announcement − 1 day].
- Contemporaneous press coverage quoting "analysts expected $X.XX" where snapshots
  are unavailable.
- Events with no recoverable ground truth are marked UNVERIFIABLE and replaced
  from the same stratum (replacement rule: next ticker alphabetically).

## 5. Measurements per event

For vendor value `v` = consensus EPS "as of" announcement − 1 trading day, and
ground truth `g`:

- `match`: |v − g| ≤ $0.01, or the difference is explained by a documented
  revision inside the window with its own timestamp.
- `backfill_flag`: vendor's as-of value equals the *post*-announcement revised
  consensus while ground truth differs → evidence of backfill. This is the
  disqualifying failure mode.
- Same two measurements for consensus recommendation (tolerance: 0.25 on a
  1–5 scale) where the vendor provides recommendation history.

## 6. Pass criteria (frozen)

A vendor **PASSES** iff, over the verifiable sample:

- match rate ≥ 90% for EPS consensus, AND
- `backfill_flag` count = 0, AND
- ≥ 40 of 50 events were verifiable (else enlarge sample before judging).

Anything else is a FAIL for that vendor. No partial credit, no "close enough."

## 7. Tooling

`scripts/audit_vendor_pit.py` scores a completed audit CSV and prints the verdict.
The CSV schema is documented in the script. The filled CSV and the script output
are both committed as the experiment's evidence.

## 8. Outcomes

- **PASS** → EXP-001 unblocked with this vendor named as the estimates source.
- **FAIL (all vendors)** → EXP-001 status set to BLOCKED-INDEFINITE; register
  EXP-002 (MSCI reconstitution) and EXP-003 (tonal inconsistency) as the leaders.

## 9. Status log

| Date | Commit | Event |
|---|---|---|
| 2026-08-13 | _(this commit)_ | Spec registered |
