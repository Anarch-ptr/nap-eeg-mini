# Artifact Audit Final Results

## 1. Research Question

The Artifact Audit asked:

> Does the sealed EEGNet baseline rely on artifact-related or ocular/frontal shortcut information for motor-imagery classification?

The purpose was not to demonstrate that NAP-A works. It was to test, independently of NAP-A, whether the baseline exhibits artifact-shortcut dependency. Artifact information, EEG contamination, and classifier dependency were treated as separate claims throughout.

## 2. Baseline Status

The baseline was sealed before the Artifact Audit. `main` and `origin/main` pointed to baseline commit `0102bc0` (`feat: add BCI2a multi-seed baseline evaluation`) when the audit branch was created. The experiment uses subject-specific BCI Competition IV 2a EEGNet models for A01--A09 and seeds 42, 43, and 44. Official `0train` is separated from official `1test`; saved training/validation splits, train-subset normalization, resolved configurations, and 27 best-validation checkpoints are frozen. Every frozen-model intervention reproduced the corresponding clean test accuracy exactly. The audit did not modify baseline architecture, training, checkpoints, or test selection.

## 3. Phase 0B — EOG Decodability

Independent three-channel EOG-only classification produced:

| Statistic | Accuracy |
|---|---:|
| Cross-subject mean | 59.93% |
| Median | 51.39% |
| Range | 40.86%--84.95% |

The highest subject means were approximately A05 84.95%, A07 81.48%, and A08 77.20%.

> Independent EOG-channel activity contains substantial class-correlated decodable information.

Here, EOG means EOG-channel activity within the baseline 8--32 Hz preprocessing passband, not unfiltered ocular activity. Decodability alone does not show that the EEGNet baseline uses an EOG shortcut.

## 4. Phase 0C — Temporal EOG Information

| Window | Cross-subject EOG-only accuracy |
|---|---:|
| Early, 0--1 s | 63.46% |
| Middle, 1.5--2.5 s | 39.66% |
| Late, 3--4 s | 27.49% |

Label-shuffle controls were near chance: A01 24.31%, A02 23.61%, and A05 21.53%.

> EOG class information is concentrated in early cue/early-MI periods, persists into middle MI for a subject-dependent subset, and is weak or near chance in late MI for most subjects.

The official session boundary, train-only normalization, label-shuffle controls, and held-out evaluation did not reveal an evident pipeline or evaluation leakage explanation.

## 5. Phase 1 — EOG–EEG Coupling

Held-out same-trial minus same-class cross-trial coupling was:

| Window | Mean ΔR² | Subjects positive |
|---|---:|---:|
| Early | 0.01947 | 8/9 |
| Middle | 0.07126 | 8/9 |
| Late | 0.11357 | 9/9 |
| Full | 0.06551 | 8/9 |

Coupling was spatially strongest over frontal/frontocentral channels, followed by central, parietal, and occipital regions. A03 remained an explicitly reported cross-session mapping exception.

> Trial-specific EOG-related EEG coupling exists beyond shared class/task structure.

Coupling is evidence about statistical correspondence, not evidence that the classifier depends on the coupled component. Its late-window maximum also dissociates coupling strength from the early-dominant EOG class information.

## 6. Phase 2A — Direct EOG-Coupled Dependency

The primary accuracy dependency contrast was `(true removal - clean) - (energy-matched cross-trial removal - clean)` at alpha 1.0:

| Window | Cross-subject contrast |
|---|---:|
| Early | -0.13 pp |
| Middle | -0.10 pp |
| Late | +0.32 pp |
| Full | -0.35 pp |

True component removal sometimes reduced performance, but matched cross-trial removal caused similar changes. Contrasts were near zero and inconsistent across subjects and seeds. Alpha 0.5 did not produce a clear dose-response.

> No robust selective dependency on trial-specific EOG-coupled EEG components was found.

In particular, strong coupling does not imply classifier dependency.

## 7. Phase 2B — Spatial Masking

Primary full-window, six-channel masking produced:

| Group | Mean accuracy change |
|---|---:|
| Frontal | -14.21 pp |
| Matched non-frontal | -15.64 pp |
| Five fixed random groups, mean | approximately -15.82 pp |

Frontal-minus-matched was +1.43 pp: the frontal intervention was not more damaging. Frontal effects were also not extreme within the frozen random-control distribution. Early, middle, and late secondary masks produced the same absence of stable frontal specificity.

> Frontal masking does not impair performance more than matched non-frontal or random-channel masking.

The common degradation is more consistent with generic EEG information loss. It cannot be interpreted as ocular dependence merely because frontal channels were removed.

## 8. Phase 2B — Noise Perturbation

Standardized Gaussian noise showed a clear general dose-response: sigma 0.25 caused small degradation, sigma 0.50 moderate degradation, and sigma 1.00 large degradation. The frontal, matched, and random six-channel conditions remained close at each dose.

| Sigma | Frontal-minus-matched accuracy change |
|---:|---:|
| 0.25 | +0.09 pp |
| 0.50 | +0.24 pp |
| 1.00 | +0.26 pp |

