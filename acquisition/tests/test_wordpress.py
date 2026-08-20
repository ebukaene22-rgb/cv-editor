#!/usr/bin/env python3
"""Phase 2 acceptance — WordPress.org ingestion and neglect scoring.

Runs entirely offline against recorded and generated API payloads. What it
proves: the wire format is parsed correctly (the two details that bite — the
0-100 rating scale and the HTML-wrapped author — plus the date format), the
neglect band admits and excludes the right plugins, the score ranks by the
formula in the brief, and a full-size scan yields the >= 200 ranked candidates
with author contact URLs that Phase 2 requires.

    python acquisition/tests/test_wordpress.py
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acq.config import Config                                   # noqa: E402
from acq.sources.fixture import FixtureSession                  # noqa: E402
from acq.sources.wordpress import (WordPressSource,             # noqa: E402
                                   neglect_score, months_since)

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)
SAMPLE = Path(__file__).parent / "fixtures" / "wordpress_sample.json"
GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"

results: list[tuple[bool, str, str]] = []


def expect(condition: bool, name: str, detail: str = "") -> None:
    results.append((bool(condition), name, detail))


# --------------------------------------------------------------------- parsing
def test_parsing() -> None:
    raw = json.loads(SAMPLE.read_text())["plugins"]
    by_slug = {p["slug"]: WordPressSource.to_candidate(p, now=NOW) for p in raw}

    booking = by_slug["simple-booking-calendar"]
    expect(booking.rating == 4.4, "rating converts 0-100 to 0-5",
           f"88 on the wire -> {booking.rating}")
    expect(booking.author == "Helen Griffiths", "author unwrapped from HTML anchor",
           f"got {booking.author!r}")
    expect(booking.author_profile.startswith("https://profiles.wordpress.org/"),
           "author profile URL retained for contact", booking.author_profile)
    expect(booking.url == "https://wordpress.org/plugins/simple-booking-calendar/",
           "plugin page URL constructed", booking.url)
    expect(43 <= booking.months_since_update <= 44,
           "'2023-01-17 9:42am GMT' parses to ~43 months stale",
           f"{booking.months_since_update} months")
    expect(booking.support_resolution_rate == round(2 / 18, 3),
           "support resolution rate computed", str(booking.support_resolution_rate))

    quiet = by_slug["quiet-shipping-rules"]
    expect(quiet.support_resolution_rate == 0.5,
           "zero support threads takes the neutral rate, not maximum neglect",
           str(quiet.support_resolution_rate))


# ------------------------------------------------------------------ the band
def test_band() -> None:
    cfg = Config.load()
    session = FixtureSession([json.loads(SAMPLE.read_text())])
    src = WordPressSource(cfg, session=session)
    src.delay = 0
    found = {n.slug for n in src.fetch_neglect()}

    expect("simple-booking-calendar" in found, "stale + popular + well-rated is admitted")
    expect("wp-invoice-lite" in found, "9k installs, 4 years stale, 3.7★ is admitted")
    expect("quiet-shipping-rules" in found, "5k installs, stale, 4.6★ is admitted")
    expect("active-cache-pro" not in found, "actively maintained plugin excluded")
    expect("tiny-contact-widget" not in found, "below the install floor excluded")
    expect("broken-gallery" not in found, "below the rating floor excluded (2.1★)")


# ------------------------------------------------------------------ the score
def test_score() -> None:
    # Reach x abandonment x quality x disengagement, each varied alone.
    base = neglect_score(10_000, 24, 4.5, 0.2)
    expect(neglect_score(100_000, 24, 4.5, 0.2) > base, "more installs scores higher")
    expect(neglect_score(10_000, 48, 4.5, 0.2) > base, "staler scores higher")
    expect(neglect_score(10_000, 24, 3.6, 0.2) < base, "lower rating scores lower")
    expect(neglect_score(10_000, 24, 4.5, 0.9) < base, "an engaged owner scores lower")
    expect(neglect_score(10_000, 24, 4.5, 1.0) == 0.0, "fully responsive owner scores zero")
    expect(neglect_score(0, 24, 4.5, 0.2) == 0.0, "zero installs scores zero, no math error")
    expect(neglect_score(10_000, 0, 4.5, 0.2) == 0.0, "updated today scores zero")

    expected = round(4.0 * (36 / 18) * (4.0 / 5) * (1 - 0.25), 4)
    expect(neglect_score(10_000, 36, 4.0, 0.25) == expected,
           "score matches the brief's formula exactly", f"want {expected}")


def test_real_data_guards() -> None:
    """Two guards added after running the brief's formula over the real directory.

    Both defects were invisible in generated data and obvious in real data, so
    they are pinned here.
    """
    # Guard 1 — the abandonment term is linear and unbounded. Uncapped, a plugin
    # last touched in 2010 scores 10x on that term alone and outranks a far
    # bigger, more recently abandoned one.
    fossil_raw = neglect_score(2_000, 189, 4.8, 0.0)
    big_raw = neglect_score(50_000, 60, 4.8, 0.0)
    expect(fossil_raw > big_raw,
           "uncapped: a 15-year-old 2k-install plugin beats a 5-year-old 50k one",
           f"{fossil_raw} vs {big_raw}")

    fossil_cap = neglect_score(2_000, 189, 4.8, 0.0, max_abandonment=4.0)
    big_cap = neglect_score(50_000, 60, 4.8, 0.0, max_abandonment=4.0)
    expect(big_cap > fossil_cap,
           "capped: reach decides once both are thoroughly abandoned",
           f"{big_cap} vs {fossil_cap}")
    expect(neglect_score(10_000, 72, 4.0, 0.5, max_abandonment=4.0)
           == neglect_score(10_000, 200, 4.0, 0.5, max_abandonment=4.0),
           "past the cap, more staleness changes nothing")
    expect(neglect_score(10_000, 36, 4.0, 0.25, max_abandonment=4.0)
           == neglect_score(10_000, 36, 4.0, 0.25),
           "below the cap the score is unchanged from the brief's formula")

    # Guard 2 — the directory counts support threads over the last two months
    # only, so 17,674 plugins have exactly one. "0 of 1 resolved" is not evidence
    # of an absent owner, and without a sample floor it scores maximum
    # disengagement.
    one_thread = {"slug": "x", "name": "X", "active_installs": 5000, "rating": 90,
                  "support_threads": 1, "support_threads_resolved": 0,
                  "last_updated": "2021-01-01 9:00am GMT"}
    loose = WordPressSource.to_candidate(one_thread, now=NOW, min_support_threads=0)
    strict = WordPressSource.to_candidate(one_thread, now=NOW, min_support_threads=5)
    expect(loose.support_resolution_rate == 0.0,
           "without a sample floor, 0 of 1 reads as total disengagement")
    expect(strict.support_resolution_rate == 0.5,
           "with a sample floor, a single thread takes the neutral rate",
           str(strict.support_resolution_rate))
    expect(strict.neglect_score < loose.neglect_score,
           "the floor stops one unanswered thread inflating the score")

    many = dict(one_thread, support_threads=12, support_threads_resolved=1)
    real = WordPressSource.to_candidate(many, now=NOW, min_support_threads=5)
    expect(abs(real.support_resolution_rate - 1 / 12) < 0.001,
           "a real sample is used as observed", str(real.support_resolution_rate))


# ------------------------------------------------- volume + ranking at scale
def _synthetic_pages(count: int = 4000, per_page: int = 100) -> list[dict]:
    """A deterministic corpus shaped like the live `browse=popular` response."""
    rng = random.Random(20260820)
    plugins = []
    for i in range(count):
        stale_days = rng.choice([5, 40, 120, 400, 700, 1100, 1600, 2400])
        updated = NOW - timedelta(days=stale_days)
        threads = rng.choice([0, 0, 3, 12, 40, 150])
        plugins.append({
            "name": f"Plugin {i}",
            "slug": f"plugin-{i}",
            "author": f'<a href="https://profiles.wordpress.org/dev{i}/">Dev {i}</a>',
            "author_profile": f"https://profiles.wordpress.org/dev{i}/",
            "rating": rng.choice([0, 40, 62, 71, 78, 84, 90, 96]),
            "num_ratings": rng.randint(0, 4000),
            "support_threads": threads,
            "support_threads_resolved": rng.randint(0, threads) if threads else 0,
            "active_installs": rng.choice([10, 100, 500, 1000, 5000, 20_000, 90_000, 400_000]),
            "last_updated": updated.strftime("%Y-%m-%d %I:%M%p GMT"),
        })
    pages = []
    total_pages = (count + per_page - 1) // per_page
    for p in range(total_pages):
        pages.append({
            "info": {"page": p + 1, "pages": total_pages, "results": count},
            "plugins": plugins[p * per_page:(p + 1) * per_page],
        })
    return pages


def test_volume() -> None:
    cfg = Config.load()
    src = WordPressSource(cfg, session=FixtureSession(_synthetic_pages()))
    src.delay = 0
    found = src.fetch_neglect()

    expect(len(found) >= 200,
           "Phase 2 gate: >= 200 ranked neglect candidates from a full scan",
           f"got {len(found)}")
    expect(all(n.author_profile for n in found),
           "every candidate carries an author contact URL")
    scores = [n.neglect_score for n in found]
    expect(scores == sorted(scores, reverse=True), "output is ranked by neglect score descending")
    expect(all(n.active_installs >= cfg["neglect.min_active_installs"] for n in found),
           "install floor holds across the whole list")
    expect(all(n.months_since_update >= cfg["neglect.min_months_since_update"] for n in found),
           "staleness floor holds across the whole list")
    expect(all(n.rating >= cfg["neglect.min_rating"] for n in found),
           "rating floor holds across the whole list")

    top = found[0]
    print(f"\n  top candidate: {top.name} — {top.active_installs:,} installs, "
          f"{top.months_since_update:.0f}mo stale, {top.rating}★, "
          f"score {top.neglect_score} → {top.author_profile}")


def test_paging_stops() -> None:
    """An exhausted feed must end the loop, not spin to max_pages."""
    cfg = Config.load()
    session = FixtureSession(_synthetic_pages(count=150))
    src = WordPressSource(cfg, session=session)
    src.delay = 0
    src.fetch_neglect()
    expect(len(session.calls) == 2, "paging stops when info.pages is reached",
           f"made {len(session.calls)} requests")


def main() -> int:
    print("WORDPRESS.ORG OFF-MARKET — PHASE 2 ACCEPTANCE")
    print("=" * 72)
    for fn in (test_parsing, test_band, test_score, test_real_data_guards,
               test_volume, test_paging_stops):
        fn()

    failed = 0
    print()
    for ok, name, detail in results:
        mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        suffix = f"  ({detail})" if detail and not ok else ""
        print(f"  [{mark}] {name}{suffix}")
        failed += 0 if ok else 1

    print("=" * 72)
    if failed:
        print(f"{RED}FAILED{RESET} — {failed} of {len(results)} checks")
        return 1
    print(f"{GREEN}PASSED{RESET} — {len(results)} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
