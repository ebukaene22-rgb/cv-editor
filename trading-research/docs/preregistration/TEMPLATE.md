# EXP-NNN — <short name>

**Status:** DRAFT | REGISTERED | RUNNING | KILLED | SURVIVED → PAPER | LIVE
**Registered at commit:** `<hash of the commit that froze this spec>`
**Blocked on:** <experiment IDs or data gates, if any>

## 1. Economic hypothesis

One paragraph. Must name the **counterparty**: who is paying this alpha and why
(forced, slow, inventory-constrained, mandate-constrained, or processing
information inefficiently). "The chart mean-reverts" is not a mechanism.

## 2. Evidence base

- Primary papers (verified links, publication dates, headline numbers as printed
  in the paper — not as summarized elsewhere).
- First public working-paper date `T_paper` (for pre/post-publication split).
- Known adversarial evidence.

## 3. Universe and filters

Exact, frozen: price floor, market-cap floor, dollar-ADV floor, spread ceiling,
security types excluded. Filters use only data observable at decision time.

## 4. Signal definition

Exact formulas. Every constant fixed here. Any alternative formulation goes in
§8 as a pre-registered robustness check, not a post-hoc swap.

## 5. Entry and exit rules

Timestamps to the second, order types, limit offsets, cancel rules, and the
primary holding period. Secondary horizons listed here are diagnostics only.

## 6. Costs and execution model

Which cost-ladder assumptions (commission bp, slippage bp, borrow), and the
survival requirement (which rung must stay positive).

## 7. Sample design

Train / walk-forward / pre-live / holdout date boundaries. The holdout is named
here and never touched until the status log says all other work is complete.

## 8. Pre-registered robustness checks and interactions

Enumerated and capped. Anything not listed here that gets tried later counts
against the multiplicity budget and must be logged.

## 9. Kill criteria (in addition to docs/KILL_CRITERIA.md)

Numeric, checkable, written before any result exists.

## 10. Status log

| Date | Commit | Event |
|---|---|---|
| YYYY-MM-DD | `hash` | Spec registered |
