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
