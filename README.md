# NAP-EEG-Mini

**Reliable failure characterization and mechanism falsification for small-sample EEG decoding.**

NAP-EEG-Mini is a reproducible research project investigating why EEG decoding performance degrades under limited-data conditions.

The project originally explored whether artifact-related shortcut learning could motivate a reliability-aware NAP architecture. However, the artifact hypothesis was not supported by the formal audit. Rather than proceeding with an unsupported model, the project was redirected toward systematically characterizing the actual failure mode of a sealed EEGNet baseline on BCI Competition IV 2a.

The final project does **not** introduce a new NAP model. Instead, it provides a preregistered experimental chain for identifying a robust small-sample failure, testing alternative explanations, evaluating candidate mechanisms, and stopping model development when the evidence does not support a mechanistic claim.

---

## Research Question

The central question of this project is:

> **Why does EEGNet become vulnerable when subject-specific motor-imagery training data are limited?**

The investigation follows four principles:

1. Verify that the failure is real and reproducible.
2. Eliminate simple optimization and regularization explanations.
3. Test candidate mechanisms using training-data-only measurements.
4. Require controlled intervention evidence before translating an observed association into a model or architectural claim.

---

## Main Findings

### 1. Artifact shortcut hypothesis was not supported

The initial project hypothesis was that EEG decoding might rely on artifact-related shortcut signals.

Formal artifact audits did not provide sufficient evidence for a robust selective artifact dependency.

**Decision:** NAP-A development was stopped.

---

### 2. EEGNet shows a robust small-sample failure

A preregistered robustness audit evaluated EEGNet using 100%, 50%, and 25% subject-specific training budgets across nine BCI Competition IV 2a subjects and three training seeds.

The primary 100%-to-25% comparison showed:

- Median degradation: **17.25 percentage points**
- Subjects degrading by at least 3 pp: **8/9**
- Positive median degradation under all three training seeds

Final classification:

`STRONG_FAILURE`

This establishes a reproducible limited-data vulnerability under the sealed experimental recipe.

---

### 3. Reduced optimizer-update count does not explain the failure

Because smaller datasets receive fewer mini-batch updates under a fixed-epoch protocol, the 25% condition was retrained using an exact optimizer-update-matched design.

The 25% condition received:

- 400 optimizer updates
- 50 validation/checkpoint opportunities

The residual performance gap remained:

- Median residual gap: **13.89 pp**
- Subjects with residual gap >= 3 pp: **8/9**

Final classification:

`PERSISTENT_STRONG_FAILURE`

Reduced optimization budget therefore explains only part of the observed small-sample vulnerability.

---

### 4. Stronger weight decay provides no meaningful group-level benefit

A preregistered simple control increased Adam weight decay from:

`1e-4` → `1e-3`

while preserving the update-matched 25% training protocol.

Results:

- Median control gain: **0.00 pp**
- Subjects improving by at least 3 pp: **0/9**
- Median post-control residual gap: **13.43 pp**

Final classification:

`NO_MEANINGFUL_CONTROL_BENEFIT`

This result does not imply that regularization in general is ineffective. It only shows that this specific stronger-weight-decay control does not resolve the observed failure.

---

## Mechanism Investigation

### Log-bandpower geometry

The first zero-new-training mechanism audit examined training-data-only properties including:

- Within-class dispersion
- Between-class separation
- Separability ratio
- Trial-level feature variability

No training-data-only feature reached the preregistered `ROBUST_CANDIDATE_SIGNAL` threshold.

---

### Subset representativeness

The frozen 25% training subsets were compared with the omitted portion of the original fixed training pool.

The audit examined:

- Class centroid shift
- Class covariance shift
- Same-class coverage distance
- Worst-class coverage distance

No feature reached `ROBUST_CANDIDATE_SIGNAL`.

In particular, same-class coverage distance showed almost no association with residual failure.

The subset-representativeness hypothesis was therefore stopped within the preregistered log-bandpower representation.

---

### Spatial covariance geometry

A final independently motivated property audit examined cross-channel spatial covariance structure using:

- Trial covariance matrices
- Trace normalization
- Fixed SPD regularization
- Log-Euclidean geometry

Three frozen training-data-only properties were tested:

- `cov_within_class_dispersion`
- `cov_between_class_separation`
- `cov_separability_ratio`

A strong cross-subject association was identified for covariance between-class separation:

- Spearman rho: **0.917**
- Kendall tau: **0.778**
- Leave-one-subject-out Spearman range: **0.881–0.952**
- Direction stability: **9/9**

Final classification:

`ROBUST_CANDIDATE_SIGNAL`

The observed direction was unexpected:

> Subjects with higher covariance between-class separation in the frozen 25% training subset tended to show larger residual small-sample failure.

This result was treated as an observational marker rather than a causal mechanism.

---

## Controlled Covariance Intervention

To test whether covariance separation was intervention-relevant, matched LOW- and HIGH-separation training subsets were constructed for every subject.

The matched subsets preserved:

- Identical sample counts
- Identical per-class counts
- Similar run distributions
- Similar acquisition-order coverage
- Similar covariance within-class dispersion

The feasibility audit succeeded for all nine subjects.

Final classification:

`INTERVENTION_FEASIBLE`

