#!/usr/bin/env python3
"""Convert clips.json → Remotion props, including only clips that exist on disk.

Output shape:
    {
      "claim":   {"src": "clips/claim.mp4",   "freezeAt": 1.5, "zoom": {...}, "annotations": [...]},
      "tension": {...},
      "instinct": {...}, "iq": {...}, "gravity": {...}
    }

Missing keys cause the corresponding scene to fall back to its non-clip presentation.
"""
import json
import os
import sys

SLOTS = ["claim", "tension", "instinct", "iq", "gravity"]


def main():
    if len(sys.argv) < 3:
        print("Usage: clips_to_props.py <clips.json> <clips_dir>", file=sys.stderr)
        sys.exit(1)

    clips_json_path = sys.argv[1]
    clips_dir = sys.argv[2]

    with open(clips_json_path) as f:
        clips = json.load(f)

    result = {}
    for slot in SLOTS:
        spec = clips.get(slot)
        if not spec:
            continue
        mp4 = os.path.join(clips_dir, f"{slot}.mp4")
        if not os.path.exists(mp4):
            print(f"[{slot}] {mp4} not found — excluding from props", file=sys.stderr)
            continue

        out = {
            "src": f"clips/{slot}.mp4",
            "freezeAt": float(spec.get("freeze_at", 1.5)),
            "annotations": spec.get("annotations", []),
        }
        if spec.get("zoom"):
            out["zoom"] = spec["zoom"]
        result[slot] = out

    print(json.dumps(result))


if __name__ == "__main__":
    main()
