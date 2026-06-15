#!/usr/bin/env python3
"""Generate voiceover from script.json using ElevenLabs TTS.

Usage:
  ELEVENLABS_API_KEY=<key> python pipeline/tts.py episodes/<slug>/script.json

Output: episodes/<slug>/vo.mp3
        episodes/<slug>/vo_timestamps.json  (word-level, for caption sync)

Requires: pip install elevenlabs
"""
import json
import os
import sys
from pathlib import Path

VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # ElevenLabs "Sarah" — cold, analytical. Pin this.
MODEL_ID = "eleven_multilingual_v2"


def main():
    if len(sys.argv) != 2:
        print("usage: python pipeline/tts.py <path/to/script.json>")
        sys.exit(2)

    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs import save
    except ImportError:
        print("Install ElevenLabs SDK: pip install elevenlabs")
        sys.exit(1)

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("Set ELEVENLABS_API_KEY environment variable.")
        sys.exit(1)

    script_path = Path(sys.argv[1]).resolve()
    episode_dir = script_path.parent
    script = json.loads(script_path.read_text())

    beats = script["beats"]
    # V3 beat order: claim → tension → evidence → reveal → loop
    beat_keys = ["claim", "tension", "evidence", "reveal", "loop"]
    # Fall back to V2 keys if this is an older script
    if "hook" in beats:
        beat_keys = ["hook", "profile", "verdict", "loop"]
    full_text = " ".join(beats[k] for k in beat_keys)

    client = ElevenLabs(api_key=api_key)

    audio_gen = client.text_to_speech.convert(
        voice_id=VOICE_ID,
        model_id=MODEL_ID,
        text=full_text,
        voice_settings={
            "stability": 0.55,
            "similarity_boost": 0.80,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    )

    output = episode_dir / "vo.mp3"
    save(audio_gen, str(output))
    print(f"Saved → {output}")


if __name__ == "__main__":
    main()
