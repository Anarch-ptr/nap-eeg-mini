"""Generate training curves from a saved training-history CSV file."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


REQUIRED_COLUMNS = {
    "epoch",
    "train_loss",
    "train_accuracy",
    "val_loss",
    "val_accuracy",
}


def load_training_history(csv_path: Path) -> pd.DataFrame:
    """Load and validate a training-history CSV file."""

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Training history was not found: {csv_path}\n"
            "Run the training pipeline before generating the figure."
        )

    history = pd.read_csv(csv_path)

    missing_columns = REQUIRED_COLUMNS.difference(history.columns)

    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"Training history is missing required columns: {missing_text}"
        )

    if history.empty:
        raise ValueError("Training history contains no rows.")

    return history


def plot_training_history(
    history: pd.DataFrame,
    output_path: Path,
) -> None:
    """Plot training and validation loss and accuracy."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(
        nrows=1,
        ncols=2,
        figsize=(12, 4.5),
    )

    axes[0].plot(
        history["epoch"],
        history["train_loss"],
        marker="o",
        label="Train loss",
    )
    axes[0].plot(
        history["epoch"],
        history["val_loss"],
        marker="o",
        label="Validation loss",
    )
    axes[0].set_title("Training and Validation Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].grid(alpha=0.3)
    axes[0].legend()

    axes[1].plot(
        history["epoch"],
        history["train_accuracy"],
        marker="o",
        label="Train accuracy",
    )
    axes[1].plot(
        history["epoch"],
        history["val_accuracy"],
        marker="o",
        label="Validation accuracy",
    )
    axes[1].set_title("Training and Validation Accuracy")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy")
    axes[1].set_ylim(0.0, 1.05)
    axes[1].grid(alpha=0.3)
    axes[1].legend()

    figure.suptitle("NAP-EEG-Mini Baseline Training")
    figure.tight_layout()
    figure.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(figure)

    print(f"Saved training figure to: {output_path}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Plot NAP-EEG-Mini training curves."
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("results/tables/training_history.csv"),
        help="Path to the training-history CSV file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("results/figures/training_curve.png"),
        help="Path used to save the generated figure.",
    )

    return parser.parse_args()


def main() -> None:
    """Load the training history and generate the figure."""

    args = parse_args()

    history = load_training_history(args.log)

    plot_training_history(
        history=history,
        output_path=args.out,
    )


if __name__ == "__main__":
    main()
    