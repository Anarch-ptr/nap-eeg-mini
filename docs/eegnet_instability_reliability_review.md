# Preregistered EEGNet Training Instability and Measurement Reliability Review

## Status and scope

**Initial status: `NOT_RUN_OR_NOT_PREREGISTERED`.** This protocol is defined
before performing any new instability or measurement-reliability analysis. The
completed Failure Cartography result—State 4, seed-sensitive or statistically
unstable failure—motivates the review but is not selectively re-mined to create
a favorable hypothesis.

**Final execution status: `COMPLETED_ZERO_TRAINING_REVIEW`.** The initial status
above records the preregistered state; the separated post-result section at the
end records the completed evidence without rewriting the frozen rules.

The primary evidence source is the existing 81 frozen checkpoints: A01–A09 ×
100%/50%/25% budgets × seeds 42/43/44. The review permits deterministic
post-hoc recomputation on the exact saved validation and official-evaluation
trials. It authorizes no retraining, new seed, model change, adaptation,
architecture, or NAP component.

The completed Failure Cartography branch is a scientific checkpoint and should
receive human review, then be pushed and merged before a future
`feat/eegnet-instability-review` branch is created from updated `main`. This
document does not itself create that branch or merge work.

## Central scientific question

> What is the simplest explanation consistent with the observed three-seed
> instability: optimization-dependent predictive variation, measurement
> unreliability, ordinary high-variance small-data learning, or insufficient
> evidence?

More specifically: do independently trained EEGNet checkpoints converge to
meaningfully different predictive and representational solutions, are the
current diagnostic measurements unstable under finite samples and activation
summarization, or do both contribute? None is preferred in advance.

Three seeds demonstrate sensitivity under seeds 42–44. They cannot establish
the population distribution of optimization outcomes, multimodality, rare
failure basins, heavy tails, or inherent EEGNet instability.

## Experimental-unit hierarchy

- Biological unit: **subject**.
- Primary descriptive unit: **subject × training budget**.
- Seeds: repeated optimization realizations nested within that unit.
- Seed pairs: 42–43, 42–44, and 43–44; these are dependent within-unit
  comparisons, not biological samples.
- Trials: matched descriptive observations used to compare frozen functions;
  they are not independent subjects.

Report individual seeds and pairs, then within subject × budget mean, sample
SD, minimum, maximum, range, and maximum absolute deviation from the seed mean
where defined. Do not replace the frozen mean with a post-hoc median. Any
median is labeled exploratory aggregation sensitivity only.

## Frozen optimization-instability diagnostics

All comparisons use identical trial identities and labels across seeds,
separately for validation and official evaluation.

### Prediction and error consistency

For each seed pair report prediction disagreement rate, agreement rate, and
Cohen's kappa between predicted labels. For all three seeds report fractions of
trials that are all-seed correct, all-seed wrong, or have mixed correctness.

For each pair define evaluation error sets `E_A` and `E_B` and freeze Jaccard
similarity:

`J(E_A,E_B) = |E_A ∩ E_B| / |E_A ∪ E_B|`.

If both error sets are empty, define Jaccard as 1; if exactly one is empty,
define it as 0. Preserve raw intersection, union, and set sizes.

### Class-wise instability

For every checkpoint retain confusion matrix, per-class recall, and per-class
precision. Compare seed-pair absolute differences by class and report whether
disagreement is concentrated or diffuse. No class-specific intervention or
class selection is authorized.

### Probability and margin instability

Convert logits to softmax probabilities. For matched trial `i` and seed pair
A/B, the primary probability-distribution distance is Jensen–Shannon
divergence with natural logarithms:

`JS(p_i,q_i) = 0.5 KL(p_i || m_i) + 0.5 KL(q_i || m_i)`,
where `m_i=(p_i+q_i)/2` and probabilities are protected by `epsilon=1e-12`.
Report the trial distribution and its mean/SD/min/max, without choosing a
threshold.

Define logit margin as the largest logit minus the second-largest logit for one
model. Report paired absolute margin difference and predicted-class
probability difference. These are descriptive and cannot alone establish
separate solution basins.

### Training-record instability

Reuse saved `metrics.csv`, checkpoint metadata, and run summaries where
present. Record missing provenance explicitly. Compare best validation epoch,
best validation accuracy/loss, final training/validation values, and aligned
50-epoch trajectory differences. Curve comparisons are descriptive; no epoch
is reselected and no checkpoint is changed.

