"""Frozen Pair-Set-1 covariance-separation intervention utilities."""

from __future__ import annotations

import copy
import json
import statistics
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.data import load_bci2a_subject
from src.evaluate import evaluate_classifier, evaluate_classifier_detailed
from src.small_sample_analysis import validate_matrix as validate_primary_matrix
from src.train import (DataBundle, build_model, is_better_validation_result,
                       restore_best_checkpoint, save_best_checkpoint,
                       save_resolved_config, save_run_summary, save_split_indices,
                       set_seed)

SUBJECTS = tuple(range(1, 10))
SEEDS = (42, 43, 44)
CONDITIONS = ("LOW_SEP", "HIGH_SEP")
FEASIBILITY_COMMIT = "3241f01"
TARGET_UPDATES = 400
VALIDATION_INTERVAL = 8
VALIDATION_EVENTS = 50


def load_frozen_pairs(path: Path) -> dict[int, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("classification") != "INTERVENTION_FEASIBLE" or not payload.get("integrity_pass"):
        raise RuntimeError("authoritative feasibility output did not pass")
    rows = {int(row["subject"]): row for row in payload["subject_rows"]}
    if set(rows) != set(SUBJECTS):
        raise RuntimeError("frozen feasibility output does not contain A01-A09")
    for subject, row in rows.items():
        for side in ("low", "high"):
            indices = [int(v) for v in row[f"{side}_trial_indices"]]
            if len(indices) != int(row["subset_size"]) or len(indices) != len(set(indices)):
                raise RuntimeError(f"invalid frozen {side} identity for A{subject:02d}")
    return rows


def selected_identity(pair: dict, condition: str) -> tuple[int, list[int], float, float]:
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}")
    side = "low" if condition == "LOW_SEP" else "high"
    return (int(pair[f"{side}_candidate_id"]),
            [int(v) for v in pair[f"{side}_trial_indices"]],
            float(pair[f"{side}_separation"]),
            float(pair[f"{side}_separation_percentile"]))


def build_intervention_dataloaders(config: dict, pair: dict, condition: str) -> DataBundle:
    """Build the frozen official-session split with explicit Pair-Set-1 indices."""
    data = config["data"]
    subject = int(data["subject_id"])
    loaded = load_bci2a_subject(subject, data.get("data_dir", "data/moabb"),
                                data.get("fmin", 8.0), data.get("fmax", 32.0),
                                data.get("tmin", 0.0), data.get("tmax", 4.0))
    x, y = torch.from_numpy(loaded.x_train).float(), torch.from_numpy(loaded.y_train).long()
    split_seed = int(data.get("split_seed", config["seed"]))
    shuffled = torch.randperm(len(x), generator=torch.Generator().manual_seed(split_seed))
    train_size = int(float(data.get("train_ratio", .8)) * len(x))
    pool, val = shuffled[:train_size], shuffled[train_size:]
    _, identities, _, _ = selected_identity(pair, condition)
    chosen = torch.tensor(identities, dtype=torch.long)
    if not set(identities).issubset(set(int(v) for v in pool.tolist())):
        raise RuntimeError("intervention subset is not contained in fixed training pool")
    expected_counts = [int(v) for v in pair["per_class_counts"]]
    actual_counts = np.bincount(y[chosen].numpy(), minlength=4).tolist()
    if actual_counts != expected_counts:
        raise RuntimeError("frozen intervention class counts do not match")
    x_train, y_train = x[chosen], y[chosen]
    x_val, y_val = x[val], y[val]
    x_test = torch.from_numpy(loaded.x_test).float()
    y_test = torch.from_numpy(loaded.y_test).long()
    mean = x_train.mean(dim=(0, 2), keepdim=True)
    std = x_train.std(dim=(0, 2), keepdim=True).clamp_min(1e-6)
    x_train, x_val, x_test = ((z - mean) / std for z in (x_train, x_val, x_test))
    batch = int(config["training"]["batch_size"])
    bundle = DataBundle(
        train_loader=DataLoader(TensorDataset(x_train, y_train), batch_size=batch,
                                shuffle=True, generator=torch.Generator().manual_seed(int(config["seed"]))),
        val_loader=DataLoader(TensorDataset(x_val, y_val), batch_size=batch, shuffle=False),
        test_loader=DataLoader(TensorDataset(x_test, y_test), batch_size=batch, shuffle=False),
        train_indices=identities, val_indices=[int(v) for v in val.tolist()],
        test_indices=list(range(len(x_test))),
        normalization={"source": "condition_train_subset", "condition": condition,
                       "mean": mean.squeeze().tolist(), "std": std.squeeze().tolist()},
        modality="eeg", channel_names=list(loaded.channel_names),
        channel_types=["eeg"] * 22, sampling_rate=loaded.sampling_rate,
        subject_id=subject, training_pool_indices=[int(v) for v in pool.tolist()])
    data["num_channels"], data["num_samples"], data["num_classes"] = 22, int(x.shape[2]), 4
    return bundle


