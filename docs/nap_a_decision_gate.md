# NAP-A Decision Gate

## 1. Original Hypothesis

The original NAP-A motivation assumed that class-correlated artifact information creates a shortcut dependency in the EEGNet baseline and that artifact-aware suppression would consequently improve decoding reliability.

## 2. Audit Evidence

The sealed baseline was audited independently of NAP-A across nine BCI2a subjects and three baseline seeds. EOG-only decoding established substantial class information, temporal controls localized much of it to early trials, and held-out coupling analysis established trial-specific EOG-related EEG correspondence. Frozen-model tests then compared true EOG-coupled component removal with energy-matched cross-trial removal, and compared pre-registered frontal masking/noise with matched non-frontal and five fixed random groups.

## 3. What Was Supported

- EOG-channel activity in the 8--32 Hz preprocessing passband contains class-correlated information.
- Trial-specific EOG-related activity couples to EEG beyond shared class/task structure.
- EEGNet is generally sensitive to six-channel information removal.
- EEGNet has a general dose-dependent response to standardized Gaussian noise.
- Subjects exhibit substantial heterogeneity.

## 4. What Was Not Supported

- Robust selective dependency on the trial-specific linear EOG-coupled EEG component.
- Greater dependency on the pre-registered frontal group than on matched or random channel groups.
- Greater vulnerability to frontal-targeted noise than to equal-energy matched or random noise.
- A demonstrated ocular/frontal shortcut mechanism in the sealed baseline.
- Any claim that NAP-A is effective or necessary.

## 5. Why the Original Motivation Is Weakened

Artifact-related information and coupling are necessary observations for the original narrative, but they do not establish classifier use. The direct dependency layer was not supported by three matched intervention families. Implementing artifact suppression as though shortcut dependency had been demonstrated would therefore turn an unsupported premise into a design assumption and risk suppressing useful neural information.

## 6. Decision

**Reframe NAP-A motivation.**

> The original artifact-shortcut-removal NAP-A should not be implemented under its original motivation.

- **Original NAP-A:** do not proceed in its current artifact-shortcut-removal form.
- **Implementation status:** do not implement the original artifact-shortcut-removal NAP-A yet.
- **Artifact Audit:** stop intervention development and preserve the negative result.

## 7. Recommended Reframe

Evaluate NAP as an uncertainty-aware robustness framework rather than an ocular artifact remover. A candidate question is:

> Can uncertainty-aware representation modulation improve cross-session and noise robustness in small-sample EEG decoding without suppressing useful neural information?

Possible target domains are cross-session stability, subject-dependent nuisance variation, distribution shift, controlled-noise robustness, limited-data uncertainty, and representation regularization. These are new hypotheses, not yet validated, and not yet implemented.

## 8. Required New Experiments Before Implementation

Before writing a new NAP module, prepare and review a new protocol that freezes:

1. a measurable target failure mode independent of ocular-shortcut assumptions;
2. primary clean and robustness metrics, including non-inferiority constraints;
3. subject-level statistical units and the seed aggregation hierarchy;
4. sealed baselines and parameter-matched controls;
5. training, validation, and official-test information boundaries;
6. cross-session and distribution-shift conditions;
7. mechanism-specific ablations against simpler regularization controls;
8. explicit success, null, and stopping criteria.

No architecture, gating, GRL, uncertainty component, or new training run is authorized by this decision document.
