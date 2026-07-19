"""Preregistered zero-new-training small-sample mechanism audit."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np
from scipy.signal import welch
from scipy.stats import kendalltau, spearmanr

from src.simple_control_analysis import validate_control_matrix
from src.small_sample_analysis import validate_matrix as validate_primary_matrix
from src.update_matched_diagnostic import validate_diagnostic_matrix


SUBJECTS = tuple(range(1, 10))
SEEDS = (42, 43, 44)
BANDS = ((8.0, 13.0), (13.0, 20.0), (20.0, 30.0))
FEATURE_SOURCES = {
    "full_data_accuracy": "result_descriptive",
    "seed_std_25_matched": "result_descriptive",
    "within_class_dispersion": "training_data_only",
    "between_class_separation": "training_data_only",
    "separability_ratio": "training_data_only",
    "trial_feature_variability": "training_data_only",
}


def log_bandpower_features(x: np.ndarray, sampling_rate: float) -> np.ndarray:
    """Return deterministic per-trial channel-by-band log Welch power."""
    x = np.asarray(x, dtype=np.float64)
    frequencies, power = welch(x, fs=sampling_rate, axis=-1,
                               nperseg=min(256, x.shape[-1]))
    output = []
    for low, high in BANDS:
        mask = (frequencies >= low) & (frequencies < high)
        output.append(np.log(np.trapezoid(power[..., mask], frequencies[mask], axis=-1) + 1e-12))
    return np.concatenate(output, axis=1)


def geometry_features(features: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    """Compute four frozen geometry descriptors in standardized feature space."""
    features, labels = np.asarray(features, float), np.asarray(labels)
    scale = features.std(axis=0, ddof=0)
    z = (features - features.mean(axis=0)) / np.where(scale > 1e-12, scale, 1.0)
    classes = np.unique(labels)
    centroids = np.asarray([z[labels == c].mean(axis=0) for c in classes])
    within = np.mean([np.linalg.norm(z[labels == c] - centroids[i], axis=1).mean()
                      for i, c in enumerate(classes)])
    pairwise = [np.linalg.norm(centroids[i] - centroids[j])
                for i in range(len(classes)) for j in range(i + 1, len(classes))]
    between = float(np.mean(pairwise))
    overall = float(np.linalg.norm(z - z.mean(axis=0), axis=1).mean())
    return {"within_class_dispersion": float(within),
            "between_class_separation": between,
            "separability_ratio": between / max(float(within), 1e-12),
            "trial_feature_variability": overall}


def frozen_subset_indices(primary_root: Path, subject: int) -> list[int]:
    """Require all three seed provenance files to identify the same 25% subset."""
    identities = []
    for seed in SEEDS:
        path = primary_root / "budget_025" / f"seed_{seed}" / f"subject_{subject:02d}" / "split_indices.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        small = payload["small_sample"]
        if int(small["split_seed"]) != 42 or int(small["subset_seed"]) != 20260719:
            raise RuntimeError(f"A{subject:02d}: frozen subset seed mismatch")
        if payload["validation_indices"] != small["validation_indices"] or payload["test_indices"] != small["test_indices"]:
            raise RuntimeError(f"A{subject:02d}: provenance identity mismatch")
        identities.append(small["selected_training_indices"])
    if not all(value == identities[0] for value in identities[1:]):
        raise RuntimeError(f"A{subject:02d}: seed-specific subset mismatch")
    return identities[0]


def build_subject_table(primary_rows, matched_rows, control_rows, geometry_by_subject):
    """Align subjects and aggregate seeds within subject."""
    primary = {(int(r["subject"]), float(r["budget"]), int(r["training_seed"])): float(r["test_accuracy"])
               for r in primary_rows if r.get("run_status") == "completed"}
    matched = {(int(r["subject"]), int(r["training_seed"])): float(r["test_accuracy"])
               for r in matched_rows if r.get("run_status") == "completed"}
    control = {(int(r["subject"]), int(r["training_seed"])): float(r["test_accuracy"])
               for r in control_rows if r.get("run_status") == "completed"}
    rows = []
    for subject in SUBJECTS:
        full = [primary[(subject, 1., s)] for s in SEEDS]
        fixed = [primary[(subject, .25, s)] for s in SEEDS]
        match = [matched[(subject, s)] for s in SEEDS]
        ctl = [control[(subject, s)] for s in SEEDS]
        f, q, m, c = map(statistics.mean, (full, fixed, match, ctl))
        row = {"subject": subject, "accuracy_100_fixed_mean": f,
               "accuracy_25_fixed_mean": q, "accuracy_25_matched_mean": m,
               "accuracy_25_wd_control_mean": c, "original_gap_pp": (f-q)*100,
               "residual_gap_pp": (f-m)*100, "post_control_residual_gap_pp": (f-c)*100,
               "update_matching_recovery_pp": (m-q)*100, "weight_decay_control_gain_pp": (c-m)*100,
               "seed_std_25_matched": statistics.stdev(match), "full_data_accuracy": f}
        row.update(geometry_by_subject[subject]); rows.append(row)
    return rows


def association(feature_values, outcomes, source: str) -> dict:
    """Compute rank associations, LOSO influence, and frozen category."""
    x, y = np.asarray(feature_values, float), np.asarray(outcomes, float)
    rho = float(spearmanr(x, y).statistic); tau = float(kendalltau(x, y).statistic)
    if not np.isfinite(rho): rho = 0.0
    if not np.isfinite(tau): tau = 0.0
    loso = []
    for index in range(len(x)):
        value = float(spearmanr(np.delete(x, index), np.delete(y, index)).statistic)
        loso.append(value if np.isfinite(value) else 0.0)
    sign = np.sign(rho)
    stable = sum(np.sign(v) == sign and sign != 0 for v in loso)
    robust = (abs(rho) >= .6 and np.sign(tau) == sign and sign != 0
              and stable >= 8 and abs(statistics.median(loso)) >= .5)
    if robust:
        category = "ROBUST_CANDIDATE_SIGNAL" if source == "training_data_only" else "ROBUST_DESCRIPTIVE_ASSOCIATION"
    elif abs(rho) < .3 and abs(statistics.median(loso)) < .3:
        category = "NO_CLEAR_ASSOCIATION"
    else:
        category = "WEAK_OR_UNSTABLE_ASSOCIATION"
    return {"feature_source": source, "spearman_rho": rho, "kendall_tau": tau,
            "loso_min_spearman_rho": min(loso), "loso_max_spearman_rho": max(loso),
            "loso_median_spearman_rho": statistics.median(loso),
            "direction_stability_count": stable, "classification": category,
            "loso_values": loso}


def analyze(subject_rows, primary_rows, matched_rows, control_rows, provenance_ok=True):
    """Validate frozen inputs and analyze the preregistered six features."""
    errors = (validate_primary_matrix(primary_rows) + validate_diagnostic_matrix(matched_rows)
              + validate_control_matrix(control_rows))
    if [r["subject"] for r in subject_rows] != list(SUBJECTS):
        errors.append("subject alignment mismatch")
    if not provenance_ok: errors.append("frozen subset provenance mismatch")
    if errors:
        associations = [{"feature_name": name, "feature_source": source,
            "spearman_rho": None, "kendall_tau": None,
            "loso_min_spearman_rho": None, "loso_max_spearman_rho": None,
            "loso_median_spearman_rho": None, "direction_stability_count": 0,
            "classification": "INCOMPLETE_OR_INVALID", "loso_values": []}
            for name, source in FEATURE_SOURCES.items()]
        return {"integrity_pass": False, "integrity_errors": list(dict.fromkeys(errors)),
                "primary_target": "residual_gap_pp", "statistical_unit": "subject",
                "n_subjects": len(subject_rows), "subject_rows": subject_rows,
                "associations": associations}
    outcomes = [r["residual_gap_pp"] for r in subject_rows]
    associations = []
    for name, source in FEATURE_SOURCES.items():
        result = association([r[name] for r in subject_rows], outcomes, source)
        result["feature_name"] = name; associations.append(result)
    return {"integrity_pass": True, "integrity_errors": [],
            "primary_target": "residual_gap_pp", "statistical_unit": "subject", "n_subjects": 9,
            "subject_rows": subject_rows, "associations": associations}
