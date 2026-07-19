# EEGNet Failure Cartography Protocol

## Scope and evidence boundary

The Artifact Audit is a completed negative-result phase: class-correlated EOG
information and EEG coupling were observed, but selective ocular/frontal
shortcut dependency was not supported. This phase does not revise that result
or revive NAP-A. It performs ordinary baseline characterization by asking
**when** the sealed EEGNet fails and **where** source/evaluation divergence
appears. No new architecture or intervention is included.

The critical hypothesis is that cross-session and limited-data failure has a
reproducible structure across subjects, budgets, seeds, layers, and confidence.
This is unverified and is the target of falsification—not an assumed benefit of
the analysis. A valid result is that no stable signature exists.

## Phase 3A — WHEN does EEGNet fail?

The intended matrix is A01–A09 × budgets 100%, 50%, and 25% × training seeds
42, 43, and 44, with `split_seed=42` and `subset_seed=20260719`. Existing frozen
small-sample checkpoints are analyzed post hoc; the cartography runner does not
train models.

For both the official-0train validation subset and official-1test evaluation
session it records accuracy, balanced accuracy, macro-F1, Cohen's kappa, NLL,
Brier score, 15-bin ECE, confidence on correct/incorrect predictions,
error-detection AUROC, risk–coverage curves, and AURC. The session
generalization gap is `validation_accuracy - evaluation_accuracy`. Analysis
summarizes mean, sample standard deviation, minimum, and maximum across seeds.

Calibration metrics are diagnostic only. They do not define a confidence
threshold, uncertainty head, rejection policy, or intervention.

## Phase 3B — WHERE does EEGNet fail?

Forward hooks capture actual EEGNet modules without changing model code or
predictions:

| Diagnostic stage | Repository module |
|---|---|
| Model input | explicit pre-forward capture |
| Temporal convolution | `block1.0` |
| Depthwise spatial convolution | `block1.2` |
| Separable pointwise convolution | `block2.1` |
| Final latent representation | `block2` |
| Classifier logits | `classifier` |

To keep covariance diagnostics tractable and comparable, input and
convolutional stages are represented per trial by feature-map means and
standard deviations over remaining spatial/temporal axes. Final latent and
logit outputs are flattened. These summaries are post-hoc diagnostic
representations; they are not claimed to be complete neural representations
and are never fed back into EEGNet.

For validation versus evaluation embeddings the infrastructure calculates
normalized feature-mean shift, normalized feature-variance shift, covariance
Frobenius difference, CORAL distance, and Gaussian-RBF MMD² with a pooled
median-distance bandwidth. Shift/gap associations aggregate training seeds
within subject-budget units before descriptive Spearman analysis. P-values are
descriptive because formal multiplicity and stability criteria have not yet
been preregistered.

## Leakage safeguards

- Official `1test` remains evaluation-only and is never used for fitting,
  normalization, checkpoint selection, subset construction, tuning, adaptive
  preprocessing, or threshold selection.
- The runner reconstructs each frozen resolved config and asserts exact
  training, validation, and official-test identities against its saved split
  provenance before inference.
- Normalization remains the frozen train-subset-only transformation.
- Source/evaluation representations are compared only after restoring the
  best-validation checkpoint.
- Evaluation statistics cannot adapt the model or alter predictions.
- The complete 81-cell command refuses to run without an explicit
  `--confirm-full-matrix` flag.

## Outcome states and falsification

The eventual complete audit must be classified as one of: (1) reproducible
dominant signature, (2) conditional signature, (3) subject-specific
heterogeneous failure, (4) seed-sensitive/statistically unstable signature,
or (5) no stable signature. The present infrastructure does not choose a state.
Quantitative reproducibility thresholds must be frozen before the full output
is interpreted; until then analysis status is
`NOT_RUN_OR_NOT_PREREGISTERED`.

Signatures A–F (input-dominant, temporal growth, spatial growth,
decision-boundary failure, calibration-only degradation, or no reproducible
pattern) remain hypotheses. They are not observed evidence. If no stable
pattern emerges, architecture design stops and that negative result must be
reported without forcing a unified story.

## Pre-Result Analysis and Decision Protocol

**Freeze status:** this protocol was defined before running or inspecting the
complete 81-cell Failure Cartography matrix. The experiment and scientific
classification status remains `NOT_RUN_OR_NOT_PREREGISTERED`. The single A01,
100%, seed-42 engineering smoke check is not scientific evidence and must not
be used to choose metrics, thresholds, subjects, budgets, layers, or a
narrative.

