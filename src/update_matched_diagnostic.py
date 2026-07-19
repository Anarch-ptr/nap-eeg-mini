"""Frozen utilities for the optimizer-update-matched diagnostic."""

from __future__ import annotations

import copy
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import torch
import torch.nn as nn

from src.evaluate import evaluate_classifier
from src.small_sample_analysis import validate_matrix as validate_primary_matrix
from src.train import (
    build_model,
    build_dataloaders,
    is_better_validation_result,
    restore_best_checkpoint,
    save_best_checkpoint,
    save_resolved_config,
    save_run_summary,
    save_split_indices,
    set_seed,
)


REQUIRED_SUBJECTS = tuple(range(1, 10))
REQUIRED_SEEDS = (42, 43, 44)
EXPECTED_SPLIT_SEED = 42
EXPECTED_SUBSET_SEED = 20260719
CONDITION = "update_matched_25"


def reference_update_budget(train_count: int, batch_size: int, epochs: int = 50,
                            drop_last: bool = False) -> tuple[int, int]:
    """Return exact steps/epoch and total updates under DataLoader semantics."""
    if min(train_count, batch_size, epochs) <= 0:
        raise ValueError("counts, batch size, and epochs must be positive")
    steps = train_count // batch_size if drop_last else math.ceil(train_count / batch_size)
    if steps <= 0:
        raise ValueError("drop_last would produce zero training batches")
    return steps, steps * epochs


def assert_frozen_identities(bundle, original_split_path: Path) -> str:
    """Require diagnostic subset, validation, and test identities to be frozen."""
    original = json.loads(original_split_path.read_text(encoding="utf-8"))
    expected = {
        "selected_training_indices": original["small_sample"]["selected_training_indices"],
        "validation_indices": original["validation_indices"],
        "test_indices": original["test_indices"],
    }
    actual = {
        "selected_training_indices": list(bundle.train_indices),
        "validation_indices": list(bundle.val_indices),
        "test_indices": list(bundle.test_indices),
    }
    if actual != expected:
        raise RuntimeError("diagnostic data identities differ from frozen 25% audit")
    return "matched"


def run_update_matched_training(config: dict, target_optimizer_updates: int,
                                validation_interval_updates: int,
                                device=None) -> dict:
    """Train to an exact update target and validate at reference intervals."""
    if target_optimizer_updates <= 0 or validation_interval_updates <= 0:
        raise ValueError("update targets and intervals must be positive")
    if target_optimizer_updates % validation_interval_updates:
        raise ValueError("target must end on a scheduled validation event")
    set_seed(int(config["seed"]))
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    bundle = build_dataloaders(config)
    save_split_indices(bundle, config)
    save_resolved_config(config)
    model = build_model(config).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(
        model.parameters(), lr=config["training"]["learning_rate"],
        weight_decay=config["training"].get("weight_decay", 0.0),
    )
    history = []
    updates = validation_events = 0
    best_event = None
    best_val_loss, best_val_accuracy = float("inf"), -float("inf")
    checkpoint_path = None
    iterator = iter(bundle.train_loader)
    interval_loss = interval_correct = interval_total = 0.0
    while updates < target_optimizer_updates:
        try:
            x, y = next(iterator)
        except StopIteration:
            iterator = iter(bundle.train_loader)
            x, y = next(iterator)
        model.train()
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad()
        logits = model(x)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()
        updates += 1
        interval_loss += loss.item() * x.size(0)
        interval_correct += (torch.argmax(logits, dim=1) == y).sum().item()
        interval_total += y.size(0)
        if updates % validation_interval_updates == 0:
            validation_events += 1
            val_loss, val_acc = evaluate_classifier(
                model, bundle.val_loader, criterion, device
            )
            history.append({
                "validation_event": validation_events,
                "optimizer_updates": updates,
                "train_loss": interval_loss / interval_total,
                "train_accuracy": interval_correct / interval_total,
                "val_loss": val_loss,
                "val_accuracy": val_acc,
            })
            if is_better_validation_result(
                val_acc, val_loss, best_val_accuracy, best_val_loss
            ):
                best_event = validation_events
                best_val_loss, best_val_accuracy = val_loss, val_acc
                checkpoint_path = save_best_checkpoint(
                    model, validation_events, val_loss, val_acc, config
                )
            interval_loss = interval_correct = interval_total = 0.0
            print(
                f"Validation {validation_events:02d} | updates: {updates} | "
                f"val loss: {val_loss:.4f} | val acc: {val_acc:.4f}"
            )
    expected_events = target_optimizer_updates // validation_interval_updates
    if updates != target_optimizer_updates or validation_events != expected_events:
        raise RuntimeError("update or validation-event integrity failure")
    if best_event is None:
        raise RuntimeError("no best-validation checkpoint was created")
    checkpoint = restore_best_checkpoint(model, config, device)
    test_loss, test_acc = evaluate_classifier(
        model, bundle.test_loader, criterion, device
    )
    summary = {
        "best_validation_event": best_event,
        "best_validation_metrics": checkpoint["best_validation_metrics"],
        "final_test_metrics": {"loss": test_loss, "accuracy": test_acc},
        "best_checkpoint": checkpoint_path,
        "normalization": bundle.normalization,
        "target_optimizer_updates": target_optimizer_updates,
        "actual_optimizer_updates": updates,
        "validation_event_count": validation_events,
    }
    save_run_summary(summary, config)
    return {"model": model, "data_bundle": bundle, "history": history,
            "summary": summary, "criterion": criterion, "device": device}


