"""A deterministic offline corpus for rehearsing a full run.

The point of the demo is that it is *repeatable* and *realistic enough to be
wrong in the same ways as the real thing*: sponsored listings outside the price
band, listings whose numbers contradict themselves, plugins whose rating comes
back on the wrong scale. A rehearsal against clean data teaches nothing.

Marketplace listings and TrustMRR records are committed JSON, so they are easy
to read and easy to edit. The WordPress corpus is generated here rather than
committed — 4,000 plugin records is not a file anyone should have to read, and
the volume is the point of that source.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
DEMO_FLIPPA = FIXTURES / "demo_flippa.json"
DEMO_TRUSTMRR = FIXTURES / "demo_trustmrr.json"

SEED = 20260820

# Plugin-name parts, chosen so the generated corpus reads like the real
# directory rather than "Plugin 0 ... Plugin 3999".
_PREFIX = ("WP", "Simple", "Easy", "Advanced", "Ultimate", "Smart", "Quick", "Pro",
           "Lite", "Super", "Mini", "Better", "Custom", "Auto")
_NOUN = ("Booking", "Invoice", "Gallery", "Contact Form", "SEO", "Backup", "Slider",
         "Popup", "Membership", "Shipping", "Analytics", "Cache", "Newsletter",
         "Testimonials", "Countdown", "Redirect", "Table", "Maps", "Chat", "Reviews",
         "Coupons", "Inventory", "Booking Calendar", "Price List", "Directory")
_SUFFIX = ("", " Manager", " Pro", " Plus", " Lite", " for WooCommerce", " Widget",
           " Blocks", " Toolkit", " Suite")
_AUTHOR_FIRST = ("Helen", "David", "Priya", "Marcus", "Sofia", "Tom", "Aiko", "Luis",
                 "Nina", "Omar", "Greta", "Sam", "Yara", "Jonas", "Mei")
_AUTHOR_LAST = ("Griffiths", "Moreau", "Nair", "Okafor", "Rossi", "Bennett", "Tanaka",
                "Alvarez", "Kowalski", "Haddad", "Lindqvist", "Doyle", "Farouk",
                "Vogel", "Chen")


def wordpress_pages(count: int = 4000, per_page: int = 100,
                    now: datetime | None = None, seed: int = SEED) -> list[dict]:
    """Build `count` plugin records in the live `query_plugins` response shape.

    Deliberately includes the two wire quirks the ingestion module has to
    survive: `rating` on a 0-100 scale and `author` wrapped in an HTML anchor.
    """
    now = now or datetime.now(timezone.utc)
    rng = random.Random(seed)
    plugins = []

    for i in range(count):
        # Most of the directory is either actively maintained or tiny. The band
        # should have to find its candidates, not be handed them.
        stale_days = rng.choices(
            [7, 45, 120, 300, 560, 900, 1400, 2200, 3000],
            weights=[18, 16, 14, 10, 10, 12, 8, 7, 5],
        )[0]
        installs = rng.choices(
            [10, 60, 200, 700, 1000, 4000, 10_000, 40_000, 100_000, 500_000],
            weights=[14, 14, 13, 12, 11, 12, 10, 8, 4, 2],
        )[0]
        rating_100 = rng.choices([0, 30, 44, 58, 66, 74, 82, 90, 96],
                                 weights=[6, 5, 6, 8, 12, 16, 18, 17, 12])[0]
        threads = rng.choices([0, 0, 1, 4, 11, 28, 70, 160],
                              weights=[22, 18, 14, 14, 12, 10, 6, 4])[0]
        resolved = rng.randint(0, threads) if threads else 0

        name = (f"{rng.choice(_PREFIX)} {rng.choice(_NOUN)}{rng.choice(_SUFFIX)}").strip()
        slug = name.lower().replace(" ", "-") + f"-{i}"
        handle = f"{rng.choice(_AUTHOR_FIRST).lower()}{rng.randint(1, 999)}"
        author = f"{rng.choice(_AUTHOR_FIRST)} {rng.choice(_AUTHOR_LAST)}"
        updated = now - timedelta(days=stale_days)

        plugins.append({
            "name": name,
            "slug": slug,
            "author": f'<a href="https://profiles.wordpress.org/{handle}/">{author}</a>',
            "author_profile": f"https://profiles.wordpress.org/{handle}/",
            "rating": rating_100,                       # 0-100 on the wire, as live
            "num_ratings": rng.randint(0, 5000),
            "support_threads": threads,
            "support_threads_resolved": resolved,
            "active_installs": installs,
            "last_updated": updated.strftime("%Y-%m-%d %I:%M%p GMT"),
            "short_description": f"{name} for WordPress.",
        })

    total_pages = (count + per_page - 1) // per_page
    return [
        {"info": {"page": p + 1, "pages": total_pages, "results": count},
         "plugins": plugins[p * per_page:(p + 1) * per_page]}
        for p in range(total_pages)
    ]
