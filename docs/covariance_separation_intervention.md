# Preregistered Covariance-Separation Intervention

This protocol follows the sealed baseline, persistent optimizer-update-matched
small-sample failure, failed weight-decay control, null log-bandpower audits,
the robust observational covariance between-class separation signal, and the
`INTERVENTION_FEASIBLE` matched-subset audit at commit `3241f01`.

The first intervention trains exactly one already frozen Pair Set 1 LOW/HIGH
pair per A01-A09 with seeds 42, 43, and 44 (54 cells). Candidate identities,
trial identities, counts, separation values, and percentiles are loaded from
the authoritative feasibility JSON; the candidate bank is not regenerated or
searched. EEGNet, Adam, learning rate 0.001, weight decay 1e-4, dropout 0.25,
batch size 32, split seed 42, 400 updates, validation every 8 updates, and 50
checkpoint opportunities remain fixed. Validation accuracy is primary and
validation loss breaks ties.

Normalization is fitted separately on each condition's training trials.
Validation and official test are transform-only. Official 1test is unavailable
to selection, fitting, training, validation, and checkpoint selection; it is
evaluated exactly once after restoring the best-validation checkpoint.

Seeds are averaged within subject first. The primary effect is
`100 * (accuracy_HIGH - accuracy_LOW)` in percentage points. Gaps from the
historical 100%-fixed baseline are secondary only. Frozen precedence is:
`INCOMPLETE_OR_INVALID`, `HIGH_SEPARATION_WORSE`,
`HIGH_SEPARATION_BETTER`, `NO_MEANINGFUL_INTERVENTION_EFFECT`, then
`HETEROGENEOUS_OR_WEAK_INTERVENTION_EFFECT`. Directional gates require a
median magnitude of at least 3 pp, concordant signs in at least 7/9 subjects,
and concordant across-subject medians for every training seed. No-effect
requires absolute median below 1 pp and fewer than three subjects at or above
3 pp absolute effect.

This is direction-agnostic and is the first intervention-style test, not
definitive causal proof. Different trial identities and unmeasured properties
remain a limitation. A directional result stops for human review and requires
separately preregistered, independently frozen Pair Set 2 replication before
micro-mechanism work. Null stops covariance-mechanism development; heterogeneous
results return to human review. Pair Set 2 is not selected or trained here.
NAP remains blocked.