### Frozen BatchNorm-state sensitivity

The actual EEGNet contains BatchNorm modules `block1.1`, `block1.3`, and
`block2.2`. For each seed pair compare saved `running_mean` and `running_var`
using relative L2 difference and cosine similarity, retaining vector length and
raw norms. Do not recompute statistics from validation or official evaluation.
BatchNorm similarity can weaken but cannot alone eliminate a different-model
solution explanation.

## Frozen representation-solution stability

This review compares **different frozen models on identical matched inputs**;
Failure Cartography compared **one model across sessions**. These questions
must not be conflated.

Use the unchanged diagnostic summaries at temporal convolution (`block1.0`),
depthwise spatial convolution (`block1.2`), separable pointwise convolution
(`block2.1`), final latent (`block2`), and classifier logits (`classifier`).
Model input is captured as an integrity control and should yield identical
representations; it is not learned-solution evidence.

The frozen primary representation-similarity metric is centered linear CKA.
For matched `n × d` summary matrices X and Y, center each feature column to Xc
and Yc and calculate:

`CKA(X,Y) = ||XcᵀYc||²_F / sqrt(||XcᵀXc||²_F ||YcᵀYc||²_F)`.

A zero or non-finite denominator is a measurement-integrity failure, not a
zero-similarity result. CKA is selected because it compares matched samples,
supports equal or different feature widths, and is invariant to isotropic
scaling and orthogonal feature transformations. Report validation and official
evaluation separately. Do not replace CKA after observing results.

Predictive and representational equivalence remain distinct:

1. stable predictions / stable representations;
2. stable predictions / unstable representations;
3. unstable predictions / stable representations;
4. unstable predictions / unstable representations.

Only cases 3–4 indicate predictive instability; none proves a particular
optimization-landscape topology.

## Frozen measurement-reliability diagnostics

### Deterministic repeatability

Repeat checkpoint inference, activation summarization, CORAL, MMD², mean/
variance shift, covariance difference, and CKA with identical inputs. Require
identical trial identities and numerically identical or explicitly tolerance-
bounded outputs (`absolute tolerance=1e-12` for NumPy diagnostic recomputation).
Any nondeterminism is investigated before interpretation.

### Preregistered sample-size sensitivity

For every subject × budget × seed × session/layer metric, draw without
replacement at fractions 0.50, 0.75, and 1.00 of each available representation
set, using `floor(n*fraction)` with a minimum of two samples. Use 20 fixed
repeat seeds `20260721` through `20260740`. Sampling is independently generated
within validation and official evaluation, while source/evaluation trial
identities remain disjoint as frozen.

For each fraction report mean, sample SD, minimum, maximum, range, and deviation
from the corresponding full-data estimate. This tests finite-sample estimator
stability; it is not population inference and cannot select a replacement
metric. The 1.00 fraction is a deterministic identity/repeatability reference.

### Synthetic metric-sensitivity controls

On copied synthetic diagnostic matrices only, apply separately:

- a fixed mean offset of `0.5` per feature;
- variance scaling by `1.5` after centering;
- a fixed deterministic off-diagonal linear mixing to alter covariance.

Verify that the mathematically relevant metrics respond in the expected
direction relative to an identical-copy zero-shift control. These controls do
not modify EEG trials, activations, checkpoints, or scientific outputs.

### Representation-summary limitation

The frozen summaries preserve per-feature-map mean and SD for inputs and
convolutional stages, then flatten final latent/logit outputs. They discard fine
temporal order, spatial detail within maps, phase, and transient structure. No
alternative summary is applied in this review. A scientifically necessary
replacement requires a separate amendment before touching scientific data.

## Frozen interpretation logic

### A. Optimization-dependent model instability

Substantial prediction disagreement, low error-set overlap, different
probabilities/margins/classes, divergent trajectories or frozen states, and
low matched-input CKA, while measurement diagnostics are reliable. This does
not establish inherent instability or authorize architecture design.

### B. Measurement-dominant instability

Predictions, error sets, probabilities, BN state, and matched-input
representations are relatively similar, while shift estimates show poor
repeatability or strong preregistered subsample sensitivity. This weakens a
model-instability interpretation.

### C. Mixed model and measurement instability

Both frozen model behavior and measurement estimates show meaningful
instability. The contributions must remain separated before attribution.

### D. Ordinary high-variance small-data learning