The conditions used the same six-channel base noise realization for each subject, baseline seed, and sigma; maximum cross-group RMS mismatch was `5.96e-8`.

> EEGNet exhibits general dose-dependent noise vulnerability, but no frontal-specific vulnerability.

## 9. Three-Layer Evidence Model

| Layer | Question | Evidence | Conclusion |
|---|---|---|---|
| 1: information | Does artifact-related EOG activity contain class information? | EOG-only decoding, temporal audit, label-shuffle controls | Supported |
| 2: coupling | Does trial-specific EOG-related activity couple into EEG beyond class/task structure? | Same-trial versus same-class cross-trial held-out OLS | Supported |
| 3: dependency | Does the frozen classifier selectively depend on EOG-coupled or frontal information? | Matched component removal, masking, random groups, and matched noise | Not supported |

> Artifact presence, EEG contamination/coupling, and classifier dependency are distinct scientific claims.

Evidence for one layer cannot substitute for evidence at another.

## 10. Final Conclusion

> No robust selective artifact-related dependency evidence was found for the sealed EEGNet baseline under the pre-registered EOG-coupled removal, frontal masking, matched-channel controls, random-channel controls, and noise perturbation tests.

This does not establish that the baseline is completely artifact-free. The audit covers specified linear synchronous EOG components and pre-registered spatial interventions; other nuisance mechanisms may exist. The justified conclusion is narrower: the current pre-registered evidence does not support a robust, selective ocular/frontal artifact shortcut dependency.

## 11. Limitations

The audit is limited to one compact EEGNet baseline, BCI2a A01--A09, three training seeds, the official within-subject cross-session setting, EOG channels filtered through the baseline 8--32 Hz passband, a linear synchronous EOG-to-EEG model, and the pre-registered masking and Gaussian-noise interventions. It does not exclude nonlinear, delayed, non-EOG, reference-related, EMG, or subject-specific nuisance mechanisms. Intervention null results also do not prove that model representations contain no artifact-related information. Generalization to other architectures, preprocessing pipelines, datasets, and recording montages remains untested.

## 12. Why the Negative Result Matters

The audit found both highly decodable class-correlated EOG activity and trial-specific EOG–EEG coupling. Nevertheless, direct matched interventions did not reveal robust selective EEGNet dependency. This dissociation is the central scientific value of the audit:

> The existence of class-correlated artifacts or contamination cannot be used as evidence that a classifier exploits those artifacts.

The negative result prevents circular motivation for an artifact-removal module, constrains scientific claims, and identifies generic perturbation sensitivity without mislabelling it as an ocular shortcut. It is therefore an informative result, not a failed experiment.

## 13. Original NAP-A Hypothesis

The original causal narrative was:

```text
artifact-correlated information
→ baseline shortcut dependency
→ artifact-aware suppression
→ more reliable EEG decoding
```

The audit supports the first premise and EOG–EEG coupling, but does not support the central shortcut-dependency premise. NAP-A should therefore not proceed under the claim that the sealed EEGNet baseline has been demonstrated to rely on ocular artifact shortcuts.

## 14. NAP-A Decision Gate

### Option A — Proceed with original NAP-A hypothesis

Not recommended. Robust selective artifact dependency was not demonstrated.

### Option B — Reframe NAP-A motivation

Recommended. Candidate directions include uncertainty-aware robustness, cross-session stability, subject-dependent nuisance robustness, distribution-shift robustness, small-sample robustness, and representation regularization. These are new hypotheses, not conclusions supported by the negative audit, and require a newly pre-registered question and evaluation protocol.

### Option C — Do not proceed with NAP-A in current form

Recommended for the original artifact-shortcut-suppression formulation. Do not implement it until a new, independently justified target failure mode exists.

**Decision: Reframe NAP-A motivation.**

## 15. Recommended New NAP Direction

A candidate direction is:

> NAP as an uncertainty-aware robustness framework rather than an artifact shortcut remover.

Subject- and session-dependent nuisance or reliability state could be estimated and used to modulate representation weighting, with the goal of improving robustness under distribution shift, controlled noise, or limited data without suppressing useful neural information. This is a candidate research program only; the Artifact Audit does not demonstrate that it will work.

## 16. New Research Question

> Can uncertainty-aware representation modulation improve cross-session and noise robustness in small-sample EEG decoding without suppressing useful neural information?

This differs explicitly from the completed audit question. The old question asked whether EEGNet exploits ocular shortcuts; the new question asks whether uncertainty-aware modelling improves robustness under heterogeneous nuisance and distribution shift.

## 17. Requirements Before Any New NAP Implementation

Any continuation must newly pre-register:

- the target failure mode;
- primary metric and biological/statistical unit;
- sealed baseline and comparison methods;
- robustness conditions and clean-performance constraints;
- training protocol and information boundaries;
- component and mechanism ablations;
- success and failure criteria.

The existence of an ocular shortcut must not be carried forward as a default premise.
