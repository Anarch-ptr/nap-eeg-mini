"""Plot BCI2a multi-seed baseline subject statistics."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


def load_statistics(
    input_path: Path,
) -> tuple[list[str], list[float], list[float]]:
    """Load subject-level multi-seed statistics."""

    subjects: list[str] = []
    means: list[float] = []
    stds: list[float] = []

    with input_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            subject_id = int(row["subject_id"])

            subjects.append(
                f"A{subject_id:02d}"
            )
            means.append(
                float(
                    row["mean_test_accuracy"]
                )
                * 100.0
            )
            stds.append(
                float(
                    row["std_test_accuracy"]
                )
                * 100.0
            )

    if not subjects:
        raise ValueError(
            f"No statistics found in {input_path}"
        )

    return subjects, means, stds


def save_figure(
    subjects: list[str],
    means: list[float],
    stds: list[float],
    output_path: Path,
) -> None:
    """Save subject mean accuracy with seed variability."""

    overall_mean = sum(means) / len(means)

    figure, axes = plt.subplots(
        figsize=(9, 5),
    )

    positions = list(
        range(len(subjects))
    )

    axes.bar(
        positions,
        means,
        yerr=stds,
        capsize=4,
    )

    axes.axhline(
        25.0,
        linestyle="--",
        label="Chance level (25%)",
    )

    axes.axhline(
        overall_mean,
        linestyle="--",
        label=(
            f"Overall mean "
            f"({overall_mean:.2f}%)"
        ),
    )

    axes.set_xticks(
        positions,
        subjects,
    )
    axes.set_xlabel("Subject")
    axes.set_ylabel(
        "Official test accuracy (%)"
    )
    axes.set_ylim(
        0.0,
        100.0,
    )
    axes.set_title(
        "BCI Competition IV 2a EEGNet Baseline "
        "(3 Seeds)"
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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Plot BCI2a multi-seed baseline results."
        ),
    )

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help=(
            "Path to "
            "subjects_multiseed_statistics.csv."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output PNG path.",
    )

    return parser.parse_args()


def main() -> None:
    """Generate the multi-seed baseline figure."""

    args = parse_args()

    subjects, means, stds = load_statistics(
        args.input
    )

    save_figure(
        subjects=subjects,
        means=means,
        stds=stds,
        output_path=args.output,
    )

    print(
        f"Saved multi-seed figure: "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()