Moderate seed variation, diffuse errors, differing representations, no stable
class/layer/trajectory/BN anomaly, and valid measurements are adequately
explained by a deep model fitted to limited, noisy, nonstationary MI-EEG. Do
not rename ordinary variance as a specialized mechanism.

### E. Insufficient evidence

The three seeds or available provenance cannot distinguish the explanations.
`UNRESOLVED_DUE_TO_SEED_SAMPLE_LIMITATION` is permitted. Do not force a cleaner
classification; report a primary interpretation and important secondary
characteristics if evidence is mixed.

A specialized mechanism may only be considered if it explains an observation
that ordinary small-data variance cannot, is reproducible across subjects and
seeds, is supported by independent metrics, predicts performance degradation,
and makes a distinct testable prediction.

## Seed-sufficiency gate and replication hierarchy

- **Seed Sufficiency A:** three seeds suffice only for the narrow conclusion,
  for example stable frozen functions plus measurement instability. Additional
  seeds are not automatically needed.
- **Seed Sufficiency B:** meaningful predictive/representational disagreement
  is present and measurement reliability is acceptable, but three seeds cannot
  characterize its distribution. This may justify a separately preregistered
  multi-seed replication.
- **Seed Sufficiency C:** evidence is too noisy or ambiguous for model-versus-
  measurement attribution. Stop with
  `UNRESOLVED_DUE_TO_SEED_SAMPLE_LIMITATION` unless replication value clearly
  justifies its cost.

Replication priority is:

1. measurement instability strongly supported → improve measurement; do not
   add seeds solely for model-instability characterization;
2. predictive seed instability strongly suggested with reliable measurement
   → preregister one complete multi-seed replication;
3. ordinary small-data overfitting sufficient → record and stop mechanistic
   excavation;
4. unresolved → no architecture; human decision on replication value/cost.

No incremental `3 → inspect → add more → inspect` sequence is allowed. A future
replication must freeze its entire seed list, subjects, budgets, training cells,
metrics, and stopping rules before training. Ten seeds, if ever selected, are a
broader sample—not a complete optimization-landscape map.

## Leakage and integrity safeguards

- Official evaluation remains post-hoc evaluation only.
- No official-evaluation sample or statistic enters training, normalization,
  BatchNorm recomputation, checkpoint selection, tuning, thresholds,
  architecture design, or adaptation.
- Validation and evaluation identities must exactly match saved provenance
  across all seed comparisons.
- Checkpoint hashes/identities and resolved configs are recorded before
  inference; models remain in evaluation mode.
- Per-trial predictions and activations are diagnostic outputs and must not be
  used to tune a model.
- Missing histories or states are reported, never silently excluded.

## Narrative safeguards and limitations

State 4 establishes sensitivity under three tested seeds, not that EEGNet is
inherently unstable, has multiple basins, or that random initialization causes
cross-session failure. Failure to localize a layer does not prove meaningful
shift is absent; the summaries and distances are incomplete.

Only three seeds, nine subjects, one dataset, one architecture, three budgets,
and one frozen preprocessing pipeline are available. Seed-pair results are
dependent, matched trials are not biological replicates, histories may be
incomplete, CKA does not imply functional equivalence, BN state covers only one
part of the network, and finite-sample reliability may vary strongly by layer
dimension.

Use ordinary terms: different predictions, representations, or model states.
Do not infer solution basins, manifolds, topology, or latent discontinuities
without direct evidence. No result in this review automatically authorizes
NAP. The objective is to decide whether State 4 contains enough reliable
structure to justify further non-architectural investigation—not to rescue a
model-development narrative.

## Pre-execution addendum: effective dimension and within-layer CKA

This addendum was frozen before executing the zero-training scientific review.
It clarifies measurement interpretation and creates neither a new gate nor a
seventh mechanistic diagnostic family. No primary metric is changed.

Nominal feature dimension is not assumed to equal effective dimension. For
every preregistered stage and session, record per-feature sample variance,
exactly zero-variance feature count/fraction, variance quantiles, centered
matrix rank, singular-value summaries, and covariance participation-ratio
effective dimension:

`effective_dimension = (sum_i lambda_i)^2 / sum_i lambda_i^2`,

where `lambda_i = singular_value_i^2 / (n-1)` are finite non-negative sample-
covariance eigenvalues. A numerically zero spectrum is reported as effective
dimension zero. This statistic is a descriptive measurement safeguard, not a
primary scientific endpoint, and no collapse threshold is defined.

