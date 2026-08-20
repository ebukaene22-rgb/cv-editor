#!/usr/bin/env python3
"""Prose extraction — the figures the marketplace endpoint does not return.

Flippa gives price, revenue, profit, traffic and dates. It does not give a
customer count, a churn rate, a stated LTV or an entry price, so without this
module LTV_IMPLAUSIBLE and CUSTOMER_COUNT_INFLATED are dead on live data.

The suite is mostly about what the extractor must *refuse* to read. A missed
figure leaves a rule unevaluated and the coverage report says so out loud; a
wrong figure raises a flag against a number the seller never gave, which is
worse than silence.

    python acquisition/tests/test_extract.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acq.extract import extract                       # noqa: E402
from acq.sources.flippa import FlippaSource           # noqa: E402

GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"
results: list[tuple[bool, str, str]] = []

# (text, expected fields) — anything not named must come back None.
READS = [
    ("1,000 customers on plans from $5/mo. Clearing $600/mo profit.",
     {"active_customers": 1000, "min_customer_price": 5},
     "count and entry price from one sentence"),
    ("LTV is $7,200 per customer. Churn is 8% monthly.",
     {"stated_ltv": 7200, "monthly_churn": 0.08},
     "stated LTV and churn"),
    ("Monthly churn of 4.5% across the base.",
     {"monthly_churn": 0.045},
     "churn phrased the other way round"),
    ("AI video app. 19.8k monthly users, only 33 of them pay.",
     {"active_customers": 19800, "paying_customers": 33},
     "headline user count AND the payer count — the inflation case"),
    ("62 paying stores on the Shopify app store.",
     {"active_customers": 62},
     "domain noun ('stores') counts as customers"),
    ("44 agency accounts.",
     {"active_customers": 44},
     "an intervening word ('agency accounts') does not break the match"),
    ("Charges $19/month per seat, 140 teams signed up.",
     {"active_customers": 140, "min_customer_price": 19},
     "bare $N/month is a plan price when nothing says otherwise"),
    ("2,400 free signups, 180 paying customers, plans start at $12/month.",
     {"paying_customers": 180, "min_customer_price": 12},
     "free signups are not counted as customers"),
    ("Lifetime value of $3,000 per customer.",
     {"stated_ltv": 3000},
     "a money amount reads as an LTV, never as a customer count"),
    ("Costs are low, around $90/mo for the SERP API.",
     {"stated_monthly_costs": 90},
     "a stated running cost is read as a cost"),
    ("Running costs are minimal, under $40/mo in API spend.",
     {"stated_monthly_costs": 40},
     "cost word after the amount also counts"),
    ("Hosting runs $200 a month on Hetzner.",
     {"stated_monthly_costs": 200},
     "'a month' phrasing is read"),
]

# Things that must NOT be read as anything.
REFUSALS = [
    ("30k monthly visitors and growing fast.", "traffic is not a customer count"),
    ("Over 300 five-star reviews. 500 downloads a week.",
     "reviews and downloads are not customers"),
    ("Priced at 2x revenue. $4,997 asking. 900 monthly uniques.",
     "an asking price is not an entry price and uniques are not customers"),
    ("Clearing $600/mo profit on this one.", "a profit figure is neither a cost nor a price"),
    ("No numbers here at all.", "prose with no figures yields nothing"),
]

FIELDS = ("active_customers", "paying_customers", "monthly_churn",
          "stated_ltv", "min_customer_price", "stated_monthly_costs")


def expect(condition: bool, name: str, detail: str = "") -> None:
    results.append((bool(condition), name, detail))


def test_reads() -> None:
    for text, wanted, label in READS:
        got = extract(text)
        for field, value in wanted.items():
            actual = getattr(got, field)
            expect(actual == value, f"{label} → {field}",
                   f"want {value}, got {actual}")
        for field in FIELDS:
            if field not in wanted:
                expect(getattr(got, field) is None,
                       f"{label} → {field} stays empty",
                       f"got {getattr(got, field)}")


def test_refusals() -> None:
    for text, label in REFUSALS:
        got = extract(text)
        populated = {f: getattr(got, f) for f in FIELDS if getattr(got, f) is not None}
        expect(not populated, f"refuses: {label}", f"read {populated}")


def test_provenance_and_precedence() -> None:
    got = extract("1,000 customers on plans from $5/mo.")
    expect("active_customers" in got.sources,
           "every extracted figure records the phrase it came from")
    expect("customers" in got.sources.get("active_customers", ""),
           "the recorded phrase contains the match")

    # An endpoint figure must always beat a prose figure.
    listing = FlippaSource.to_listing({
        "id": 1, "title": "Thing", "current_price": 9000,
        "average_revenue": 6000, "established_at": "2021-01-01",
        "summary": "1,000 customers on plans from $5/mo.",
    })
    expect(listing.active_customers == 1000, "prose fills an empty field")

    listing.active_customers = None
    from acq.extract import apply_to
    listing.active_customers = 42          # pretend the endpoint supplied it
    apply_to(listing)
    expect(listing.active_customers == 42,
           "prose never overrides a figure the endpoint gave")


def test_rules_now_fire() -> None:
    """The point of the module: two flags that were dead on live data."""
    from acq.classify import HeuristicClassifier
    from acq.config import Config
    from acq.fx import FixedRates
    from acq.normalise import normalise
    from acq.rules import RuleEngine

    fx = FixedRates({"USD": 0.79, "GBP": 1.0})
    engine = RuleEngine(Config.load(), classifier=HeuristicClassifier())

    inflated = normalise(FlippaSource.to_listing({
        "id": 1, "title": "AI video creator", "industry": "saas",
        "business_model": "subscription", "current_price": 15000,
        "average_revenue": 6900, "profit_per_month": 600,
        "established_at": "2024-01-01",
        "summary": "1,000 customers on plans from $5/mo. Clearing $600/mo profit.",
    }), fx)
    engine.screen(inflated)
    expect("CUSTOMER_COUNT_INFLATED" in inflated.flag_names(),
           "CUSTOMER_COUNT_INFLATED fires from an endpoint-shaped listing",
           str(inflated.flag_names()))

    ltv = normalise(FlippaSource.to_listing({
        "id": 2, "title": "YouTube growth tool", "industry": "saas",
        "business_model": "subscription", "current_price": 9000,
        "average_revenue": 7000, "revenue_per_month": 470,
        "established_at": "2023-01-15",
        "summary": "LTV is $7,200 per customer. Churn is 8% monthly. "
                   "Early users came from my audience.",
    }), fx)
    engine.screen(ltv)
    expect("LTV_IMPLAUSIBLE" in ltv.flag_names(),
           "LTV_IMPLAUSIBLE fires from an endpoint-shaped listing",
           str(ltv.flag_names()))
    expect("CHANNEL_RISK" in ltv.flag_names(),
           "CHANNEL_RISK still fires alongside", str(ltv.flag_names()))


def test_costs_flag_evidence() -> None:
    """A flag whose evidence is wrong is a flag nobody trusts."""
    from acq.classify import HeuristicClassifier
    from acq.config import Config
    from acq.fx import FixedRates
    from acq.normalise import normalise
    from acq.rules import RuleEngine

    fx = FixedRates({"USD": 0.79, "GBP": 1.0})
    engine = RuleEngine(Config.load(), classifier=HeuristicClassifier())

    base = {"id": 3, "title": "Rank tracker", "industry": "saas",
            "business_model": "subscription", "current_price": 16000,
            "average_revenue": 13200, "revenue_per_month": 1100,
            "established_at": "2021-11-01", "currency": "USD"}

    stated = normalise(FlippaSource.to_listing(
        dict(base, summary="White-label rank tracking. Costs are low, around "
                           "$90/mo for the SERP API.")), fx)
    engine.screen(stated)
    costs = next(f for f in stated.flags if f["flag"] == "COSTS_AMBIGUOUS")
    expect("no cost figure stated" not in costs["trigger"],
           "does not claim 'no cost figure stated' when one is stated in prose",
           costs["trigger"])
    expect("prose" in costs["trigger"] and "71" in costs["trigger"],
           "the flag quotes the prose cost it found, converted to GBP",
           costs["trigger"])
    expect("margin" in costs["evidence"],
           "the evidence gives the margin that figure implies", costs["evidence"])

    silent = normalise(FlippaSource.to_listing(
        dict(base, summary="White-label rank tracking for agencies.")), fx)
    engine.screen(silent)
    quiet = next(f for f in silent.flags if f["flag"] == "COSTS_AMBIGUOUS")
    expect(quiet["trigger"] == "no cost figure stated",
           "still says so plainly when no cost is stated anywhere", quiet["trigger"])

    expect(stated.ttm_costs is None,
           "a prose cost never becomes ttm_costs, so it cannot drive a hard reject")
    expect(stated.payback_months is None,
           "payback stays uncomputable rather than resting on a prose figure")


def main() -> int:
    print("PROSE EXTRACTION — figures the endpoint does not return")
    print("=" * 72)
    for fn in (test_reads, test_refusals, test_provenance_and_precedence,
               test_rules_now_fire, test_costs_flag_evidence):
        fn()

    failed = 0
    for ok, name, detail in results:
        if ok:
            continue
        failed += 1
    for ok, name, detail in results:
        mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        suffix = f"  ({detail})" if detail and not ok else ""
        print(f"  [{mark}] {name}{suffix}")

    print("=" * 72)
    if failed:
        print(f"{RED}FAILED{RESET} — {failed} of {len(results)} checks")
        return 1
    print(f"{GREEN}PASSED{RESET} — {len(results)} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
