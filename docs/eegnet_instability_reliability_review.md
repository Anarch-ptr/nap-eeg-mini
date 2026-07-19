# Preregistered EEGNet Training Instability and Measurement Reliability Review

## Status and scope

**Initial status: `NOT_RUN_OR_NOT_PREREGISTERED`.** This protocol is defined
before performing any new instability or measurement-reliability analysis. The
completed Failure Cartography result—State 4, seed-sensitive or statistically
unstable failure—motivates the review but is not selectively re-mined to create
a favorable hypothesis.

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
