"""Currency normalisation — ECB daily reference rates, converted once at ingestion.

Listings are mostly USD; the buyer thinks in GBP and operates in AED. Ratios
(price/revenue, payback) are currency-invariant, but the budget band and the
ARPU floor are absolute — so a wrong rate silently changes which deals pass.
The rate used is recorded on every candidate.
"""
from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

ECB_DAILY = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_NS = {"ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}

# Last-resort rates (EUR base) if the ECB feed is unreachable. Used only with a
# loud warning: a stale rate is a wrong budget band, not a rounding error.
FALLBACK_EUR = {"USD": 1.08, "GBP": 0.855, "AED": 3.96, "EUR": 1.0}


class FxError(RuntimeError):
    pass


class FxRates:
    """EUR-based rate table with a disk cache."""

    def __init__(self, rates: dict[str, float], fetched_at: float, stale: bool = False) -> None:
        self.rates = {k.upper(): float(v) for k, v in rates.items()}
        self.rates.setdefault("EUR", 1.0)
        self.fetched_at = fetched_at
        self.stale = stale

    @classmethod
    def load(cls, cache_path: Path, max_age_hours: float = 24.0, offline: bool = False) -> "FxRates":
        cached = cls._read_cache(cache_path)
        if cached and (time.time() - cached.fetched_at) < max_age_hours * 3600:
            return cached
        if offline:
            return cached or cls(FALLBACK_EUR, 0.0, stale=True)
        try:
            rates = cls._fetch()
            fresh = cls(rates, time.time())
            cls._write_cache(cache_path, fresh)
            return fresh
        except Exception as exc:  # network, parse, anything
            if cached:
                print(f"WARN fx: ECB fetch failed ({exc}); using cache from "
                      f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(cached.fetched_at))}")
                cached.stale = True
                return cached
            print(f"WARN fx: ECB fetch failed ({exc}) and no cache; using FALLBACK rates. "
                  f"Budget-band results are approximate.")
            return cls(FALLBACK_EUR, 0.0, stale=True)

    @staticmethod
    def _fetch(timeout: int = 20) -> dict[str, float]:
        resp = requests.get(ECB_DAILY, timeout=timeout)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        rates = {"EUR": 1.0}
        for cube in root.iterfind(".//ecb:Cube[@currency]", _NS):
            rates[cube.attrib["currency"]] = float(cube.attrib["rate"])
        if "GBP" not in rates:
            raise FxError("ECB response contained no GBP rate")
        return rates

    @staticmethod
    def _read_cache(path: Path) -> "FxRates | None":
        if not path.exists():
            return None
        try:
            blob = json.loads(path.read_text())
            return FxRates(blob["rates"], float(blob["fetched_at"]))
        except Exception:
            return None

    @staticmethod
    def _write_cache(path: Path, rates: "FxRates") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"rates": rates.rates, "fetched_at": rates.fetched_at}, indent=2))

    def rate(self, src: str, dst: str = "GBP") -> float:
        src, dst = src.upper(), dst.upper()
        if src == dst:
            return 1.0
        for cur in (src, dst):
            if cur not in self.rates:
                raise FxError(f"no ECB rate for {cur}")
        return self.rates[dst] / self.rates[src]

    def convert(self, amount: float | None, src: str, dst: str = "GBP") -> float | None:
        if amount is None:
            return None
        return amount * self.rate(src, dst)


class FixedRates(FxRates):
    """Pinned rates — used by the regression tests and the `--fx-rate` override,
    so an acceptance run never depends on what the ECB published today."""

    def __init__(self, to_gbp: dict[str, float]) -> None:
        # store as EUR-base equivalents so `rate()` maths is unchanged
        gbp_per_eur = 1.0
        rates = {"GBP": gbp_per_eur}
        for cur, r in to_gbp.items():
            rates[cur.upper()] = gbp_per_eur / r if r else 0.0
        super().__init__(rates, time.time())
