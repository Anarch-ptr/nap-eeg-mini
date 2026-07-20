# External Boundary Replication of EEGNet Reliability Findings

**STATUS: `DRAFT_PRE_EXECUTION_PROTOCOL`**

**Scientific execution status:** No Phase A scientific results exist.

**Candidate-specific raw metadata status:** see Section 20; scientific
feasibility remains `PENDING_HUMAN_DECISION`.

This document defines a possible new research project. It is not a mandatory
continuation of the completed NAP-EEG-Mini evidence chain, and it does not
authorize dataset download, adapter implementation, model training, inference,
or scientific analysis. It must not be marked `FROZEN_PRE_EXECUTION_PROTOCOL`
until every `PENDING_HUMAN_DECISION` item and all required raw-metadata facts
have been resolved before execution.

## 1. Research question and study framing

The central question is:

> Under which independent MI-EEG dataset and protocol conditions do the
> seed-dependent predictive variation and finite-sample measurement sensitivity
> observed in BCI IV 2a reproduce, and under which conditions do they not?

The study is an **external boundary replication**, not a confirmation that
EEGNet or MI-EEG decoding is generally unstable. Full replication, partial
replication, non-replication, protocol-conditional results, subject
heterogeneity, and largely unstructured results are all scientifically valid.

## 2. Frozen scope of the original local finding

The completed finding being externally tested has the following exact scope:

| Property | Frozen setting |
|---|---|
| Dataset | BCI Competition IV 2a / BNCI2014-001 |
| Subjects | 9 |
| Architecture | EEGNet |
| Training mode | Subject-specific |
| Training budgets | 100%, 50%, 25% |
| Training seeds | 42, 43, 44 |
| Split seed | 42 |
| Subset seed | 20260719 |
| Primary observation | Seed-dependent predictive/model variation together with finite-sample representation-measurement sensitivity |
| Final classification | `MIXED_MODEL_AND_MEASUREMENT_INSTABILITY` |
| Mechanistic conclusion | `NO_MECHANISTIC_EXPLANATION_ESTABLISHED` |
| Seed-sample conclusion | `UNRESOLVED_DUE_TO_SEED_SAMPLE_LIMITATION` / `SUFFICIENCY_C` |
| Multi-seed replication trigger | `NOT_SATISFIED` |
| Architecture Stop Rule | `ACTIVE` |

The original result is local to this tested dataset, architecture, split,
budget, and seed protocol. The new study does not assume that it generalizes.
It also does not convert the original result into a causal claim about
optimization, representations, classifiers, noise, signal-to-noise ratio, or
small-data overfitting.

## 3. Dataset eligibility and provenance states

A candidate external-replication dataset should preferably provide:

- a Motor Imagery task;
- multiple identifiable subjects;
- multiple sessions or clearly independent recording blocks per subject;
- stable subject, session, and run/block identities;
- recoverable stable trial identities and ordering;
- known label semantics and event timing;
- EEG channel names, types, order, and sampling-rate metadata;
- sufficient trials for preregistered subject-specific limited-data budgets;
- explicit or reconstructable train/evaluation session separation;
- enough raw or exported metadata to audit preprocessing and leakage boundaries.

Dataset size alone does not establish eligibility. Clinical EEG corpora or
other datasets with fundamentally different prediction tasks are not direct
MI-EEG replications.

Candidate status follows this hierarchy:

```text
DOCUMENTATION_ELIGIBLE
-> RAW_METADATA_VERIFICATION_PENDING
-> RAW_METADATA_VERIFIED
-> REPLICATION_FEASIBLE
```

If stable trial identity, stable session identity, or leakage-free session roles
cannot be established, the candidate is `REPLICATION_INFEASIBLE` for the Phase A
estimand. A paper, README, dataset website, or MOABB description cannot by itself
establish `REPLICATION_FEASIBLE`.

### 3.1 Dataset-screening record

No candidate is selected by this draft. Unsupported values must remain
`TO_BE_VERIFIED`. Each candidate must receive a separate record using the
following schema; a documentation reviewer must not fill an unknown field from
memory or inference.

