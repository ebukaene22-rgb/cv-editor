#!/usr/bin/env python3
"""Generate A/B thumbnail pair from a variant YAML config.

Usage:
  python thumbnails/generate_thumbnail.py thumbnails/variants/pedri-fraud-watch.yaml

Outputs per episode:
  thumbnails/output/<stem>_with_cutout.png
  thumbnails/output/<stem>_no_cutout.png

Player images:
  - Place transparent PNG cutouts in assets/players/<name>.png
  - If the file doesn't exist, the placeholder silhouette is used automatically.
  - Images are copied to remotion/public/players/ before rendering (Remotion needs them there).
"""
import json
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


def stage_player_image(image_path_str: str | None) -> str | None:
    """Copy image to remotion/public/players/ and return the public key, or None."""
    if not image_path_str:
        return None

    src = REPO / image_path_str
    if not src.exists():
        print(f"  ⚠ Player image not found: {src}")
        print(f"    Falling back to placeholder silhouette.")
        return None

    PUBLIC_PLAYERS.mkdir(parents=True, exist_ok=True)
    dest = PUBLIC_PLAYERS / src.name
    shutil.copy2(src, dest)
    print(f"  Staged player image → remotion/public/players/{src.name}")
    return f"players/{src.name}"


def build_props(cfg: dict, player_image_key: str | None) -> dict:
    variant = cfg["variant"]
    defaults = VARIANT_DEFAULTS[variant]

    props: dict = {
        "player_name": cfg["player_name"].upper(),
        "variant": variant,
        "scores": {
            "instinct": int(cfg["instinct"]),
            "iq": int(cfg["iq"]),
            "gravity": int(cfg["gravity"]),
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

    if player_image_key:
        props["player_image_key"] = player_image_key
        props["player_image_position"] = cfg.get("player_image_position", "right")
        props["player_image_scale"] = float(cfg.get("player_image_scale", 1.0))
        props["player_image_opacity"] = float(cfg.get("player_image_opacity", 1.0))
        props["player_image_rotation"] = float(cfg.get("player_image_rotation", 0))
    else:
        # No cutout: use placeholder with lower opacity so it reads as a ghost silhouette
        props["player_image_key"] = PLACEHOLDER_KEY
        props["player_image_position"] = cfg.get("player_image_position", "right")
        props["player_image_scale"] = 1.0
        props["player_image_opacity"] = 0.12
        props["player_image_rotation"] = 0

    return props


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
    print(f"\n  Rendering {label}...")
    result = subprocess.run(cmd, cwd=REMOTION_DIR)
    if result.returncode == 0:
        print(f"  ✓ {output_path.name}")
        return True
    else:
        print(f"  ✗ FAILED: {label}")
        return False


def main():
    if len(sys.argv) < 2:
        print("usage: generate_thumbnail.py <variant.yaml>")
        sys.exit(2)

    config_path = Path(sys.argv[1])
    cfg = yaml.safe_load(config_path.read_text())

    errors = validate(cfg)
    if errors:
        print("CONFIG ERROR")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    stem = config_path.stem
    print(f"\n── Thumbnail generator: {stem} ──")

    # Stage the real player image (copies to remotion/public/)
    player_key = stage_player_image(cfg.get("player_image_path"))

    # A/B pair: with cutout and without
    results = []

    # Version A: with real cutout (or placeholder at low opacity if image missing)
    props_with = build_props(cfg, player_key)
    out_with = OUTPUT_DIR / f"{stem}_with_cutout.png"
    results.append(render(props_with, out_with, "with_cutout"))

    # Version B: text-only, no image layer
    props_without = build_props(cfg, None)
    props_without["player_image_opacity"] = 0.0  # fully hidden
    out_without = OUTPUT_DIR / f"{stem}_no_cutout.png"
    results.append(render(props_without, out_without, "no_cutout"))

    if all(results):
        print(f"""
╔═══════════════════════════════════════════════════╗
║  A/B THUMBNAILS READY                            ║
║  {str(out_with.name):<47} ║
║  {str(out_without.name):<47} ║
╚═══════════════════════════════════════════════════╝
""")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
