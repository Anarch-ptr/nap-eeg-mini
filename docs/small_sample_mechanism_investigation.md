# Preregistered Small-Sample Mechanism Investigation

The evidence chain is: fixed-epoch `STRONG_FAILURE`, update-matched
`PERSISTENT_STRONG_FAILURE`, and `NO_MEANINGFUL_CONTROL_BENEFIT` for the single
weight-decay control. Subject heterogeneity remains, but NAP remains blocked.

The frozen question is: which measurable subject-level properties are
associated with persistent limited-data residual failure? The outcome is
`residual_gap_pp = 100 * (mean 100%-fixed accuracy - mean 25%-update-matched
accuracy)`. The statistical unit is subject (A01--A09, n=9); seeds are not
independent subjects.

## Candidate features

Two result-derived descriptors are preregistered: mean full-data accuracy and
sample standard deviation of 25%-matched accuracy over seeds. Full-data
accuracy is mathematically related to an absolute gap and is only a ceiling or
learnability descriptor. Neither result-derived feature is eligible as a
future model input or candidate mechanism signal.

Four training-data-only features use the exact frozen 25% subset. For every
trial and EEG channel, Welch power is integrated in 8--13, 13--20, and 20--30
Hz and transformed with `log(power + 1e-12)`. Feature dimensions are z-scored
within the selected training subset. No official-test data are used.

- `within_class_dispersion`: mean across classes of the mean Euclidean distance
  from trials to their class centroid.
- `between_class_separation`: mean Euclidean distance over the six pairs of
  four class centroids.
- `separability_ratio`: between-class separation divided by within-class
  dispersion with a `1e-12` safe denominator.
- `trial_feature_variability`: mean Euclidean distance from trials to the
  global centroid.

Class-specific degradation is not included because matched/control aggregates
do not contain per-class recall or confusion matrices. It will not be added
after inspecting correlations. Existing validation histories are available,
but extra validation-derived candidates are not included to keep the feature
set small.

## Association rules

For each of exactly six features, report Spearman rho, Kendall tau, and nine
leave-one-subject-out Spearman correlations. A robust association requires
absolute rho at least 0.6, matching nonzero Spearman/Kendall direction, at
least 8/9 LOSO directions preserved, and LOSO median absolute rho at least 0.5.
Training-only features receive `ROBUST_CANDIDATE_SIGNAL`; result-derived
features receive `ROBUST_DESCRIPTIVE_ASSOCIATION`. Associations with both
absolute full rho and LOSO-median rho below 0.3 receive
`NO_CLEAR_ASSOCIATION`; other non-robust results receive
`WEAK_OR_UNSTABLE_ASSOCIATION`. Integrity failure overrides all categories.

No composite score, regression, automated selection, or neural-network
training is permitted. Correlation does not establish mechanism. A robust
training-data-only association authorizes a targeted follow-up hypothesis, not
a new architecture. No clear association is an acceptable outcome.
