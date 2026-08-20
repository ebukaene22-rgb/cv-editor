---
description: Stage 3 triage for a single acquisition candidate
argument-hint: <candidate-id>
---

Triage candidate **$1**.

1. `python acquisition/run.py show $1` for the computed metrics, flags and evidence.
2. Read `acquisition/config.yaml` for the thresholds actually in force. Quote
   those, never a number from memory.
3. Invoke the **deal-screen** skill. Work the four Stage 3 questions in order and
   interpret each flag against this specific listing using
   `.claude/skills/deal-screen/references/flag-playbook.md`.
4. Give me the verdict in the skill's format. Be decisive — a hedge costs me the
   whole point of the pipeline.
5. If the verdict is CONTACT, generate the diligence pack
   (`python acquisition/run.py promote $1 contacted`) and show me the draft
   enquiry to edit. Do not send it.

Remember: passing every rule means the listing did not contradict itself. It does
not mean any figure in it is real.
