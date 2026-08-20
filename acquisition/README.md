# Micro-SaaS Acquisition Pipeline

A deal sourcing and screening system that produces a weekly ranked shortlist of
micro-SaaS acquisition candidates, filtered against fixed criteria, with the
arithmetic that catches misstated listings applied automatically.

**Success looks like** 15 minutes a week of human review instead of several
hours of browsing, with a shortlist where every candidate has already passed the
arithmetic.

> **The engine detects internal inconsistency, not truth.** A listing that passes
> every rule is a candidate for verification, never a validated business.
> Marketplace inputs at this end of the market are self-reported, and every rule
> in `src/acq/rules.py` exists because a real listing lied or contradicted
> itself in that specific way.

---

## Quick start

```bash
pip install -r acquisition/requirements.txt

# 1. Is the config sane?
python .claude/skills/deal-screen/scripts/check_config.py

# 2. Does the rule engine still catch known-bad listings?
python acquisition/run.py gate

# 3. Run the week
python acquisition/run.py weekly --sender "Your Name"
```

Or, in Claude Code: **`/weekly-deals`**.

Everything lands in `acquisition/out/` — the candidate sheet, the deal tracker,
the diligence packs and the outreach drafts. That directory and the candidate
store are gitignored: no seller's financial data goes into version control.

---

## Deliverables

| # | Artefact | Where |
|---|---|---|
| D1 | Config — every threshold, nothing hardcoded | `config.yaml` |
| D2 | Marketplace ingestion (Flippa, TrustMRR) | `src/acq/sources/flippa.py`, `trustmrr.py` |
| D3 | Off-market ingestion (WordPress.org) | `src/acq/sources/wordpress.py` |
| D4 | Normalisation and derived metrics | `src/acq/normalise.py` |
| D5 | Rule engine — rejects, flags, score | `src/acq/rules.py` |
| D6 | Ranked candidate sheet | `out/candidates.xlsx` |
| D7 | Deal tracker | `out/deal-tracker.xlsx` |
| D8 | Diligence pack per candidate | `out/diligence/*.md` |
| D9 | This document | `README.md` |

Plus the judgement layer, which is not automatable: the **`deal-screen`** and
**`deal-verify`** skills and the `/weekly-deals`, `/triage` and `/verify-deal`
commands.

---

## Commands

```bash
python acquisition/run.py gate                     # acceptance tests (run this first)
python acquisition/run.py neglect                  # D3 — WordPress.org off-market pull
python acquisition/run.py marketplace              # D2 — Flippa pull + TrustMRR cross-check
python acquisition/run.py screen                   # re-run the engine over the store
python acquisition/run.py weekly                   # everything, then write D6/D7/D8
python acquisition/run.py show <id>                # one candidate, in full
python acquisition/run.py promote <id> contacted   # move a stage; generates the D8 pack
python acquisition/run.py diligence <id>           # D8 pack on demand
python acquisition/run.py outreach                 # drafts for review
```

Global flags work before or after the subcommand:

| Flag | Effect |
|---|---|
| `--fx-rate 0.79` | Pin USD→GBP instead of fetching ECB rates. Use for reproducible runs. |
| `--offline` | Never reach the network for FX; use the cache or the fallback table. |
| `--fixture path.json` | Replay a recorded API response instead of calling out. |
| `--llm` | Use the Claude classifier for `CHANNEL_RISK` instead of the offline heuristic. |
| `--apify-actor ID` | Read Flippa through an Apify actor rather than the JSON endpoint. |
| `--trustmrr-actor ID` | Enable the TrustMRR cross-check. |
| `--sender "Name"` | Sign outreach drafts. |

---

## How screening works

### Derived fields (`src/acq/normalise.py`)

```
annual_revenue    = ttm_revenue
annual_profit     = ttm_revenue - ttm_costs
run_rate_arr      = mrr * 12
price_to_revenue  = asking_price / annual_revenue
price_to_profit   = asking_price / annual_profit
payback_months    = asking_price / monthly_profit
arpu              = mrr / paying_customers
implied_lifetime  = 1 / monthly_churn
implied_ltv       = arpu * implied_lifetime
trend_ratio       = run_rate_arr / ttm_revenue
```

All currency is converted to GBP once, at ingestion. The original currency and
the rate used are recorded on every candidate. Where a run-rate had to stand in
for a missing TTM, that substitution is recorded too — it is exactly the
substitution a misleading listing makes.

### Hard rejects

`ARPU_BELOW_FLOOR` · `PRICE_TO_REVENUE_TOO_HIGH` · `PAYBACK_TOO_LONG` ·
`NOT_PROFITABLE` · `TOO_YOUNG` · `CATEGORY_EXCLUDED` · `REVENUE_MODEL_EXCLUDED` ·
`PLATFORM_EXCLUDED` · `PRICE_OUT_OF_BAND`

Rejected candidates are dropped from the shortlist but written to a second tab
of the candidate sheet with their reasons, so "why did we never see this one?"
is answerable a month later.

### Flags — surfaced, never auto-rejecting

`DECLINING` · `TREND_MISMATCH` · `LTV_IMPLAUSIBLE` · `CUSTOMER_COUNT_INFLATED` ·
`SELF_CONTRADICTORY` · `COSTS_AMBIGUOUS` · `UNVERIFIED` · `CHANNEL_RISK` ·
`LOSS_MAKING` · `DATA_INCOMPLETE`

Each records the arithmetic that fired it plus the evidence. See
`.claude/skills/deal-screen/references/flag-playbook.md` for what each one means
and the single question to ask about it.

### Two design rules worth knowing