```yaml
dataset_id: TO_BE_VERIFIED
dataset_version: TO_BE_VERIFIED
official_source: TO_BE_VERIFIED
task_type: TO_BE_VERIFIED
MI_task_description: TO_BE_VERIFIED

subject_count: TO_BE_VERIFIED
number_of_subjects: TO_BE_VERIFIED
session_count: TO_BE_VERIFIED
runs_or_blocks: TO_BE_VERIFIED

class_count: TO_BE_VERIFIED
class_semantics: TO_BE_VERIFIED
native_class_comparability: TO_BE_VERIFIED
trials_per_session: TO_BE_VERIFIED
trials_per_class: TO_BE_VERIFIED
total_eligible_training_trials: TO_BE_VERIFIED
training_trials_per_fitted_model: TO_BE_VERIFIED
eligible_training_trials_per_class: TO_BE_VERIFIED
minimum_class_coverage_under_proposed_fractions: TO_BE_VERIFIED

channel_count: TO_BE_VERIFIED
channel_names_available: TO_BE_VERIFIED
sampling_rate: TO_BE_VERIFIED
event_metadata_available: TO_BE_VERIFIED
trial_identity_documented: TO_BE_VERIFIED
session_identity_documented: TO_BE_VERIFIED
run_identity_documented: TO_BE_VERIFIED

inter_session_interval: TO_BE_VERIFIED
same_day_or_cross_day: TO_BE_VERIFIED
cap_repositioning_documented: TO_BE_VERIFIED
acquisition_restart_documented: TO_BE_VERIFIED
recording_environment_changes_documented: TO_BE_VERIFIED
continuous_or_independent_recording: TO_BE_VERIFIED
physical_session_definition_source: TO_BE_VERIFIED

raw_format: TO_BE_VERIFIED
MOABB_support: TO_BE_VERIFIED
subject_specific_training_feasible: TO_BE_VERIFIED
fraction_matched_budget_feasible: TO_BE_VERIFIED
absolute_count_budget_feasible: TO_BE_VERIFIED

original_experiment_definition: TO_BE_VERIFIED
native_raw_file_structure: TO_BE_VERIFIED
framework_abstraction: TO_BE_VERIFIED
multi_view_provenance_status: TO_BE_VERIFIED
candidate_comparability_tier: TO_BE_VERIFIED

known_protocol_differences: TO_BE_VERIFIED
potential_confounders: TO_BE_VERIFIED
documentation_sources: TO_BE_VERIFIED
documentation_status: TO_BE_VERIFIED
raw_metadata_status: RAW_METADATA_VERIFICATION_PENDING
replication_feasibility_status: TO_BE_VERIFIED
notes: TO_BE_VERIFIED
```

`native_class_comparability` must distinguish at least:

- native class structure reasonably comparable to BCI2a;
- partially overlapping class semantics;
- fundamentally different MI task.

This field does not authorize automatic reduction to a common class subset.
Any common-class estimand remains a later explicit human decision.

### 3.2 Documentation-only status discipline

Documentation screening may assign only:

- `DOCUMENTATION_ELIGIBLE`; or
- `DOCUMENTATION_INELIGIBLE`.

It may not assign `RAW_METADATA_VERIFIED` or `REPLICATION_FEASIBLE`. MOABB
support is an `ENGINEERING_PREFERENCE`, not a scientific eligibility criterion.
A non-MOABB dataset may remain eligible when its task, physical-session
structure, provenance, and subject-specific limited-data feasibility are
stronger.

### 3.3 Abstraction and physical-session safeguards

Framework abstractions are not physical ground truth. In particular:

```text
MOABB session != automatically a physical experimental session
MOABB run != automatically an original experimental run
MOABB event_id != automatically the original event semantics
train/test split != automatically a cross-session split
```

Every candidate advancing beyond documentation screening must compare three
views:

1. `ORIGINAL_EXPERIMENT_DEFINITION` from the paper and official documentation;
2. `NATIVE_RAW_FILE_STRUCTURE` and native annotations/events;
3. `FRAMEWORK_ABSTRACTION` exposed by MOABB, MNE, or another loader.

Discrepancies in subjects, sessions, runs, blocks, event codes, trial counts,
class labels, ordering, or excluded recordings must be recorded as one of:

- `PROVENANCE_CONSISTENT`;
- `ABSTRACTION_RENAMING_ONLY`;
- `ABSTRACTION_SEMANTIC_MISMATCH`;
- `PROVENANCE_INCOMPLETE`;
- `REPLICATION_BLOCKING_MISMATCH`.

Unexplained discrepancies remain unresolved and cannot be silently replaced by
framework semantics.

Physical-session definition sources must be recorded as `ORIGINAL_PAPER`,
`OFFICIAL_DATA_DOCUMENTATION`, `RAW_STRUCTURE`, `FRAMEWORK_ABSTRACTION`,
`INFERRED`, or `UNKNOWN`. Unknown intervals remain `UNKNOWN`; a precise interval
must not be inferred. Same-day/cross-day status, cap removal or repositioning,
acquisition restart, recording environment, and continuous versus independent
recording are descriptive protocol properties. They are
`KNOWN_PROTOCOL_DIFFERENCES` or `POTENTIAL_CONFOUNDERS`, not causal findings.

