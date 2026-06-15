#!/usr/bin/env python3
"""Convert clips.json into Remotion-compatible props, including only clips that exist on disk.

Usage:
    python pipeline/clips_to_props.py episodes/<slug>/clips.json remotion/public/clips/

Prints JSON to stdout. Only includes exhibits where the .mp4 file was actually fetched.
CaseFile.tsx reads this as props.clips — absent keys cause ProfileScene to fall back to TacticalBoard.
"""
import json
import os
import sys


def main():
    if len(sys.argv) < 3:
        print("Usage: clips_to_props.py <clips.json> <clips_dir>", file=sys.stderr)
        sys.exit(1)

    clips_json_path = sys.argv[1]
    clips_dir = sys.argv[2]

    with open(clips_json_path) as f:
        clips = json.load(f)

    result = {}
    for key, spec in clips.items():
        mp4 = os.path.join(clips_dir, f"{key}.mp4")
        if os.path.exists(mp4):
            result[key] = {
                "src": f"clips/{key}.mp4",
                "freezeAt": spec["freeze_at"],
                "annotations": spec["annotations"],
            }
        else:
            print(f"[{key}] {mp4} not found — excluding from props", file=sys.stderr)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
