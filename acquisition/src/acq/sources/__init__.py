"""Ingestion sources. Every source sits behind `Source` so it can be swapped
when an undocumented endpoint breaks — which it will."""
from .base import Source, SourceError

__all__ = ["Source", "SourceError"]
