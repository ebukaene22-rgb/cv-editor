"""D3 via public mirrors of the WordPress.org plugin directory.

Why this exists
---------------
`api.wordpress.org` is unreachable from some networks (this one blocks it at the
egress proxy). The directory's data is nonetheless public, and two projects
mirror it to GitHub, which is reachable. This source reads those mirrors so a
real run is possible without the official endpoint.

It is a fallback, not a replacement. `WordPressSource` remains the primary: it
talks to the documented API, which is authoritative and current to the minute.

Provenance, stated plainly
--------------------------
Two mirrors are joined on slug because neither carries every field:

| Field                              | From                        | Freshness      |
|------------------------------------|-----------------------------|----------------|
| name, active_installs, last_updated| rix4uni/wordpress-plugins   | ~6 hours       |
| num_ratings                        | rix4uni/wordpress-plugins   | ~6 hours       |
| rating, support_threads(+resolved) | jcmpagel/wordpress-dataset  | 2024 snapshot  |

The reach and abandonment terms of the neglect score are therefore current; the
quality and disengagement terms are from an older snapshot. Every candidate
carries `data_as_of` saying so, because a score built from mixed-vintage inputs
that does not admit it is worse than no score.

Neither mirror carries `author_profile`, so the author handle is unavailable and
the plugin page is used as the contact route instead. The playbook allows for
this — "contact details are typically on the plugin page or author profile" —
but it is one click further than the API would give you.

Records are mapped into the exact shape the official API returns and pushed
through `WordPressSource.to_candidate`, so this path exercises the real parsing
and scoring code rather than a parallel implementation of it.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from ..models import NeglectCandidate
from .base import SourceError
from .wordpress import PLUGIN_PAGE, WordPressSource

CURRENT_URL = "https://raw.githubusercontent.com/rix4uni/wordpress-plugins/main/plugins.json"
RATINGS_URL = ("https://raw.githubusercontent.com/jcmpagel/wordpress-dataset/main/"
               "Wordpress_active_plugins.csv")

CURRENT_LABEL = "rix4uni/wordpress-plugins (refreshed ~6-hourly)"
RATINGS_LABEL = "jcmpagel/wordpress-dataset (2024 snapshot)"

csv.field_size_limit(10 ** 7)


def _download(url: str, dest: Path, max_age_hours: float, label: str) -> Path:
    """Fetch once, then reuse. These are ~37MB each; re-pulling them on every
    run would be rude to a host that is doing us a favour."""
    if dest.exists() and (time.time() - dest.stat().st_mtime) < max_age_hours * 3600:
        age = (time.time() - dest.stat().st_mtime) / 3600
        print(f"  cached  {label}  ({dest.stat().st_size / 1e6:.0f}MB, {age:.1f}h old)")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  fetching {label} …", end=" ", flush=True)
    try:
        with requests.get(url, timeout=300, stream=True) as resp:
            resp.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            written = 0
            with tmp.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
                    written += len(chunk)
            tmp.replace(dest)
    except requests.RequestException as exc:
        raise SourceError(f"{label}: download failed: {exc}") from exc
    print(f"{written / 1e6:.0f}MB")
    return dest


class WordPressMirrorSource(WordPressSource):
    """Same parsing and scoring as `WordPressSource`, different transport."""

    name = "wordpress-mirror"

    def __init__(self, config, cache_dir: Path | None = None,
                 max_age_hours: float = 24.0) -> None:
        super().__init__(config)
        self.cache_dir = Path(cache_dir) if cache_dir else config.base_dir() / "data" / "mirror"
        self.max_age_hours = max_age_hours
        self.provenance: dict[str, str] = {}

    # ------------------------------------------------------------------ load
    def _load_ratings(self) -> dict[str, dict]:
        """slug -> {rating, support_threads, support_threads_resolved}.

        The CSV is denormalised one row per tag, so a plugin appears many times;
        the first row per slug is taken and the rest skipped.
        """
        path = _download(RATINGS_URL, self.cache_dir / "wp_ratings.csv",
                         self.max_age_hours * 30, RATINGS_LABEL)  # a 2024 snapshot does not go stale
        out: dict[str, dict] = {}
        with path.open(newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                slug = row.get("slug")
                if slug and slug not in out:
                    out[slug] = {
                        "rating": row.get("rating") or 0,
                        "support_threads": row.get("support_threads") or 0,
                        "support_threads_resolved": row.get("support_threads_resolved") or 0,
                    }
        return out

    def _load_current(self) -> list[dict]:
        path = _download(CURRENT_URL, self.cache_dir / "wp_current.json",
                         self.max_age_hours, CURRENT_LABEL)
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise SourceError(f"{CURRENT_LABEL}: not valid JSON ({exc})") from exc
        if not isinstance(data, list):
            raise SourceError(f"{CURRENT_LABEL}: expected a list of plugin objects")
        return data

    # --------------------------------------------------------------- neglect
    def fetch_neglect(self, limit: int | None = None, pages: int | None = None,
                      browse: str = "popular") -> list[NeglectCandidate]:
        print(f"{self.name}: reading public mirrors of the WordPress.org directory")
        ratings = self._load_ratings()
        current = self._load_current()

        band_installs = self.cfg["neglect.min_active_installs"]
        band_months = self.cfg["neglect.min_months_since_update"]
        band_rating = self.cfg["neglect.min_rating"]
        divisor = self.cfg.get("neglect.abandonment_divisor", 18)
        cap = self.cfg.get("neglect.max_abandonment_multiple", None)
        min_threads = self.cfg.get("neglect.min_support_threads", 0) or 0

        joined = 0
        found: list[NeglectCandidate] = []
        for raw in current:
            slug = raw.get("slug")
            if not slug:
                continue
            extra = ratings.get(slug)
            if extra is None:
                continue        # no rating or support data: the score cannot be built
            joined += 1

            # Rebuild the official API's response shape so the real mapper runs.
            api_shaped = {
                "name": raw.get("name", slug),
                "slug": slug,
                "active_installs": raw.get("active_installs") or 0,
                "last_updated": raw.get("last_updated", ""),
                "num_ratings": raw.get("num_ratings") or 0,
                "rating": extra["rating"],                       # 0-100, as the API returns
                "support_threads": extra["support_threads"],
                "support_threads_resolved": extra["support_threads_resolved"],
                "author": "",                                    # not in either mirror
                "author_profile": "",
                "short_description": raw.get("short_description", ""),
            }
            candidate = self.to_candidate(api_shaped, divisor, max_abandonment=cap,
                                          min_support_threads=min_threads)
            if candidate is None:
                continue
            if (candidate.active_installs >= band_installs
                    and candidate.months_since_update >= band_months
                    and candidate.rating >= band_rating):
                found.append(candidate)

        found.sort(key=lambda n: n.neglect_score, reverse=True)
        self.provenance = {
            "current": CURRENT_LABEL,
            "ratings": RATINGS_LABEL,
            "joined_on": "slug",
            "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        print(f"{self.name}: {len(current):,} plugins current · {len(ratings):,} with rating "
              f"data · {joined:,} joined on slug")
        print(f"{self.name}: {len(found):,} inside the neglect band "
              f"(>= {band_installs:,} installs, >= {band_months}mo stale, >= {band_rating}★)")
        print(f"{self.name}: NOTE rating and support figures are from the "
              f"{RATINGS_LABEL}; installs and last-updated are current.")
        print(f"{self.name}: NOTE neither mirror carries author_profile — the plugin "
              f"page is the contact route.")
        return found[:limit] if limit else found

    @classmethod
    def to_candidate(cls, raw: dict, divisor: float = 18.0, now=None,
                     max_abandonment: float | None = None,
                     min_support_threads: int = 0) -> NeglectCandidate | None:
        candidate = super().to_candidate(raw, divisor, now, max_abandonment,
                                         min_support_threads)
        if candidate is not None and not candidate.author_profile:
            # The plugin page carries the author link and the support forum.
            candidate.author_profile = PLUGIN_PAGE.format(slug=candidate.slug)
        return candidate
