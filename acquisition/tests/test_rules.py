#!/usr/bin/env python3
"""Phase 1 acceptance gate — Appendix A regression suite.

"If the rule engine can't catch known-bad listings, ingestion volume is
worthless." Run this before every screening run and before every config change:

    python acquisition/tests/test_rules.py

Exit 0 = the gate passes. Exit 1 = do not run the pipeline.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acq.classify import HeuristicClassifier          # noqa: E402
from acq.config import Config                         # noqa: E402
from acq.fx import FixedRates                         # noqa: E402
from acq.models import Listing                        # noqa: E402
from acq.normalise import normalise                   # noqa: E402
from acq.rules import RuleEngine                      # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "appendix_a.yaml"
GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def load_cases():
    with FIXTURES.open() as fh:
        return yaml.safe_load(fh)


def run_case(case, engine, fx):
    listing = Listing(**case["listing"])
    candidate = normalise(listing, fx)
    return engine.screen(candidate)


def check(case, c) -> list[str]:
    failures = []
    got_rejects, got_flags = set(c.reject_reasons()), set(c.flag_names())

    want_disposition = case.get("expect_disposition")
    if want_disposition and c.disposition != want_disposition:
        failures.append(f"disposition: want {want_disposition}, got {c.disposition}")

    missing_rejects = set(case.get("expect_rejects") or []) - got_rejects
    if missing_rejects:
        failures.append(f"missing hard rejects: {sorted(missing_rejects)}")

    missing_flags = set(case.get("expect_flags") or []) - got_flags
    if missing_flags:
        failures.append(f"missing flags: {sorted(missing_flags)}")

    # A `review` case must not have been rejected for any reason, expected or not
    # — a stray reject rule would silently drop a candidate the human should see.
    if want_disposition == "review" and got_rejects:
        failures.append(f"unexpected hard rejects on a review case: {sorted(got_rejects)}")

    return failures


def describe(c) -> str:
    def fmt(v, spec=",.2f"):
        return "—" if v is None else format(v, spec)

    return (f"      price £{fmt(c.asking_price, ',.0f')} · rev £{fmt(c.annual_revenue, ',.0f')} · "
            f"p/r {fmt(c.price_to_revenue)}x · payback {fmt(c.payback_months, ',.0f')}mo · "
            f"arpu £{fmt(c.arpu)} · trend {fmt(c.trend_ratio)} · score {c.score}")


def main() -> int:
    data = load_cases()
    fx = FixedRates(data["fx"])
    engine = RuleEngine(Config.load(), classifier=HeuristicClassifier())

    print("APPENDIX A — RULE ENGINE ACCEPTANCE GATE")
    print("═" * 72)

    failed = 0
    for case in data["cases"]:
        c = run_case(case, engine, fx)
        failures = check(case, c)
        mark = f"{GREEN}PASS{RESET}" if not failures else f"{RED}FAIL{RESET}"
        print(f"\n[{mark}] {case['id']}  →  {c.disposition.upper()}")
        print(describe(c))
        for r in c.rejects:
            print(f"      {RED}REJECT{RESET} {r['rule']}: {r['detail']}")
        for f in c.flags:
            print(f"      FLAG   {f['flag']}: {f['trigger']}")
            if f["evidence"]:
                print(f"             {DIM}{f['evidence']}{RESET}")
        for problem in failures:
            print(f"      {RED}✗ {problem}{RESET}")
            failed += 1

    print("\n" + "═" * 72)
    if failed:
        print(f"{RED}GATE FAILED{RESET} — {failed} expectation(s) unmet. Do not run the pipeline.")
        return 1
    print(f"{GREEN}GATE PASSED{RESET} — all {len(data['cases'])} Appendix A cases handled correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
