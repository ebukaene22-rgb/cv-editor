> **This repo currently hosts two unrelated projects**, both scaffolded here for
> the same session-access reason. The football pipeline is below;
> [`ecommerce_os/`](ecommerce_os/README.md) is a compliant-ecommerce decision
> engine with its own [strategy doc](docs/ecommerce-os/strategy.md). Both are
> intended to migrate to dedicated repos.

# Instinct / IQ — Football Scout Channel

A reproducible production pipeline for a faceless YouTube Shorts / TikTok channel that
profiles footballers through a proprietary **3-Axis Framework** (Instinct · Football IQ ·
Gravity) in a cold, investigative "case file" voice.

> Scaffolded in the `cv-editor` repo for now (session access constraint). Intended to migrate
> to a dedicated `instinct-iq-football` repo.

## Principle
Every video = **one structured input** (`episodes/<slug>/dossier.yaml`) → deterministic
pipeline → finished Short. Same input, same output. Everything is version-controlled.

## Pipeline
```
dossier.yaml → [skill: football-scout] → script.json → [validate] → [TTS] → vo.mp3
                                                  ↓
                          [Remotion render: graphics + captions + clips]
                                                  ↓
              episode.mp4 + metadata → ⏸ HUMAN REVIEW → publish (YouTube / TikTok)
```

## What exists today
- `.claude/skills/football-scout/` — the script engine: framework, **scoring rubric**,
  **Transferability formula**, tone bank, banned-words list, and a `validate.py` gate.
- `.claude/commands/make-episode.md` — `/make-episode <slug>` orchestrator (stops at review).
- `episodes/2026-06-14-nico-williams/` — a complete first-draft example (dossier + script).

## Generate a script
```bash
# via Claude Code
/make-episode nico-williams

# validate any script
python .claude/skills/football-scout/scripts/validate.py episodes/2026-06-14-nico-williams/script.json
```

## Monetization & fair use (decided from research)
- **Spine = original case-file graphics/animation** (Tifo model) — zero Content ID risk, monetizable.
- **Footage in small, transformative doses only** — Content ID *claims* redirect ad revenue
  even without a strike, so never base a video's monetization on broadcast clips.
- **Licensed footage** (Wyscout / Getty) for hero shots where budget allows.
- A `fair-use-lint` skill (planned) will flag footage ratio per episode.

## Planned stack
Script: Claude skill · Voice: ElevenLabs · Motion graphics: Remotion (data-driven from
`script.json`) · Static brand templates: Canva MCP · Publish: drafts for human review.