def validate_diagnostic_matrix(rows: list[dict]) -> list[str]:
    """Return protocol errors; outcome classification is forbidden on errors."""
    errors = []
    keys = []
    for i, row in enumerate(rows, start=2):
        label = f"row {i}"
        try:
            subject, seed = int(row["subject"]), int(row["training_seed"])
            keys.append((subject, seed))
            if row["condition"] != CONDITION or float(row["budget"]) != 0.25:
                errors.append(f"{label}: wrong condition or budget")
            if int(row["split_seed"]) != EXPECTED_SPLIT_SEED:
                errors.append(f"{label}: wrong split seed")
            if int(row["subset_seed"]) != EXPECTED_SUBSET_SEED:
                errors.append(f"{label}: wrong subset seed")
            if row["run_status"] != "completed":
                errors.append(f"{label}: failed run")
            if int(row["actual_optimizer_updates"]) != int(row["target_optimizer_updates"]):
                errors.append(f"{label}: wrong optimizer-update count")
            if int(row["validation_event_count"]) != 50:
                errors.append(f"{label}: wrong validation-event count")
            if row["subset_identity_status"] != "matched":
                errors.append(f"{label}: subset identity mismatch")
            if row["primary_metric"] != "accuracy" or not row["checkpoint"].strip():
                errors.append(f"{label}: invalid metric or checkpoint")
            if not 0 <= float(row["test_accuracy"]) <= 1:
                errors.append(f"{label}: invalid accuracy")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{label}: invalid row: {exc}")
    expected = {(s, seed) for s in REQUIRED_SUBJECTS for seed in REQUIRED_SEEDS}
    counts = Counter(keys)
    missing, unexpected = expected - set(keys), set(keys) - expected
    duplicates = [key for key, count in counts.items() if count != 1]
    if missing: errors.append(f"missing diagnostic cells: {sorted(missing)}")
    if unexpected: errors.append(f"unexpected diagnostic cells: {sorted(unexpected)}")
    if duplicates: errors.append(f"duplicate diagnostic cells: {sorted(duplicates)}")
    return list(dict.fromkeys(errors))


def analyze_diagnostic(primary_rows: list[dict], diagnostic_rows: list[dict]) -> dict:
    """Apply the four frozen update-matched classifications."""
    errors = validate_primary_matrix(primary_rows) + validate_diagnostic_matrix(diagnostic_rows)
    primary = {(int(r["subject"]), float(r["budget"]), int(r["training_seed"])):
               float(r["test_accuracy"]) for r in primary_rows
               if r.get("run_status") == "completed"}
    diagnostic = {(int(r["subject"]), int(r["training_seed"])):
                  float(r["test_accuracy"]) for r in diagnostic_rows
                  if r.get("run_status") == "completed"}
    for subject in REQUIRED_SUBJECTS:
        for seed in REQUIRED_SEEDS:
            if (subject, 1.0, seed) not in primary or (subject, .25, seed) not in primary:
                errors.append(f"missing primary reference A{subject:02d}/seed={seed}")
    subjects = []
    for subject in REQUIRED_SUBJECTS:
        full = [primary[(subject, 1.0, s)] for s in REQUIRED_SEEDS if (subject, 1.0, s) in primary]
        fixed = [primary[(subject, .25, s)] for s in REQUIRED_SEEDS if (subject, .25, s) in primary]
        matched = [diagnostic[(subject, s)] for s in REQUIRED_SEEDS if (subject, s) in diagnostic]
        if len(full) == len(fixed) == len(matched) == 3:
            f, q, m = map(statistics.mean, (full, fixed, matched))
            gap, recovery, residual = (f-q)*100, (m-q)*100, (f-m)*100
            subjects.append({"subject": subject, "accuracy_100_fixed_mean": f,
                "accuracy_25_fixed_mean": q, "accuracy_25_matched_mean": m,
                "original_gap_pp": gap, "recovery_pp": recovery,
                "residual_gap_pp": residual,
                "gap_closure_fraction": recovery/gap if gap > 0 else None})
    seed_rows = []
    for seed in REQUIRED_SEEDS:
        values = [(primary[(s, 1.0, seed)] - diagnostic[(s, seed)])*100
                  for s in REQUIRED_SUBJECTS
                  if (s, 1.0, seed) in primary and (s, seed) in diagnostic]
        seed_rows.append({"training_seed": seed, "n_subjects": len(values),
                          "median_residual_gap_pp": statistics.median(values) if values else None})
    residuals = [r["residual_gap_pp"] for r in subjects]
    integrity = not errors and len(subjects) == 9
    median_residual = statistics.median(residuals) if residuals else None
    count_ge3 = sum(v >= 3 for v in residuals)
    seed_positive = integrity and all(r["n_subjects"] == 9 and r["median_residual_gap_pp"] > 0 for r in seed_rows)
    if not integrity:
        classification = "INCOMPLETE_OR_INVALID"
    elif median_residual >= 5 and count_ge3 >= 7 and seed_positive:
        classification = "PERSISTENT_STRONG_FAILURE"
    elif median_residual < 3 and count_ge3 < 3:
        classification = "UPDATE_COUNT_EXPLAINS_MOST"
    else:
        classification = "PARTIAL_UPDATE_CONFOUND"
    closures = [r["gap_closure_fraction"] for r in subjects if r["gap_closure_fraction"] is not None]
    return {"classification": classification, "integrity_pass": integrity,
            "integrity_errors": errors,
            "original_median_gap_pp": statistics.median([r["original_gap_pp"] for r in subjects]) if subjects else None,
            "median_recovery_pp": statistics.median([r["recovery_pp"] for r in subjects]) if subjects else None,
            "median_residual_gap_pp": median_residual,
            "subjects_residual_ge_3pp": count_ge3,
            "median_gap_closure_fraction": statistics.median(closures) if closures else None,
            "seed_residual_diagnostics": seed_rows, "subject_diagnostics": subjects}
