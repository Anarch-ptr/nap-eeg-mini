"""Run the pre-registered BCI2a Small-Sample Robustness Audit v1."""

from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

import torch

from scripts.run_bci2a_multiseed import validate_seeds
from scripts.run_bci2a_multisubject import validate_subjects
from src.evaluate import evaluate_classifier_detailed
from src.small_sample_audit import ALLOWED_BUDGETS
from src.small_sample_audit import validate_budget
from src.train import load_config
from src.train import run_training
from src.train import save_training_history


FIELDS = [
    "subject", "budget", "subset_seed", "split_seed", "training_seed",
    "train_sample_count", "train_class_counts", "validation_sample_count",
    "test_sample_count", "primary_metric", "test_accuracy",
    "balanced_accuracy", "macro_f1", "per_class_recall",
    "confusion_matrix", "best_epoch", "checkpoint", "split_provenance",
    "resolved_config", "run_status",
]


def budget_label(budget: float) -> str:
    return f"budget_{round(validate_budget(budget) * 100):03d}"


def build_run_config(base, subject, budget, training_seed, output_root, epochs):
    config = copy.deepcopy(base)
    config["seed"] = int(training_seed)
    config["data"]["subject_id"] = int(subject)
    config["small_sample"]["budget"] = validate_budget(budget)
    if epochs is not None:
        config["training"]["epochs"] = int(epochs)
    run_dir = (
        output_root / budget_label(budget) / f"seed_{training_seed}"
        / f"subject_{subject:02d}"
    )
    config["output"]["table_dir"] = str(run_dir)
    return config, run_dir


def result_row(result, config, run_dir):
    bundle = result["data_bundle"]
    provenance = bundle.subset_provenance
    if provenance is None:
        raise RuntimeError("small-sample provenance was not produced")
    detailed = evaluate_classifier_detailed(
        result["model"], result["data_bundle"].test_loader,
        result["device"], config["data"]["num_classes"],
    )
    recorded = result["summary"]["final_test_metrics"]["accuracy"]
    if abs(detailed["accuracy"] - recorded) > 1e-12:
        raise RuntimeError("detailed and standard test accuracy disagree")
    return {
        "subject": provenance["subject"],
        "budget": provenance["budget"],
        "subset_seed": provenance["subset_seed"],
        "split_seed": provenance["split_seed"],
        "training_seed": provenance["training_seed"],
        "train_sample_count": provenance["train_sample_count"],
        "train_class_counts": json.dumps(provenance["train_class_counts"]),
        "validation_sample_count": provenance["validation_sample_count"],
        "test_sample_count": provenance["test_sample_count"],
        "primary_metric": "accuracy",
        "test_accuracy": detailed["accuracy"],
        "balanced_accuracy": detailed["balanced_accuracy"],
        "macro_f1": detailed["macro_f1"],
        "per_class_recall": json.dumps(detailed["per_class_recall"]),
        "confusion_matrix": json.dumps(detailed["confusion_matrix"]),
        "best_epoch": result["summary"]["best_epoch"],
        "checkpoint": result["summary"]["best_checkpoint"],
        "split_provenance": str(run_dir / "split_indices.json"),
        "resolved_config": str(run_dir / "resolved_config.yaml"),
        "run_status": "completed",
    }


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def load_rows(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def upsert_row(rows, row):
    key_fields = (
        "subject", "budget", "subset_seed", "split_seed", "training_seed"
    )
    key = tuple(str(row[field]) for field in key_fields)
    retained = [
        existing for existing in rows
        if tuple(str(existing[field]) for field in key_fields) != key
    ]
    retained.append(row)
    return retained


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path,
        default=Path("configs/bci2a_small_sample_audit.yaml"),
    )
    parser.add_argument("--subjects", type=int, nargs="+", default=[1])
    parser.add_argument("--budgets", type=float, nargs="+", default=[1.0])
    parser.add_argument("--training-seeds", type=int, nargs="+", default=[42])
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("results/bci2a_small_sample_audit"),
    )
    parser.add_argument(
        "--epochs", type=int, default=None,
        help="Smoke-only epoch override; omit for the frozen 50-epoch protocol.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    subjects = validate_subjects(args.subjects)
    seeds = validate_seeds(args.training_seeds)
    budgets = [validate_budget(value) for value in args.budgets]
    if len(set(budgets)) != len(budgets):
        raise ValueError("budgets must be unique")
    if args.epochs is not None and args.epochs <= 0:
        raise ValueError("epochs override must be positive")
    base = load_config(str(args.config))
    if float(base["small_sample"]["subset_seed"]) < 0:
        raise ValueError("subset_seed must be non-negative")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    summary_path = args.output_root / "small_sample_runs.csv"
    rows = load_rows(summary_path)
    for subject in subjects:
        for budget in budgets:
            for training_seed in seeds:
                config, run_dir = build_run_config(
                    base, subject, budget, training_seed,
                    args.output_root, args.epochs,
                )
                result = run_training(config, device=device)
                save_training_history(result["history"], config)
                row = result_row(result, config, run_dir)
                rows = upsert_row(rows, row)
                write_rows(summary_path, rows)
                (run_dir / "small_sample_result.json").write_text(
                    json.dumps(row, indent=2), encoding="utf-8"
                )
                print(
                    f"Completed A{subject:02d} budget={budget:.2f} "
                    f"training_seed={training_seed}"
                )
    print(f"Completed runs: {len(rows)}")
    print(f"Saved audit summary: {summary_path}")


if __name__ == "__main__":
    main()
