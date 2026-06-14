#!/usr/bin/env python3
"""Render a single episode from its script.json via Remotion.

Usage:
  python pipeline/render.py episodes/<slug>/script.json

Output: episodes/<slug>/episode.mp4
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"


def main():
    if len(sys.argv) != 2:
        print("usage: python pipeline/render.py <path/to/script.json>")
        sys.exit(2)

    script_path = Path(sys.argv[1]).resolve()
    episode_dir = script_path.parent
    output = episode_dir / "episode.mp4"

    script_data = json.loads(script_path.read_text())
    props_json = json.dumps(script_data)

    cmd = [
        "npx", "remotion", "render",
        "src/index.ts",
        "CaseFile",
        str(output),
        f"--props={props_json}",
        "--log=verbose",
    ]

    print(f"Rendering → {output}")
    result = subprocess.run(cmd, cwd=REMOTION_DIR)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
