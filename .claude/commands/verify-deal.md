---
description: Reconcile a seller's processor export against their stated figures
argument-hint: <candidate-id> <path/to/export.csv>
---

The seller for **$1** has sent `$2`. Reconcile it.

1. Invoke the **deal-verify** skill.
2. `python .claude/skills/deal-verify/scripts/reconcile.py $2 --candidate $1`
3. Check the detected-columns line before reading anything else. If the date or
   amount column looks wrong, say so and stop — a reconciliation run against the
   wrong column is worse than none.
4. Tell me:
   - does the TTM agree, and if not, by how much and in which direction
   - what shape the twelve-month series is, not just its total
   - whether any single customer exceeds 10% of revenue
   - which months are missing, if any
5. Then the standard: **any single unexplained discrepancy resets this deal to
   Stage 3.** If you find one, say so and name the question I should ask —
   do not explain it away on the seller's behalf.
6. Do not copy the seller's raw financial data into the repo. Record the
   conclusion on the candidate record; the export stays outside version control.
