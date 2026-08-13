# HOLDOUT ESCROW — DO NOT READ

Everything under this directory covers **2025-01-01 onward** and exists for one
purpose: the final, single-shot evaluation of a frozen experiment spec.

Rules:

1. No experiment, notebook, script, or "quick look" reads this directory until
   the experiment's spec status log records that all training, walk-forward,
   and pre-live work is complete and the spec is frozen.
2. Each experiment gets **one** holdout evaluation. The result is committed to
   the spec's status log, pass or fail. There is no second attempt with the
   same experiment ID.
3. Raw data files placed here are git-ignored (see `.gitignore`); only this
   README and per-experiment evaluation records are tracked, so history shows
   *when* the holdout was touched.

If you are reading this because you were about to peek: that is the multiple-
testing failure mode this entire directory exists to prevent.