### 3.4 Provisional comparability tiers

Candidates may receive a provisional tier only after the evidence supporting
the tier is recorded:

- `TIER_1_NEAR_DIRECT_REPLICATION`: MI, subject-specific training, at least two
  physically meaningful independent sessions, stable trial identity, feasible
  cross-session evaluation, and feasible limited-data protocol;
- `TIER_2_BOUNDARY_REPLICATION`: retains the MI reliability estimand but has
  substantial documented protocol differences;
- `TIER_3_DIFFERENT_ESTIMAND`: materially changes the question, for example
  single-session run-to-run evaluation, motor execution rather than imagery, or
  pooled cross-subject training.

Tier 3 candidates cannot serve as direct Phase A replication datasets. Many
runs must not be treated as many physical sessions, and a large subject count
does not by itself improve candidate suitability.

### 3.5 Required raw-metadata reconnaissance

Before freezing dataset-specific protocol details, a read-only provenance
inspection must complete the following checklist:

- enumerate native subject identifiers;
- enumerate sessions and compare their physical meaning across documentation,
  raw structure, and framework abstraction;
- enumerate runs/blocks without promoting runs to sessions;
- enumerate annotations, events, event codes, and class labels;
- count actual trials per session and per native class;
- verify stable trial identity and ordering;
- verify stable session identity;
- verify run/block identity where applicable;
- verify no ambiguous or duplicated trial identifiers;
- verify event ordering against native file structure;
- verify sampling rate, channels, channel types, order, and units;
- verify raw file format and dataset version;
- record excluded, missing, or framework-dropped recordings;
- verify known preprocessing before scientific epoch construction;
- verify that train/evaluation roles can be assigned without overlap;
- verify actual usable trial counts after protocol eligibility rules;
- verify per-class coverage under every proposed fraction or absolute count;
- assign a multi-view provenance status and record every discrepancy.

Initial reconnaissance should inspect raw/native structure, annotations, events,
labels, channels, and sampling rate before constructing scientific epochs.
Epoch construction is deferred unless it is strictly necessary to verify
event-to-trial identity.

This reconnaissance is engineering/provenance work, not scientific analysis: it
must not load a model, run inference, or calculate performance. Any future
reconnaissance code must be isolated under `scripts/recon/`, must not modify the
training pipeline, and must not import BCI2a, EEGNet, Failure Cartography, or
Instability Review runners. This draft creates no reconnaissance code.

### 3.6 Documentation Screening Results

The following classifications record the first documentation-level candidate
screening. They are based on approved documentation-screening conclusions only.
They do not establish `RAW_METADATA_VERIFIED` or `REPLICATION_FEASIBLE`, and
they do not select the final Phase A dataset. Raw/native provenance inspection
is still required.

#### Lee2019_MI

| Field | Documentation-level record |
|---|---|
| Dataset | `Lee2019_MI` |
| Documentation status | `DOCUMENTATION_ELIGIBLE` |
| Provisional tier | `TIER_1_NEAR_DIRECT_REPLICATION` |
| Raw reconnaissance priority | `PRIMARY` |
| Raw metadata status | `RAW_METADATA_VERIFIED` |
| Replication feasibility | `PENDING_HUMAN_DECISION` |

Documentation-level strengths:

- relatively large subject population;
- documented multiple-session structure;
- Motor Imagery task;
- subject-specific external replication appears conceptually possible;
- sufficient documented trial volume for a limited-data protocol appears
  plausible.

Unresolved issues requiring raw/native provenance reconnaissance:

- exact physical-session semantics;
- exact inter-session timing;
- offline versus online phase semantics;
- which trials contain ground-truth labels;
- native trial identity;
- MOABB session/run mapping;
- whether independently labeled trials can support the intended cross-session
  protocol.

These were unresolved at documentation screening time; Section 20 records the
subsequent cohort-wide raw-metadata verification without rewriting that earlier
screening stage.

#### BNCI2015-001

| Field | Documentation-level record |
|---|---|
| Dataset | `BNCI2015-001` |
| Documentation status | `DOCUMENTATION_ELIGIBLE` |
| Provisional tier | `TIER_1_NEAR_DIRECT_REPLICATION` |
| Raw reconnaissance priority | `SECONDARY` |
| Raw metadata status | `RAW_METADATA_VERIFIED` |
| Replication feasibility | `PENDING_HUMAN_DECISION` |

Documentation-level strengths:

- subject-specific Motor Imagery dataset;
- multiple documented sessions;
- substantial trial volume per session appears compatible with limited-data
  analysis;
- useful candidate for comparing original experiment semantics against the
  MOABB abstraction.