The documented 58-by-496 `block2` regime may reflect finite-sample CKA bias,
effective representation collapse, or both. High absolute `block2` CKA is not
direct evidence of representational equivalence. If its values have limited
resolution relative to predictive variation, report
`REPRESENTATION_MEASUREMENT_LIMITATION`; do not replace CKA or declare model
representation stability.

All scientific CKA analysis is `GROUPED_WITHIN_LAYER`. Absolute CKA values must
not be ranked, plotted, tabulated, or interpreted across layers because feature
dimension, rank, sample-to-dimension ratio, finite-sample baseline, and summary
semantics differ. Cross-layer discussion is restricted to qualitative within-
layer variation patterns. CKA denotes global summarized linear similarity, not
functional equivalence, identical basins, manifold identity, or topology.

Predictive divergence can coexist with apparently stable CKA because of range
compression, summary information loss, or insensitivity to local decision-
relevant differences. Conversely, representation variation with stable
predictions is not predictive failure. Hierarchical divergence remains
descriptive and cannot localize a causal failure to the classifier.

The final review explicitly permits `NO_MECHANISTIC_EXPLANATION_ESTABLISHED`
and `UNRESOLVED_DUE_TO_SEED_SAMPLE_LIMITATION`. Behavior may be described as
consistent with high-variance learning under limited noisy data, but ordinary
high variance is not a proven root cause. Before using that description, audit
preprocessing, windows, normalization, subsets, checkpoint selection, sample
alignment, and dataset identity. Lack of structure must not trigger new post-
hoc metrics, representation methods, or mechanistic families.

Every CKA result section must state that values are analyzed within layer only
and that absolute magnitudes are not compared across layers. The `block2`
section must separately state its high-dimensional finite-sample baseline and
compressed range; any effective-dimension concentration is reported as an
additional, not interchangeable, limitation.

For representation-shift subsampling, validation and official evaluation use
independent deterministic RNG streams derived with NumPy `SeedSequence` from
`[repeat_seed, domain_id]`, with domain ids 0 and 1 respectively. For relative
deviation from the full estimate, freeze
`abs(estimate-full) / max(abs(full), 1e-12)`. Fractions, rounding, and repeat
seeds remain 0.50/0.75/1.00, floor with minimum two, and 20260721–20260740.

For the already-preregistered BatchNorm relative L2 diagnostic, freeze
`||a-b||_2 / max(||a||_2, ||b||_2, 1e-12)`. Cosine similarity uses the standard
dot-product definition; it is 1 when both vectors have zero norm and 0 when
exactly one has zero norm. Raw norms and vector length are retained.

After this addendum, protocol and diagnostic-family proliferation stops unless
an implementation bug, blocking integrity/leakage problem, or demonstrably
invalid measurement is discovered. Reporting follows: observed evidence,
descriptive result, measurement limitation, competing explanations,
conservative interpretation, seed-sufficiency decision, and allowed next step.

## Post-result section: completed zero-training review

### Observed Evidence

All 81 frozen checkpoints were analyzed without training. Validation and
official-evaluation targets, session-local trial identities, ordering, frozen
splits, and normalization provenance matched across seeds in all 54 subject by
budget by session groups. Model-input CKA was exactly 1 for every seed pair,
providing an integrity control. Official evaluation remained post-hoc only.

Mean subject-level pairwise prediction disagreement increased as training data
decreased. On validation it was 33.78%, 44.38%, and 50.64% at 100%, 50%, and
25% budgets; on official evaluation it was 36.77%, 44.55%, and 51.77%.
Corresponding mixed-correctness fractions were 37.74%, 45.79%, and 51.34% on
validation and 38.54%, 41.47%, and 46.72% on official evaluation. These are
descriptive summaries over nine biological subjects at each budget, not 81
independent biological observations.

Error sets were neither identical nor disjoint. Mean subject-level pairwise
Jaccard overlap ranged from 0.480 to 0.545 on validation and 0.559 to 0.603 on
official evaluation across budgets. Higher overlap at lower budgets coexisted
with more prediction disagreement and more all-seed-wrong trials, consistent
with a mixture of shared task difficulty and seed-dependent decisions.

