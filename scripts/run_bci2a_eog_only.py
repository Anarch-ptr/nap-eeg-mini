"""Run an independent BCI2a EOG-only Artifact Audit experiment."""

from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

from src.train import load_config
from src.train import run_training
from src.train import save_training_history
from src.train import save_run_summary
from src.evaluate import evaluate_classifier_detailed


SUMMARY_FIELDS = [
    "experiment",
    "subject",
    "seed",
    "modality",
    "channels",
    "channel_names",
    "train_samples",
    "validation_samples",
    "test_samples",
    "best_epoch",
    "validation_accuracy",
    "test_accuracy",
    "balanced_accuracy",
    "macro_f1",
    "per_class_recall",
    "confusion_matrix",
    "checkpoint",
    "normalization_source",
    "interpretation",
]


def save_eog_summary(summary: dict, config: dict) -> Path:
    """Save one explicit, audit-only EOG result row."""

    output = config["output"]
    output_path = Path(output["table_dir"]) / output.get(
        "experiment_summary_file",
        "eog_only_summary.csv",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    validation = summary["best_validation_metrics"]
    test = summary["final_test_metrics"]
    detailed = summary["official_test_detailed_metrics"]
    row = {
        "experiment": summary["experiment"],
        "subject": summary["subject"],
        "seed": summary["seed"],
        "modality": summary["modality"],
        "channels": summary["channels"],
        "channel_names": ",".join(summary["channel_names"]),
        "train_samples": summary["train_samples"],
        "validation_samples": summary["validation_samples"],
        "test_samples": summary["test_samples"],
        "best_epoch": summary["best_epoch"],
        "validation_accuracy": validation["accuracy"],
        "test_accuracy": test["accuracy"],
        "balanced_accuracy": detailed["balanced_accuracy"],
        "macro_f1": detailed["macro_f1"],
        "per_class_recall": json.dumps(detailed["per_class_recall"]),
        "confusion_matrix": json.dumps(detailed["confusion_matrix"]),
        "checkpoint": summary["best_checkpoint"],
        "normalization_source": summary["normalization"]["source"],
        "interpretation": (
            "EOG-only performance tests class-correlated decodable information; "
            "it does not prove that the frozen 22-EEG baseline uses an ocular shortcut."
        ),
    }
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerow(row)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/bci2a_eog_only.yaml"),
    )
    parser.add_argument("--subject", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--epochs",
        type=int,
        default=None,
        help="Explicit short override for a smoke test only.",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = copy.deepcopy(load_config(str(args.config)))
    if args.subject is not None:
        config["data"]["subject_id"] = args.subject
    if args.seed is not None:
        config["seed"] = args.seed
    if args.epochs is not None:
        if args.epochs <= 0:
            raise ValueError("--epochs must be positive.")
        config["training"]["epochs"] = args.epochs
        config["experiment"] += "_smoke_test"
    if args.output_dir is not None:
        config["output"]["table_dir"] = str(args.output_dir)

    result = run_training(config)
    detailed_metrics = evaluate_classifier_detailed(
        model=result["model"],
        dataloader=result["data_bundle"].test_loader,
        device=result["device"],
        num_classes=config["data"]["num_classes"],
    )
    test_accuracy = result["summary"]["final_test_metrics"]["accuracy"]
    if abs(detailed_metrics["accuracy"] - test_accuracy) > 1e-12:
        raise RuntimeError("Detailed and standard test accuracy disagree.")
    result["summary"]["official_test_detailed_metrics"] = detailed_metrics
    save_run_summary(result["summary"], config)
    save_training_history(result["history"], config)
    summary_path = save_eog_summary(result["summary"], config)
    print(f"Saved EOG-only experiment summary: {summary_path}")
    if args.epochs is not None:
        print("SMOKE TEST ONLY - NOT A SCIENTIFIC RESULT")


if __name__ == "__main__":
    main()
