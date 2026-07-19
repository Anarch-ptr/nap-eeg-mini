# Optimizer-Update-Matched Small-Sample Diagnostic

The preregistered fixed-epoch audit found `STRONG_FAILURE`: the median
100%-to-25% subject-level accuracy degradation was 17.25 percentage points,
with at least 3 pp degradation in 8/9 subjects. This establishes vulnerability
of the sealed fixed-epoch recipe, not a sample-diversity mechanism.

## Scientific purpose

With batch size 32 and `drop_last=False`, the 230-trial full training pool has
`ceil(230/32) = 8` optimizer updates per epoch. The 100%-data, 50-epoch
reference therefore performs exactly 400 Adam updates for every subject.
The 25% fixed-epoch condition performs fewer updates, creating an optimization
budget confound.

This diagnostic trains only the frozen 25% subsets for exactly 400 optimizer
updates. It covers A01--A09 and training seeds 42, 43, and 44: 27 runs. It does
not rerun either primary reference condition.

Validation occurs every 8 optimizer updates, producing exactly 50 validation
and checkpoint-selection opportunities. The validation metric and tie-breaking
rule are unchanged. Official session `1test` is evaluated once, after training,
using the selected best-validation checkpoint.

The split seed remains 42 and subset seed remains 20260719. Before training,
the selected training, validation, and official-test indices must exactly equal
the stored formal 25% identities. Normalization remains fitted only on the
selected 25% training subset.

## Frozen analysis

Training seeds are aggregated within subject first:

- `original_gap_pp = 100 * (accuracy_100_fixed_mean - accuracy_25_fixed_mean)`
- `recovery_pp = 100 * (accuracy_25_matched_mean - accuracy_25_fixed_mean)`
- `residual_gap_pp = 100 * (accuracy_100_fixed_mean - accuracy_25_matched_mean)`
- `gap_closure_fraction = recovery_pp / original_gap_pp`, descriptively and
  only when the original gap is positive.

The four classifications are frozen before real diagnostic outcomes:

- `PERSISTENT_STRONG_FAILURE`: integrity passes, median residual gap is at
  least 5 pp, at least 7/9 subjects have residual gap at least 3 pp, and each
  training seed independently has positive median residual degradation.
- `UPDATE_COUNT_EXPLAINS_MOST`: integrity passes, median residual gap is below
  3 pp, and fewer than three subjects have residual gap at least 3 pp.
- `PARTIAL_UPDATE_CONFOUND`: integrity passes and meaningful residual
  degradation remains, but not all persistent-strong criteria pass.
- `INCOMPLETE_OR_INVALID`: any matrix, seed, identity, update-count,
  validation-count, run-status, or reference-integrity requirement fails.

## Interpretation boundaries

A positive recovery does not prove that sample diversity is irrelevant. A
persistent residual failure does not prove that NAP is required. No NAP,
attention, GRL, uncertainty gating, augmentation, or regularization change is
part of this diagnostic.