Unresolved issues requiring raw/native provenance reconnaissance:

- heterogeneous two-session/three-session structure across subjects;
- exact subject-level session availability;
- physical inter-session timing;
- native run/session identity;
- exact MOABB session mapping;
- whether a common Session-1-to-Session-2 primary estimand is feasible for all
  eligible subjects.

The two-session/three-session discrepancy is not resolved by documentation
screening.

#### Zhou2016

| Field | Documentation-level record |
|---|---|
| Dataset | `Zhou2016` |
| Documentation status | `DOCUMENTATION_ELIGIBLE` |
| Provisional tier | `TIER_1_NEAR_DIRECT_REPLICATION` |
| Additional limitation | `LOW_SUBJECT_COUNT_LIMITATION` |
| Raw reconnaissance priority | `RESERVE` |
| Raw metadata status | `PENDING_RAW_METADATA_VERIFICATION` |
| Replication feasibility | `TO_BE_VERIFIED` |

Documentation-level strengths:

- genuine multi-session Motor Imagery structure;
- strong physical cross-session relevance;
- useful candidate for testing session-boundary robustness.

The principal documentation-level limitation is the very small subject
population. This does not by itself make the dataset scientifically ineligible,
but it prevents promotion to the primary population-level replication
candidate.

Unresolved issues requiring raw/native provenance reconnaissance:

- native trial/session/run provenance;
- exact usable trial counts;
- native versus derived/BIDS representation;
- framework-abstraction consistency.

#### Shin2017A

| Field | Documentation-level record |
|---|---|
| Dataset | `Shin2017A` |
| Documentation status | `DOCUMENTATION_ELIGIBLE` |
| Provisional tier | `TIER_2_BOUNDARY_REPLICATION` |
| Raw reconnaissance priority | `NOT_FIRST_ROUND` |
| Raw metadata status | `PENDING_RAW_METADATA_VERIFICATION` |
| Replication feasibility | `TO_BE_VERIFIED` |

Documentation-level strengths:

- multiple MI recording sessions;
- useful subject population.

Important documented or unresolved protocol differences are:

- low trial count per MI session;
- strong prior preprocessing in the released data;
- ICA/EOG-related preprocessing history;
- uncertain physical inter-session interval;
- limited-data fractions may create a substantially different optimization
  regime.

These differences do not make `Shin2017A` scientifically useless. They make it
better suited to a later boundary-replication question than to the first
near-direct Phase A candidate.

#### Provisional raw-reconnaissance shortlist

`RAW_METADATA_RECON_SHORTLIST` is:

1. **Primary:** `Lee2019_MI`;
2. **Secondary:** `BNCI2015-001`;
3. **Reserve:** `Zhou2016`;
4. **Boundary-only for current Phase A:** `Shin2017A`.

This shortlist is provisional. It does not mean that `Lee2019_MI` is the final
selected dataset or that `BNCI2015-001` is replication-feasible. It determines
only which candidates should receive the first raw metadata/provenance
reconnaissance.

For `Lee2019_MI` and `BNCI2015-001`, future reconnaissance must explicitly
compare:

1. `ORIGINAL_EXPERIMENT_DEFINITION`;
2. `NATIVE_RAW_FILE_STRUCTURE`;
3. `FRAMEWORK_ABSTRACTION`.

It may later assign one of `PROVENANCE_CONSISTENT`,
`ABSTRACTION_RENAMING_ONLY`, `ABSTRACTION_SEMANTIC_MISMATCH`,
`PROVENANCE_INCOMPLETE`, or `REPLICATION_BLOCKING_MISMATCH`. No such provenance
classification is assigned by documentation screening.

The following physical-session rules remain binding:

```text
Run != Session
Train/Test split != Cross-session split
Multiple recording blocks != automatically independent sessions
MOABB session label != automatically physical-session ground truth
```

Raw reconnaissance must establish physical-session semantics before any
session-role mapping is frozen.

External replication does not require exact equality with BCI2a in class count,
channel count, sampling rate, or trial count. The primary target remains the
within-dataset reliability response under limited-data and cross-session
conditions, not direct absolute accuracy comparison between datasets. The
native-task/common-class estimand, fraction-matched/absolute-count design, and
final session-role mapping remain `PENDING_HUMAN_DECISION`.

## 4. Primary scientific estimand

The primary estimand is:

> **Subject-specific limited-data cross-session reliability.**

Each fitted model corresponds to one subject. Subjects must not be pooled for
the Phase A primary analysis. The protocol distinguishes:

- `number_of_subjects`, which affects estimation of population heterogeneity;
- `number_of_training_trials_per_model`, which controls the information
  available to each subject-specific fit.

