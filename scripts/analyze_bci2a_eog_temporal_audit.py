"""Aggregate pre-registered BCI2a EOG temporal and shuffle controls."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


WINDOWS = {
    "full": (0.0, 4.0, 1001),
    "early": (0.0, 1.0, 251),
    "middle": (1.5, 2.5, 251),
    "late": (3.0, 4.0, 251),
}
METRICS = ("test_accuracy", "balanced_accuracy", "macro_f1")


def read_one(path: Path) -> dict:
    with path.open(encoding="utf-8", newline="") as file:
        return next(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-root", type=Path, required=True)
    parser.add_argument("--temporal-root", type=Path, required=True)
    args = parser.parse_args()

    rows = []
    for window, (tmin, tmax, samples) in WINDOWS.items():
        root = args.full_root if window == "full" else args.temporal_root / window
        for path in sorted(root.glob("seed_*/subject_*/eog_only_summary.csv")):
            source = read_one(path)
            rows.append({
                "subject": int(source["subject"]),
                "seed": int(source["seed"]),
                "window_name": window,
                "tmin": tmin,
                "tmax": tmax,
                "num_samples": samples,
                "test_accuracy": float(source["test_accuracy"]),
                "balanced_accuracy": float(source["balanced_accuracy"]),
                "macro_f1": float(source["macro_f1"]),
                "best_epoch": int(source["best_epoch"]),
                "per_class_recall": source["per_class_recall"],
                "confusion_matrix": source["confusion_matrix"],
            })

    expected = {
        (subject, seed, window)
        for subject in range(1, 10)
        for seed in (42, 43, 44)
        for window in WINDOWS
    }
    observed = {(r["subject"], r["seed"], r["window_name"]) for r in rows}
    if observed != expected:
        raise RuntimeError(f"Incomplete temporal matrix: missing={sorted(expected-observed)}")

    run_fields = list(rows[0])
    write_csv(args.temporal_root / "temporal_runs.csv", rows, run_fields)

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["subject"], row["window_name"])].append(row)
    subject_rows = []
    for subject in range(1, 10):
        for window in WINDOWS:
            group = grouped[(subject, window)]
            result = {"subject": subject, "window_name": window}
            for metric in METRICS:
                values = [float(row[metric]) for row in group]
                result[f"mean_{metric}"] = statistics.mean(values)
                result[f"sd_{metric}"] = statistics.stdev(values)
            subject_rows.append(result)
    write_csv(
        args.temporal_root / "temporal_subjects.csv",
        subject_rows,
        list(subject_rows[0]),
    )

    by_run = {(r["subject"], r["seed"], r["window_name"]): r for r in rows}
    differences = []
    for subject in range(1, 10):
        for seed in (42, 43, 44):
            for window in ("early", "middle", "late"):
                differences.append({
                    "subject": subject,
                    "seed": seed,
                    "window_name": window,
                    "accuracy_minus_full": (
                        by_run[(subject, seed, window)]["test_accuracy"]
                        - by_run[(subject, seed, "full")]["test_accuracy"]
                    ),
                })
    write_csv(
        args.temporal_root / "temporal_paired_differences.csv",
        differences,
        list(differences[0]),
    )

    window_summary = {}
    for window in WINDOWS:
        subject_means = [
            row for row in subject_rows if row["window_name"] == window
        ]
        window_summary[window] = {
            metric: {
                "mean_of_subject_means": statistics.mean(
                    float(row[f"mean_{metric}"]) for row in subject_means
                ),
                "median_of_subject_means": statistics.median(
                    float(row[f"mean_{metric}"]) for row in subject_means
                ),
                "sd_across_subject_means": statistics.stdev(
                    float(row[f"mean_{metric}"]) for row in subject_means
                ),
            }
            for metric in METRICS
        }
    with (args.temporal_root / "temporal_analysis.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(window_summary, file, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
