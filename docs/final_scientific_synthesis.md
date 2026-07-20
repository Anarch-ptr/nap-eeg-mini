# Final Scientific Synthesis and Stop-Gate

> **Scope note:** This synthesis freezes the evidence chain through the spatial
> covariance intervention stage. It is preserved as a historical scientific
> checkpoint, not the current project-final review. Failure Cartography and the
> subsequent instability-reliability review extend the chain; the current
> final status is summarized in the README and
> `docs/eegnet_instability_reliability_review.md`.

## A. Initial hypothesis

The initial hypothesis was that the sealed EEGNet baseline exploited an
artifact-related ocular or frontal shortcut. The audit found decodable EOG
information and EOG–EEG coupling, but no robust selective classifier dependency
under matched component removal, masking, or noise controls. The artifact
shortcut hypothesis was therefore **not supported**, and the original NAP-A
motivation was stopped.

## B. Failure discovery

The Small-Sample Robustness Audit produced `STRONG_FAILURE`. Reducing the fixed
training pool from 100% to 25% caused a median subject-level degradation of
17.25 percentage points, establishing a reproducible limited-data weakness in
the sealed EEGNet recipe.

## C. Optimization confound

The Optimizer-Update-Matched Diagnostic produced
`PERSISTENT_STRONG_FAILURE`, with a median residual gap of 13.89 percentage
points. Fewer optimizer updates explained only part of the initial failure.

## D. Simple regularization control

The single preregistered stronger-weight-decay control produced
`NO_MEANINGFUL_CONTROL_BENEFIT`. This result concerns the tested change from
`1e-4` to `1e-3`; it does not prove that every simple control would fail.

## E. First mechanism property audit

The preregistered log-bandpower geometry audit found no robust
training-data-only candidate signal. The null result is specific to the frozen
log-bandpower representation and does not cover every property EEGNet could
encode.

## F. Subset representativeness audit

The log-bandpower Subset Representativeness Audit also found no robust
candidate signal. The preregistered subset-representativeness hypothesis was
therefore stopped in that feature space rather than rescued by post-result
metrics or representation changes.

## G. Spatial covariance audit

The Spatial Covariance Mechanism Audit produced a `ROBUST_CANDIDATE_SIGNAL` for
`cov_between_class_separation`. Its association with residual limited-data
failure was strong and cross-subject stable: Spearman rho 0.917, Kendall tau
0.778, LOSO Spearman range 0.881–0.952, LOSO median 0.905, and direction
stability 9/9. The observed direction was unexpectedly positive: subjects
with higher covariance between-class separation showed larger residual
failure. This remains a robust observational result, not a causal result.

## H. Intervention feasibility

The zero-training feasibility audit produced `INTERVENTION_FEASIBLE`. All 9/9
subjects had meaningful LOW/HIGH pairs with identical sample and class counts
and preregistered matching on run distribution, acquisition order, and
covariance within-class dispersion.

## I. Formal intervention

The 54-run Pair Set 1 intervention produced
`HETEROGENEOUS_OR_WEAK_INTERVENTION_EFFECT` with integrity passing. Median
HIGH-minus-LOW accuracy was 0.00 percentage points. HIGH was worse for four
subjects, better for four, and tied for one; five subjects had an absolute
effect of at least 3 percentage points. Seed-level medians were +2.08, +2.08,
and −1.39 percentage points for seeds 42, 43, and 44, respectively.

Subject-level effects were:

| Subject | HIGH minus LOW |
|---|---:|
| A01 | 0.00 pp |
| A02 | −0.93 pp |
| A03 | +11.46 pp |
| A04 | +8.45 pp |
| A05 | +0.69 pp |
| A06 | −0.69 pp |
| A07 | +5.90 pp |
| A08 | −13.43 pp |
| A09 | −4.05 pp |

These results suggest substantial subject-specific heterogeneity, but they do
not authorize post-hoc searches for moderators separating A03/A04/A07 from
A08/A09. Such work would require an independently motivated hypothesis and a
new preregistration.

### Between-subject versus within-subject evidence

The observational and intervention audits answered different questions. The
observational audit asked whether subjects with different covariance
properties also differed in residual small-sample vulnerability. The
intervention asked whether changing covariance separation within the same
subject, while matching measured nuisance variables, systematically changed
EEGNet generalization. The project found a strong between-subject association
but a heterogeneous within-subject response. These findings cannot be
collapsed into one causal claim.

## J. Final scientific decision

**STOP COVARIANCE-SEPARATION MECHANISM ESCALATION.**

Pair Set 2 replication was conditional on Pair Set 1 producing a stable
`HIGH_SEPARATION_WORSE` or `HIGH_SEPARATION_BETTER` result. Pair Set 1 produced
neither, leaving no stable directional claim to replicate. Selecting or
training Pair Set 2 now would be an outcome-driven continuation; it remains
unselected and untrained. Micro-mechanism hunting, covariance-aware
architecture development, and NAP implementation are not authorized.

## Final scientific conclusion

The project identified a robust and reproducible small-sample vulnerability in
the sealed EEGNet baseline. The vulnerability persisted after matching
optimizer-update count and was not meaningfully improved by the preregistered
stronger-weight-decay control. Log-bandpower geometry and subset-
representativeness audits did not identify a robust training-data-only
explanatory signal.

A subsequent spatial-covariance audit identified a strong, LOSO-stable
cross-subject association between covariance between-class separation and
residual small-sample failure. However, a preregistered matched-subset
intervention deliberately manipulating covariance separation produced
heterogeneous and directionally inconsistent effects across subjects and
training seeds.

Covariance between-class separation is therefore retained as a robust
observational marker but is not supported as a universal intervention-relevant
mechanism of small-sample EEGNet failure under the tested design. The mechanism
of the robust vulnerability remains unresolved. The project stops
mechanism-driven architecture development rather than introducing an
unsupported NAP module.

## Final project evidence status

| Evidence question | Status |
|---|---|
| Robust failure | **YES** |
| Optimizer-update-only explanation | **NO** |
| Single stronger weight-decay solution | **NO** |
| Artifact-shortcut mechanism | **NOT SUPPORTED** |
| Log-bandpower geometry mechanism | **NOT SUPPORTED** |
| Subset representativeness mechanism | **NOT SUPPORTED IN THE FROZEN LOG-BANDPOWER SPACE** |
| Spatial covariance observational signal | **SUPPORTED** |
| Spatial covariance universal intervention effect | **NOT SUPPORTED** |
| General causal mechanism | **UNIDENTIFIED** |
| NAP justification | **NOT ESTABLISHED** |
| NAP implemented | **NO** |

The completed work is a reliable failure-characterization and mechanism-
falsification/diagnostic study. Its null, negative, and heterogeneous findings
are preserved as scientific results rather than rewritten as failed model
development.