A dataset with more subjects does not automatically provide more trials to each
fitted model. Cross-subject pooled training changes the estimand and is outside
Phase A.

## 5. Session-role semantics

Dataset adapters and result records must use abstract roles:

- `TRAIN_SESSION_ROLE`;
- `VALIDATION_SOURCE`;
- `EVALUATION_SESSION_ROLE`.

BCI2a-specific names such as `0train` and `1test` are not assumed. For a dataset
with more than two sessions, the rule may use a predefined training/evaluation
pair, chronological earliest-to-later evaluation, a fixed session-pair design,
or a predefined leave-one-session-out design. The final rule must be selected
from verified metadata and frozen before scientific execution, never after
viewing performance.

The candidate record must document the number of sessions, run/block structure,
known temporal separation, same-day versus different-day acquisition, cap
removal or repositioning, and documented acquisition-environment changes.
Differences from BCI2a are `KNOWN_PROTOCOL_DIFFERENCE` and
`POTENTIAL_CONFOUNDER`, not demonstrated causal explanations.

**Session-role rule:** `PENDING_HUMAN_DECISION` after raw-metadata verification.

## 6. Per-model training-budget semantics

Every fitted model must report:

```text
budget_fraction
actual_training_trial_count
per_class_training_trial_count
```

Two distinct analyses are available:

### Analysis A: fraction-matched replication

Within-dataset fractions such as 100%, 50%, and 25% test whether reliability
changes as the available training data in that dataset is reduced. This does
not match absolute trial counts across datasets.

### Analysis B: absolute-count boundary analysis

Common absolute trial counts test whether cross-dataset differences persist
when per-model sample sizes are approximately controlled. Counts must be shown
feasible by verified metadata, retain class coverage, and be frozen before
scientific outcomes are inspected. Values such as 144, 72, or 36 are not
assumed by this draft.

**Phase A budget design:** `PENDING_HUMAN_DECISION` among Analysis A, Analysis B,
or both as separately reported analyses. The analyses must never be silently
combined.

Configured batch size is not a physical minimum training-set size. Future
freezing must consider actual samples, per-class coverage, effective batch
behavior, `drop_last`, optimizer updates, validation opportunities, and whether
very small sets create an incomparable optimization regime.

## 7. Seed policy

**Status: `SEED_POLICY_PENDING_DATASET_AND_COMPUTE_REVIEW`.**

The Phase A seed list must be fixed before training. Seeds 42, 43, and 44 are
not automatically reused merely because they were used in BCI2a. No seed may be
added sequentially after outcomes are inspected. The final policy must specify
the seed list, its evidential scope, compute boundary, and stopping rule.

## 8. Predictive endpoints

Hard-prediction evidence remains logically independent of representation
distance. Core endpoints are:

- pairwise prediction disagreement and agreement;
- correctness stability;
- all-seed-correct fraction;
- all-seed-wrong fraction;
- mixed-correctness fraction;
- error-set Jaccard.

Where verified class semantics permit, supporting endpoints include:

- classwise recall variation;
- classwise precision variation.

Probability/logit diagnostics may include:

- absolute predicted-probability or confidence difference;
- logit-margin difference;
- Jensen-Shannon divergence.

Representation metrics cannot be the sole basis of the replication outcome.

### 8.1 Performance reporting across different class counts

Raw Balanced Accuracy must be reported. If descriptive cross-dataset
normalization is needed, chance-normalized Balanced Accuracy lift may also be
reported:

```text
normalized_lift = (balanced_accuracy - 1/K) / (1 - 1/K)
```

Here `K` is the native task's class count. This maps chance-level Balanced
Accuracy to zero and perfect Balanced Accuracy to one. It is not a causal
adjustment for task difficulty, class semantics, session structure, or data
quality. Raw accuracy must not be ranked directly across datasets as evidence
of greater reliability.

If a reduced common class subset is proposed, it must be frozen before
execution and reported as a separate estimand from native-task replication.

## 9. Measurement-reliability endpoints

Potential endpoints are:

- deterministic repeatability;
- deterministic subsampling sensitivity;
- CORAL;
- RBF-MMD squared;
- normalized feature-mean shift;
- normalized feature-variance shift;
- covariance Frobenius difference;
- centered linear CKA with its documented limitations.

CKA analysis remains `GROUPED_WITHIN_LAYER`. Absolute CKA must not be compared
across layers or architectures. High-dimensional finite-sample baselines,
feature-dimension differences, compressed dynamic range, spectrum
concentration, and representation-summary differences must remain explicit.
No metric is assumed to reveal a uniquely true representation distance.

