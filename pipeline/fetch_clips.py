#!/usr/bin/env python3
"""Fetch evidence clips for a Case File episode from explicit URLs + timestamps.

V6 Path A: the operator provides 3-5 URLs in clips.json (one per scene slot
they want real footage in). yt-dlp downloads ONLY the specified time segment
via --download-sections, then ffmpeg scales to 9:16 portrait.

If any clip fails (404, region-locked, geo-blocked, etc.), it is skipped with
a warning and that scene slot falls back to its non-clip presentation.

Usage:
    python pipeline/fetch_clips.py episodes/<slug>/clips.json --out remotion/public/clips/
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

# Order matters only for log readability; each is independent.
SLOTS = ["claim", "tension", "instinct", "iq", "gravity"]


def parse_time(t) -> float:
    """Accept 7, 7.5, '7', '0:07', '1:23', '01:23' → seconds (float)."""
    if isinstance(t, (int, float)):
        return float(t)
    s = str(t).strip()
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2:
            m, sec = parts
            return int(m) * 60 + float(sec)
        if len(parts) == 3:
            h, m, sec = parts
            return int(h) * 3600 + int(m) * 60 + float(sec)
    return float(s)


def fetch_clip(url: str, start: float, end: float, out_path: str) -> bool:
    duration = end - start
    if duration <= 0:
        print(f"  Bad time range: start={start} end={end}", file=sys.stderr)
        return False

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    os.unlink(tmp_path)  # yt-dlp writes its own file at this path

    try:
        # yt-dlp downloads ONLY the requested segment via --download-sections.
        # *START-END format is the modern syntax (supports float seconds).
        section = f"*{start}-{end}"
        dl = subprocess.run([
            "yt-dlp",
            url,
            "--download-sections", section,
            "--force-keyframes-at-cuts",
            "--format", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--output", tmp_path,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
        ], capture_output=True, text=True, timeout=240)

        if dl.returncode != 0:
            print(f"  yt-dlp error: {dl.stderr[:400]}", file=sys.stderr)
            return False

        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            print(f"  yt-dlp produced no file", file=sys.stderr)
            return False

        # Re-cut to exactly the requested duration (download-sections can
        # over-shoot to nearest keyframe) and scale to 1080x1920 portrait.
        cut = subprocess.run([
            "ffmpeg", "-y",
            "-i", tmp_path,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
            out_path,
        ], capture_output=True, text=True, timeout=180)

        if cut.returncode != 0:
            print(f"  ffmpeg error: {cut.stderr[:400]}", file=sys.stderr)
            return False

        size_kb = os.path.getsize(out_path) // 1024
        print(f"  Saved {duration}s clip → {out_path} ({size_kb} KB)")
        return True

    except subprocess.TimeoutExpired:
        print(f"  Timeout fetching clip", file=sys.stderr)
        return False
    except FileNotFoundError as e:
        print(f"  Missing tool: {e}", file=sys.stderr)
        return False
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("clips_json", help="Path to episode clips.json")
    parser.add_argument("--out", default="remotion/public/clips", help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    with open(args.clips_json) as f:
        clips = json.load(f)

    ok, failed = [], []

    for slot in SLOTS:
        spec = clips.get(slot)
        if not spec:
            continue

        url = spec.get("url", "")
        if not url or url.startswith("PASTE_") or not url.startswith(("http://", "https://")):
            print(f"[{slot}] URL not set ({url!r}) — skipping (scene uses non-clip fallback)")
            continue

        out_path = os.path.join(args.out, f"{slot}.mp4")
        if os.path.exists(out_path):
            print(f"[{slot}] Already present — skipping")
            ok.append(slot)
            continue

        start = parse_time(spec.get("start", 0))
        end = parse_time(spec.get("end", start + 3))

        print(f"[{slot}] Fetching {url} [{start}s–{end}s]")
        if fetch_clip(url, start, end, out_path):
            ok.append(slot)
        else:
            print(f"[{slot}] FAILED — scene will use non-clip fallback")
            failed.append(slot)

    print(f"\nDone: {len(ok)} clip(s) ready, {len(failed)} failed")
    if ok:
        print(f"Ready: {ok}")
    if failed:
        print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