### Experimental-unit hierarchy

The biological unit is the **subject**. The primary descriptive analysis unit
is **subject × training budget**, after aggregating seeds 42, 43, and 44.
Within every such unit, report the mean, sample standard deviation, minimum,
and maximum. Preserve every seed-level result and inspect it for stability,
but do not treat optimization seeds as biological replicates or the 81 cells
as 81 independent biological observations.

### Frozen representation-shift metrics

The primary representation-shift metric is the CORAL-style covariance
distance implemented as
`||C_source - C_evaluation||²_F / (4 d²)`, where `d` is the diagnostic feature
dimension. Supporting metrics are:

- Gaussian-RBF MMD² using the pooled median squared-distance bandwidth;
- normalized feature-mean shift, `||mean_source-mean_evaluation||₂/sqrt(d)`;
- normalized feature-variance shift,
  `||var_source-var_evaluation||₂/sqrt(d)`;
- covariance Frobenius difference, `||C_source-C_evaluation||_F`.

No existing metric is deleted. One favorable secondary metric cannot establish
a candidate signature. A CORAL-only pattern contradicted or unsupported by all
other diagnostics must be treated cautiously. Supporting metrics may expose a
phenomenon that CORAL misses, but remain supporting or exploratory; they may
not silently replace the primary metric after results are observed.

### Predefined diagnostic questions and relationships

**WHEN does EEGNet fail?** Examine validation versus official-evaluation
performance, operational session generalization gap, budget sensitivity,
subject heterogeneity, seed instability, and calibration degradation. The
predefined descriptive relationships are:

- session generalization gap versus training budget;
- seed variability versus training budget;
- subject-specific official-evaluation degradation;
- evaluation degradation from 100% to 50% and 25% budgets;
- calibration degradation versus budget;
- calibration degradation versus official-evaluation performance.

**WHERE does EEGNet fail?** Examine model input, temporal convolution,
depthwise spatial convolution, separable pointwise convolution, final latent
representation, and classifier logits. The predefined relationships are
layer-wise representation shift, change in shift across successive processing
stages, and layer-wise shift versus session generalization gap. These analyses
remain descriptive or exploratory unless the sample size and statistical
assumptions justify more.

### Reproducibility dimensions

Every candidate signature must be evaluated for:

1. consistency across subjects;
2. stability across training seeds;
3. stability or interpretable dependence across budgets;
4. robustness across supporting shift metrics;
5. association with actual official-session evaluation degradation.

A single subject, seed, budget, metric, or visually compelling figure is
insufficient. No arbitrary pseudo-precise rule such as “7/9 means
reproducible” is introduced. Conclusions require transparent qualitative
integration across the predefined dimensions, with discordant evidence
reported rather than averaged away.

### Frozen five-state decision logic

1. **Reproducible dominant failure signature.** A broadly consistent pattern
   spans a meaningful range of subjects, is reasonably seed-stable, and is
   associated with evaluation degradation. Dependence on one subject,
   disappearance across seeds, complete metric disagreement, or absence of a
   degradation relationship weakens or disqualifies this state. It permits
   Failure Attribution, not an architecture intervention.
2. **Conditional failure signature.** A reproducible pattern exists only under
   a clearly identified condition such as low budget, high gap, poor
   calibration, a defined subject subset, or a stage. It cannot be presented
   as a universal EEGNet mechanism.
3. **Subject-specific heterogeneous failure.** Subjects show materially
   different temporal, spatial, latent, calibration, or no-shift patterns. A
   single global architecture must not be proposed from this state.
4. **Seed-sensitive or statistically unstable failure.** The apparent stage or
   signature changes substantially with optimization realization. Evidence is
   insufficient for architecture design; training stability or measurement
   reliability must be examined first.
5. **No stable failure signature.** No sufficiently reproducible relationship
   links shift, layer, gap, budget, calibration, and subject-level failure.
   This is a valid negative result and stops Evidence-guided Intervention.

State 1 is neither expected nor preferred. The complete evidence may support
any state, including State 5.

### Interpretation hierarchy

- **Observed Evidence:** directly measured performance, confidence, or shift
  values and patterns.
- **Statistical Result:** quantitative summaries or associations calculated
  from those observations.