A formal intervention experiment then trained EEGNet on the frozen LOW- and HIGH-separation subsets.

Experimental matrix:

- 9 subjects
- 2 conditions
- 3 training seeds
- 54 total runs
- 400 optimizer updates per run
- 50 validation/checkpoint opportunities per run

The primary effect was defined as:

`HIGH accuracy - LOW accuracy`

Results:

- Median effect: **0.00 pp**
- HIGH worse: **4/9 subjects**
- HIGH better: **4/9 subjects**
- Tie: **1/9 subject**

Seed-level effect direction was also inconsistent.

Final classification:

`HETEROGENEOUS_OR_WEAK_INTERVENTION_EFFECT`

---

## Final Scientific Conclusion

The project identified a robust and reproducible small-sample vulnerability in EEGNet.

The failure persisted after optimizer-update matching and was not meaningfully improved by a preregistered stronger-weight-decay control.

Artifact-related shortcut learning, log-bandpower geometry, and subset representativeness did not provide sufficient evidence for a general mechanism.

Spatial covariance between-class separation showed a strong and leave-one-subject-out-stable cross-subject association with residual small-sample vulnerability. However, controlled within-subject manipulation of the same property produced heterogeneous and directionally inconsistent effects.

Therefore:

> **Covariance between-class separation is retained as a robust cross-subject observational marker, but it is not supported as a universal intervention-relevant mechanism of small-sample EEGNet failure under the tested design.**

The mechanism underlying the robust small-sample vulnerability remains unresolved.

The project deliberately stops mechanism-driven architecture development rather than introducing an unsupported NAP module.

---

## Evidence Chain

```text
Artifact shortcut hypothesis
        ↓
NOT SUPPORTED
        ↓
STOP NAP-A

Small-sample robustness audit
        ↓
STRONG_FAILURE

Optimizer-update-matched diagnostic
        ↓
PERSISTENT_STRONG_FAILURE

Stronger weight-decay control
        ↓
NO_MEANINGFUL_CONTROL_BENEFIT

Log-bandpower mechanism audit
        ↓
NO ROBUST TRAINING-DATA-ONLY SIGNAL

Subset representativeness audit
        ↓
NOT SUPPORTED IN FROZEN LOG-BANDPOWER SPACE

Spatial covariance audit
        ↓
ROBUST_CANDIDATE_SIGNAL
rho = 0.917

Matched-subset feasibility
        ↓
INTERVENTION_FEASIBLE

LOW/HIGH covariance-separation intervention
        ↓
HETEROGENEOUS_OR_WEAK_INTERVENTION_EFFECT

Final decision
        ↓
STOP COVARIANCE MECHANISM ESCALATION
STOP NAP DEVELOPMENT
MECHANISM REMAINS UNRESOLVED

Key Methodological Lesson

A central result of this study is the distinction between:

cross-subject observational association and within-subject intervention relevance.

A training-data property may strongly correlate with vulnerability across subjects without producing a common directional effect when manipulated within the same subject.

In this project:

Strong cross-subject covariance association did not translate into a consistent within-subject intervention effect.

This finding reinforces the need to separate predictive markers from manipulable mechanisms before using them to motivate new model architectures.

```

## Project Structure

configs/
    Experiment and audit configurations

docs/
    Preregistered protocols
    Audit documentation
    Limitations
    Final scientific synthesis

scripts/
    Formal experiment runners
    Frozen analysis scripts

src/
    EEGNet training infrastructure
    Small-sample audit logic
    Mechanism analysis modules
    Covariance intervention modules

tests/
    Synthetic integrity and classification tests

results/
    Formal experimental outputs
    Subject-level summaries
    Seed diagnostics
    Machine-readable analyses

## Reproducibility

The project uses:

Fixed subject splits
Deterministic subset selection
Explicit split, subset, and training seeds
Subject-level statistical aggregation
Frozen analysis thresholds
Training-data-only mechanism features
Official-test isolation during training and checkpoint selection
Optimizer-update matching
Synthetic tests for protocol integrity
Git commits to freeze experimental definitions before observing formal outcomes

The final repository test suite contains:

207 passing tests

## Final Project Status

Completed scientific chain: archived through the heterogeneous covariance
intervention STOP gate.

Current engineering/research phase: EEGNet Failure Cartography infrastructure.
This phase tests—without assuming—that cross-session and limited-data failure
has reproducible structure. It does not reopen the artifact hypothesis or
authorize NAP. The full 81-cell cartography experiment has not been run.

Robust small-sample failure: Supported

Optimizer-update-only explanation: Not supported

Single stronger-weight-decay solution: Not supported

Artifact-shortcut mechanism: Not supported

Log-bandpower geometry mechanism: Not supported

Subset-representativeness mechanism: Not supported in the frozen log-bandpower space

Spatial covariance observational signal: Supported

Universal covariance intervention effect: Not supported

General causal mechanism: Unidentified

NAP justification: Not established

NAP implementation: No

## Documentation

The complete scientific evidence chain is documented in:

docs/final_scientific_synthesis.md

Study limitations are documented in:

docs/limitations.md

Individual preregistered protocols and audit reports are available under:

docs/

## License

This project is released under the MIT License.
