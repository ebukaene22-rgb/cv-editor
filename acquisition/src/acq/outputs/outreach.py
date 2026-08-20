"""Outreach drafting — assisted only. Generate, never send.

At this deal size the counterparty is one person; anything that reads as bulk
mail gets deleted. So the drafts go to a review file, the human edits them, and
the human sends from their own client. There is deliberately no send path in
this codebase.

Two templates:

  off-market  — for WordPress.org authors who are not selling. Names the product
    and its install count, states intent plainly, asks one question, gives an
    easy no. No valuation. No portfolio talk.
  marketplace — skips the seller's pitch and asks for three primary-data items.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..models import Candidate, NeglectCandidate

SIGNOFF = "{your_name}"


def off_market_draft(n: NeglectCandidate, sender: str = SIGNOFF) -> str:
    installs = f"{n.active_installs:,}"
    stale = f"{n.months_since_update:.0f} months"
    return f"""\
To:      {n.author or 'the author'} — {n.author_profile or '(find contact on the plugin page)'}
Subject: Your {n.name}

Hi {(n.author or '').split()[0] if n.author else 'there'},

I came across {n.name} — it's got {installs} active installs and looks like it's
been running quietly for a while without much attention lately (last update was
about {stale} ago).

I buy and run small software products, and I'd be interested in taking it on if
you've stopped working on it. No pressure either way, and I'm not looking for you
to do a load of work — happy to handle the transfer side.

If you're open to it, could you tell me roughly what it makes a month and how much
time it takes you? I can come back with a number quickly.

{sender}

---
Plugin page: {n.url}
Neglect score: {n.neglect_score} · {n.rating}★ from {n.num_ratings} ratings ·
support threads resolved: {n.support_threads_resolved}/{n.support_threads}
"""


def marketplace_draft(c: Candidate, sender: str = SIGNOFF) -> str:
    body = f"""\
To:      seller — via {c.url or 'the listing'}
Subject: {c.name}

Hi,

Interested in {c.name}. Before we go further, three things:

1. Monthly revenue for the last 12 months — a processor export or a screen-share of
   the Stripe dashboard is fine, I don't need a spreadsheet.
2. Current active paying subscribers, and the split between subscription revenue and
   one-off purchases.
3. Where the last 20 customers came from.

If those look how I'd expect, I'll move quickly.

{sender}
"""
    # The footer is for the human, not the seller — it never goes in the mail.
    facts = [f"Listing: {c.url}" if c.url else "Listing: —"]
    if c.asking_price is not None:
        facts.append(f"Asking £{c.asking_price:,.0f}")
    if c.price_to_revenue is not None:
        facts.append(f"price/revenue {c.price_to_revenue:.2f}x")
    if c.payback_months is not None:
        facts.append(f"payback {c.payback_months:,.0f} months")
    facts.append(f"Flags to keep in mind on the call: {', '.join(c.flag_names()) or 'none'}")
    return body + "\n---\n" + " · ".join(facts) + "\n"


HEADER = """# Outreach drafts — review before sending

**These are drafts. Nothing here has been sent, and this system has no send path.**

Edit each one so it doesn't read as a template, then send it from your own mail
client. Space them out — 20–30 off-market approaches gets roughly 3–5 replies and
about one real conversation. Never bulk-send.

Do not attach a valuation. Do not mention a portfolio.

"""


def write(neglect: list[NeglectCandidate], marketplace: list[Candidate],
          path: str | Path, sender: str = SIGNOFF) -> Path:
    parts = [HEADER, f"Generated {datetime.now(timezone.utc):%Y-%m-%d} · "
                     f"{len(neglect)} off-market · {len(marketplace)} marketplace\n"]

    if neglect:
        parts.append("\n---\n\n## Off-market cold approaches\n")
        for n in neglect:
            parts.append(f"\n### {n.name}\n\n```\n{off_market_draft(n, sender)}```\n")

    if marketplace:
        parts.append("\n---\n\n## Marketplace enquiries\n")
        for c in marketplace:
            parts.append(f"\n### {c.name}\n\n```\n{marketplace_draft(c, sender)}```\n")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts))
    return path
