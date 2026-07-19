"""Frozen analysis for the preregistered weight-decay simple control."""

from __future__ import annotations

import statistics
from collections import Counter

from src.small_sample_analysis import validate_matrix as validate_primary_matrix
from src.update_matched_diagnostic import validate_diagnostic_matrix


REQUIRED_SUBJECTS = tuple(range(1, 10))
REQUIRED_SEEDS = (42, 43, 44)
CONDITION = "update_matched_25_wd1e3"
EXPECTED_WEIGHT_DECAY = 1e-3


def validate_control_matrix(rows: list[dict]) -> list[str]:
    """Validate the isolated 27-cell simple-control matrix."""
    errors, keys = [], []
    for position, row in enumerate(rows, start=2):
        label = f"row {position}"
        try:
            subject, seed = int(row["subject"]), int(row["training_seed"])
            keys.append((subject, seed))
            if row["condition"] != CONDITION or float(row["budget"]) != .25:
                errors.append(f"{label}: wrong condition or budget")
            if float(row["weight_decay"]) != EXPECTED_WEIGHT_DECAY:
                errors.append(f"{label}: wrong effective weight_decay")
            if int(row["split_seed"]) != 42 or int(row["subset_seed"]) != 20260719:
                errors.append(f"{label}: wrong split or subset seed")
            if int(row["target_optimizer_updates"]) != 400 or int(row["actual_optimizer_updates"]) != 400:
                errors.append(f"{label}: wrong optimizer-update count")
            if int(row["validation_event_count"]) != 50:
                errors.append(f"{label}: wrong validation-event count")
            if row["subset_identity_status"] != "matched":
                errors.append(f"{label}: subset identity mismatch")
            if row["run_status"] != "completed":
                errors.append(f"{label}: failed run")
            if row["primary_metric"] != "accuracy" or not row["checkpoint"].strip():
                errors.append(f"{label}: invalid metric or checkpoint")
            if not 0 <= float(row["test_accuracy"]) <= 1:
                errors.append(f"{label}: invalid accuracy")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{label}: invalid row: {exc}")
    expected = {(s, seed) for s in REQUIRED_SUBJECTS for seed in REQUIRED_SEEDS}
    counts = Counter(keys)
    if expected - set(keys): errors.append(f"missing control cells: {sorted(expected-set(keys))}")
    if set(keys) - expected: errors.append(f"unexpected control cells: {sorted(set(keys)-expected)}")
    duplicates = sorted(k for k, count in counts.items() if count != 1)
    if duplicates: errors.append(f"duplicate control cells: {duplicates}")
    return list(dict.fromkeys(errors))


def analyze_simple_control(primary_rows: list[dict], matched_rows: list[dict],
                           control_rows: list[dict]) -> dict:
    """Apply frozen classification rules with the preregistered precedence."""
    errors = (validate_primary_matrix(primary_rows)
              + validate_diagnostic_matrix(matched_rows)
              + validate_control_matrix(control_rows))
    primary = {(int(r["subject"]), float(r["budget"]), int(r["training_seed"])):
               float(r["test_accuracy"]) for r in primary_rows if r.get("run_status") == "completed"}
    matched = {(int(r["subject"]), int(r["training_seed"])): float(r["test_accuracy"])
               for r in matched_rows if r.get("run_status") == "completed"}
    control = {(int(r["subject"]), int(r["training_seed"])): float(r["test_accuracy"])
               for r in control_rows if r.get("run_status") == "completed"}
    subjects = []
    for subject in REQUIRED_SUBJECTS:
        full = [primary[(subject, 1., seed)] for seed in REQUIRED_SEEDS
                if (subject, 1., seed) in primary]
        base = [matched[(subject, seed)] for seed in REQUIRED_SEEDS if (subject, seed) in matched]
        ctl = [control[(subject, seed)] for seed in REQUIRED_SEEDS if (subject, seed) in control]
        if len(full) == len(base) == len(ctl) == 3:
            f, b, c = map(statistics.mean, (full, base, ctl))
            before, gain, residual = (f-b)*100, (c-b)*100, (f-c)*100
            subjects.append({"subject": subject, "accuracy_100_fixed_mean": f,
                "accuracy_25_matched_mean": b, "accuracy_25_matched_wd1e3_mean": c,
                "matched_residual_gap_pp": before, "control_gain_pp": gain,
                "control_residual_gap_pp": residual,
                "control_gap_closure_fraction": gain/before if before > 0 else None})
    seeds = []
    for seed in REQUIRED_SEEDS:
        residuals = [(primary[(s, 1., seed)]-control[(s, seed)])*100
                     for s in REQUIRED_SUBJECTS
                     if (s, 1., seed) in primary and (s, seed) in control]
        seeds.append({"training_seed": seed, "n_subjects": len(residuals),
                      "median_control_residual_gap_pp": statistics.median(residuals) if residuals else None})
    integrity = not errors and len(subjects) == 9
    residuals = [r["control_residual_gap_pp"] for r in subjects]
    gains = [r["control_gain_pp"] for r in subjects]
    med_residual = statistics.median(residuals) if residuals else None
    med_gain = statistics.median(gains) if gains else None
    residual_ge3 = sum(v >= 3 for v in residuals)
    gain_ge3 = sum(v >= 3 for v in gains)
    seed_positive = integrity and all(s["n_subjects"] == 9 and s["median_control_residual_gap_pp"] > 0 for s in seeds)
    persistent = integrity and med_residual >= 5 and residual_ge3 >= 7 and seed_positive
    solves = integrity and med_residual < 3 and residual_ge3 < 3
    no_benefit = persistent and med_gain < 1 and gain_ge3 < 3
    if not integrity: classification = "INCOMPLETE_OR_INVALID"
    elif solves: classification = "SIMPLE_CONTROL_SOLVES_MOST"
    elif no_benefit: classification = "NO_MEANINGFUL_CONTROL_BENEFIT"
    elif persistent: classification = "PERSISTENT_STRONG_FAILURE_AFTER_CONTROL"
    else: classification = "PARTIAL_SIMPLE_CONTROL_EFFECT"
    closures = [r["control_gap_closure_fraction"] for r in subjects
                if r["control_gap_closure_fraction"] is not None]
    return {"classification": classification, "integrity_pass": integrity,
            "integrity_errors": list(dict.fromkeys(errors)),
            "median_matched_residual_gap_pp": statistics.median([r["matched_residual_gap_pp"] for r in subjects]) if subjects else None,
            "median_control_gain_pp": med_gain, "median_control_residual_gap_pp": med_residual,
            "subjects_control_residual_ge_3pp": residual_ge3,
            "subjects_control_gain_ge_3pp": gain_ge3,
            "median_control_gap_closure_fraction": statistics.median(closures) if closures else None,
            "seed_control_residual_diagnostics": seeds, "subject_control_diagnostics": subjects}
