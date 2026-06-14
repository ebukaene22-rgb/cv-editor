#!/usr/bin/env python3
"""Parse footage.yaml and run the fair-use rules mechanically before Claude audits.

Usage: python .claude/skills/fair-use-lint/scripts/lint_footage.py episodes/<slug>/footage.yaml

Prints a structured pre-audit report. Exit code 0 = all rules pass, 1 = violations found.
"""
import sys
import yaml
from pathlib import Path

VIDEO_DURATION_S = 50
RATIO_FAIL = 0.30
RATIO_WARN = 0.20
MAX_CLIP_S = 6

HIGH_RISK_SOURCES = [
    "premier league", "uefa", "la liga", "ligue 1",
    "bundesliga", "serie a", "eredivisie", "champions league",
    "europa league", "conference league",
]
MEDIUM_RISK_SOURCES = ["official", "club", "highlight"]
LOW_RISK_SOURCES = ["getty", "reuters", "licensed"]


def source_risk(source: str) -> str:
    s = source.lower()
    if any(k in s for k in HIGH_RISK_SOURCES):
        return "HIGH"
    if any(k in s for k in LOW_RISK_SOURCES):
        return "LOW"
    if any(k in s for k in MEDIUM_RISK_SOURCES):
        return "MEDIUM"
    return "MEDIUM"


def main():
    if len(sys.argv) != 2:
        print("usage: lint_footage.py <footage.yaml>")
        sys.exit(2)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"No footage.yaml at {path}. If episode has no footage, nothing to lint.")
        sys.exit(0)

    data = yaml.safe_load(path.read_text())
    clips = data.get("clips", [])

    total_s = sum(c.get("duration_s", 0) for c in clips)
    ratio = total_s / VIDEO_DURATION_S
    violations = []

    # Rule 1: ratio
    if ratio > RATIO_FAIL:
        violations.append(f"FAIL  footage ratio {ratio:.0%} exceeds 30% hard limit")
    elif ratio > RATIO_WARN:
        violations.append(f"WARN  footage ratio {ratio:.0%} in caution zone (20–30%)")

    print(f"Footage total: {total_s}s / {VIDEO_DURATION_S}s  ({ratio:.0%})")
    print()

    for i, clip in enumerate(clips, 1):
        src = clip.get("source", "unknown")
        dur = clip.get("duration_s", 0)
        risk = source_risk(src)
        has_text = clip.get("on_screen_text", False)
        has_vo = clip.get("voiceover", False)
        transformative = has_text and has_vo

        status = "PASS"
        if risk == "HIGH":
            status = "WARN"
        if not transformative or dur > MAX_CLIP_S:
            status = "FAIL"

        print(f"  [{status}] Clip {i} — {src} ({dur}s)")
        print(f"         Risk: {risk}  |  Transformative: {'YES' if transformative else 'NO'}")
        if dur > MAX_CLIP_S:
            v = f"Clip {i}: {dur}s exceeds 6s max — trim it"
            violations.append(f"FAIL  {v}")
            print(f"         ⚠ {v}")
        if not transformative:
            missing = []
            if not has_text:
                missing.append("on_screen_text")
            if not has_vo:
                missing.append("voiceover")
            v = f"Clip {i}: missing {', '.join(missing)} — not transformative"
            violations.append(f"FAIL  {v}")
            print(f"         ⚠ {v}")
        if risk == "HIGH":
            print(f"         ⚠ HIGH-risk source — Content ID claim expected, revenue may be redirected")

    print()
    if violations:
        print("VIOLATIONS:")
        for v in violations:
            print(f"  {v}")
        sys.exit(1)
    else:
        print("All mechanical rules pass. Run fair-use-lint skill for full editorial review.")
        sys.exit(0)


if __name__ == "__main__":
    main()