If an estimator detects little hidden-representation divergence while hard
predictions differ, the permitted conclusion is only that the estimator did
not detect substantial divergence under its defined geometry while predictive
divergence remained observable. Classifier localization requires independent
evidence.

## 10. Preregistered outcome categories

- **Outcome A:** Predictive seed variation and measurement sensitivity both
  reproduce.
- **Outcome B:** Predictive seed variation reproduces, but measurement
  sensitivity is weak or materially different.
- **Outcome C:** Measurement sensitivity reproduces, but predictive seed
  variation is weak.
- **Outcome D:** Neither main pattern reproduces.
- **Outcome E:** Results are strongly conditional on subject, session
  structure, trial budget, or protocol.

All outcomes are valid. Non-replication is not experimental failure, and full
replication under one additional dataset does not establish universality.

## 11. Interpretation boundaries

The report must distinguish `OBSERVED`, `SUPPORTED`, `CONSISTENT_WITH`,
`PLAUSIBLE`, `UNRESOLVED`, `NOT_DETECTED`, and `NOT_REPLICATED` claims.

Without independent evidence, the following statements are prohibited:

- EEGNet is generally unstable;
- MI-EEG deep learning is inherently unstable;
- small data causes optimization instability;
- low signal-to-noise ratio causes the observed variation;
- representation instability causes prediction instability;
- classifier noise is the sole mechanism;
- measurement bias explains all observed variation;
- session interval, channels, preprocessing, population, or trial count caused
  a replication difference.

The ordinary competing explanation remains that limited task-relevant
information, nuisance/noise variability, finite training samples, and
stochastic optimization may yield high estimator variance and different fitted
decision functions. This is not described as proven overfitting or a special
EEG-specific mechanism.

Allowed non-replication language is:

> The reliability pattern observed in BCI IV 2a did not reproduce under the
> tested external dataset and protocol. The original finding should therefore
> not be interpreted as a universal property of MI-EEG decoding.

Allowed full-replication language is:

> The original BCI2a reliability pattern reproduced under one additional
> independent MI-EEG dataset and protocol.

## 12. Pipeline and leakage safeguards

Future Phase A implementation must guarantee:

- normalization fitted using training data only;
- evaluation-session data used post hoc only;
- no evaluation-based checkpoint selection or hyperparameter tuning;
- stable trial, subject, session, and run/block identities;
- deterministic subset provenance and explicit actual trial counts;
- matched trial identity and ordering across seed comparisons;
- no train/validation/evaluation overlap;
- dataset name and version provenance;
- raw/exported-file provenance where available;
- preprocessing and resampling provenance;
- label mapping and class-count provenance;
- checkpoint architecture/configuration provenance;
- explicit session-role and split identities.

## 13. Future DatasetAdapter contract

This contract is descriptive only and is not implemented by this protocol task.
It must expose at minimum:

```text
dataset_id
dataset_version
subject_id
session_id
run_or_block_id
trial_id
eeg_tensor
label
label_semantics
channel_names
channel_types
sampling_rate
epoch_window
preprocessing_spec
session_role
split_identity
actual_training_trial_count
```

Subject IDs are opaque identifiers. The contract does not assume integer
subjects, four classes, 22 channels, a single evaluation session, or BCI2a
session names.

## 14. Future ModelReliabilityAdapter contract

Phase A remains EEGNet-only. This descriptive abstraction prevents EEGNet
module names from leaking into the scientific protocol; it does not begin
cross-architecture analysis.

The adapter must expose:

```text
architecture_id
build(data_spec, model_config)
forward_logits(model, x)
load_checkpoint(model, checkpoint)
representation_stages()
capture(model, stage_specs, x)
state_diagnostics()
```

Each `StageSpec` must record:

```text
stage_id
semantic_role
module_path_or_callable
summary_function
feature_shape_metadata
comparison_scope = WITHIN_LAYER_ONLY
```

Checkpoint loading must validate architecture, data shape, class semantics,
preprocessing, split provenance, and model-state compatibility. State
diagnostics such as BatchNorm comparisons are optional capabilities, not
universal architecture endpoints.

## 15. Synthetic integrity requirements

Before real Phase A execution, future implementation must pass synthetic tests
for:

- stable trial identity and ordering;
- stable subject/session/run identity;
- matched seed-comparison ordering;
- deterministic class-aware subset selection;
- no train/validation/evaluation overlap;
- training-only normalization provenance;
- checkpoint and resolved-config provenance;
- DatasetAdapter output schema;
- ModelReliabilityAdapter output and stage schema;
- optional multiple-session handling;
- rejection of ambiguous session roles;
- rejection of non-reconstructable split identities;
- support for non-integer subject IDs and non-four-class tasks.

