#!/usr/bin/env python3
"""Remove background from a player photo using the remove.bg API.

Usage:
  REMOVEBG_API_KEY=your_key python pipeline/removebg.py <input_image> <output_png>

Example:
  REMOVEBG_API_KEY=abc123 python pipeline/removebg.py \
    downloads/pedri_original.jpg assets/players/pedri.png

API key: free tier at remove.bg gives 50 images/month.
Output: transparent PNG cutout, written to <output_png>.

Called automatically by thumbnails/generate_thumbnail.py when --source-image is passed.
"""
import os
import sys
from pathlib import Path

import requests

API_URL = "https://api.remove.bg/v1.0/removebg"


def remove_background(source: Path, output: Path, api_key: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"  Sending to remove.bg: {source.name} ({source.stat().st_size // 1024}KB)")

    with source.open("rb") as f:
        response = requests.post(
            API_URL,
            files={"image_file": (source.name, f, "image/jpeg")},
            data={
                "size": "hd",       # hd = full resolution; use "regular" to save credits
                "type": "person",   # football players are always person type
                "crop": "false",    # keep full frame, don't crop to subject
            },
            headers={"X-Api-Key": api_key},
            timeout=60,
        )

    if response.status_code == 200:
        output.write_bytes(response.content)
        size_kb = len(response.content) // 1024
        print(f"  ✓ Cutout saved → {output} ({size_kb}KB)")
    else:
        # Parse error from API
        try:
            error = response.json().get("errors", [{}])[0].get("title", response.text)
        except Exception:
            error = response.text[:200]
        raise RuntimeError(f"remove.bg API error {response.status_code}: {error}")


def main():
    if len(sys.argv) != 3:
        print("usage: removebg.py <input_image> <output_png>")
        sys.exit(2)

    api_key = os.environ.get("REMOVEBG_API_KEY")
    if not api_key:
        print("Set REMOVEBG_API_KEY environment variable.")
        print("Get a free key (50 images/month) at: remove.bg/api")
        sys.exit(1)

    source = Path(sys.argv[1])
    output = Path(sys.argv[2])

    if not source.exists():
        print(f"Source image not found: {source}")
        sys.exit(1)

    try:
        remove_background(source, output, api_key)
    except RuntimeError as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
