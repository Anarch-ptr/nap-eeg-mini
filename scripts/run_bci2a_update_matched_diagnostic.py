"""Run the frozen 25%-data optimizer-update-matched diagnostic."""

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
from src.train import build_dataloaders, load_config
from src.update_matched_diagnostic import (
    CONDITION, assert_frozen_identities, reference_update_budget,
    run_update_matched_training,
)


FIELDS = ["subject", "condition", "budget", "split_seed", "subset_seed",
          "training_seed", "train_sample_count", "batch_size",
          "reference_steps_per_epoch", "target_optimizer_updates",
          "actual_optimizer_updates", "validation_event_count",
          "subset_identity_status", "primary_metric", "test_accuracy",
          "balanced_accuracy", "macro_f1", "checkpoint", "run_status",
          "diagnostic_freeze_commit"]


def build_config(base, subject, seed, root):
    config = copy.deepcopy(base)
    config["seed"] = seed
    config["data"]["subject_id"] = subject
    config["small_sample"]["budget"] = 0.25
    run_dir = root / f"seed_{seed}" / f"subject_{subject:02d}"
    config["output"]["table_dir"] = str(run_dir)
    return config, run_dir


def write_history(path, history):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(history[0]))
        writer.writeheader(); writer.writerows(history)


def load_rows(path):
    if not path.is_file(): return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/bci2a_small_sample_audit.yaml"))
    parser.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 10)))
    parser.add_argument("--training-seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--primary-root", type=Path, default=Path("results/bci2a_small_sample_audit"))
    parser.add_argument("--output-root", type=Path, default=Path("results/bci2a_update_matched_diagnostic"))
    parser.add_argument("--diagnostic-freeze-commit", required=True)
    args = parser.parse_args()
    subjects, seeds = validate_subjects(args.subjects), validate_seeds(args.training_seeds)
    base = load_config(str(args.config))
    if int(base["data"]["split_seed"]) != 42 or int(base["small_sample"]["subset_seed"]) != 20260719:
        raise RuntimeError("frozen split/subset seeds changed")
    if int(base["training"]["batch_size"]) != 32:
        raise RuntimeError("frozen batch size changed")
    primary_rows = load_rows(args.primary_root / "small_sample_runs.csv")
    full_counts = {int(r["subject"]): int(r["train_sample_count"]) for r in primary_rows
                   if float(r["budget"]) == 1.0}
    rows = load_rows(args.output_root / "update_matched_runs.csv")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # Complete the identity gate for all 27 cells before the first update.
    for subject in subjects:
        for seed in seeds:
            config, _ = build_config(base, subject, seed, args.output_root)
            preflight = build_dataloaders(copy.deepcopy(config))
            original = args.primary_root / "budget_025" / f"seed_{seed}" / f"subject_{subject:02d}" / "split_indices.json"
            assert_frozen_identities(preflight, original)
    print("Preflight identity verification passed for every requested cell.")
    for subject in subjects:
        steps, target = reference_update_budget(full_counts[subject], 32, 50, False)
        for seed in seeds:
            config, run_dir = build_config(base, subject, seed, args.output_root)
            original = args.primary_root / "budget_025" / f"seed_{seed}" / f"subject_{subject:02d}" / "split_indices.json"
            identity = "matched"
            result = run_update_matched_training(config, target, steps, device)
            if assert_frozen_identities(result["data_bundle"], original) != "matched":
                raise RuntimeError("post-training identity verification failed")
            detailed = evaluate_classifier_detailed(result["model"], result["data_bundle"].test_loader, device, 4)
            if abs(detailed["accuracy"] - result["summary"]["final_test_metrics"]["accuracy"]) > 1e-12:
                raise RuntimeError("detailed test metric mismatch")
            row = {"subject": subject, "condition": CONDITION, "budget": .25,
                   "split_seed": 42, "subset_seed": 20260719, "training_seed": seed,
                   "train_sample_count": len(result["data_bundle"].train_loader.dataset),
                   "batch_size": 32, "reference_steps_per_epoch": steps,
                   "target_optimizer_updates": target,
                   "actual_optimizer_updates": result["summary"]["actual_optimizer_updates"],
                   "validation_event_count": result["summary"]["validation_event_count"],
                   "subset_identity_status": identity, "primary_metric": "accuracy",
                   "test_accuracy": detailed["accuracy"], "balanced_accuracy": detailed["balanced_accuracy"],
                   "macro_f1": detailed["macro_f1"], "checkpoint": result["summary"]["best_checkpoint"],
                   "run_status": "completed", "diagnostic_freeze_commit": args.diagnostic_freeze_commit}
            rows = [r for r in rows if (int(r["subject"]), int(r["training_seed"])) != (subject, seed)] + [row]
            write_rows(args.output_root / "update_matched_runs.csv", rows)
            write_history(run_dir / "metrics.csv", result["history"])
            (run_dir / "update_matched_result.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            print(f"Completed update-matched A{subject:02d} seed={seed}")
    print(f"Completed runs: {len(rows)}")


if __name__ == "__main__": main()
