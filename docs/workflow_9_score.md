# NAP-EEG-Mini 9-Score Workflow

## Project Goal

The goal of **NAP-EEG-Mini** is to upgrade the current artifact-audited EEG decoding demo into a reproducible, reliability-first EEG decoding research project.

This project does not aim to claim a new state-of-the-art EEG classifier at the current stage. Instead, it focuses on building a rigorous experimental pipeline for testing whether an EEG decoding model is learning neural patterns or exploiting artifact-related shortcut signals.

## Core Principle

The project follows a fixed research order:

1. Establish the scientific positioning before adding new modules.
2. Visualize and audit the existing baseline before claiming improvement.
3. Define artifact sensitivity tests before designing NAP-A.
4. Evaluate the proposed module only after baseline failure modes are documented.
5. Keep every experiment reproducible, logged, and separately committed.

The key rule is:

> Do not design the solution before proving the problem.

## Nine-Stage Execution Plan

### Stage 1: Project Positioning and Related Work

**Outputs:**

- `docs/workflow_9_score.md`
- `docs/related_work.md`

**Purpose:**

Clarify the academic position of the project, define what is and is not being claimed, and prevent later overclaiming.

**Acceptance criteria:**

- EEGNet is clearly described as a baseline, not the novelty.
- Synthetic EEG is clearly described as a smoke-test dataset, not evidence for neuroscience conclusions.
- Channel masking is clearly described as an audit tool, not a proposed training method.
- The document explains why artifact sensitivity matters for reliable EEG decoding.

------

### Stage 2: Training Visualization

**Outputs:**

- `src/visualize.py`
- `results/figures/training_curve.png`

**Purpose:**

Convert training logs into a clear visualization of training and validation behavior.

**Acceptance criteria:**

- Training loss, validation loss, training accuracy, and validation accuracy are plotted.
- The figure can be regenerated from saved CSV logs.
- The script runs from the command line.
- The figure is saved under `results/figures/`.

------

### Stage 3: Real Data Interface

**Outputs:**

- `src/data.py`
- `EEGArrayDataset`
- Optional toy `.npy` or `.csv` loading example

**Purpose:**

Separate model training from synthetic data generation, making the project ready for real EEG datasets.

**Acceptance criteria:**

- Dataset loading is modular.
- Input tensor shape is documented.
- Label format is documented.
- Synthetic data and array-based real data use the same training interface.

------

### Stage 4: Artifact-Only Experiment

**Outputs:**

- `src/experiments/artifact_only.py`
- `results/tables/artifact_only_results.csv`

**Purpose:**

Test whether the classifier can achieve non-trivial performance using only artifact-related signals.

**Acceptance criteria:**

- Neural-like signal and artifact-like signal can be separated.
- The model is trained or evaluated under an artifact-only condition.
- Artifact-only accuracy is reported.
- The result is interpreted as a shortcut-learning audit, not as a final model performance score.

------

### Stage 5: Noise Injection Experiment

**Outputs:**

- `src/experiments/noise_injection.py`
- `results/tables/noise_injection_results.csv`

**Purpose:**

Evaluate model robustness under controlled perturbations.

**Perturbation types may include:**

- Gaussian noise
- Channel masking
- Time masking
- Artifact amplitude scaling

**Acceptance criteria:**

- Clean accuracy and corrupted accuracy are both reported.
- Accuracy degradation is measured.
- Perturbation strength is explicitly logged.
- The experiment can be reproduced from config files.

------

### Stage 6: NAP-A Module Design

**Outputs:**

- `src/models/nap_a.py`
- Updated model configuration

**Purpose:**

Design a lightweight reliability module only after baseline artifact sensitivity has been demonstrated.

**Acceptance criteria:**

- The module has a clearly defined input and output.
- The module is small enough to be justified as a reliability component rather than a completely new architecture.
- The design is motivated by Stage 4 and Stage 5 results.
- No improvement claim is made before ablation testing.

------

### Stage 7: Ablation Study

**Outputs:**

- `results/tables/ablation_results.csv`

**Purpose:**

Test whether NAP-A improves robustness because of its intended mechanism rather than extra parameters or accidental regularization.

**Minimum comparisons:**

- EEGNet baseline
- EEGNet + NAP-A
- EEGNet + random channel masking
- EEGNet + noise augmentation
- EEGNet + NAP-A without key gating component

**Acceptance criteria:**

- All models use the same train/validation/test split.
- All models use the same random seed list.
- Mean and standard deviation are reported.
- The comparison includes both clean and corrupted test conditions.

------

### Stage 8: Main Result Table

**Outputs:**

- `results/tables/main_results.csv`
- Optional `results/figures/main_results.png`

**Purpose:**

Summarize the main experimental findings in a form suitable for README, project report, and academic discussion.

**Required columns:**

- Model
- Clean accuracy
- Artifact-only accuracy
- Noise-injected accuracy
- Accuracy drop
- Notes

**Acceptance criteria:**

- Results are generated from saved experiment logs.
- No manual editing of final metrics.
- The table clearly separates performance and robustness.

------

### Stage 9: README and Research Packaging

**Outputs:**

- Updated `README.md`
- Project diagram
- Reproducibility instructions
- Optional resume bullet points

**Purpose:**

Package the project as a research-oriented engineering artifact.

**Acceptance criteria:**

- README explains the problem, pipeline, experiments, and limitations.
- Installation and reproduction commands are provided.
- Results are presented with appropriate caution.
- Limitations are explicitly stated.
- The project is framed as a reliability audit framework, not as a universal EEG decoding solution.

## Git Commit Policy

Each stage must be committed independently.

Recommended commit format:

```text
docs: add reliability-first workflow and related work
feat: add training curve visualization
feat: add array-based EEG dataset interface
exp: add artifact-only shortcut audit
exp: add noise injection robustness test
feat: add NAP-A reliability module
exp: add ablation study
docs: update README with results and limitations
```

Before every commit:

```bash
python -m src.train --config configs/baseline.yaml
```

If relevant:

```bash
python -m src.visualize --log results/logs/training_log.csv --out results/figures/training_curve.png
```

## Non-Claims

At the current stage, this project does not claim:

- A new state-of-the-art EEG decoding architecture.
- Neuroscientific conclusions from synthetic EEG data.
- Clinical reliability.
- Artifact removal superiority over ICA, CCA, or other established preprocessing methods.
- Generalization to real EEG datasets before real-data experiments are completed.

## Final Position

NAP-EEG-Mini is a small but rigorous project. Its value comes from the experimental discipline: define the failure mode, audit the baseline, stress-test robustness, then propose a targeted reliability module.