Probability behavior was not a monotonic copy of hard-label disagreement.
Official-evaluation mean absolute confidence difference was 0.142, 0.148, and
0.106; absolute logit-margin difference was 0.941, 0.743, and 0.412; and JS
divergence was 0.0631, 0.0576, and 0.0310 from 100% to 25%. Thus hard-label
disagreement increased while probability/logit distances became smaller at the
lowest budget, plausibly because weak models produced smaller margins rather
than a single coherent divergence pattern.

Recall variation occurred in all four classes and was heterogeneous by subject,
budget, and session. No class was the largest-range class in a majority of the
27 units: validation counts were 5/7/10/5 for classes 0/1/2/3, and official-
evaluation counts were 12/5/7/3. This does not support a universal class-specific
mechanism.

Training histories varied across seeds. Mean within-subject best-epoch ranges
were 16.56, 16.44, and 18.56 epochs across the three budgets; best-validation-
accuracy ranges were 12.45, 8.81, and 9.20 percentage points. Epoch-wise
validation-accuracy seed ranges averaged about 9.3-11.2 percentage points.
These are optimization-history differences, not evidence for basin topology.

Frozen BatchNorm states also differed. Running-mean relative L2 summaries were
large but must be read with raw norms: block1 running means were only around
1e-3 in norm. Running-variance cosine similarity was heterogeneous (mean 0.806
at `block1.1`, 0.470 at `block1.3`, and 0.905 at `block2.2`). BatchNorm therefore
supports seed-dependent state variation but neither localizes nor explains it.

### Statistical / Descriptive Result

The three tested seeds produced materially different predictions on identical
trials, with strong subject heterogeneity and greater average hard-label
disagreement at lower training budgets. Differences were diffuse across
classes, histories, frozen BN states, probabilities, and summarized
representations. No single diagnostic family supplied a stable specialized
mechanism across subjects, budgets, and sessions.

CKA values are analyzed within layer only. Absolute CKA magnitudes are not
compared across layers because feature dimension, rank, finite-sample baseline,
and representation summarization differ across stages.

- Within `block1.0`, seed-pair variation was usually narrow but remained
  subject-specific, with larger ranges in some limited-data units.
- Within `block1.2`, the three seed pairs showed heterogeneous variation across
  subject by budget units; no uniform budget direction was present.
- Within `block2.1`, some units had broad seed-pair ranges while others were
  tightly grouped, again without stable subject-independent localization.
- Within `block2`, pairwise values retained measurable within-stage resolution
  across subjects, budgets, and seed pairs, but their absolute magnitude is not
  direct equivalence evidence.
- Within `classifier`, summarized-logit CKA varied substantially by subject and
  seed pair. This is decision-output variation, not proof that failure occurs in
  or is caused by the classifier.

The tested seeds can therefore preserve relatively similar early summarized
patterns in some units while showing greater decision-output variation. Small
upstream differences, nonlinear amplification, summary insensitivity, decision-
boundary sensitivity, and ordinary training variance remain alternatives.

### Measurement Limitation

The final latent representation has a documented high-dimensional finite-sample
CKA baseline and compressed dynamic range. High absolute block2 CKA values are
therefore not interpreted directly as strong representational equivalence.

The effective-dimension addendum showed that finite-sample bias is not the only
relevant consideration. No block2 feature was exactly zero-variance, and ranks
reached the sample bounds: 57 for validation and 287 for official evaluation.
Nevertheless, covariance participation-ratio effective dimension was much lower
than nominal dimension: validation mean 18.20 (range 6.07-36.93) and official-
evaluation mean 23.06 (range 4.12-78.51). This is spectrum concentration, not a
thresholded claim of representation collapse. Finite-sample bias and effective-
dimension concentration are separate, coexisting limitations.

The early summaries retain per-map means and standard deviations but discard
fine temporal order, phase, transients, and spatial detail. Block2 flattening
retains pooled temporal positions but is high-dimensional relative to validation
sample count. Consequently, apparently stable global linear similarity cannot
establish complete representational or functional equivalence. The current
block2 CKA retains some within-stage variation, so it is not rejected, but all
block2-specific conclusions are weakened by
`REPRESENTATION_MEASUREMENT_LIMITATION`.

Failure Cartography shift estimates showed finite-sample sensitivity. Across
486 checkpoint by layer units, mean absolute relative deviation from the full
estimate at 50%/75% sampling was 112.96%/55.34% for CORAL, 43.68%/21.87% for
RBF-MMD squared, 23.22%/13.75% for mean shift, 37.70%/22.37% for variance shift,
and 39.00%/22.58% for covariance Frobenius difference. CORAL includes some very
small full estimates, so its relative deviations can be amplified; all full
estimates remained above 1e-12. The 100% identity reference reproduced exactly.
No metric is replaced or selected post hoc.

