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

---

# Second subsystem: Micro-SaaS Acquisition Pipeline

The same repo also scaffolds a deal sourcing and screening system for buying small
SaaS products — see [`acquisition/README.md`](acquisition/README.md). Same
scaffolding caveat as above: intended to migrate to its own repo.

```
WordPress.org API ─┐
Flippa / TrustMRR ─┴→ [normalise → GBP] → [rule engine] → ranked shortlist
                                                 ↓
                        candidates.xlsx · deal-tracker.xlsx · diligence packs
                                                 ↓
                          ⏸ HUMAN REVIEW → outreach drafts (never sent)
```

```bash
python acquisition/run.py gate      # Appendix A acceptance gate — run this first
python acquisition/run.py weekly    # the weekly run
```

- Skills: `deal-screen` (Stage 3 triage), `deal-verify` (Stage 5 reconciliation).
- Commands: `/weekly-deals`, `/triage <id>`, `/verify-deal <id> <export.csv>`.

## Planned stack
Script: Claude skill · Voice: ElevenLabs · Motion graphics: Remotion (data-driven from
`script.json`) · Static brand templates: Canva MCP · Publish: drafts for human review.
