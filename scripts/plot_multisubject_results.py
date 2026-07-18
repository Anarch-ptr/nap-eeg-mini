"""Plot multi-subject BCI2a baseline results."""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


def load_results(summary_path: Path) -> tuple[list[str], list[float]]:
    """Load subject identifiers and official test accuracies.

    Parameters
    ----------
    summary_path:
        Path to the multi-subject summary CSV file.

    Returns
    -------
    tuple[list[str], list[float]]
        Subject labels and official test accuracies.
    """

    subjects: list[str] = []
    accuracies: list[float] = []

    with summary_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            subject_id = int(row["subject_id"])
            accuracy = float(row["final_test_accuracy"])

            subjects.append(f"A{subject_id:02d}")
            accuracies.append(accuracy)

    if not subjects:
        raise ValueError(
            f"No subject results found in {summary_path}"
        )

    return subjects, accuracies


def save_accuracy_figure(
    subjects: list[str],
    accuracies: list[float],
    output_path: Path,
) -> None:
    """Save per-subject official test accuracy figure."""

    accuracy_percent = [
        accuracy * 100.0
        for accuracy in accuracies
    ]
    mean_accuracy = statistics.mean(accuracy_percent)

    figure, axes = plt.subplots(
        figsize=(9, 5),
    )

    axes.bar(
        subjects,
        accuracy_percent,
    )

    axes.axhline(
        25.0,
        linestyle="--",
        label="Chance level (25%)",
    )
    axes.axhline(
        mean_accuracy,
        linestyle="--",
        label=f"Mean ({mean_accuracy:.2f}%)",
    )

    axes.set_xlabel("Subject")
    axes.set_ylabel("Official test accuracy (%)")
    axes.set_ylim(0.0, 100.0)
    axes.set_title(
        "BCI Competition IV 2a EEGNet Baseline"
    )
    axes.legend()

    figure.tight_layout()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    figure.savefig(
        output_path,
        dpi=200,
    )
    plt.close(figure)


def print_statistics(accuracies: list[float]) -> None:
    """Print aggregate accuracy statistics."""

    accuracy_percent = [
        accuracy * 100.0
        for accuracy in accuracies
    ]

    print(f"Subjects: {len(accuracy_percent)}")
    print(
        "Mean:   "
        f"{statistics.mean(accuracy_percent):.2f}%"
    )
    print(
        "Std:    "
        f"{statistics.stdev(accuracy_percent):.2f}%"
    )
    print(
        "Median: "
        f"{statistics.median(accuracy_percent):.2f}%"
    )
    print(
        "Min:    "
        f"{min(accuracy_percent):.2f}%"
    )
    print(
        "Max:    "
        f"{max(accuracy_percent):.2f}%"
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Plot BCI2a multi-subject baseline results."
        ),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        required=True,
        help="Path to subjects_summary.csv.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output PNG path.",
    )

    return parser.parse_args()


def main() -> None:
    """Generate the multi-subject baseline figure."""

    args = parse_args()

    subjects, accuracies = load_results(
        args.summary,
    )

    print_statistics(accuracies)

    save_accuracy_figure(
        subjects=subjects,
        accuracies=accuracies,
        output_path=args.output,
    )

    print(
        f"Saved multi-subject figure: {args.output}"
    )


if __name__ == "__main__":
    main()