- **Interpretation:** a plausible explanation supported by multiple pieces of
  observed and statistical evidence.
- **Hypothesis:** an explanation that remains unverified.
- **Future Intervention:** a separately proposed experiment or model change
  motivated by the preceding evidence.

Representation shift alone is not causal failure attribution. In particular,
high spatial-layer CORAL distance does not imply “implement spatial alignment”
without subject consistency or defined conditionality, seed stability,
reproducibility, and association with actual generalization failure.

### Small-n and multiplicity safeguards

Only nine biological subjects are available. Seeds are repeated optimization
realizations, not biological replication. The audit compares multiple layers,
shift metrics, calibration metrics, and budgets. Consequently, descriptive
Spearman correlations are not causal evidence, nominal significance across
exploratory comparisons must not be over-interpreted, and aggressive tests
must not be added merely to strengthen claims. Effect consistency and
reproducibility are at least as important as isolated p-values. The operational
`validation_accuracy - evaluation_accuracy` gap is useful but is not a pure
causal estimate of session shift.

### Measurement Validity and Controlled Unfreezing

Before scientific classification, every layer/session embedding is checked for
finite values, nonzero feature-value variation, feature shape, covariance rank,
maximum sample-supported rank, and rank fraction. Every shift metric is checked
for finite values, cross-cell minimum/maximum/sample SD, and exact constancy.
These diagnostics test whether the ruler functions; they do not test whether a
scientific relationship is strong.

A valid CORAL metric with weak gap association is a scientific null or weak
relationship and remains primary. CORAL is not invalid merely because MMD² is
stronger or a figure is uninteresting. Metric invalidity requires demonstrable
numerical, mathematical, feature-extraction, shape, saturation, or structural
degeneracy. Natural sample-limited covariance rank alone is recorded and does
not automatically invalidate CORAL.

If measurement or implementation invalidity is demonstrated, scientific
interpretation and five-state classification stop. Any correction requires a
separate dated protocol amendment preserving the original protocol, stating
the invalid assumption, evidence, exact change, exposure to observed cells,
and bias risk. Scientific inconvenience, State 5, weak CORAL correlation, or
a more attractive secondary metric are not valid reasons to unfreeze.

Seed aggregation remains mean-based for biological subject × budget summaries.
Individual seeds, sample SD, minimum, maximum, range, and maximum absolute
deviation from the seed mean remain visible as optimization-instability
diagnostics. A weak aggregate with one extreme seed is not automatically
absence; it may support State 4 if accompanied by broader evidence. Median is
not a replacement primary summary and, if ever shown, is exploratory
sensitivity analysis only.

Before full-matrix launch, the required conditions are: (A) engineering
validity, (B) measurement capability on actual representations, and (C)
analysis sufficiency for the frozen WHEN/WHERE questions. Early cells may be
used only to detect numerical or shape failure—not to select a favorable
metric, layer, budget, subject, or direction.

### Architecture Stop Rule

If the complete audit does not identify a sufficiently reproducible signature
across the five predefined reproducibility dimensions, architecture design
must stop. Failure Cartography tests the assumption that EEGNet failure is
structured enough to support targeted intervention; that assumption may be
falsified or remain unsupported. In that event, further investigation—not an
evidence-themed NAP component—is the correct next step.

### Repository and narrative safeguards

Legacy Artifact Audit experiments remain preserved as scientific history and
are not refactored into the independent cartography pipeline. Repository
continuity remains cheaper and clearer than replacement; no new repository is
created.

The project must not replace the unsupported claim that artifact shortcuts are
the dominant failure with a new absolute claim that cartography will reveal a
clean mechanism and produce NAP. A sophisticated research vocabulary does not
compensate for weak or inconsistent evidence. “Failure Cartography,” “Failure
Attribution,” “Evidence-guided Intervention,” and “Representation Drift” must
refer to actual measurements or experimental stages, not inflate ordinary
engineering. Prefer simpler explanations when they sufficiently account for
the evidence.

Before accepting any future conclusion, answer:

1. What observed evidence directly supports it?
2. Which unverified assumption does it depend on?
3. What evidence would falsify or substantially weaken it?
4. Is there a simpler explanation?
5. Is the pattern stable across subjects?
6. Is it stable across training seeds?
7. Is it robust across budgets?
8. Is it supported by more than one diagnostic metric?
9. Is representation shift associated with evaluation degradation?
10. Are we describing evidence, or renaming uncertainty with sophisticated terminology?

