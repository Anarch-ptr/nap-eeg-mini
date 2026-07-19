"""Analyze a complete Small-Sample Robustness Audit v1 result matrix."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.small_sample_analysis import classify


SUBJECT_FIELDS = [
    "subject", "metric_100_mean", "metric_100_std", "metric_50_mean",
    "metric_50_std", "metric_25_mean", "metric_25_std", "n_seeds_100",
    "n_seeds_50", "n_seeds_25", "delta50_fraction", "delta25_fraction",
    "degradation50_pp", "degradation25_pp", "dose_response_monotonic",
]
SEED_FIELDS = [
    "training_seed", "n_subjects", "median_degradation25_pp",
    "positive_group_direction",
]


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def markdown_report(result):
    subjects = result["subject_comparisons"]
    subject_lines = [
        "| Subject | 100% | 50% | 25% | Degradation 25 (pp) | Monotonic |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for row in subjects:
        subject_lines.append(
            f"| A{row['subject']:02d} | {row['metric_100_mean']:.4f} | "
            f"{row['metric_50_mean']:.4f} | {row['metric_25_mean']:.4f} | "
            f"{row['degradation25_pp']:.2f} | "
            f"{'yes' if row['dose_response_monotonic'] else 'no'} |"
        )
    seed_lines = [
        "| Training seed | Subjects | Median degradation (pp) | Positive direction |",
        "|---:|---:|---:|:---:|",
    ]
    for row in result["seed_diagnostics"]:
        value = row["median_degradation25_pp"]
        text = "n/a" if value is None else f"{value:.2f}"
        seed_lines.append(
            f"| {row['training_seed']} | {row['n_subjects']} | {text} | "
            f"{'yes' if row['positive_group_direction'] else 'no'} |"
        )
    errors = result["integrity_errors"]
    error_text = "None." if not errors else "\n".join(f"- {x}" for x in errors)
    median = result["median_degradation25_pp"]
    median_text = "n/a" if median is None else f"{median:.2f} pp"
    return f"""# Small-Sample Robustness Audit v1 Analysis

## Matrix Completeness

- Integrity pass: `{result['integrity_pass']}`
- Subjects required: A01--A09
- Budgets required: 1.0, 0.5, 0.25
- Training seeds required: 42, 43, 44
- Primary metric: accuracy stored as a 0--1 fraction
- Degradation values: percentage points

Integrity errors:

{error_text}

## Subject-Level Results

{chr(10).join(subject_lines)}

## Primary 25%-versus-100% Result

- Median subject-level degradation: {median_text}
- Subjects with at least 3 pp degradation: {result['subjects_degraded_ge_3pp']}/9
- Subject-level monotonic dose responses: {result['subject_monotonic_count']}/9

## Seed-Direction Diagnostic

{chr(10).join(seed_lines)}

Seed medians are reproducibility diagnostics, not independent biological
replicates. Seed-direction consistency: `{result['seed_direction_consistent']}`.

## Dose Response

Group-level median ordering 100% >= 50% >= 25%:
`{result['dose_response_pass']}`.

## Final Classification

**{result['classification']}**

## Interpretation Boundary

This analysis does not justify a NAP architecture by itself. If a
`STRONG_FAILURE` is observed, the next required step is an
optimizer-update-matched small-sample diagnostic, followed by a simple
control gate. That diagnostic is not implemented or run here.
"""


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    rows = read_rows(args.input)
    result = classify(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output_dir / "small_sample_subject_summary.csv",
        result["subject_comparisons"], SUBJECT_FIELDS,
    )
    write_csv(
        args.output_dir / "small_sample_seed_diagnostics.csv",
        result["seed_diagnostics"], SEED_FIELDS,
    )
    public_result = {
        key: value for key, value in result.items()
        if key not in {"subject_budget_rows", "subject_comparisons", "seed_diagnostics"}
    }
    (args.output_dir / "small_sample_analysis.json").write_text(
        json.dumps(public_result, indent=2), encoding="utf-8"
    )
    (args.output_dir / "small_sample_analysis.md").write_text(
        markdown_report(result), encoding="utf-8"
    )
    print(f"Classification: {result['classification']}")
    print(f"Integrity pass: {result['integrity_pass']}")
    print(f"Saved analysis: {args.output_dir}")


if __name__ == "__main__":
    main()
