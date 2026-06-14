# Transferability Score — the formula

Transferability answers one question: **how much of this player's value survives a move to
a different system?** It is reproducible: same scores + same context risk → same percentage.

## Step 1 — Weighted base (0–100)

IQ travels best (a tactical brain works anywhere). Instinct travels well. Gravity is
partly dependent on teammates and system, so it is weighted lowest.

```
base = (iq * 0.45 + instinct * 0.30 + gravity * 0.25) * 10
```

## Step 2 — Context Risk deduction (0–20)

Add points for each dependence factor that is true in the dossier (cap at 20):

| Factor | Points |
|--------|--------|
| Output relies on one specific teammate/system feature | +6 |
| Thrives only in one phase (e.g. transition-only) | +5 |
| Unproven against a step up in league/level | +4 |
| Age/physical profile threatens the core trait | +3 |
| Role is rare in target leagues | +2 |

## Step 3 — Final score

```
transferability = round(base - context_risk)
```

Store `context_risk` in `script.json` so the number is auditable. The validator recomputes
`transferability` from `scores` + `context_risk` and fails if they disagree.

## Verdict mapping
- **≥ 75%** → "system-independent outlier".
- **60–74%** → "transferable with conditions" — name the condition.
- **< 60%** → "system product at risk of collapsing".
