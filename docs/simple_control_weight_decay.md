# Preregistered Weight-Decay Simple Control

The primary fixed-epoch audit produced `STRONG_FAILURE`. After matching the
optimizer-update budget, the frozen diagnostic produced
`PERSISTENT_STRONG_FAILURE`: median residual degradation remained 13.89 pp and
8/9 subjects retained at least 3 pp degradation. This does not justify NAP; it
requires one simple-control gate.

The single preregistered control increases Adam weight decay from the sealed
`1e-4` to `1e-3`. No other value is tested. This ordinary one-order-of-magnitude
regularization control was selected before outcomes to ask whether stronger L2
regularization substantially reduces residual limited-data failure.

## Frozen matrix and variables

The new matrix is A01--A09 by training seeds 42, 43, and 44: 27 runs. Every run
uses the exact frozen 25% subset, split seed 42, subset seed 20260719, batch size
32, learning rate 0.001, Adam, dropout 0.25, unchanged EEGNet, 400 optimizer
updates, and 50 validation/checkpoint opportunities. Normalization is fitted
only on the selected subset. Official `1test` is evaluated only after restoring
the best-validation checkpoint.

The only scientific change is `weight_decay: 1e-4 -> 1e-3`. Effective decay is
recorded in every control row. Training, validation, and test identities must
match the frozen 25% reference before training begins.

## Frozen analysis

Seeds are aggregated within subject first:

- `matched_residual_gap_pp = 100 * (accuracy_100_fixed_mean - accuracy_25_matched_mean)`
- `control_gain_pp = 100 * (accuracy_25_matched_wd1e3_mean - accuracy_25_matched_mean)`
- `control_residual_gap_pp = 100 * (accuracy_100_fixed_mean - accuracy_25_matched_wd1e3_mean)`
- `control_gap_closure_fraction = control_gain_pp / matched_residual_gap_pp`
  when the pre-control gap is positive; this is descriptive only.

Classification precedence is frozen as:

1. `INCOMPLETE_OR_INVALID` for any matrix, identity, seed, decay, update,
   validation, status, or reference error.
2. `SIMPLE_CONTROL_SOLVES_MOST` when median residual is below 3 pp and fewer
   than three subjects retain at least 3 pp.
3. `NO_MEANINGFUL_CONTROL_BENEFIT` when strong residual failure persists,
   median gain is below 1 pp, and fewer than three subjects gain at least 3 pp.
4. `PERSISTENT_STRONG_FAILURE_AFTER_CONTROL` when median residual is at least
   5 pp, at least 7/9 subjects retain at least 3 pp, and every seed has positive
   median residual degradation.
5. `PARTIAL_SIMPLE_CONTROL_EFFECT` for all other valid outcomes.

Failure of this one weight-decay control does not prove that all simple controls
will fail. Success argues against a complex NAP architecture. Persistent failure
permits mechanism investigation but does not prove that NAP is correct.