### Competing Explanation

- **A, optimization-dependent predictive/model variation:** supported under
  seeds 42/43/44 by disagreement, mixed correctness, history, state, probability,
  and within-stage representation differences. It does not establish inherent
  instability, multiple basins, or a causal optimization mechanism.
- **B, measurement-dominant instability:** not supported as the sole explanation
  because hard predictions differ directly on matched trials. Subsampling
  sensitivity does weaken previous shift-metric attribution.
- **C, mixed model and measurement instability:** best matches the joint evidence:
  frozen model behavior varies while several shift estimators are composition-
  sensitive.
- **D, ordinary high-variance small-data learning:** remains a simple plausible
  description because variation is heterogeneous and no specialized mechanism
  is stable. It is not a proven cause.
- **E, insufficient evidence:** applies to mechanistic attribution and to the
  distribution of optimization outcomes, which three seeds cannot characterize.

### Pipeline-Level Alternative

The pipeline review found `NO_SYSTEMATIC_PIPELINE_ISSUE_FOUND`: all cells used
8-32 Hz, 0-4 s, split seed 42, subset seed 20260719, identical within-group trial
identities and class-balanced nested subsets, train-subset normalization,
best-validation checkpoints, and post-hoc-only official evaluation. No subject-
specific preprocessing branch, evaluation fitting, sample-order mismatch, or
checkpoint-selection inconsistency was found. This reduces an obvious pipeline
explanation but cannot prove that every unmeasured implementation effect is absent.

### Conservative Interpretation

Under seeds 42, 43, and 44, EEGNet exhibits seed-dependent predictive and model-
state variation together with finite-sample sensitivity in prior shift metrics.
The behavior is consistent with high-variance learning under limited and noisy
data, but the evidence is insufficient to attribute it to one optimization,
representation, or measurement mechanism. Global summarized linear similarity
does not by itself explain the observed predictive divergence.

### Final Review Classification

Primary descriptive classification:
`MIXED_MODEL_AND_MEASUREMENT_INSTABILITY`.

Mechanistic classification:
`NO_MECHANISTIC_EXPLANATION_ESTABLISHED`.

Seed-sample conclusion:
`UNRESOLVED_DUE_TO_SEED_SAMPLE_LIMITATION`.

### Seed Sufficiency Classification

`SUFFICIENCY_C`: three seeds establish the narrow fact of seed-dependent
variation, but model-versus-measurement attribution and the optimization-outcome
distribution remain too ambiguous for a stronger mechanism claim.

### Multi-Seed Replication Trigger Decision

`NOT_SATISFIED`. Prediction disagreement is clear, but error overlap is not
uniformly low, probability/logit differences do not strengthen coherently with
limited data, representation patterns remain heterogeneous, and shift-metric
subsampling reliability is limited. Additional seeds are not authorized merely
because they could provide more data.

### Allowed Next Step

Human review and evidence freeze. Stop mechanistic and architectural escalation.
No NAP, intervention, new representation metric, or additional training seed is
authorized. The Architecture Stop Rule remains `ACTIVE`.

## Final evidence-freeze addendum

This addendum authorizes no new analysis. It freezes conclusion dependence,
narrative transition, replication restraint, and retrospective interpretation
for future README, SOP, proposal, or publication writing. The completed
classifications remain provisional interpretations under the tested protocol,
not permanent truths.

### What the mixed conclusion depends on

`MIXED_MODEL_AND_MEASUREMENT_INSTABILITY` does not depend on CORAL alone. The
model/predictive component is independently supported by hard prediction
disagreement on identical trials, mixed correctness, training and best-
validation variation, frozen BatchNorm-state variation, and heterogeneous
within-layer representation patterns. The measurement component is supported
by finite-sample sensitivity in CORAL, RBF-MMD squared, normalized mean and
variance shifts, and covariance Frobenius difference.

A future small-sample-unbiased distance estimator could reweight the estimated
measurement contribution without erasing independently observed model
variation. Conclusion invalidation and conclusion reweighting must remain
distinct. The mixed interpretation should be reconsidered only if a more
appropriate estimator is independently validated, substantially more stable
under the same finite-sample conditions, and changes interpretation
reproducibly across subjects and budgets. Possible revisions include weaker
measurement evidence with retained model variation, strengthened mixed
evidence, or narrowed historical measurement claims. Original evidence,
methodological limitation, new evidence, and revised interpretation must remain
separate stages.

