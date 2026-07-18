"""Aggregate formal BCI2a EOG-only audit results by run and subject."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


RUN_FIELDS = [
    "subject", "seed", "test_accuracy", "balanced_accuracy", "macro_f1",
    "best_epoch", "per_class_recall", "confusion_matrix",
]
SUBJECT_FIELDS = [
    "subject", "mean_accuracy", "accuracy_sd", "mean_balanced_accuracy",
    "balanced_accuracy_sd", "mean_macro_f1", "macro_f1_sd",
]


def sample_sd(values):
    return statistics.stdev(values) if len(values) > 1 else 0.0


def describe(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "sd": sample_sd(values),
        "min": min(values),
        "max": max(values),
    }


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    args = parser.parse_args()

    run_rows = []
    for path in sorted(args.results_root.glob("seed_*/subject_*/eog_only_summary.csv")):
        with path.open(encoding="utf-8", newline="") as file:
            row = next(csv.DictReader(file))
        run_rows.append({field: row[field] for field in RUN_FIELDS})

    expected = {(subject, seed) for subject in range(1, 10) for seed in (42, 43, 44)}
    observed = {(int(row["subject"]), int(row["seed"])) for row in run_rows}
    if observed != expected:
        raise RuntimeError(f"Incomplete audit: missing={sorted(expected-observed)}, extra={sorted(observed-expected)}")

    grouped = defaultdict(list)
    for row in run_rows:
        grouped[int(row["subject"])].append(row)

    subject_rows = []
    for subject in range(1, 10):
        rows = grouped[subject]
        acc = [float(row["test_accuracy"]) for row in rows]
        bacc = [float(row["balanced_accuracy"]) for row in rows]
        f1 = [float(row["macro_f1"]) for row in rows]
        subject_rows.append({
            "subject": subject,
            "mean_accuracy": statistics.mean(acc),
            "accuracy_sd": sample_sd(acc),
            "mean_balanced_accuracy": statistics.mean(bacc),
            "balanced_accuracy_sd": sample_sd(bacc),
            "mean_macro_f1": statistics.mean(f1),
            "macro_f1_sd": sample_sd(f1),
        })

    cross_subject = {
        metric: describe([float(row[field]) for row in subject_rows])
        for metric, field in {
            "accuracy": "mean_accuracy",
            "balanced_accuracy": "mean_balanced_accuracy",
            "macro_f1": "mean_macro_f1",
        }.items()
    }
    confusion = [[0] * 4 for _ in range(4)]
    recalls = [[] for _ in range(4)]
    for row in run_rows:
        matrix = json.loads(row["confusion_matrix"])
        recall = json.loads(row["per_class_recall"])
        for i in range(4):
            recalls[i].append(float(recall[i]))
            for j in range(4):
                confusion[i][j] += int(matrix[i][j])

    analysis = {
        "biological_unit": "subject",
        "nominal_chance_level": 0.25,
        "cross_subject": cross_subject,
        "mean_per_class_recall_across_runs": [statistics.mean(x) for x in recalls],
        "pooled_confusion_matrix_descriptive_only": confusion,
    }
    write_csv(args.results_root / "eog_only_runs.csv", run_rows, RUN_FIELDS)
    write_csv(args.results_root / "eog_only_subjects.csv", subject_rows, SUBJECT_FIELDS)
    with (args.results_root / "eog_only_analysis.json").open("w", encoding="utf-8") as file:
        json.dump(analysis, file, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
