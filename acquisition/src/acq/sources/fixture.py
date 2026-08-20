"""Replay recorded API responses instead of calling the network.

Used by the offline test suite, and by `--fixture` on the CLI so a run can be
rehearsed (or re-run against yesterday's data) without touching a live endpoint.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class _Response:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.status_code = 200
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class FixtureSession:
    """Quacks like `requests.Session` for GET-with-params.

    `pages` is a list of response payloads served in request order; once
    exhausted it serves an empty result so paging loops terminate.
    """

    def __init__(self, pages: list[Any], empty: Any | None = None) -> None:
        self.pages = list(pages)
        self.empty = empty if empty is not None else {"info": {"page": 0, "pages": 0, "results": 0},
                                                      "plugins": []}
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict | None = None, timeout: int | None = None) -> _Response:
        self.calls.append((url, dict(params or {})))
        payload = self.pages.pop(0) if self.pages else self.empty
        return _Response(payload)

    @classmethod
    def from_file(cls, path: str | Path) -> "FixtureSession":
        blob = json.loads(Path(path).read_text())
        return cls(blob if isinstance(blob, list) else [blob])
