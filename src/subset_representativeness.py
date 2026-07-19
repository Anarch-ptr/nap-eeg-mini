"""Frozen zero-training subset representativeness utilities."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.mechanism_audit import association, log_bandpower_features


SUBJECTS = tuple(range(1, 10))
SEEDS = (42, 43, 44)
FEATURES = ("class_centroid_shift", "class_covariance_shift",
            "class_coverage_distance", "worst_class_coverage_distance")


def reconstruct_partition(primary_root: Path, subject: int) -> dict:
    """Reconstruct and verify subset/remainder partition from frozen provenance."""
    records = []
    for seed in SEEDS:
        path = primary_root / "budget_025" / f"seed_{seed}" / f"subject_{subject:02d}" / "split_indices.json"
        payload = json.loads(path.read_text(encoding="utf-8")); small = payload["small_sample"]
        record = {"pool": small["training_pool_indices"],
                  "subset": small["selected_training_indices"],
                  "validation": payload["validation_indices"], "test": payload["test_indices"],
                  "split_seed": small["split_seed"], "subset_seed": small["subset_seed"]}
        records.append(record)
    if not all(record == records[0] for record in records[1:]):
        raise RuntimeError(f"A{subject:02d}: seed provenance mismatch")
    record = records[0]
    if int(record["split_seed"]) != 42 or int(record["subset_seed"]) != 20260719:
        raise RuntimeError(f"A{subject:02d}: frozen seed mismatch")
    pool, subset, validation = map(set, (record["pool"], record["subset"], record["validation"]))
    remainder = pool - subset
    if not subset or subset & remainder or subset | remainder != pool:
        raise RuntimeError(f"A{subject:02d}: invalid subset/remainder partition")
    if pool & validation or subset & validation or remainder & validation:
        raise RuntimeError(f"A{subject:02d}: validation leaked into training pool")
    # Official-test indices are session-local identities, never indexes into 0train.
    # Their only permitted use here is the provenance assertion that 288 are recorded.
    if record["test"] != list(range(288)):
        raise RuntimeError(f"A{subject:02d}: unexpected official-test provenance")
    return {"training_pool_indices": record["pool"], "subset_indices": record["subset"],
            "remainder_indices": [i for i in record["pool"] if i in remainder],
            "validation_indices": record["validation"], "test_indices": record["test"]}


def shared_normalize(pool_features, subset_features, remainder_features):
    """Map subset and remainder into coordinates fitted on the full training pool."""
    pool = np.asarray(pool_features, float)
    mean, std = pool.mean(axis=0), pool.std(axis=0, ddof=0)
    safe = np.where(std > 1e-12, std, 1.0)
    return ((np.asarray(subset_features)-mean)/safe,
            (np.asarray(remainder_features)-mean)/safe)


def representativeness_features(subset_features, subset_labels,
                                remainder_features, remainder_labels) -> dict:
    """Calculate the four frozen class-balanced representativeness properties."""
    subset_features, remainder_features = map(lambda x: np.asarray(x, float),
                                               (subset_features, remainder_features))
    subset_labels, remainder_labels = map(np.asarray, (subset_labels, remainder_labels))
    centroids, covariances, coverages = [], [], []
    for class_id in range(4):
        a, b = subset_features[subset_labels == class_id], remainder_features[remainder_labels == class_id]
        if len(a) < 2 or len(b) < 2: raise RuntimeError(f"class {class_id} lacks covariance samples")
        centroid = float(np.linalg.norm(a.mean(axis=0)-b.mean(axis=0)))
        cov_a, cov_b = np.cov(a, rowvar=False), np.cov(b, rowvar=False)
        covariance = float(np.linalg.norm(cov_a-cov_b, ord="fro") /
                           (np.linalg.norm(cov_b, ord="fro")+1e-12))
        distances = np.linalg.norm(b[:, None, :]-a[None, :, :], axis=2)
        coverage = float(distances.min(axis=1).mean())
        centroids.append(centroid); covariances.append(covariance); coverages.append(coverage)
    return {"class_centroid_shift": float(np.mean(centroids)),
            "class_covariance_shift": float(np.mean(covariances)),
            "class_coverage_distance": float(np.mean(coverages)),
            "worst_class_coverage_distance": float(np.max(coverages)),
            "centroid_shift_per_class": centroids,
            "covariance_shift_per_class": covariances,
            "coverage_distance_per_class": coverages}


def analyze(rows: list[dict], integrity_errors=None) -> dict:
    """Apply the unchanged training-only association gate to four frozen features."""
    errors = list(integrity_errors or [])
    if [row.get("subject") for row in rows] != list(SUBJECTS):
        errors.append("subject alignment mismatch")
    associations = []
    if not errors:
        outcomes = [row["residual_gap_pp"] for row in rows]
        for feature in FEATURES:
            result = association([row[feature] for row in rows], outcomes, "training_data_only")
            result["feature_name"] = feature; associations.append(result)
    else:
        associations = [{"feature_name": f, "feature_source": "training_data_only",
            "spearman_rho": None, "kendall_tau": None, "loso_min_spearman_rho": None,
            "loso_max_spearman_rho": None, "loso_median_spearman_rho": None,
            "direction_stability_count": 0, "classification": "INCOMPLETE_OR_INVALID",
            "loso_values": []} for f in FEATURES]
    return {"integrity_pass": not errors, "integrity_errors": errors,
            "primary_target": "residual_gap_pp", "statistical_unit": "subject",
            "n_subjects": len(rows), "subject_rows": rows, "associations": associations}
