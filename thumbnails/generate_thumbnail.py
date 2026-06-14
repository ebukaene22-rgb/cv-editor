#!/usr/bin/env python3
"""Generate a thumbnail for an episode from a variant YAML config.

Usage:
  python thumbnails/generate_thumbnail.py thumbnails/variants/fraud-watch.yaml
  python thumbnails/generate_thumbnail.py thumbnails/variants/fraud-watch.yaml --output episodes/2026-06-14-nico-williams/thumbnail.mp4

Reads the YAML config, validates it, writes thumbnail.json, then renders
via Remotion ThumbnailComposition → thumbnail.png (single frame at t=0).

Config fields:
  player_name       str   UPPERCASE player name
  variant           str   fraud_watch | system_product | outlier | transfer_trap
  instinct          int   1-10
  iq                int   1-10
  gravity           int   1-10
  transferability   int   0-100
  verdict_label     str   override stamp text (optional)
  verdict_color     str   red | green (optional, variant sets default)
  transfer_club     str   for transfer_trap variant (optional)
  collapse_risk     str   for system_product variant (optional, default HIGH)
  subtitle          str   extra subtext line (optional)
"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO / "remotion"

VARIANT_DEFAULTS = {
    "fraud_watch":    {"verdict_label": "FRAUD WATCH?",   "verdict_color": "red"},
    "system_product": {"verdict_label": "SYSTEM PRODUCT", "verdict_color": "red",  "collapse_risk": "HIGH"},
    "outlier":        {"verdict_label": "OUTLIER",         "verdict_color": "green"},
    "transfer_trap":  {"verdict_label": "TRANSFER TRAP",  "verdict_color": "red"},
}

REQUIRED_FIELDS = ["player_name", "variant", "instinct", "iq", "gravity", "transferability"]
VALID_VARIANTS = list(VARIANT_DEFAULTS.keys())


def validate(cfg: dict) -> list[str]:
    errors = []
    for f in REQUIRED_FIELDS:
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


def build_props(cfg: dict) -> dict:
    variant = cfg["variant"]
    defaults = VARIANT_DEFAULTS[variant].copy()

    props = {
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

    # Variant-specific optional fields
    if variant == "transfer_trap" and "transfer_club" in cfg:
        props["transfer_club"] = cfg["transfer_club"].upper()
    if variant == "system_product":
        props["collapse_risk"] = cfg.get("collapse_risk", defaults.get("collapse_risk", "HIGH"))
    if "subtitle" in cfg:
        props["subtitle"] = cfg["subtitle"]

    return props


def main():
    if len(sys.argv) < 2:
        print("usage: generate_thumbnail.py <variant.yaml> [--output <path.png>]")
        sys.exit(2)

    config_path = Path(sys.argv[1])
    output_path = None
    if "--output" in sys.argv:
        output_path = Path(sys.argv[sys.argv.index("--output") + 1])

    cfg = yaml.safe_load(config_path.read_text())
    errors = validate(cfg)
    if errors:
        print("CONFIG ERROR")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    props = build_props(cfg)

    # Write thumbnail.json next to the config for inspection
    thumb_json = config_path.parent / f"{config_path.stem}.json"
    thumb_json.write_text(json.dumps(props, indent=2))
    print(f"Props written → {thumb_json}")

    if output_path is None:
        output_path = config_path.parent / f"{config_path.stem}.png"

    cmd = [
        "npx", "remotion", "still",
        "src/index.ts",
        "Thumbnail",
        str(output_path),
        f"--props={json.dumps(props)}",
        "--frame=0",
    ]

    print(f"Rendering → {output_path}")
    result = subprocess.run(cmd, cwd=REMOTION_DIR)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
