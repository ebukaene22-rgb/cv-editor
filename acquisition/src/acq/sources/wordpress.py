"""D3 — off-market ingestion from WordPress.org. The priority build.

This is the only fully sanctioned source in the system: the plugin API is
public, documented, free and needs no auth. It is also the only source whose
owners are not selling, which is the entire advantage — no competing bidders
and no pitch copy to see through.

Query strategy
--------------
`query_plugins` cannot filter by staleness, and `browse=updated` sorts the
wrong way (most-recently updated first). So the run pages through
`browse=popular` — which orders by install base, exactly the axis the target
band cares about — and applies the neglect band client-side. Scanning
`max_pages × 100` popular plugins reaches the long tail of 1k–100k-install
products, which is where an absent owner is both likely and affordable.

Two API details that bite
-------------------------
* `rating` is returned on a **0–100** scale, not 0–5. The brief's formula uses
  `rating / 5`, so the value is converted on ingestion and stored as 0–5.
* `author` arrives as an HTML anchor, not a name. It is unwrapped here, and the
  `author_profile` URL is kept — that URL is the contact route for Stage 4.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from ..models import Listing, NeglectCandidate
from .base import Source, SourceError

API = "https://api.wordpress.org/plugins/info/1.2/"
PLUGIN_PAGE = "https://wordpress.org/plugins/{slug}/"

_TAG = re.compile(r"<[^>]+>")
_LAST_UPDATED_FORMATS = ("%Y-%m-%d %I:%M%p %Z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")

# Support-thread resolution is the disengagement signal. A plugin with no
# threads at all gives no signal either way, so it takes a neutral 0.5 rather
# than 0.0 — otherwise silence would rank as maximum neglect and flood the top
# of the list with quiet, well-behaved plugins.
NO_THREADS_RESOLUTION = 0.5


def _strip_html(value: str) -> str:
    return _TAG.sub("", value or "").strip()


def _parse_last_updated(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in _LAST_UPDATED_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # "2024-03-11 4:07pm GMT" with a lowercase meridiem
    try:
        return datetime.strptime(text.upper().replace("GMT", "").strip(),
                                 "%Y-%m-%d %I:%M%p").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def months_since(when: datetime | None, now: datetime | None = None) -> float | None:
    if when is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - when).days / 30.44)


def neglect_score(active_installs: int, months_since_update: float, rating_5: float,
                  support_resolution_rate: float, abandonment_divisor: float = 18.0) -> float:
    """The brief's formula, guarded at every term.

        log10(installs) * (months_since_update / 18) * (rating / 5) * (1 - resolution)

    Reach × abandonment × quality retained × owner disengagement. Ranked, never
    filtered on — a hard cutoff loses the good ones sitting just outside it.
    """
    if active_installs <= 0:
        return 0.0
    reach = math.log10(max(active_installs, 10))
    abandonment = max(0.0, months_since_update) / abandonment_divisor
    quality = max(0.0, min(1.0, rating_5 / 5.0))
    disengagement = max(0.0, 1.0 - max(0.0, min(1.0, support_resolution_rate)))
    return round(reach * abandonment * quality * disengagement, 4)


class WordPressSource(Source):
    name = "wordpress"

    def fetch(self, limit: int | None = None) -> list[Listing]:
        """Present the neglect list through the common Source interface.

        These are not listings — nobody is selling — so the monetary fields stay
        empty and the rule engine is not asked to price them. The ranked neglect
        output is what this source is for; `fetch_neglect` is the real entry point.
        """
        return [
            Listing(
                source=self.name,
                source_id=n.slug,
                url=n.url,
                name=n.name,
                category="wordpress-plugin",
                revenue_model="",
                listing_text=f"{n.active_installs:,} active installs, last updated "
                             f"{n.last_updated}. Author: {n.author}.",
                raw=n.to_dict(),
            )
            for n in self.fetch_neglect(limit=limit)
        ]

    # ---------------------------------------------------------------- neglect
    def fetch_neglect(self, limit: int | None = None, pages: int | None = None,
                      browse: str = "popular") -> list[NeglectCandidate]:
        band_installs = self.cfg["neglect.min_active_installs"]
        band_months = self.cfg["neglect.min_months_since_update"]
        band_rating = self.cfg["neglect.min_rating"]
        max_pages = pages or self.cfg["neglect.max_pages"]
        divisor = self.cfg.get("neglect.abandonment_divisor", 18)

        found: list[NeglectCandidate] = []
        scanned = 0
        for page in range(1, max_pages + 1):
            payload = self.get_json(API, self._params(page, browse))
            plugins = payload.get("plugins") if isinstance(payload, dict) else None
            if plugins is None:
                raise SourceError(f"{self.name}: unexpected response shape on page {page}")
            if not plugins:
                break
            scanned += len(plugins)

            for raw in plugins:
                candidate = self.to_candidate(raw, divisor)
                if candidate is None:
                    continue
                if (candidate.active_installs >= band_installs
                        and candidate.months_since_update >= band_months
                        and candidate.rating >= band_rating):
                    found.append(candidate)

            info = payload.get("info") or {}
            if info.get("pages") and page >= int(info["pages"]):
                break

        found.sort(key=lambda n: n.neglect_score, reverse=True)
        print(f"{self.name}: scanned {scanned} plugins over {min(page, max_pages)} pages, "
              f"{len(found)} inside the neglect band "
              f"(>= {band_installs:,} installs, >= {band_months}mo stale, >= {band_rating}★)")
        return found[:limit] if limit else found

    def _params(self, page: int, browse: str) -> dict:
        per_page = 100
        return {
            "action": "query_plugins",
            "request[browse]": browse,
            "request[per_page]": per_page,
            "request[page]": page,
            "request[fields][active_installs]": 1,
            "request[fields][last_updated]": 1,
            "request[fields][ratings]": 1,
            "request[fields][support_threads]": 1,
            "request[fields][short_description]": 1,
            "request[fields][sections]": 0,
            "request[fields][description]": 0,
            "request[fields][screenshots]": 0,
        }

    @classmethod
    def to_candidate(cls, raw: dict, divisor: float = 18.0,
                     now: datetime | None = None) -> NeglectCandidate | None:
        slug = raw.get("slug")
        if not slug:
            return None

        updated = _parse_last_updated(raw.get("last_updated", ""))
        stale_months = months_since(updated, now)
        if stale_months is None:
            return None

        installs = int(raw.get("active_installs") or 0)

        # 0-100 on the wire; the formula wants 0-5.
        raw_rating = float(raw.get("rating") or 0.0)
        rating_5 = raw_rating / 20.0 if raw_rating > 5 else raw_rating

        threads = int(raw.get("support_threads") or 0)
        resolved = int(raw.get("support_threads_resolved") or 0)
        resolution = (resolved / threads) if threads else NO_THREADS_RESOLUTION

        today = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        return NeglectCandidate(
            slug=slug,
            name=_strip_html(raw.get("name", slug)),
            url=PLUGIN_PAGE.format(slug=slug),
            author=_strip_html(raw.get("author", "")),
            author_profile=raw.get("author_profile", "") or "",
            active_installs=installs,
            last_updated=raw.get("last_updated", ""),
            months_since_update=round(stale_months, 1),
            rating=round(rating_5, 2),
            num_ratings=int(raw.get("num_ratings") or 0),
            support_threads=threads,
            support_threads_resolved=resolved,
            support_resolution_rate=round(resolution, 3),
            neglect_score=neglect_score(installs, stale_months, rating_5, resolution, divisor),
            first_seen=today,
            last_seen=today,
        )
