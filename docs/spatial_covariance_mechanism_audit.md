# Preregistered Spatial Covariance Mechanism Audit

The persistent small-sample failure survived optimizer-update matching and one
weight-decay control. Two preregistered log-bandpower property audits found no
robust training-data-only signal. This separately motivated audit tests
cross-channel spatial covariance; it is not a post-hoc rescue.

The frozen outcome remains `residual_gap_pp = 100 * (mean accuracy_100_fixed -
mean accuracy_25_update_matched)`, with subject as the statistical unit (n=9).
Only exact frozen 25% official-0train subsets are used. Validation, remainder,
and official-test signals are excluded from feature extraction.

For each 8--32 Hz preprocessed channels-by-time trial, channels are centered
over time and sample covariance is `XX^T/(T-1)`. Covariance is divided by its
trace and regularized once as `(1-alpha)C + alpha I/n_channels`, with frozen
`alpha=1e-3`. Positive eigenvalues are required. The symmetric matrix logarithm
uses eigendecomposition, and the sole distance is Frobenius distance between
log-covariance matrices.

Exactly three candidates are frozen: equal-class mean distance to log-space
class centroid (`cov_within_class_dispersion`); mean of six class-centroid
distances (`cov_between_class_separation`); and between divided by within plus
`1e-12` (`cov_separability_ratio`). Per-class within values are descriptive and
receive no separate correlations.

Spearman, Kendall, and nine LOSO Spearman values use the unchanged gate:
absolute Spearman at least 0.6, matching rank-correlation direction, at least
8/9 LOSO directions preserved, and LOSO median absolute rho at least 0.5.
Expected directions are positive for within dispersion and negative for
between separation and ratio, but direction is reported rather than hidden in
classification.

Spatial covariance remains incomplete: it does not fully represent phase,
fine temporal dynamics, transients, or nonlinear interactions. With n=9, this
is exploratory. A robust association authorizes only a targeted intervention,
not NAP. If all three miss the gate, the current mechanism-driven architecture
search stops; further audits require new independent rationale and human
preregistration.
