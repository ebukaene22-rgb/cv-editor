"""Persistence: dedupe on source + listing ID, keep first-seen, mark new arrivals.

Stage 1 of the playbook: "daily pull, dedupe on listing ID, append to a store,
flag new listings since last run." The store is a plain JSON file — the whole
system is on-demand scripts with no hosted infrastructure, and a file that a
human can open and read is worth more here than a database.

What is deliberately *not* stored: anything of the seller's beyond the candidate
record itself. No processor exports, no statements, no customer data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import Candidate, NeglectCandidate


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class Store:
    """Keyed JSON store. `upsert` returns the keys seen for the first time."""

    def __init__(self, path: Path, factory=Candidate) -> None:
        self.path = Path(path)
        self.factory = factory
        self.records: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            blob = json.loads(self.path.read_text())
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"store at {self.path} is corrupt ({exc}). Refusing to overwrite it — "
                f"move it aside if you intend to start fresh."
            ) from exc
        self.records = blob.get("records", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated": today(), "count": len(self.records), "records": self.records}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(self.path)   # atomic: a killed run never truncates the store

    # ------------------------------------------------------------------ write
    def upsert(self, items: Iterable) -> list[str]:
        """Merge a run's results in. Preserves `first_seen` and the human-owned
        `status` field — a re-pull must never reset a candidate you have already
        moved to `contacted`."""
        new_keys: list[str] = []
        stamp = today()
        for item in items:
            key = item.key if isinstance(item.key, str) else item.key()
            record = item.to_dict()
            existing = self.records.get(key)
            if existing is None:
                record["first_seen"] = record.get("first_seen") or stamp
                new_keys.append(key)
            else:
                record["first_seen"] = existing.get("first_seen", stamp)
                if existing.get("status") and existing["status"] != "sourced":
                    record["status"] = existing["status"]
            record["last_seen"] = stamp
            self.records[key] = record
        return new_keys

    # ------------------------------------------------------------------- read
    def all(self) -> list:
        return [self.factory.from_dict(r) for r in self.records.values()]

    def get(self, key: str):
        raw = self.records.get(key)
        return self.factory.from_dict(raw) if raw else None

    def new_since(self, date: str) -> list:
        return [self.factory.from_dict(r) for r in self.records.values()
                if r.get("first_seen", "") >= date]

    def set_status(self, key: str, status: str) -> bool:
        if key not in self.records:
            return False
        self.records[key] = {**self.records[key], "status": status}
        return True

    def __len__(self) -> int:
        return len(self.records)


def candidate_store(config) -> Store:
    return Store(config.path("paths.store"), Candidate)


def neglect_store(config) -> Store:
    return Store(config.path("paths.neglect_store"), NeglectCandidate)
