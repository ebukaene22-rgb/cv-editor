#!/usr/bin/env python3
"""Validate a football-scout script.json against the channel's hard constraints.

Usage: python validate.py <path/to/script.json>
Exit code 0 = pass, 1 = fail. Prints every violation.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANNED_FILE = HERE.parent / "references" / "banned-words.txt"
REQUIRED_BEATS = ["hook", "profile", "verdict", "loop"]
WORD_MIN, WORD_MAX = 120, 140
AXES = ["instinct", "iq", "gravity"]


def load_banned():
    words = []
    for line in BANNED_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line.lower())
    return words


def count_words(text: str) -> int:
    # Hyphenated terms ("half-space", "sixty-one") count as one word, matching speech.
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text))


def compute_transferability(scores: dict, context_risk: int) -> int:
    base = (scores["iq"] * 0.45 + scores["instinct"] * 0.30 + scores["gravity"] * 0.25) * 10
    return round(base - context_risk)


def validate(path: str) -> list[str]:
    errors = []
    data = json.loads(Path(path).read_text())

    beats = data.get("beats", {})
    for beat in REQUIRED_BEATS:
        if not beats.get(beat, "").strip():
            errors.append(f"missing or empty beat: '{beat}'")

    # Word count across all beats, in declared order.
    full_text = " ".join(beats.get(b, "") for b in REQUIRED_BEATS)
    wc = count_words(full_text)
    if not (WORD_MIN <= wc <= WORD_MAX):
        errors.append(f"word_count {wc} outside {WORD_MIN}-{WORD_MAX}")
    if data.get("word_count") != wc:
        errors.append(f"declared word_count {data.get('word_count')} != actual {wc}")

    # Scores present and in range.
    scores = data.get("scores", {})
    for axis in AXES:
        v = scores.get(axis)
        if not isinstance(v, int) or not (1 <= v <= 10):
            errors.append(f"score '{axis}' must be int 1-10, got {v!r}")

    # Transferability recomputed from scores + context_risk.
    cr = data.get("context_risk")
    if not isinstance(cr, int) or not (0 <= cr <= 20):
        errors.append(f"context_risk must be int 0-20, got {cr!r}")
    elif all(isinstance(scores.get(a), int) for a in AXES):
        expected = compute_transferability(scores, cr)
        if data.get("transferability") != expected:
            errors.append(
                f"transferability {data.get('transferability')} != formula result {expected}"
            )

    # Banned hype words (whole-word, case-insensitive).
    banned = load_banned()
    lowered = full_text.lower()
    for w in banned:
        if re.search(rf"\b{re.escape(w)}\b", lowered):
            errors.append(f"banned hype word used: '{w}'")

    # V2 verdict-first fields. The accusation drives the hook; the evidence
    # makes each score feel earned rather than arbitrary.
    vh = data.get("verdict_hook")
    if not isinstance(vh, str) or not vh.strip():
        errors.append("missing 'verdict_hook' (the 0-2s accusation, e.g. 'TRANSFER TRAP?')")
    elif not vh.strip().endswith("?"):
        errors.append(f"'verdict_hook' should end with '?' to pose a question, got {vh!r}")

    vl = data.get("verdict_label")
    if not isinstance(vl, str) or not vl.strip():
        errors.append("missing 'verdict_label' (the resolved verdict, e.g. 'SYSTEM-DEPENDENT WEAPON')")

    axes = data.get("axes", {})
    if not isinstance(axes, dict):
        errors.append("'axes' must be an object with instinct/iq/gravity evidence")
    else:
        for axis in AXES:
            a = axes.get(axis)
            if not isinstance(a, dict):
                errors.append(f"axes.{axis} missing (needs 'evidence' + 'percentile')")
                continue
            if not str(a.get("evidence", "")).strip():
                errors.append(f"axes.{axis}.evidence is empty")
            if not str(a.get("percentile", "")).strip():
                errors.append(f"axes.{axis}.percentile is empty (benchmark, e.g. 'Top 5% in transition')")

    return errors


def main():
    if len(sys.argv) != 2:
        print("usage: python validate.py <script.json>")
        sys.exit(2)
    errors = validate(sys.argv[1])
    if errors:
        print("FAIL")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
