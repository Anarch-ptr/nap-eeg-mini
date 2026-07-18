"""Run the BCI Competition IV 2a EEGNet baseline across subjects."""

from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

import torch

from src.train import load_config
from src.train import run_artifact_audit
from src.train import run_training
from src.train import save_audit_summary
from src.train import save_training_history


SUMMARY_FIELDS = [
    "subject_id",
    "best_epoch",
    "best_validation_loss",
    "best_validation_accuracy",
    "final_test_loss",
    "final_test_accuracy",
]


def validate_subjects(subjects: list[int]) -> list[int]:
    """Validate and de-duplicate BCI2a subject identifiers.

    Parameters
    ----------
    subjects:
        Requested subject identifiers.

    Returns
    -------
    list[int]
        Validated subject identifiers with input order preserved.
    """

    validated: list[int] = []

    for subject_id in subjects:
        if subject_id not in range(1, 10):
            raise ValueError(
                "BCI2a subject identifiers must be between 1 and 9, "
                f"got {subject_id}"
            )

        if subject_id not in validated:
            validated.append(subject_id)

    if not validated:
        raise ValueError("At least one subject identifier is required.")

    return validated


def build_subject_config(
    base_config: dict,
    subject_id: int,
    output_root: Path,
) -> dict:
    """Create an isolated configuration for one subject.

    Parameters
    ----------
    base_config:
        Base experiment configuration.
    subject_id:
        BCI2a subject identifier.
    output_root:
        Parent directory for subject-level outputs.

    Returns
    -------
    dict
        Deep-copied subject-specific configuration.
    """

    config = copy.deepcopy(base_config)
    subject_dir = output_root / f"subject_{subject_id:02d}"

    config["data"]["subject_id"] = subject_id
    config["output"]["table_dir"] = str(subject_dir)

    return config


def get_summary_path(config: dict) -> Path:
    """Resolve the run-summary path for one subject."""

    output_config = config["output"]

    return (
        Path(output_config["table_dir"])
        / output_config.get("run_summary_file", "run_summary.json")
    )


def load_existing_summary(summary_path: Path) -> dict:
    """Load an existing subject-level run summary."""

    with summary_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def run_subject(config: dict, device: torch.device) -> dict:
    """Train and evaluate one subject using the standard pipeline."""

    result = run_training(
        config=config,
        device=device,
    )

    save_training_history(
        result["history"],
        config,
    )

    audit_summary = run_artifact_audit(
        model=result["model"],
        val_loader=result["data_bundle"].val_loader,
        criterion=result["criterion"],
        device=result["device"],
        config=config,
        clean_val_acc=(
            result["summary"]["best_validation_metrics"]["accuracy"]
        ),
    )

    if audit_summary is not None:
        save_audit_summary(audit_summary, config)

    return result["summary"]


def summary_to_row(subject_id: int, summary: dict) -> dict:
    """Convert one run summary to an aggregate CSV row."""

    validation = summary["best_validation_metrics"]
    final_test = summary.get("final_test_metrics")

    if final_test is None:
        final_test = {
            "loss": "",
            "accuracy": "",
        }

    return {
        "subject_id": subject_id,
        "best_epoch": summary["best_epoch"],
        "best_validation_loss": validation["loss"],
        "best_validation_accuracy": validation["accuracy"],
        "final_test_loss": final_test["loss"],
        "final_test_accuracy": final_test["accuracy"],
    }


def save_aggregate_summary(
    rows: list[dict],
    output_path: Path,
) -> None:
    """Save the current multi-subject aggregate summary."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=SUMMARY_FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run the EEGNet baseline across BCI2a subjects.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/bci2a_eegnet_baseline.yaml"),
        help="Base YAML configuration.",
    )
    parser.add_argument(
        "--subjects",
        type=int,
        nargs="+",
        default=list(range(1, 10)),
        help="Subject identifiers to run. Defaults to 1 through 9.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results/bci2a_eegnet_baseline"),
        help="Parent directory for subject-level outputs.",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=None,
        help="Aggregate CSV path. Defaults inside output-root.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse subjects that already contain run_summary.json.",
    )

    return parser.parse_args()


def main() -> None:
    """Run all requested subjects and save aggregate metrics."""

    args = parse_args()
    subjects = validate_subjects(args.subjects)
    base_config = load_config(str(args.config))
    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    summary_path = args.summary_file

    if summary_path is None:
        summary_path = args.output_root / "subjects_summary.csv"

    rows: list[dict] = []

    print(f"Using device: {device}")
    print(f"Subjects: {subjects}")
    print(f"Aggregate summary: {summary_path}")

    for position, subject_id in enumerate(subjects, start=1):
        print("")
        print("=" * 72)
        print(
            f"Subject A{subject_id:02d} "
            f"({position}/{len(subjects)})"
        )
        print("=" * 72)

        config = build_subject_config(
            base_config=base_config,
            subject_id=subject_id,
            output_root=args.output_root,
        )
        run_summary_path = get_summary_path(config)

        if args.skip_existing and run_summary_path.is_file():
            print(f"Reusing existing summary: {run_summary_path}")
            summary = load_existing_summary(run_summary_path)
        else:
            summary = run_subject(
                config=config,
                device=device,
            )

        rows.append(
            summary_to_row(
                subject_id=subject_id,
                summary=summary,
            )
        )
        save_aggregate_summary(rows, summary_path)

        print(f"Updated aggregate summary: {summary_path}")

    mean_test_accuracy = sum(
        float(row["final_test_accuracy"])
        for row in rows
    ) / len(rows)

    print("")
    print("Multi-subject baseline finished.")
    print(f"Subjects completed: {len(rows)}")
    print(f"Mean official test accuracy: {mean_test_accuracy:.4f}")
    print(f"Saved aggregate summary: {summary_path}")


if __name__ == "__main__":
    main()

