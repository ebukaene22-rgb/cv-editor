---
name: deal-verify
description: >
  Reconcile a seller's stated figures against primary sources during acquisition
  diligence. Use when a seller has sent a Stripe or processor export, a revenue
  CSV, invoices or dashboard screenshots, and the numbers need checking against
  what the listing claimed — or when the user asks what evidence to accept, how
  to build a cohort table, or whether a discrepancy matters. Stage 5 of the
  acquisition playbook.
---

# Deal Verify — Stage 5 Reconciliation

Automate the parsing. Never automate the asking.

You are checking a seller's claims against primary sources. The listing has
already passed automated screening, which means only that it did not contradict
itself — it says nothing about whether any figure is real.

## The standard

**Every number the seller gave must agree with its primary source.** Any single
unexplained discrepancy resets the deal to Stage 3 triage. Not "note it and
proceed". The first discrepancy you find is rarely the only one; it is the one
that happened to be checkable.

`references/../../deal-screen/references/verification.md` holds the evidence
table — what counts and what doesn't. The short version:

| Claim | Accept | Refuse |
|---|---|---|
| Revenue | processor export, read-only access, live screen-share | seller's spreadsheet, screenshots |
| Costs | 3 months of actual invoices | one stated figure |
| Customers | processor subscriber count | the listing's metric box |
| Churn | a cohort table you build | the seller's stated rate |

## Running the reconciliation

```bash
python .claude/skills/deal-verify/scripts/reconcile.py <export.csv> --candidate <id>
python .claude/skills/deal-verify/scripts/reconcile.py <export.csv> --stated-ttm 9600 --stated-mrr 800
```

The script reads a processor export, computes monthly revenue for the trailing
twelve months, derives MRR and the trend, and prints each figure beside what the
seller stated with a variance. It does not decide — it puts the two columns next
to each other, which is the whole job.

Column names vary between processors, so it detects the date and amount columns
by header rather than by position, and reports which ones it used. **Check that
line.** A reconciliation run against the wrong column is worse than none.

## Reading the result

- **Revenue agrees within a few percent.** Good. Now check the *shape* — the
  monthly series matters more than the total. A flat twelve months and a
  collapsing twelve months can share a TTM figure.
- **Export total is below the stated figure.** The usual causes are refunds
  netted out, a second processor, or the stated figure being gross of fees.
  Ask which. An answer that arrives instantly and specifically is a good sign.
- **Export total is above the stated figure.** Rarer and more interesting.
  Usually one-off revenue counted in the export but excluded from "MRR", which
  means the recurring base is smaller than advertised.
- **A month is missing.** Ask for it before anything else.

## Churn: build it, don't accept it

A stated churn rate is an output of whatever definition the seller chose. Build
the cohort table yourself from the subscriber data: for each signup month, how
many were still paying at +1, +3, +6 months. Then compare with the stated rate.

`implied_lifetime = 1 / monthly_churn` — so 8% monthly churn is a 12.5-month
lifetime, and a stated LTV that implies more than that is describing something
other than a customer.

## Customer concentration

Ask the export the question the listing never volunteers: **does any single
customer exceed 10% of MRR?** At this deal size one enterprise customer leaving
is the whole thesis. The script reports the top-five share when the export
carries a customer column.

## What not to do

- Do not store the seller's raw financial data in this repo. Read it, reconcile
  it, record the *conclusion* on the candidate record, delete the export.
- Do not reconcile a screenshot. Ask again.
- Do not explain a discrepancy on the seller's behalf. Ask them.
