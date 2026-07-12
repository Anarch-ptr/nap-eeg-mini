# NAP-EEG-Mini

Reliability-first artifact-audited EEG decoding for noisy and small-sample BCI research.

## Overview

NAP-EEG-Mini is a lightweight research project for EEG decoding under noisy and small-sample BCI settings.

The goal is not only to improve classification accuracy, but also to audit whether the model relies on neural signals or artifact-related shortcuts such as eye movement, muscle noise, or unstable trial-specific patterns.

## Core Idea

This project focuses on three questions:

1. Can a baseline EEG decoder perform reliably under noisy EEG conditions?
2. Can artifact-only signals predict labels, suggesting possible shortcut learning?
3. Can a reliability-first model reduce artifact sensitivity while preserving decoding performance?

## Project Structure

```text
src/           Core Python modules
experiments/   Reproducible experiment scripts
configs/       Training and evaluation configurations
docs/          Research notes and audit protocols
results/       Report-ready tables and figures
tests/         Basic automated tests
```

## Current Status

Completed:

* [x] Initialize project structure
* [x] Implement the EEGNet baseline
* [x] Add a synthetic EEG dataset for pipeline testing
* [x] Add config-driven training
* [x] Add reusable model evaluation
* [x] Add channel-masking artifact audit
* [x] Save training and audit results to CSV
* [x] Document the reliability-first research workflow

Planned:

* [ ] Add training-curve visualization
* [ ] Add an array-based real EEG data interface
* [ ] Add artifact-only experiments
* [ ] Add controlled noise-injection experiments
* [ ] Implement and ablate the NAP-A reliability module
* [ ] Validate the framework on public EEG datasets

## Quick Start

Install the required packages:

```bash
pip install -r requirements.txt
```

Run the configurable EEGNet smoke test:

```bash
python -m src.train --config configs/baseline.yaml
```

The command generates:

```text
results/tables/training_history.csv
results/tables/audit_summary.csv
```

## Current Limitations

The current repository uses synthetic EEG only to verify the software pipeline. Synthetic results do not provide evidence of real EEG decoding performance, neuroscientific validity, clinical reliability, or generalization to public BCI datasets.

Channel masking is treated as a diagnostic sensitivity test. A decrease in accuracy after masking selected channels does not by itself prove that the model learned ocular or muscular artifacts.

## License

This project is released under the MIT License.