These requirements are frozen here; the tests are not implemented in this
protocol task.

## 16. Phase A stop rule

Phase A ends after the external boundary replication has been completed and
reviewed. It does not automatically authorize Phase B.

Permitted Phase A decisions are:

- **A:** Proceed to separately approved cross-architecture boundary analysis.
- **B:** First investigate dataset/protocol boundary conditions under a new
  protocol.
- **C:** Stop because the pattern did not reproduce meaningfully.
- **D:** Stop because provenance or scientific comparability is insufficient.

Phase B requires a new explicit human decision and a separate protocol. No
architecture intervention is authorized by any Phase A outcome.

## 17. Boundary of the completed NAP-EEG-Mini project

The original evidence chain remains closed. This new project must not
retroactively rewrite the original evidence freeze. Later evidence may
strengthen, weaken, narrow, or contextualize the external validity of the local
BCI2a finding, but original evidence, later evidence, and revised external-validity
interpretation must remain traceable as separate stages.

NAP implementation, EEGNet modification, architectural intervention, automatic
multi-seed escalation, and reopening of the original mechanistic investigation
remain unauthorized.

## 18. Unresolved decisions before protocol freeze

The following items are `PENDING_HUMAN_DECISION`:

1. candidate external dataset;
2. native-task-only versus an additional preregistered common-class estimand;
3. exact session-role selection rule after raw-metadata verification;
4. Phase A budget design: fraction-matched, absolute-count, or both separately;
5. exact fractions and/or absolute counts supported by verified class counts;
6. minimum per-class coverage and smallest acceptable optimization regime;
7. batch size, `drop_last`, optimizer-update, and validation-opportunity policy;
8. fixed training-seed list and compute boundary;
9. exact replication-classification decision rules and aggregation hierarchy;
10. treatment of datasets with missing run/block identity but stable session and
    trial identity;
11. output artifact retention and dataset/version hashing policy.

The protocol may become `FROZEN_PRE_EXECUTION_PROTOCOL` only after raw metadata
is verified, the candidate is classified `REPLICATION_FEASIBLE`, and every item
above is resolved before scientific execution.

## 19. Exact next permitted step

The next permitted step after this documentation update is **raw metadata /
provenance reconnaissance** for the first-round candidates, in this order:

1. `Lee2019_MI`;
2. `BNCI2015-001`.

That future work must remain engineering/provenance-only. It may inspect the
original, native/raw, and framework views needed to resolve dataset identities
and physical-session semantics. It must not train models, run inference,
calculate performance or reliability metrics, freeze scientific conclusions,
or change the protocol status automatically.

## 20. Raw metadata / provenance reconnaissance

This section records engineering observations only. The protocol remains
`DRAFT_PRE_EXECUTION_PROTOCOL`; neither candidate is classified
`REPLICATION_FEASIBLE`, and no final dataset or session-role decision has been
made. No filtering, resampling, normalization, epoch construction, model
loading, inference, or scientific metric calculation was performed.

### 20.1 Lee2019_MI

The framework exposes 54 subjects, and all 54 were inspected. Raw metadata is
`RAW_METADATA_VERIFIED`; provenance is `ABSTRACTION_RENAMING_ONLY`. Under the
inspected native metadata and MOABB representation,
`NO_COHORT_WIDE_STRUCTURAL_BLOCKER_OBSERVED`. This is structural verification,
not a claim that the dataset is unbiased, scientifically reliable, or expected
to reproduce the BCI2a result.

The following structure was observed for every subject:

| Physical session | Native phase | Native events | Native label-vector entries | Label interpretation |
|---|---|---:|---:|---|
| S1 | `offline_train` | 100 | 100 | ground-truth labels present |
| S1 | `online_test` | 100 | 100 | values exist, but are not documented as online-phase ground truth |
| S2 | `offline_train` | 100 | 100 | ground-truth labels present |
| S2 | `online_test` | 100 | 100 | values exist, but are not documented as online-phase ground truth |

The framework exposes physical S1/S2 as session IDs `0`/`1` and exposes
`1train` and `4test` within each session. Each framework run contains 100 event
markers, split 50/50 between codes 1 and 2; the class mapping is right hand = 1
and left hand = 2. Sampling rate, channel count, and channel order were
consistent across all subjects. The observed sample rate is 1,000 Hz.

All 54 subjects expose ground-truth labels in both S1 offline `1train` and S2
offline `1train`, so `OFFLINE_COMMON_SESSION_PAIR_AVAILABLE` holds for 54/54.
This does not freeze S1 as training or S2 as evaluation. Online `4test` exposes
events and label-like values, but its documentation states that MI online runs
do not have trial ground truth. Online status therefore remains
`ONLINE_LABEL_SEMANTICS_UNRESOLVED` for both sessions of every subject.

