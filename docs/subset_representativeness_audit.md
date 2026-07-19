# Preregistered Subset Representativeness Audit

The fixed-epoch failure survived optimizer-update matching and one stronger
weight-decay control. The first zero-training mechanism audit found no robust
training-data-only signal. That audit described the retained subset internally;
this audit asks whether the retained subset represents omitted training-pool
variability.

The frozen outcome remains subject-level `residual_gap_pp = 100 *
(mean_accuracy_100_fixed - mean_accuracy_25_update_matched)`. Subjects A01--A09
are the statistical units; seeds are aggregated within subject.

For each subject, `subset_25` is the exact frozen selected-index list.
`remainder_75` is the fixed official-0train training pool minus that subset.
The implementation requires disjointness, exact union equality, and exclusion
of the fixed validation indices. Official `1test` signals are never loaded for
feature calculation.

The feature representation is unchanged: existing 8--32 Hz preprocessing,
Welch PSD, 8--13/13--20/20--30 Hz channel-wise band powers, and
`log(power + 1e-12)`. Each feature dimension is standardized using population
mean and standard deviation fitted over the complete fixed 230-trial training
pool. The same transformation is applied to subset and remainder; validation
and test data do not contribute statistics.

Four and only four subject-level candidates are frozen:

- `class_centroid_shift`: equal-class mean Euclidean subset/remainder centroid
  distance.
- `class_covariance_shift`: equal-class mean of
  `||Cov_subset-Cov_remainder||F / (||Cov_remainder||F + 1e-12)`, using sample
  covariance (`N-1`).
- `class_coverage_distance`: equal-class mean of each remainder trial's nearest
  same-class subset-trial Euclidean distance.
- `worst_class_coverage_distance`: maximum of the four class-specific mean
  coverage distances.

Per-class values are descriptive only and receive no separate correlations.
For each primary candidate, Spearman, Kendall, and nine LOSO Spearman values are
reported. The previous gate is unchanged: absolute Spearman at least 0.6,
matching Spearman/Kendall direction, at least 8/9 preserved LOSO directions,
and LOSO median absolute rho at least 0.5. Otherwise the existing weak/unstable
and no-clear semantics apply. Integrity failure overrides interpretation.

With n=9, results are exploratory. Subset representativeness is a hypothesis
candidate, not an established mechanism. A robust association authorizes a
targeted intervention study, not a NAP architecture. No association is an
acceptable outcome.
