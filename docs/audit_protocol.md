## Phase 0A: independent BCI2a EOG path

The frozen baseline remains exactly 22 EEG channels passed to EEGNet. EOG is
never appended to baseline input and baseline configs do not enable EOG.

The audit-only loader uses MOABB 1.5.0
`BNCI2014_001(return_all_modalities=True)`. The underlying official recording
contains 22 EEG channels followed by three channels whose dataset metadata
identifies them as `EOG1`, `EOG2`, and `EOG3` with MNE type `eog`. The loader
selects those channels only after validating an independently loaded default
EEG view against the all-modality view.

Alignment must hold exactly for:

- encoded labels;
- MOABB subject, official session, and run metadata;
- MNE event sample and event code;
- the 22 EEG epoch samples present in both views.

The MOABB metadata has no globally unique trial identifier. The strongest
available audit identity is therefore `(subject, session, run, trial_in_run,
event_sample, event_code)`. Loading fails rather than continuing if any
alignment invariant fails.

Official session isolation remains `0train` for train/validation and `1test`
for the final test. Per-channel normalization statistics are calculated from
the training subset only and then fixed for validation and test.

The EOG-only experiment asks whether independently recorded EOG contains
motor-imagery-class-correlated decodable information. Performance above the
four-class 25% chance level does **not** establish that the frozen 22-EEG
baseline uses an ocular shortcut. Smoke-test metrics are engineering checks,
not scientific results.

## Phase 0C: pre-registered temporal and leakage sanity audit

MOABB 1.5.0 defines `BNCI2014_001.interval == [2, 6]`. The project passes
`MotorImagery(tmin=0, tmax=4)`, and MOABB adds the dataset interval start when
constructing MNE epochs. Actual MNE epoch times are therefore 2.000 through
6.000 seconds relative to MOABB's shifted trial event (1001 inclusive samples
at 250 Hz). The class annotation/cue and motor-imagery onset is at epoch sample
0; the current epoch contains the four-second task interval and no cue-preceding
baseline.

The temporal conditions are frozen before formal evaluation:

| Name | Project-relative time | Samples | Meaning |
| --- | --- | ---: | --- |
| full | 0.0–4.0 s | 1001 | Existing full task-period EOG audit |
| early | 0.0–1.0 s | 251 | Cue-visible / early motor imagery |
| middle | 1.5–2.5 s | 251 | Middle motor-imagery interval |
| late | 3.0–4.0 s | 251 | Late motor-imagery interval |

Early, middle, and late have identical duration and model input shape. Full is
retained as the frozen Phase 0B reference but has a longer input and therefore
must not be treated as an architecture-matched contrast with the cropped
conditions. Windows are identical for every subject and seed and will not be
refined after results are observed.

The label-shuffle control is pre-registered for A05 (high), A01 (medium), and
A02 (lower), training seed 42 and shuffle seed 20260718. Train and validation
labels are permuted independently within their frozen subsets; official test
labels remain real. Metadata is retained only for alignment and logging and is
never included in the model input tensor.

## Phase 1: pre-registered EOG-to-EEG coupling audit

The analyzed signals are 22 EEG channels and three EOG channels from the same
BNCI2014-001 Raw recording, both processed by the identical MOABB 1.5.0
`MotorImagery(fmin=8, fmax=32, tmin=0, tmax=4)` pipeline at 250 Hz. The EOG
predictors must therefore be described as EOG-channel activity within the
baseline 8–32 Hz preprocessing passband, not raw broadband ocular activity.

For every subject and frozen Phase 0C window, ordinary least squares maps the
three simultaneous EOG samples to all 22 EEG channels. Channel-wise mean and
standard deviation are fit using the complete official `0train` session only;
coefficients are fit only on that session. Both transformations are fixed and
evaluated on official `1test`. Held-out R2 is primary and may be negative;
predicted/true Pearson correlation is secondary.

The primary control is a deterministic, class-preserving, one-to-one
cross-trial derangement within each official session. Train uses permutation
seed 20260718 and test uses 20260719. It preserves subject, session, class,
task phase, trial count, and temporal window while ensuring no EEG trial is
paired with its own EOG trial. Separate OLS mappings are fit for same-trial and
control conditions using identical EEG targets. The primary contrast is
`R2_same_trial - R2_same_class_cross_trial`.

All 22 EEG channels are primary. Regions are frozen before results as frontal
(`Fz`, `FC3`, `FC1`, `FCz`, `FC2`, `FC4`), central (`C5`, `C3`, `C1`, `Cz`,
`C2`, `C4`, `C6`), parietal (`CP3`, `CP1`, `CPz`, `CP2`, `CP4`, `P1`, `Pz`,
`P2`), and occipital (`POz`). Region summaries are descriptive only.
