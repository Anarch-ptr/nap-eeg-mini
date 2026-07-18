"""Analyze BCI2a multi-seed baseline results."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


SUBJECT_FIELDS = [
    "subject_id",
    "num_seeds",
    "mean_test_accuracy",
    "std_test_accuracy",
    "min_test_accuracy",
    "max_test_accuracy",
]


def load_results(
    input_path: Path,
) -> list[dict]:
    """Load multi-seed run-level results."""

    with input_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def build_subject_statistics(
    rows: list[dict],
) -> list[dict]:
    """Aggregate official test accuracy by subject."""

    grouped: dict[int, list[float]] = defaultdict(list)

    for row in rows:
        subject_id = int(row["subject_id"])
        accuracy = float(row["final_test_accuracy"])

        grouped[subject_id].append(accuracy)

    results: list[dict] = []

    for subject_id in sorted(grouped):
        accuracies = grouped[subject_id]

        std_accuracy = 0.0

        if len(accuracies) > 1:
            std_accuracy = statistics.stdev(
                accuracies
            )

        results.append(
            {
                "subject_id": subject_id,
                "num_seeds": len(accuracies),
                "mean_test_accuracy": statistics.mean(
                    accuracies
                ),
                "std_test_accuracy": std_accuracy,
                "min_test_accuracy": min(accuracies),
                "max_test_accuracy": max(accuracies),
            }
        )

    return results


def build_seed_mean_statistics(
    rows: list[dict],
) -> tuple[float, float]:
    """Calculate mean and spread across seed-level means."""

    grouped: dict[int, list[float]] = defaultdict(list)

    for row in rows:
        seed = int(row["seed"])
        accuracy = float(row["final_test_accuracy"])

        grouped[seed].append(accuracy)

    seed_means = [
        statistics.mean(grouped[seed])
        for seed in sorted(grouped)
    ]

    mean_accuracy = statistics.mean(
        seed_means
    )

    std_accuracy = 0.0

    if len(seed_means) > 1:
        std_accuracy = statistics.stdev(
            seed_means
        )

    return mean_accuracy, std_accuracy


def save_subject_statistics(
    rows: list[dict],
    output_path: Path,
) -> None:
    """Save subject-level multi-seed statistics."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=SUBJECT_FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Analyze BCI2a multi-seed baseline results."
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to multiseed_subjects_summary.csv.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for subject-level statistics CSV.",
    )

    return parser.parse_args()


def main() -> None:
    """Run multi-seed result analysis."""

    args = parse_args()

    rows = load_results(
        args.input
    )

    subject_statistics = build_subject_statistics(
        rows
    )

    save_subject_statistics(
        rows=subject_statistics,
        output_path=args.output,
    )

    mean_accuracy, seed_std = (
        build_seed_mean_statistics(rows)
    )

    print(f"Runs: {len(rows)}")
    print(
        "Overall mean accuracy: "
        f"{mean_accuracy * 100.0:.2f}%"
    )
    print(
        "Seed-mean sample SD: "
        f"{seed_std * 100.0:.2f} percentage points"
    )

    print("")
    print("Per-subject mean +/- seed SD:")

    for row in subject_statistics:
        print(
            f"A{row['subject_id']:02d}: "
            f"{row['mean_test_accuracy'] * 100.0:.2f}% "
            f"+/- "
            f"{row['std_test_accuracy'] * 100.0:.2f} pp"
        )

    print(
        f"Saved subject statistics: {args.output}"
    )


if __name__ == "__main__":
    main()

