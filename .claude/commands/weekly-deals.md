---
description: Run the weekly acquisition sourcing and screening review
argument-hint: "[--no-pull]"
---

Run this week's deal review. Target: 15 minutes of my time, not several hours.

1. **Check the config first.**
   `python .claude/skills/deal-screen/scripts/check_config.py`
   Stop and tell me if it reports an error. Report warnings but carry on.

2. **Confirm the gate still passes.**
   `python acquisition/run.py gate`
   If the Appendix A suite fails, stop. Ingestion volume is worthless when the
   rule engine can't catch known-bad listings — say which case broke and why.

3. **Run the pipeline.** `python acquisition/run.py weekly $ARGUMENTS`
   Sources are undocumented endpoints and will break. If a pull fails, say so
   plainly with the error, then continue on stored data — do not paper over it
   and do not present a short list as a quiet week.

4. **Invoke the deal-screen skill** and triage the shortlist. For each candidate
   that survived: the four Stage 3 questions, every flag interpreted against
   *this* listing rather than in general, and a one-line verdict —
   CONTACT / PASS / ASK FIRST.

5. **Report** in this shape:
   - how many sourced, how many rejected, the rejection rate (expect 95%+)
   - the top 3 marketplace candidates with their verdicts
   - the top 3 off-market neglect candidates with install counts and author
     contact URLs
   - anything that changed on a candidate I'd already seen
   - one line on what broke, if anything

6. **Never invent a candidate.** If a source is unreachable, report the failure
   and the count you actually have. A short week is a real answer; an
   illustrative listing is not. See rule zero in the deal-screen skill.

7. **Stop there.** Outreach drafts are generated for review at
   `acquisition/out/outreach-drafts.md`. I edit and send them myself — do not
   send anything, and do not offer to.