def assert_pair_identity(bundle: DataBundle, pair: dict, condition: str) -> str:
    _, expected, _, _ = selected_identity(pair, condition)
    if bundle.train_indices != expected:
        raise RuntimeError("trial identities differ from frozen feasibility output")
    if set(bundle.train_indices) & set(bundle.val_indices):
        raise RuntimeError("training/validation contamination")
    if bundle.test_indices != list(range(288)):
        raise RuntimeError("official-test identity mismatch")
    return "matched"


def run_intervention_training(config: dict, pair: dict, condition: str, device=None) -> dict:
    set_seed(int(config["seed"]))
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    bundle = build_intervention_dataloaders(config, pair, condition)
    assert_pair_identity(bundle, pair, condition)
    save_split_indices(bundle, config); save_resolved_config(config)
    model, criterion = build_model(config).to(device), nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=config["training"]["learning_rate"],
                                 weight_decay=config["training"]["weight_decay"])
    iterator, history = iter(bundle.train_loader), []
    updates = events = 0; best_event = None
    best_loss, best_accuracy = float("inf"), -float("inf")
    interval_loss = interval_correct = interval_total = 0.0
    checkpoint_path = None
    while updates < TARGET_UPDATES:
        try: x_batch, y_batch = next(iterator)
        except StopIteration:
            iterator = iter(bundle.train_loader); x_batch, y_batch = next(iterator)
        model.train(); x_batch, y_batch = x_batch.to(device), y_batch.to(device)
        optimizer.zero_grad(); logits = model(x_batch); loss = criterion(logits, y_batch)
        loss.backward(); optimizer.step(); updates += 1
        interval_loss += loss.item() * len(y_batch)
        interval_correct += (logits.argmax(1) == y_batch).sum().item(); interval_total += len(y_batch)
        if updates % VALIDATION_INTERVAL == 0:
            events += 1
            val_loss, val_accuracy = evaluate_classifier(model, bundle.val_loader, criterion, device)
            history.append({"validation_event": events, "optimizer_updates": updates,
                            "train_loss": interval_loss/interval_total,
                            "train_accuracy": interval_correct/interval_total,
                            "val_loss": val_loss, "val_accuracy": val_accuracy})
            if is_better_validation_result(val_accuracy, val_loss, best_accuracy, best_loss):
                best_event, best_loss, best_accuracy = events, val_loss, val_accuracy
                checkpoint_path = save_best_checkpoint(model, events, val_loss, val_accuracy, config)
            interval_loss = interval_correct = interval_total = 0.0
    if updates != TARGET_UPDATES or events != VALIDATION_EVENTS or best_event is None:
        raise RuntimeError("training schedule integrity failure")
    restored = restore_best_checkpoint(model, config, device)
    metrics = evaluate_classifier_detailed(model, bundle.test_loader, device, 4)
    summary = {"best_validation_event": best_event,
               "best_validation_metrics": restored["best_validation_metrics"],
               "final_test_metrics": metrics, "best_checkpoint": checkpoint_path,
               "normalization": bundle.normalization, "target_optimizer_updates": TARGET_UPDATES,
               "actual_optimizer_updates": updates, "validation_event_count": events,
               "official_test_evaluations": 1, "best_checkpoint_restored_before_test": True}
    save_run_summary(summary, config)
    return {"model": model, "data_bundle": bundle, "history": history,
            "summary": summary, "metrics": metrics, "device": device}


