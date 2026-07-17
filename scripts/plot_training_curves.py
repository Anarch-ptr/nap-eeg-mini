"""Plot training curves from a metrics CSV file."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


def load_metrics(metrics_path: Path) -> dict[str, list[float]]:
    """Load epoch-level training metrics.

    Parameters
    ----------
    metrics_path:
        Path to the CSV metrics file.

    Returns
    -------
    dict[str, list[float]]
        Numeric metric columns indexed by column name.
    """

    columns: dict[str, list[float]] = {
        "epoch": [],
        "train_loss": [],
        "train_accuracy": [],
        "val_loss": [],
        "val_accuracy": [],
    }

    with metrics_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            for name in columns:
                columns[name].append(float(row[name]))

    if not columns["epoch"]:
        raise ValueError(f"No metric rows found in {metrics_path}")

    return columns


def load_best_epoch(summary_path: Path) -> int | None:
    """Load the selected validation epoch when available.

    Parameters
    ----------
    summary_path:
        Path to the run summary JSON file.

    Returns
    -------
    int | None
        Best validation epoch, or None when the file does not exist.
    """

    if not summary_path.is_file():
        return None

    with summary_path.open("r", encoding="utf-8") as file:
        summary = json.load(file)

    return int(summary["best_epoch"])


def save_loss_curve(
    metrics: dict[str, list[float]],
    best_epoch: int | None,
    output_path: Path,
) -> None:
    """Save the training and validation loss curve."""

    figure, axes = plt.subplots(figsize=(8, 5))

    axes.plot(
        metrics["epoch"],
        metrics["train_loss"],
        label="Training loss",
    )
    axes.plot(
        metrics["epoch"],
        metrics["val_loss"],
        label="Validation loss",
    )

    if best_epoch is not None:
        axes.axvline(
            best_epoch,
            linestyle="--",
            label=f"Best epoch: {best_epoch}",
        )

    axes.set_xlabel("Epoch")
    axes.set_ylabel("Loss")
    axes.set_title("BCI2a Subject 01 EEGNet Loss")
    axes.grid(True, alpha=0.3)
    axes.legend()

    figure.tight_layout()
    figure.savefig(output_path, dpi=200)
    plt.close(figure)


def save_accuracy_curve(
    metrics: dict[str, list[float]],
    best_epoch: int | None,
    output_path: Path,
) -> None:
    """Save the training and validation accuracy curve."""

    train_accuracy = [
        accuracy * 100.0
        for accuracy in metrics["train_accuracy"]
    ]
    val_accuracy = [
        accuracy * 100.0
        for accuracy in metrics["val_accuracy"]
    ]

    figure, axes = plt.subplots(figsize=(8, 5))

    axes.plot(
        metrics["epoch"],
        train_accuracy,
        label="Training accuracy",
    )
    axes.plot(
        metrics["epoch"],
        val_accuracy,
        label="Validation accuracy",
    )

    if best_epoch is not None:
        axes.axvline(
            best_epoch,
            linestyle="--",
            label=f"Best epoch: {best_epoch}",
        )

    axes.set_xlabel("Epoch")
    axes.set_ylabel("Accuracy (%)")
    axes.set_ylim(0.0, 100.0)
    axes.set_title("BCI2a Subject 01 EEGNet Accuracy")
    axes.grid(True, alpha=0.3)
    axes.legend()

    figure.tight_layout()
    figure.savefig(output_path, dpi=200)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Plot EEGNet training curves.",
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        required=True,
        help="Path to metrics.csv.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        required=True,
        help="Path to run_summary.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for generated figures.",
    )

    return parser.parse_args()


def main() -> None:
    """Generate loss and accuracy figures."""

    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    metrics = load_metrics(args.metrics)
    best_epoch = load_best_epoch(args.summary)

    loss_path = args.output_dir / "bci2a_subject01_loss.png"
    accuracy_path = args.output_dir / "bci2a_subject01_accuracy.png"

    save_loss_curve(metrics, best_epoch, loss_path)
    save_accuracy_curve(metrics, best_epoch, accuracy_path)

    print(f"Saved loss curve: {loss_path}")
    print(f"Saved accuracy curve: {accuracy_path}")


if __name__ == "__main__":
    main()

