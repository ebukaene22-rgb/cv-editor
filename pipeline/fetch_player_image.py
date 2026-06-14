#!/usr/bin/env python3
"""Fetch a footballer's photo automatically from Wikimedia/Wikipedia.

Fully automated — no manual download. Used by the CI pipeline so episodes
render with a real player image without a human dropping files in.

Usage:
  python pipeline/fetch_player_image.py "Nico Williams" --out /tmp/raw.jpg
  python pipeline/fetch_player_image.py "Nico Williams" --out /tmp/raw.jpg \
      --query "Nico Williams (footballer, born 2002)"

Source: Wikipedia lead (infobox) image via the MediaWiki API. These are
freely / CC-licensed and safe to reuse. No API key required.

Resolution order:
  1. --query (explicit search hint, best for disambiguating common names)
  2. "<name> footballer" search
Exit 0 on success (image written to --out), 1 on failure.
"""
import argparse
import sys
from pathlib import Path

import requests

WIKI_API = "https://en.wikipedia.org/w/api.php"
# Wikimedia requires a descriptive User-Agent or it returns 403.
HEADERS = {
    "User-Agent": "InstinctIQFootball/1.0 (https://github.com/ebukaene22-rgb; ebukaene22@gmail.com)"
}


def search_title(query: str) -> str | None:
    """Return the best-matching Wikipedia article title for a query."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 1,
        "srnamespace": 0,
        "format": "json",
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    hits = r.json().get("query", {}).get("search", [])
    return hits[0]["title"] if hits else None


def get_lead_image_url(title: str) -> str | None:
    """Return the URL of the article's lead/infobox image (full resolution)."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "pageimages",
        "piprop": "original",
        "redirects": 1,
        "format": "json",
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    for page in pages.values():
        original = page.get("original")
        if original and "source" in original:
            return original["source"]
    return None


def download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    out.write_bytes(r.content)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="Player name, e.g. 'Nico Williams'")
    ap.add_argument("--out", required=True, help="Where to write the downloaded image")
    ap.add_argument("--query", help="Explicit search hint to disambiguate")
    args = ap.parse_args()

    out = Path(args.out)
    query = args.query or f"{args.name} footballer"

    try:
        title = search_title(query)
        if not title:
            print(f"  ✗ No Wikipedia article found for query: {query!r}")
            sys.exit(1)
        print(f"  Matched article: {title!r}")

        url = get_lead_image_url(title)
        if not url:
            print(f"  ✗ Article {title!r} has no lead image.")
            sys.exit(1)

        # Skip SVG (logos/crests, not photos) — they break remove.bg.
        if url.lower().endswith(".svg"):
            print(f"  ✗ Lead image is an SVG (not a photo): {url}")
            sys.exit(1)

        print(f"  Downloading: {url}")
        download(url, out)
        print(f"  ✓ Saved → {out} ({out.stat().st_size // 1024}KB)")
    except requests.HTTPError as e:
        print(f"  ✗ HTTP error: {e}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"  ✗ Network error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
