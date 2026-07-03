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

## Planned Structure

```text
src/           Core Python modules
experiments/   Reproducible experiment scripts
configs/       Training and evaluation configurations
docs/          Research notes and audit protocol
results/       Tables and figures for reporting
tests/         Basic tests
Current Status

This repository is under active early-stage development.

Current stage:

 Initialize project structure
 Add minimal training pipeline
 Implement EEGNet baseline
 Add artifact audit metrics
 Add noise injection experiments
 Implement NAP-A module
License

This project is released under the MIT License.