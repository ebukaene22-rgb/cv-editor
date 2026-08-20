"""Source interface and shared HTTP behaviour.

§10 of the brief: Flippa and TrustMRR are reached through undocumented
endpoints or third-party scrapers. Expect breakage. Abstract every source
behind an interface and **fail loudly, not silently** — a source that returns
an empty list on a 403 looks exactly like a quiet week, and a quiet week is
the one thing a weekly-cadence pipeline must never fake.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests

from ..config import Config
from ..models import Listing


class SourceError(RuntimeError):
    """Raised when a source cannot be trusted to have returned a full result."""


class Source(ABC):
    name = "source"

    def __init__(self, config: Config, session: requests.Session | None = None) -> None:
        self.cfg = config
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", config["run.user_agent"])
        self.delay = float(config.get("run.request_delay_seconds", 1.5))
        self._last_request = 0.0

    @abstractmethod
    def fetch(self, limit: int | None = None) -> list[Listing]:
        """Return listings. Raise SourceError rather than returning [] on failure."""

    # ------------------------------------------------------------------ http
    def _throttle(self) -> None:
        """Back off politely. This is a weekly-cadence system; there is no
        reason to hammer anything."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.monotonic()

    def get_json(self, url: str, params: dict | None = None, *, retries: int = 3) -> dict | list:
        last: Exception | None = None
        for attempt in range(retries):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=30)
                if resp.status_code == 429:
                    wait = float(resp.headers.get("Retry-After", 2 ** (attempt + 2)))
                    print(f"WARN {self.name}: rate limited, sleeping {wait:.0f}s")
                    time.sleep(wait)
                    last = SourceError(f"{self.name}: 429 rate limited")
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                last = exc
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        raise SourceError(f"{self.name}: GET {url} failed after {retries} attempts: {last}")

    @staticmethod
    def _num(value) -> float | None:
        """Coerce a marketplace's idea of a number. Returns None rather than 0
        for anything unparseable — a 0 would pass a `< threshold` check."""
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "").replace("$", "").replace("£", "")
        if not text or text.lower() in {"n/a", "na", "none", "-", "—"}:
            return None
        multiplier = 1.0
        if text[-1].lower() in {"k", "m"}:
            multiplier = 1_000.0 if text[-1].lower() == "k" else 1_000_000.0
            text = text[:-1]
        try:
            return float(text) * multiplier
        except ValueError:
            return None
