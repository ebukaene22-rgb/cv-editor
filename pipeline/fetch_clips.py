#!/usr/bin/env python3
"""Fetch short evidence clips for a Case File episode.

Reads clips.json from the episode folder, searches YouTube for each exhibit,
downloads the top result, cuts to the specified timestamp range, and writes
to remotion/public/clips/<key>.mp4.

If yt-dlp or ffmpeg fails for any clip, that clip is skipped and the Remotion
component falls back to the procedural TacticalBoard for that exhibit.

Usage:
    python pipeline/fetch_clips.py episodes/<slug>/clips.json --out remotion/public/clips/
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

EXHIBIT_KEYS = ["instinct", "iq", "gravity"]


def fetch_clip(query: str, start: float, end: float, out_path: str) -> bool:
    duration = end - start

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Search YouTube and download best quality up to 720p
        dl = subprocess.run([
            "yt-dlp",
            f"ytsearch1:{query}",
            "--format", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--output", tmp_path,
            "--no-playlist",
            "--max-downloads", "1",
            "--quiet",
            "--no-warnings",
        ], capture_output=True, text=True, timeout=180)

        if dl.returncode != 0:
            print(f"  yt-dlp error: {dl.stderr[:300]}", file=sys.stderr)
            return False

        # Cut to the specified segment and scale to 1080x1920 (9:16 portrait)
        cut = subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", tmp_path,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            # Scale to fit portrait frame; letterbox if source is landscape
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
            out_path,
        ], capture_output=True, text=True, timeout=120)

        if cut.returncode != 0:
            print(f"  ffmpeg error: {cut.stderr[:300]}", file=sys.stderr)
            return False

        size_kb = os.path.getsize(out_path) // 1024
        print(f"  Saved {duration}s clip → {out_path} ({size_kb} KB)")
        return True

    except subprocess.TimeoutExpired:
        print(f"  Timeout fetching clip", file=sys.stderr)
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

    for key in EXHIBIT_KEYS:
        spec = clips.get(key)
        if not spec:
            print(f"[{key}] No spec in clips.json — skipping")
            continue

        out_path = os.path.join(args.out, f"{key}.mp4")
        if os.path.exists(out_path):
            print(f"[{key}] Already present — skipping")
            ok.append(key)
            continue

        query = spec["query"]
        start = spec.get("start", 0)
        end = spec.get("end", start + 3)

        print(f"[{key}] Fetching: {query!r} [{start}s–{end}s]")
        if fetch_clip(query, start, end, out_path):
            ok.append(key)
        else:
            print(f"[{key}] FAILED — exhibit will use procedural TacticalBoard fallback")
            failed.append(key)

    print(f"\nDone: {len(ok)} clip(s) ready, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
