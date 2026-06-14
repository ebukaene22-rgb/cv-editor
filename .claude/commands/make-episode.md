---
description: Generate a validated football-scout script for a player from a dossier
argument-hint: <player-slug>
---

Build a new episode for: **$1**

Pipeline (human review before any publish):

1. Read `episodes/$1/dossier.yaml`. If it doesn't exist, ask me for the player's role,
   key phases of play, and any system-dependence factors, then create it.
2. Invoke the **football-scout** skill. Anchor every Instinct/IQ/Gravity score to the
   dossier evidence (no invented numbers). Compute Transferability via the formula.
3. Write `episodes/$1/script.json` following the output contract in the skill.
4. Run `python .claude/skills/football-scout/scripts/validate.py episodes/$1/script.json`
   and fix every violation until it prints PASS.
5. Present the script for my review. Do NOT proceed to TTS / render / publish until I approve.

Later stages (after approval, separate steps): ElevenLabs TTS → Remotion render → draft upload.
