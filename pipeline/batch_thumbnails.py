#!/usr/bin/env python3
"""Batch-generate A/B thumbnails for every config in thumbnails/variants/.

Usage:
  REMOVEBG_API_KEY=your_key python pipeline/batch_thumbnails.py

  # Or with source images (matched by player_name in each config):
  REMOVEBG_API_KEY=your_key python pipeline/batch_thumbnails.py \\
    --source-dir downloads/player_photos/

If --source-dir is provided, each config's player_name (lowercased, spaces→_)
is matched against files like downloads/player_photos/pedri.jpg.
Unmatched configs fall back to existing assets/players/ PNGs or the placeholder.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VARIANTS_DIR = REPO / "thumbnails" / "variants"
GENERATOR = REPO / "thumbnails" / "generate_thumbnail.py"


def find_source_image(player_name: str, source_dir: Path) -> Path | None:
    slug = player_name.lower().replace(" ", "_")
    for ext in ("jpg", "jpeg", "png", "webp"):
        candidate = source_dir / f"{slug}.{ext}"
        if candidate.exists():
            return candidate
    return None


def main():
    source_dir: Path | None = None
    if "--source-dir" in sys.argv:
        idx = sys.argv.index("--source-dir")
        source_dir = Path(sys.argv[idx + 1])
        if not source_dir.is_dir():
            print(f"Source dir not found: {source_dir}")
            sys.exit(1)

    configs = sorted(VARIANTS_DIR.glob("*.yaml"))
    if not configs:
        print(f"No YAML configs found in {VARIANTS_DIR}")
        sys.exit(1)

    print(f"Processing {len(configs)} thumbnail config(s)...\n")
    results = {}

    for config_path in configs:
        import yaml
        cfg = yaml.safe_load(config_path.read_text())
        player_name = cfg.get("player_name", "")

        cmd = [sys.executable, str(GENERATOR), str(config_path)]

        if source_dir:
            src = find_source_image(player_name, source_dir)
            if src:
                cmd += ["--source-image", str(src)]
                print(f"▶ {config_path.stem} + {src.name}")
            else:
                print(f"▶ {config_path.stem} (no source image found — using existing asset or placeholder)")
        else:
            print(f"▶ {config_path.stem}")

        result = subprocess.run(cmd, cwd=REPO)
        results[config_path.stem] = result.returncode == 0

    print("\n── Batch summary ──")
    for name, ok in results.items():
        status = "✓" if ok else "✗"
        print(f"  {status}  {name}")

    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\n{len(failed)} failed. Check output above.")
        sys.exit(1)
    else:
        print(f"\nAll {len(results)} thumbnails rendered → thumbnails/output/")


if __name__ == "__main__":
    main()
