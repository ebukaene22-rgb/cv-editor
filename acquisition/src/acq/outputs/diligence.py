"""D8 — the diligence pack.

Generated for any candidate promoted to `contacted`. Four sections, in the
order they get used: what the engine computed, every flag with the evidence
that triggered it, the four triage questions from Stage 3, and the data request
to send.

The pack states what is *unverified* as prominently as what is known. A listing
that passes every rule is a candidate for verification, never a validated
business, and the document a human reads before a call should say so on its
face.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..models import Candidate

TRIAGE_QUESTIONS = [
    ("Where did the customers come from?",
     "If the answer is a person's audience, a launch spike, or \"not sure\" — stop."),
    ("Is my skill the growth lever here?",
     "Pricing, funnel, retention, measurement. If the bottleneck is design, content "
     "volume or sales, there is no edge."),
    ("What breaks if I ignore it for a month?",
     "Uptime-critical or platform-policy-exposed products fail this."),
    ("What does the platform it depends on think of it?",
     "App store policy, API terms, search guidelines."),
]

DATA_REQUEST = [
    "Monthly revenue for the last 12 months — processor export or a screen-share of the "
    "Stripe dashboard. Not a spreadsheet.",
    "Current active paying subscribers, and the split between subscription revenue and "
    "one-off purchases.",
    "Where the last 20 customers came from.",
    "Hosting and API invoices for the last 3 months.",
    "Read-only processor access, or a live screen-share of the dashboard.",
    "Google Analytics guest access and Search Console access.",
    "Confirmation of ownership: domain, repository, third-party accounts, brand assets.",
]


def _money(value: float | None) -> str:
    return "—" if value is None else f"£{value:,.0f}"


def _ratio(value: float | None, suffix: str = "x") -> str:
    return "—" if value is None else f"{value:,.2f}{suffix}"


def render(c: Candidate) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    verified = c.has_verified_revenue or c.trustmrr_match == "agrees"

    lines: list[str] = [
        f"# Diligence pack — {c.name or c.key}",
        "",
        f"**Candidate ID:** `{c.key}`  ",
        f"**Source:** {c.source}  ",
        f"**URL:** {c.url or '—'}  ",
        f"**Generated:** {stamp}  ",
        f"**Screening score:** {c.score}  ",
        f"**Stage:** {c.status}",
        "",
        "> Every figure below is the seller's, converted to GBP. The engine has "
        "checked it for internal consistency, not for truth. Nothing here is "
        "verified until it is reconciled against a primary source.",
        "",
        "## 1. Computed metrics",
        "",
        "| Metric | Value | Note |",
        "|---|---|---|",
        f"| Asking price | {_money(c.asking_price)} | original {c.original_currency}, "
        f"rate {c.fx_rate:.4f} |" if c.fx_rate else
        f"| Asking price | {_money(c.asking_price)} | |",
        f"| TTM revenue | {_money(c.ttm_revenue)} | trailing twelve months |",
        f"| MRR | {_money(c.mrr)} | |",
        f"| Run-rate ARR | {_money(c.run_rate_arr)} | mrr × 12 |",
        f"| Annual profit | {_money(c.annual_profit)} | |",
        f"| ARPU | {'—' if c.arpu is None else f'£{c.arpu:,.2f}'} | per paying customer |",
        f"| Price / revenue | {_ratio(c.price_to_revenue)} | |",
        f"| Price / profit | {_ratio(c.price_to_profit)} | |",
        f"| Payback | {_ratio(c.payback_months, ' months')} | target under 36 at offer |",
        f"| Trend ratio | {_ratio(c.trend_ratio, '')} | run-rate ÷ trailing |",
        f"| Implied lifetime | {_ratio(c.implied_lifetime, ' months')} | 1 ÷ monthly churn |",
        f"| Implied LTV | {_money(c.implied_ltv)} | arpu × lifetime |",
        f"| Stated LTV | {_money(c.stated_ltv)} | seller's figure |",
        f"| Age | {_ratio(c.age_months, ' months')} | |",
        "",
        f"**Verification:** {'processor-verified' if verified else 'UNVERIFIED'}"
        + (f" — TrustMRR reports {_money(c.trustmrr_mrr)} MRR ({c.trustmrr_match})"
           if c.trustmrr_match in ("agrees", "disagrees") else
           " — no verified figure and no TrustMRR match."),
        "",
    ]

    lines += ["## 2. Flags", ""]
    if not c.flags:
        lines += ["No flags raised. That is not the same as clean — it means nothing in the "
                  "listing contradicted anything else in the listing.", ""]
    else:
        for f in c.flags:
            lines += [f"### `{f['flag']}`", "",
                      f"**Triggered by:** {f['trigger']}", ""]
            if f["evidence"]:
                lines += [f"**Evidence:** {f['evidence']}", ""]

    if c.rejects:
        lines += ["## 2b. Hard rejects on record", "",
                  "This candidate failed automated screening. It is in the pack because it "
                  "was promoted manually — the reasons stand and should be answered before "
                  "anything else.", ""]
        for r in c.rejects:
            lines += [f"- **`{r['rule']}`** — {r['detail']}"]
        lines += [""]

    lines += ["## 3. Triage — answer these before spending more time", ""]
    for i, (question, why) in enumerate(TRIAGE_QUESTIONS, start=1):
        lines += [f"{i}. **{question}**", f"   {why}", "   ", "   > *Answer:*", ""]

    lines += ["## 4. Data request", "",
              "Send this list. Accept nothing seller-built in place of any of it.", ""]
    for item in DATA_REQUEST:
        lines += [f"- [ ] {item}"]
    lines += ["",
              "## 5. Reconciliation", "",
              "Every number the seller gives must agree with the primary source. Any single "
              "unexplained discrepancy resets this deal to triage.", "",
              "| Item | Seller says | Primary source says | Agrees? |",
              "|---|---|---|---|",
              f"| TTM revenue | {_money(c.ttm_revenue)} | | |",
              f"| MRR | {_money(c.mrr)} | | |",
              f"| Paying customers | {'—' if c.active_customers is None else f'{c.active_customers:,.0f}'} | | |",
              f"| Monthly churn | {'—' if c.monthly_churn is None else f'{c.monthly_churn:.1%}'} | | |",
              "| Monthly costs | | | |",
              "| Traffic | | | |",
              ""]
    return "\n".join(lines)


def write(candidate: Candidate, out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = candidate.key.replace(":", "-").replace("/", "-")
    path = out_dir / f"diligence-{safe}.md"
    path.write_text(render(candidate))
    return path
