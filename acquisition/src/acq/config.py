"""D1 — config loader. Every threshold in the system resolves through here."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = REPO / "acquisition" / "config.yaml"


class Config:
    """Dotted-path read-only view over config.yaml.

    Missing keys raise rather than defaulting silently — a threshold that
    quietly becomes None would turn a hard reject into a pass.
    """

    def __init__(self, data: dict[str, Any], source: Path | None = None) -> None:
        self._data = data
        self.source = source

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        p = Path(path) if path else DEFAULT_CONFIG
        if not p.exists():
            raise FileNotFoundError(f"config not found: {p}")
        with p.open() as fh:
            return cls(yaml.safe_load(fh) or {}, source=p)

    def get(self, dotted: str, default: Any = ...) -> Any:
        node: Any = self._data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                if default is ...:
                    raise KeyError(f"missing config key: {dotted} (in {self.source})")
                return default
            node = node[part]
        return node

    def __getitem__(self, dotted: str) -> Any:
        return self.get(dotted)

    def base_dir(self) -> Path:
        """Directory that relative `paths.*` entries resolve against."""
        return self.source.parent if self.source else Path.cwd()

    def path(self, dotted: str) -> Path:
        p = Path(self.get(dotted))
        return p if p.is_absolute() else self.base_dir() / p

    def excluded_categories(self) -> set[str]:
        return {c.lower() for c in self.get("exclusions.categories", [])}

    def excluded_revenue_models(self) -> set[str]:
        return {c.lower() for c in self.get("exclusions.revenue_models", [])}

    def excluded_platforms(self) -> set[str]:
        return {c.lower() for c in self.get("exclusions.platforms", [])}