## Repository continuity audit

Continuing in this repository is currently cheaper and scientifically clearer:
the BCI2a loader, frozen split semantics, checkpoints, model builder, and
evaluation boundary are reusable. Legacy Artifact Audit scripts and
`experiments/02_artifact_only.py` / `03_noise_injection.py` remain preserved as
historical artifacts but are not imported by the new pipeline.

The repository has mixed historical result schemas and several specialized
runners, but isolation in `src/failure_cartography.py` and dedicated scripts is
sufficient. No hard-coded absolute path or hardware assumption blocks the new
pipeline; device selection retains the existing CPU/CUDA behavior. A new
repository or broad legacy refactor is not justified at this stage.

## Commands and expected outputs

Minimal one-cell diagnostic smoke run:

```powershell
python -m scripts.run_bci2a_failure_cartography --subjects 1 --budgets 1.0 --training-seeds 42 --output-root results/bci2a_failure_cartography_smoke
```

Full post-hoc matrix (documented, not run in this infrastructure task):

```powershell
python -m scripts.run_bci2a_failure_cartography --subjects 1 2 3 4 5 6 7 8 9 --budgets 1.0 0.5 0.25 --training-seeds 42 43 44 --confirm-full-matrix
python -m scripts.analyze_bci2a_failure_cartography
python -m scripts.plot_bci2a_failure_cartography
```

Expected outputs include `cartography_runs.csv`, `layer_shifts.csv`, per-cell
`risk_coverage.json`, `budget_summary.csv`, `subject_budget_summary.csv`,
`layer_shift_aggregates.csv`, `shift_gap_associations.csv`,
`analysis_status.json`, and seven figures under `figures/`.

## Interpretation discipline and limitations

Every report must separately label hypothesis, experiment, observed evidence,
statistical result, interpretation, limitation, and future intervention.
Between-session validation/evaluation differences also combine session shift
with the fact that validation is a held-out subset of official-0train; they are
not a pure causal estimate of session shift. Activation summaries discard fine
temporal/spatial detail, MMD depends on its kernel, n=9 limits inference, seeds
are not biological replicates, and many layer/metric comparisons create
multiplicity. A simpler explanation—previously incomplete baseline operating-
limit characterization—remains sufficient unless stable evidence supports
more.

The evidence chain is: Baseline → completed Artifact Audit → artifact-shortcut
hypothesis not supported → Failure Cartography → conditional Failure
Attribution → conditional Minimal Intervention → only then potentially
evidence-guided NAP. The latter steps are not authorized by this protocol.

## Protocol Amendment 1 — Shift-Metric Schema Correction (2026-07-20)

This amendment was triggered after the 81 checkpoint-inference cells completed
but before scientific analysis, figures, effect-direction inspection, or
outcome-state classification. The original frozen protocol above is preserved.

1. **Invalid implementation assumption:** every key returned by
   `representation_shift()` was assumed to be a shift metric.
2. **Validity evidence:** the function also returned `feature_dimension`, a
   layer metadata field. The runner consequently wrote 486 dimension rows into
   `layer_shifts.csv`; analysis would have treated constant dimensions as shift
   measurements, correlations, and metric-degeneracy evidence.
3. **Why this is measurement failure:** feature dimension is not a
   source-to-evaluation distance and cannot validly enter shift association or
   metric-validity analysis. This is independent of whether any scientific
   effect is strong, weak, positive, or null.
4. **Exact amendment:** remove `feature_dimension` from
   `representation_shift()` output. Dimension remains recorded correctly in
   `representation_validity.csv`. The five frozen scientific shift metrics and
   their definitions are unchanged.
5. **Previously observed cells:** all 81 inference cells had completed. Only
   matrix counts, integrity fields, and metric names were inspected; no shift
   values, performance directions, correlations, figures, or candidate layers
   were inspected before this amendment.
6. **Bias risk:** low but nonzero because the amendment occurred after matrix
   execution. The change is a type/schema correction that cannot favor a
   layer, metric direction, budget, subject, or outcome state. Transparency is
   maintained by this separate amendment and commit.

Scientific interpretation remains stopped until corrected outputs pass the
measurement-validity gate. The study is no longer described as operating under
an untouched original preregistration; it operates under the original protocol
plus this explicit amendment.