def validate_intervention_matrix(rows: list[dict], pairs: dict[int, dict]) -> list[str]:
    errors, keys = [], []
    for index, row in enumerate(rows, 2):
        label = f"row {index}"
        try:
            subject, condition, seed = int(row["subject"]), row["condition"], int(row["training_seed"])
            keys.append((subject, condition, seed))
            candidate, identities, separation, percentile = selected_identity(pairs[subject], condition)
            checks = [(int(row["candidate_id"]) == candidate, "wrong candidate identity"),
                      (json.loads(row["trial_indices"]) == identities, "wrong trial identity"),
                      (int(row["sample_count"]) == len(identities), "wrong sample count"),
                      (json.loads(row["per_class_counts"]) == pairs[subject]["per_class_counts"], "wrong class counts"),
                      (int(row["target_optimizer_updates"]) == TARGET_UPDATES, "wrong target optimizer-update count"),
                      (int(row["actual_optimizer_updates"]) == TARGET_UPDATES, "wrong optimizer-update count"),
                      (int(row["validation_event_count"]) == VALIDATION_EVENTS, "wrong validation-event count"),
                      (row["frozen_feasibility_commit"] == FEASIBILITY_COMMIT, "wrong feasibility freeze commit"),
                      (row["trial_identity_integrity"] == "matched", "trial identity mismatch"),
                      (row["run_status"] == "completed", "failed run"),
                      (int(row["official_test_evaluations"]) == 1 and row["best_checkpoint_restored_before_test"] == "True", "official-test policy failure")]
            for ok, message in checks:
                if not ok: errors.append(f"{label}: {message}")
            if abs(float(row["separation_value"]) - separation) > 1e-12 or abs(float(row["separation_percentile"]) - percentile) > 1e-12:
                errors.append(f"{label}: wrong separation metadata")
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"{label}: invalid row: {exc}")
    expected = {(s, c, seed) for s in SUBJECTS for c in CONDITIONS for seed in SEEDS}
    counts = Counter(keys)
    if expected - set(keys): errors.append(f"missing intervention cells: {sorted(expected-set(keys))}")
    if set(keys) - expected: errors.append(f"unexpected intervention cells: {sorted(set(keys)-expected)}")
    duplicates = sorted(k for k, count in counts.items() if count != 1)
    if duplicates: errors.append(f"duplicate intervention cells: {duplicates}")
    return list(dict.fromkeys(errors))


def analyze_intervention(rows: list[dict], pairs: dict[int, dict], primary_rows: list[dict]) -> dict:
    errors = validate_intervention_matrix(rows, pairs) + validate_primary_matrix(primary_rows)
    values = {(int(r["subject"]), r["condition"], int(r["training_seed"])): float(r["test_accuracy"])
              for r in rows if r.get("run_status") == "completed"}
    references = {(int(r["subject"]), int(r["training_seed"])): float(r["test_accuracy"])
                  for r in primary_rows if float(r["budget"]) == 1.0 and r.get("run_status") == "completed"}
    subjects = []
    for subject in SUBJECTS:
        low = [values[(subject, "LOW_SEP", seed)] for seed in SEEDS if (subject, "LOW_SEP", seed) in values]
        high = [values[(subject, "HIGH_SEP", seed)] for seed in SEEDS if (subject, "HIGH_SEP", seed) in values]
        full = [references[(subject, seed)] for seed in SEEDS if (subject, seed) in references]
        if len(low) == len(high) == len(full) == 3:
            lo, hi, ref = statistics.mean(low), statistics.mean(high), statistics.mean(full)
            subjects.append({"subject": subject, "accuracy_low": lo, "accuracy_high": hi,
                             "intervention_effect_pp": 100*(hi-lo),
                             "accuracy_100_fixed": ref,
                             "low_residual_gap_pp": 100*(ref-lo),
                             "high_residual_gap_pp": 100*(ref-hi)})
    seed_rows = []
    for seed in SEEDS:
        effects = [100*(values[(s,"HIGH_SEP",seed)]-values[(s,"LOW_SEP",seed)])
                   for s in SUBJECTS if (s,"HIGH_SEP",seed) in values and (s,"LOW_SEP",seed) in values]
        seed_rows.append({"training_seed": seed, "n_subjects": len(effects),
                          "median_intervention_effect_pp": statistics.median(effects) if effects else None})
    integrity = not errors and len(subjects) == 9
    effects = [r["intervention_effect_pp"] for r in subjects]
    median = statistics.median(effects) if effects else None
    negative, positive = sum(v < 0 for v in effects), sum(v > 0 for v in effects)
    if not integrity: classification = "INCOMPLETE_OR_INVALID"
    elif median <= -3 and negative >= 7 and all(r["median_intervention_effect_pp"] < 0 for r in seed_rows): classification = "HIGH_SEPARATION_WORSE"
    elif median >= 3 and positive >= 7 and all(r["median_intervention_effect_pp"] > 0 for r in seed_rows): classification = "HIGH_SEPARATION_BETTER"
    elif abs(median) < 1 and sum(abs(v) >= 3 for v in effects) < 3: classification = "NO_MEANINGFUL_INTERVENTION_EFFECT"
    else: classification = "HETEROGENEOUS_OR_WEAK_INTERVENTION_EFFECT"
    return {"classification": classification, "evidence_label": "FIRST_INTERVENTION_STYLE_EVIDENCE",
            "integrity_pass": integrity, "integrity_errors": errors,
            "median_intervention_effect_pp": median, "subjects_high_worse": negative,
            "subjects_high_better": positive, "subjects_abs_effect_ge_3pp": sum(abs(v)>=3 for v in effects),
            "subject_results": subjects, "seed_diagnostics": seed_rows}
