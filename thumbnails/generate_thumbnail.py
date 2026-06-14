#!/usr/bin/env python3
"""Generate A/B thumbnail pair from a variant YAML config.

Usage:
  # With a pre-existing transparent PNG cutout:
  python thumbnails/generate_thumbnail.py thumbnails/variants/pedri-fraud-watch.yaml

  # With a raw player photo — remove.bg removes the background automatically:
  REMOVEBG_API_KEY=your_key python thumbnails/generate_thumbnail.py \\
    thumbnails/variants/pedri-fraud-watch.yaml \\
    --source-image downloads/pedri_photo.jpg

Outputs:
  thumbnails/output/<stem>_with_cutout.png   — player image visible
  thumbnails/output/<stem>_no_cutout.png     — text-only layout (A/B test)

Player image resolution:
  1. --source-image flag (auto-removes bg via remove.bg API)
  2. player_image_path in config (must already be a transparent PNG)
  3. Placeholder SVG silhouette (fallback, always works)
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO / "remotion"
PUBLIC_PLAYERS = REMOTION_DIR / "public" / "players"
OUTPUT_DIR = REPO / "thumbnails" / "output"
PLACEHOLDER_KEY = "players/placeholder.svg"

VARIANT_DEFAULTS = {
    "fraud_watch":    {"verdict_label": "FRAUD WATCH?",   "verdict_color": "red"},
    "system_product": {"verdict_label": "SYSTEM PRODUCT", "verdict_color": "red",  "collapse_risk": "HIGH"},
    "outlier":        {"verdict_label": "OUTLIER",         "verdict_color": "green"},
    "transfer_trap":  {"verdict_label": "TRANSFER TRAP",  "verdict_color": "red"},
}

REQUIRED = ["player_name", "variant", "instinct", "iq", "gravity", "transferability"]
VALID_VARIANTS = list(VARIANT_DEFAULTS.keys())


# ── Validation ────────────────────────────────────────────────────────────────

def validate(cfg: dict) -> list[str]:
    errors = []
    for f in REQUIRED:
        if f not in cfg:
            errors.append(f"missing required field: '{f}'")
    if cfg.get("variant") not in VALID_VARIANTS:
        errors.append(f"variant must be one of {VALID_VARIANTS}")
    for score in ["instinct", "iq", "gravity"]:
        v = cfg.get(score)
        if v is not None and not (1 <= int(v) <= 10):
            errors.append(f"'{score}' must be 1-10, got {v}")
    t = cfg.get("transferability")
    if t is not None and not (0 <= int(t) <= 100):
        errors.append(f"'transferability' must be 0-100, got {t}")
    return errors


# ── Image handling ────────────────────────────────────────────────────────────

def auto_remove_bg(source: Path, output: Path) -> bool:
    """Call pipeline/removebg.py to strip background. Returns True on success."""
    api_key = os.environ.get("REMOVEBG_API_KEY")
    if not api_key:
        print("  ⚠ REMOVEBG_API_KEY not set — skipping background removal.")
        print("    Get a free key at remove.bg/api")
        return False

    removebg_script = REPO / "pipeline" / "removebg.py"
    result = subprocess.run(
        [sys.executable, str(removebg_script), str(source), str(output)],
        cwd=REPO,
    )
    return result.returncode == 0


def resolve_player_image(cfg: dict, source_image: Path | None) -> Path | None:
    """
    Returns path to a ready-to-use transparent PNG, or None (triggers placeholder).

    Priority:
      1. --source-image CLI flag → run remove.bg → save to assets/players/
      2. player_image_path in config → use as-is if it exists
      3. None → placeholder
    """
    player_slug = cfg["player_name"].lower().replace(" ", "_")
    cutout_dest = REPO / "assets" / "players" / f"{player_slug}.png"

    if source_image:
        if not source_image.exists():
            print(f"  ✗ Source image not found: {source_image}")
            return None
        print(f"\n── Background removal: {source_image.name} ──")
        cutout_dest.parent.mkdir(parents=True, exist_ok=True)
        if auto_remove_bg(source_image, cutout_dest):
            return cutout_dest
        else:
            print("  Falling back to placeholder.")
            return None

    # No source image — check config path
    config_path = cfg.get("player_image_path")
    if config_path:
        p = REPO / config_path
        if p.exists():
            return p
        print(f"  ⚠ player_image_path not found: {p}")
        print(f"    Run with --source-image to auto-generate the cutout.")

    return None


def stage_image(image_path: Path) -> str:
    """Copy image to remotion/public/players/ and return the public key."""
    PUBLIC_PLAYERS.mkdir(parents=True, exist_ok=True)
    dest = PUBLIC_PLAYERS / image_path.name
    shutil.copy2(image_path, dest)
    print(f"  Staged → remotion/public/players/{image_path.name}")
    return f"players/{image_path.name}"


# ── Props builder ─────────────────────────────────────────────────────────────

def build_props(cfg: dict, player_image_key: str | None, show_image: bool) -> dict:
    variant = cfg["variant"]
    defaults = VARIANT_DEFAULTS[variant]

    props: dict = {
        "player_name": cfg["player_name"].upper(),
        "variant": variant,
        "scores": {
            "instinct": int(cfg["instinct"]),
            "iq":       int(cfg["iq"]),
            "gravity":  int(cfg["gravity"]),
        },
        "transferability": int(cfg["transferability"]),
        "verdict_label": cfg.get("verdict_label", defaults["verdict_label"]),
        "verdict_color": cfg.get("verdict_color", defaults["verdict_color"]),
    }

    if variant == "transfer_trap" and "transfer_club" in cfg:
        props["transfer_club"] = cfg["transfer_club"].upper()
    if variant == "system_product":
        props["collapse_risk"] = cfg.get("collapse_risk", defaults.get("collapse_risk", "HIGH"))
    if "subtitle" in cfg:
        props["subtitle"] = cfg["subtitle"]

    position = cfg.get("player_image_position", "right")
    props["player_image_position"] = position
    props["player_image_scale"]    = float(cfg.get("player_image_scale", 1.0))
    props["player_image_rotation"] = float(cfg.get("player_image_rotation", 0))

    if show_image and player_image_key:
        # Real cutout — full opacity
        props["player_image_key"]     = player_image_key
        props["player_image_opacity"] = float(cfg.get("player_image_opacity", 1.0))
    elif show_image:
        # No cutout available — ghost placeholder so layout is still visible
        props["player_image_key"]     = PLACEHOLDER_KEY
        props["player_image_opacity"] = 0.12
    else:
        # No-cutout A/B variant — completely hide image
        props["player_image_key"]     = PLACEHOLDER_KEY
        props["player_image_opacity"] = 0.0

    return props


# ── Renderer ──────────────────────────────────────────────────────────────────

def render(props: dict, output_path: Path, label: str) -> bool:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "npx", "remotion", "still",
        "src/index.ts",
        "Thumbnail",
        str(output_path),
        f"--props={json.dumps(props)}",
        "--frame=0",
        "--log=error",
    ]
    print(f"\n  Rendering [{label}]...")
    result = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True)
    if result.returncode == 0:
        size_kb = output_path.stat().st_size // 1024
        print(f"  ✓ {output_path.name} ({size_kb}KB)")
        return True
    else:
        print(f"  ✗ FAILED: {label}")
        if result.stderr:
            print(result.stderr[-400:])
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("usage: generate_thumbnail.py <variant.yaml> [--source-image <photo.jpg>]")
        sys.exit(2)

    config_path = Path(sys.argv[1])
    cfg = yaml.safe_load(config_path.read_text())

    errors = validate(cfg)
    if errors:
        print("CONFIG ERROR")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    source_image: Path | None = None
    if "--source-image" in sys.argv:
        idx = sys.argv.index("--source-image")
        source_image = Path(sys.argv[idx + 1])

    stem = config_path.stem
    print(f"\n══ Thumbnail generator: {stem} ══")

    # Resolve player image → optionally strip background
    cutout_path = resolve_player_image(cfg, source_image)
    player_key  = stage_image(cutout_path) if cutout_path else None

    results = []

    # A: with cutout (or ghost placeholder if no image)
    props_with = build_props(cfg, player_key, show_image=True)
    out_with   = OUTPUT_DIR / f"{stem}_with_cutout.png"
    results.append(render(props_with, out_with, "with_cutout"))

    # B: text-only
    props_without = build_props(cfg, player_key, show_image=False)
    out_without   = OUTPUT_DIR / f"{stem}_no_cutout.png"
    results.append(render(props_without, out_without, "no_cutout"))

    if all(results):
        had_real = "real cutout" if (cutout_path and cutout_path.name != "placeholder.svg") else "placeholder"
        print(f"""
╔══════════════════════════════════════════════════════╗
║  A/B THUMBNAILS READY  ({had_real:<26}) ║
║                                                      ║
║  {str(out_with.name):<50} ║
║  {str(out_without.name):<50} ║
╚══════════════════════════════════════════════════════╝
""")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
