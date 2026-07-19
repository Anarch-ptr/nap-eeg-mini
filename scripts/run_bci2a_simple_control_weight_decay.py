"""Run the frozen weight_decay=1e-3 update-matched simple control."""

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
from src.update_matched_diagnostic import assert_frozen_identities, run_update_matched_training


CONDITION = "update_matched_25_wd1e3"
FIELDS = ["subject", "condition", "budget", "weight_decay", "split_seed",
          "subset_seed", "training_seed", "train_sample_count", "batch_size",
          "target_optimizer_updates", "actual_optimizer_updates",
          "validation_event_count", "subset_identity_status", "primary_metric",
          "test_accuracy", "balanced_accuracy", "macro_f1", "checkpoint",
          "run_status", "simple_control_freeze_commit"]


def config_for(base, subject, seed, root):
    config = copy.deepcopy(base); config["seed"] = seed
    config["data"]["subject_id"] = subject
    config["small_sample"]["budget"] = .25
    config["training"]["weight_decay"] = 1e-3
    run_dir = root / f"seed_{seed}" / f"subject_{subject:02d}"
    config["output"]["table_dir"] = str(run_dir)
    return config, run_dir


def load_rows(path):
    if not path.is_file(): return []
    with path.open(encoding="utf-8", newline="") as f: return list(csv.DictReader(f))


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)


def write_history(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("configs/bci2a_small_sample_audit.yaml"))
    p.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 10)))
    p.add_argument("--training-seeds", type=int, nargs="+", default=[42, 43, 44])
    p.add_argument("--primary-root", type=Path, default=Path("results/bci2a_small_sample_audit"))
    p.add_argument("--output-root", type=Path, default=Path("results/bci2a_simple_control_weight_decay"))
    p.add_argument("--simple-control-freeze-commit", required=True)
    a = p.parse_args(); subjects = validate_subjects(a.subjects); seeds = validate_seeds(a.training_seeds)
    base = load_config(str(a.config))
    if float(base["training"]["weight_decay"]) != 1e-4:
        raise RuntimeError("sealed reference weight_decay is not 1e-4")
    frozen = {"dropout": .25, "learning_rate": .001, "batch_size": 32,
              "split_seed": 42, "subset_seed": 20260719}
    actual = {"dropout": float(base["model"]["dropout"]),
              "learning_rate": float(base["training"]["learning_rate"]),
              "batch_size": int(base["training"]["batch_size"]),
              "split_seed": int(base["data"]["split_seed"]),
              "subset_seed": int(base["small_sample"]["subset_seed"])}
    if actual != frozen: raise RuntimeError(f"frozen non-control variables changed: {actual}")
    # Gate every identity before the first control optimizer update.
    for subject in subjects:
        for seed in seeds:
            config, _ = config_for(base, subject, seed, a.output_root)
            bundle = build_dataloaders(copy.deepcopy(config))
            original = a.primary_root / "budget_025" / f"seed_{seed}" / f"subject_{subject:02d}" / "split_indices.json"
            assert_frozen_identities(bundle, original)
    print("Preflight identity verification passed for every requested cell.")
    rows = load_rows(a.output_root / "simple_control_runs.csv")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    for subject in subjects:
        for seed in seeds:
            config, run_dir = config_for(base, subject, seed, a.output_root)
            result = run_update_matched_training(config, 400, 8, device)
            original = a.primary_root / "budget_025" / f"seed_{seed}" / f"subject_{subject:02d}" / "split_indices.json"
            identity = assert_frozen_identities(result["data_bundle"], original)
            detailed = evaluate_classifier_detailed(result["model"], result["data_bundle"].test_loader, device, 4)
            if abs(detailed["accuracy"]-result["summary"]["final_test_metrics"]["accuracy"]) > 1e-12:
                raise RuntimeError("detailed test metric mismatch")
            row = {"subject": subject, "condition": CONDITION, "budget": .25,
                   "weight_decay": config["training"]["weight_decay"], "split_seed": 42,
                   "subset_seed": 20260719, "training_seed": seed,
                   "train_sample_count": len(result["data_bundle"].train_loader.dataset),
                   "batch_size": 32, "target_optimizer_updates": 400,
                   "actual_optimizer_updates": result["summary"]["actual_optimizer_updates"],
                   "validation_event_count": result["summary"]["validation_event_count"],
                   "subset_identity_status": identity, "primary_metric": "accuracy",
                   "test_accuracy": detailed["accuracy"], "balanced_accuracy": detailed["balanced_accuracy"],
                   "macro_f1": detailed["macro_f1"], "checkpoint": result["summary"]["best_checkpoint"],
                   "run_status": "completed", "simple_control_freeze_commit": a.simple_control_freeze_commit}
            rows = [r for r in rows if (int(r["subject"]), int(r["training_seed"])) != (subject, seed)] + [row]
            write_rows(a.output_root / "simple_control_runs.csv", rows)
            write_history(run_dir / "metrics.csv", result["history"])
            (run_dir / "simple_control_result.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            print(f"Completed wd1e3 A{subject:02d} seed={seed}")
    print(f"Completed runs: {len(rows)}")


if __name__ == "__main__": main()