1. **Missing data never causes a hard reject.** A rule that fires on `None`
   rejects an incomplete listing and a bad one identically, and the incomplete
   one might be the good deal. Absence raises `DATA_INCOMPLETE` instead.
2. **Rejects and flags are computed independently.** A rejected listing still
   carries its full flag set, so a later config change can be audited against
   what was already dropped.

### Score

```
score = fit_score - (flag_count * penalty) + verification_bonus
```

The engine only sorts. Every candidate is output with its flags visible; the
human decides.

---

## Three additions beyond the brief

Flagged here rather than buried, because they change what the engine does:

1. **`TREND_MISMATCH`** — the brief flags `trend_ratio < 0.9` (`DECLINING`). The
   inverse also matters: a run-rate far *above* trailing revenue is the same
   misstatement inverted, and it is what Appendix A case 2 actually does
   ($5,753 "ARR" on $1,178 TTM). Threshold: `thresholds.max_trend_ratio`.
2. **`DATA_INCOMPLETE` and `LOSS_MAKING`** — see design rule 1 above, and the
   case of a listing whose own figures show negative profit, where there is no
   payback period to test.
3. **`paying_customers` alongside `active_customers`** — listings that quote a
   user count in the headline and a payer count in the metrics box are the
   common inflation pattern. ARPU is computed against payers where disclosed,
   which is what makes an impossible ARPU surface rather than average away.

Appendix A case 2 is listed in the brief as a flag case; the engine additionally
hard-rejects it on the multiple (7.6× against TTM) and on ARPU. Both are correct,
and the flags are still recorded on the rejected record.

---

## Sources

| Source | Access | Status |
|---|---|---|
| WordPress.org | Documented, free, unauthenticated plugin API | **Fully sanctioned. The priority build.** |
| Flippa | Undocumented JSON search endpoint, or an Apify actor | Fragile. Behind a swappable backend. |
| TrustMRR | Apify actor, no login | Fragile. Source *and* cross-check. |
| Microns, Acquire.com | Behind login, no accessible API | Out of scope. Browse weekly by hand. |

### The off-market stream is the differentiated one

`query_plugins` cannot filter on staleness, so the run pages through
`browse=popular` — which orders by install base, the axis the target band cares
about — and applies the neglect band client-side:

```
neglect_score = log10(active_installs)          # reach
              * months_since_update / 18        # abandonment
              * (rating / 5)                    # quality retained
              * (1 - support_resolution_rate)   # owner disengagement
```

Ranked, never filtered on a hard cutoff — nothing good is lost to a threshold.
These owners are not selling, which is the entire advantage: no competing
bidders and no pitch copy to see through.

Two wire details the module handles, both of which silently corrupt the score if
missed: `rating` comes back on a **0–100** scale (not 0–5), and `author` is an
**HTML anchor**, not a name. The author profile URL is kept — it is the contact
route.

### The TrustMRR join

The cross-check joins on product domain or name. A marketplace listing's URL is
the *marketplace's* domain, so those hosts are excluded from the join key —
folding `flippa.com/11500001` to `flippa` would match every Flippa candidate to
each other and to nothing useful, and every candidate would stay `UNVERIFIED`
while looking like TrustMRR simply had no data. A join that quietly fails is
worse than no join.

---

## Testing

Three suites, all offline and all deterministic. They pin USD→GBP so an
acceptance run never depends on what the ECB published today, and they use the
heuristic channel-risk classifier so it never depends on model sampling.

```bash
python acquisition/run.py gate          # runs all three
python acquisition/tests/test_rules.py       # Appendix A — the Phase 1 gate
python acquisition/tests/test_wordpress.py   # Phase 2 — parsing, band, score, volume
python acquisition/tests/test_pipeline.py    # Phases 3-5 — ingestion through outputs
```

**Phase 1 is the acceptance gate for the whole system.** If the rule engine
can't catch known-bad listings, ingestion volume is worthless. Run it after
every config change — a slipped digit in a threshold raises no error anywhere,
it just quietly returns nothing, or everything.

---

## Constraints

- **Fragility.** Flippa and TrustMRR are undocumented endpoints or third-party
  scrapers. Every source is behind an interface and every failure is loud —
  a source that returned `[]` on a 403 would look exactly like a quiet week.
- **Terms of service.** Scraping sits awkwardly with most marketplace terms. Use
  official APIs where they exist. WordPress.org is fully sanctioned and needs no
  auth, which is a further reason it is the priority build.
- **Rate limits.** `run.request_delay_seconds` throttles every source. This is a
  weekly-cadence system; there is no reason to hammer anything.
- **Data quality ceiling.** The engine detects internal inconsistency, not truth.
- **Currency.** Listings are mostly USD; the buyer thinks in GBP and operates in
  AED. Normalised once, at ingestion, at ECB daily reference rates.

### Egress note

`api.wordpress.org` is blocked by the network policy of the environment this was
built in, so the live D3 pull has **not** been exercised end to end. The module
is verified offline against recorded and generated payloads (28 checks, including
the ≥200-ranked-candidate volume gate), and it will need one live run to confirm
the wire format before the Phase 2 gate is genuinely closed.

---

## Explicitly not built

Out of scope, by design:

- **Automated outreach sending.** Drafting only. There is no send path in this
  codebase, and adding one would be a mistake — at this deal size the
  counterparty is one person, and anything that reads as bulk mail gets deleted.
- **Persistent hosted infrastructure or a scheduler.** Scripts run on demand.
- **Valuation modelling** beyond the screening multiples. Stage 7 is manual.
- **Anything touching a live product post-acquisition.** Different project.
- **Storage of any seller's financial data** beyond the candidate record.
