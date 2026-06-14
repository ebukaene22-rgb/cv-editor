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

# V3 five-beat structure.
REQUIRED_BEATS = ["claim", "tension", "evidence", "reveal", "loop"]
AXES = ["instinct", "iq", "gravity"]

# Per-beat word count ranges at ~3 words/second.
# claim:    0-5s   (~12-18 words)
# tension:  5-15s  (~25-35 words)
# evidence: 15-30s (~42-52 words)
# reveal:   30-40s (~26-36 words)
# loop:     40-50s (~12-20 words)
BEAT_RANGES: dict[str, tuple[int, int]] = {
    "claim":    (10, 20),
    "tension":  (22, 38),
    "evidence": (38, 55),
    "reveal":   (22, 40),
    "loop":     (10, 22),
}
WORD_MIN, WORD_MAX = 120, 160


def load_banned():
    words = []
    for line in BANNED_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line.lower())
    return words


def count_words(text: str) -> int:
    # Hyphenated terms ("half-space", "sixty-one") count as one word.
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text))


def compute_transferability(scores: dict, context_risk: int) -> int:
    base = (scores["iq"] * 0.45 + scores["instinct"] * 0.30 + scores["gravity"] * 0.25) * 10
    return round(base - context_risk)


def validate(path: str) -> list[str]:
    errors = []
    data = json.loads(Path(path).read_text())

    # ── Beat presence and per-beat word counts ────────────────────────────────
    beats = data.get("beats", {})
    total_wc = 0
    for beat in REQUIRED_BEATS:
        text = beats.get(beat, "").strip()
        if not text:
            errors.append(f"missing or empty beat: '{beat}'")
            continue
        wc = count_words(text)
        total_wc += wc
        lo, hi = BEAT_RANGES[beat]
        if not (lo <= wc <= hi):
            errors.append(
                f"beat '{beat}' word count {wc} outside {lo}-{hi} "
                f"(~{(lo+hi)//2} target at 3 words/sec)"
            )

    # ── Total word count ──────────────────────────────────────────────────────
    if not (WORD_MIN <= total_wc <= WORD_MAX):
        errors.append(f"total word_count {total_wc} outside {WORD_MIN}-{WORD_MAX}")
    if data.get("word_count") != total_wc:
        errors.append(f"declared word_count {data.get('word_count')} != actual {total_wc}")

    # ── Scores ────────────────────────────────────────────────────────────────
    scores = data.get("scores", {})
    for axis in AXES:
        v = scores.get(axis)
        if not isinstance(v, int) or not (1 <= v <= 10):
            errors.append(f"score '{axis}' must be int 1-10, got {v!r}")

    # ── Transferability formula check ─────────────────────────────────────────
    cr = data.get("context_risk")
    if not isinstance(cr, int) or not (0 <= cr <= 20):
        errors.append(f"context_risk must be int 0-20, got {cr!r}")
    elif all(isinstance(scores.get(a), int) for a in AXES):
        expected = compute_transferability(scores, cr)
        if data.get("transferability") != expected:
            errors.append(
                f"transferability {data.get('transferability')} != formula result {expected}"
            )

    # ── Banned hype words ─────────────────────────────────────────────────────
    full_text = " ".join(beats.get(b, "") for b in REQUIRED_BEATS)
    banned = load_banned()
    lowered = full_text.lower()
    for w in banned:
        if re.search(rf"\b{re.escape(w)}\b", lowered):
            errors.append(f"banned hype word used: '{w}'")

    # ── V3 verdict-first fields ───────────────────────────────────────────────
    vh = data.get("verdict_hook")
    if not isinstance(vh, str) or not vh.strip():
        errors.append("missing 'verdict_hook' (e.g. 'TRANSFER TRAP?')")
    elif not vh.strip().endswith("?"):
        errors.append(f"'verdict_hook' must end with '?', got {vh!r}")

    vl = data.get("verdict_label")
    if not isinstance(vl, str) or not vl.strip():
        errors.append("missing 'verdict_label' (e.g. 'SYSTEM-DEPENDENT WEAPON')")

    # ── V3 axes evidence + benchmark ──────────────────────────────────────────
    axes = data.get("axes", {})
    if not isinstance(axes, dict):
        errors.append("'axes' must be an object with instinct/iq/gravity entries")
    else:
        for axis in AXES:
            a = axes.get(axis)
            if not isinstance(a, dict):
                errors.append(f"axes.{axis} missing (needs 'evidence' + 'percentile')")
                continue
            if not str(a.get("evidence", "")).strip():
                errors.append(f"axes.{axis}.evidence is empty")
            if not str(a.get("percentile", "")).strip():
                errors.append(f"axes.{axis}.percentile is empty (e.g. 'Top 5% in transition')")

    # ── V3 twitter thread (4 lines — planning artifact) ───────────────────────
    thread = data.get("thread")
    if thread is None:
        errors.append("missing 'thread' array (4-tweet planning artifact)")
    elif not isinstance(thread, list) or len(thread) != 4:
        errors.append(f"'thread' must have exactly 4 items, got {len(thread) if isinstance(thread, list) else type(thread).__name__}")

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