The structural trial-retention waterfall is identical across all 216
subject/session/phase cells:

```text
documented = 100
native observed = 100
framework observed = 100
structurally eligible = 100
scientifically usable = NOT_YET_DETERMINED
trial-loss classification = NO_OBSERVED_LOSS
```

No subject has a missing session, missing run, native/framework count mismatch,
sampling-rate anomaly, channel-count/order anomaly, duplicated structural ID,
ambiguous trial identity, or unresolved session mapping. In total, 21,600
structural trial identities were checked. Scientifically usable trial counts
remain `NOT_YET_DETERMINED`. Whether the two labeled offline sessions should
become training/evaluation roles remains `PENDING_HUMAN_DECISION`.

### 20.2 BNCI2015-001

All 12 framework-listed subjects were inspected. Every observed native session
contains one run with 200 events (100 right-hand and 100 feet), and every
corresponding framework session retains all 200 events. The observed sample
rate is 512 Hz. Structurally eligible count is therefore 200 per session;
scientifically usable count remains `NOT_YET_DETERMINED`.

| Subjects | Native sessions | Framework sessions | Physical mapping |
|---|---|---|---|
| 1–7, 12 | A, B | `0A`, `1B` | S1, S2 |
| 8–11 | A, B, C | `0A`, `1B`, `2C` | S1, S2, S3 |

Common-pair coverage is: S1 = 12 subjects, S2 = 12, S3 = 4, verified S1+S2
= 12, and verified S1+S2+S3 = 4. Thus
`PRIMARY_COMMON_SESSION_PAIR_STRUCTURALLY_POSSIBLE`, while the session-role
decision remains `PENDING_HUMAN_DECISION`. Available loader metadata and local
documentation do not establish why S3 was assigned, so its status is
`S3_ASSIGNMENT_CONDITION_UNKNOWN`. S3 is not treated as exchangeable or as an
automatic replicate.

Native suffixes and framework IDs preserve chronological A/B/C identity in all
observed subjects, and deterministic unique trial IDs can be reconstructed.
There is no observed native-to-framework trial loss. However, the MOABB dataset
object declares two sessions per subject while the same loader exposes a third
session for subjects 8–11. Raw metadata is therefore
`RAW_METADATA_VERIFIED`, but provenance is conservatively classified
`ABSTRACTION_SEMANTIC_MISMATCH` rather than `PROVENANCE_CONSISTENT`. This class
metadata conflict does not silently exclude three-session subjects and does not
by itself invalidate the common S1/S2 pair.

Human review records BNCI2015-001 as an active Phase A candidate. The common
S1/S2 structure across all 12 subjects is
`STRUCTURALLY_ACCEPTABLE_FOR_CONTINUED_CONSIDERATION`, but physical homogeneity
has not been established. Subjects 8–11 must not be excluded solely because
they have S3, and S3 must not enter a primary analysis automatically. Any S3
use would require a separately defined secondary analysis.

### 20.3 Cache-path provenance

The initial reconnaissance passed the absolute Windows path
`E:\nap-eeg-mini\data\external_recon` to MOABB 1.5.0. Its downloader sanitized
the colon in the full destination, converting `E:` to `E-`; the resulting
relative path was then resolved under the working directory as
`E:\nap-eeg-mini\E-\nap-eeg-mini\data\external_recon`. The reconnaissance
script now passes the repository-relative argument `data\external_recon` while
setting the effective process-level MNE/MOABB root to the intended absolute
directory. New files therefore resolve under
`E:\nap-eeg-mini\data\external_recon`.

The old nested cache was not moved, deleted, renamed, or redownloaded. Lee
subject 1 was reused from that read-only legacy root; missing subjects were
downloaded only to the corrected root. Cache handling is engineering
provenance, not scientific evidence.

### 20.4 Interpretation and next gate

The machine-readable artifacts contain the subject-level availability matrix,
per-run retention waterfall, label counts, channel metadata, source paths, and
the checked trial-identity status and counts. They contain no EEG arrays or
scientific results.

Lee2019_MI now has sufficient cohort-wide structural provenance to enter review
alongside BNCI2015-001. `RAW_METADATA_VERIFIED` is not
`REPLICATION_FEASIBLE`, and neither is `FINAL_PHASE_A_DATASET`.

The exact next allowed action is `HUMAN_COMPARATIVE_DATASET_SELECTION_REVIEW`
using the two candidate provenance records. That review must not collapse the
candidates into a numerical score or select based on expected scientific
results. Only humans may select a candidate and resolve the pending scientific
protocol decisions in Section 18.