The review does not estimate percentage contributions from model and
measurement instability. No causal variance decomposition such as “60% model,
40% measurement” is supported. Mixed means that both sources have credible
evidence, not that their relative causal weights are known.

### Honest project narrative

The historical trajectory is preserved:

artifact-related shortcut learning as a plausible initial hypothesis
→ Artifact Audit
→ insufficient support for the hypothesized dominant mechanism
→ architecture intervention stopped
→ Failure Cartography
→ no stable layer localization
→ Architecture Stop Rule activated
→ Instability/Reliability Review
→ seed-dependent predictive variation and finite-sample measurement
sensitivity observed
→ no single mechanistic explanation established.

The project did not begin with perfect knowledge of the correct question, and
negative results are not retrospectively promoted into a dramatic breakthrough.
The appropriate contribution is progressive narrowing of the hypothesis space
through experiments capable of falsifying desired interventions. The initial
artifact hypothesis was scientifically reasonable, not foolish, but the early
narrative may have assigned it more confidence than baseline evidence
justified. The Artifact Audit corrected that overcommitment before architecture
construction.

A defensible research-statement lesson is the transition from “How can I make
my proposed model work?” to “What evidence would justify building the model at
all?” Preferred language is: the evidence collected in this project did not
justify introducing NAP as an evidence-guided intervention. The project neither
proved NAP unnecessary in general nor proved that EEGNet has no fixable
weakness.

Future public summaries should use a factual structure—research question,
initial hypothesis, audit design, observed evidence, unsupported
interpretations, current limits, and stopping decision. Avoid claims of a
definitive mechanism, complete explanation, revolutionary pivot, or proof that
architecture innovation is unnecessary.

### Replication restraint

The preregistered multi-seed trigger remains `NOT_SATISFIED`; it must not be
retrospectively changed because the result is scientifically unsatisfying.
Future multi-seed work is not forbidden, but it must begin a new evidence chain
with a new question, explicit motivation, frozen seed list, subjects, budgets,
metrics, distributional questions, and no sequential seed addition after
intermediate inspection.

A legitimate future question could characterize the broader distribution of
optimization outcomes under a fixed protocol. It must not add seeds until the
current mechanism becomes clearer, nor search preferentially for bimodality,
multiple basins, or another dramatic answer. Unimodal, diffuse, multimodal, or
unstructured outcomes must be equally acceptable in advance. Scientific
curiosity and dissatisfaction with the present narrative are not equivalent
motivations.

Questions about more seeds, unbiased distances, another dataset, or another
architecture remain allowed as `NEW_RESEARCH_QUESTIONS`, not mandatory
continuations. The current chain ends because its preregistered escalation
conditions were not satisfied.

### Final project boundary

The strongest project-level claim is: the completed evidence chain did not
identify a reproducible failure mechanism sufficient to justify an evidence-
guided NAP intervention. The evidence supports a small-sample vulnerability,
does not support the initial artifact shortcut as the dominant tested
mechanism, identifies no stable layer localization, observes seed-dependent
predictive variation and finite-sample measurement sensitivity, and remains
limited by three seeds for stronger attribution.

The project’s academic-training value lies in falsifiable hypotheses,
preserving negative results, separating engineering from scientific validity,
preregistering interpretation, auditing measurement, resisting post-hoc metric
selection, distinguishing description from cause, and stopping escalation when
evidence is insufficient. These are documented behaviors, not a claim of
superior scientific maturity.

Evidence freeze preserves simultaneously:

- `MIXED_MODEL_AND_MEASUREMENT_INSTABILITY`;
- `NO_MECHANISTIC_EXPLANATION_ESTABLISHED`;
- `UNRESOLVED_DUE_TO_SEED_SAMPLE_LIMITATION`;
- `SUFFICIENCY_C`;
- `MULTI_SEED_REPLICATION_TRIGGER = NOT_SATISFIED`;
- `ARCHITECTURE_STOP_RULE = ACTIVE`.

These statements are compatible: real seed-dependent model variation and
measurement sensitivity coexist; their causal contributions are not
decomposed; no single mechanism is established; three seeds do not characterize
the optimization distribution; and neither additional training nor an
architecture intervention is automatically justified.
