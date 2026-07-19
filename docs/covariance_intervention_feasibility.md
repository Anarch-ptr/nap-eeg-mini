# Covariance Intervention Feasibility Audit

The frozen spatial-covariance audit found an unexpected positive robust
association between residual failure and covariance between-class separation.
The identical-rank separability ratio is redundant, so separation is the sole
intervention property. Association is not causality; this zero-training stage
asks only whether a controlled LOW/HIGH experiment can be constructed.

The representation is exactly frozen log-Euclidean spatial covariance, not
log-bandpower: 8--32 Hz trial, channel centering, sample covariance, trace
normalization, alpha `1e-3` shrinkage toward `I/22`, matrix logarithm, and
Frobenius distances. Each subject uses the exact 230-trial fixed training pool.
Candidate subsets use the original nominal-25% total and per-class counts.

Exactly 512 unique candidates are drawn with master seed 20260720 and a
subject-keyed deterministic SeedSequence. Each records identities, three frozen
covariance summaries, six-run distribution, TVD from pool, normalized
acquisition-position mean, and population SD. No neural network is trained.

One LOW/HIGH pair maximizes separation difference subject to run-distribution
TVD <=0.10, chronological mean and spread differences <=0.10, and relative
within-class dispersion difference <=10%. Ties use candidate IDs. Meaningful
contrast additionally requires LOW percentile <=25 and HIGH percentile >=75.
At least 7/9 feasible and 7/9 meaningful subjects are required for
`INTERVENTION_FEASIBLE`; provenance failure is invalid, otherwise the result is
`INTERVENTION_NOT_FEASIBLE`. Thresholds are never relaxed post hoc. Trial overlap
is reported descriptively without a threshold, and multiple feasible/meaningful
pairs are counted for possible separately preregistered replication.

## Causal Interpretation Boundary and Ultimate Exit Protocol

Feasibility is not causality. Covariance separation is calculated in frozen
log-Euclidean spatial-covariance space. A future experiment must use validation
only for checkpoint selection, restore the best checkpoint, and evaluate
official test once. Its primary paired outcome is `100*(accuracy_HIGH-
accuracy_LOW)`; gaps to 100% are secondary. HIGH worse, HIGH better, no effect,
and heterogeneous effects are symmetric preregistered outcomes.

One pair per subject is a `FIRST INTERVENTION-STYLE TEST`; differing trial
identities leave unmeasured nuisance possibilities. No extra trained pairs may
be added after results. Micro-mechanism hunting remains blocked unless a stable
directional intervention effect exists. If feasibility fails, constraints are
not relaxed. If a future intervention has no meaningful effect, covariance
mechanism development stops; heterogeneous results return to human review.
None of these stages authorizes NAP.
