"""Frozen zero-training spatial covariance mechanism audit."""

from __future__ import annotations

import numpy as np

from src.mechanism_audit import association
from src.subset_representativeness import reconstruct_partition


ALPHA = 1e-3
FEATURES = ("cov_within_class_dispersion", "cov_between_class_separation",
            "cov_separability_ratio")
SUBJECTS = tuple(range(1, 10))


def trial_covariance(trial: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    """Center a channel-time trial and return trace-normalized regularized SPD."""
    x = np.asarray(trial, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] < 2: raise ValueError("trial must be channels x time")
    centered = x - x.mean(axis=1, keepdims=True)
    covariance = centered @ centered.T / (x.shape[1]-1)
    trace = float(np.trace(covariance))
    if not np.isfinite(trace) or trace <= 1e-12: raise RuntimeError("non-positive covariance trace")
    normalized = covariance / trace; channels = x.shape[0]
    regularized = (1.-alpha)*normalized + alpha*np.eye(channels)/channels
    if np.linalg.eigvalsh(regularized).min() <= 0: raise RuntimeError("SPD regularization failed")
    return regularized


def matrix_log_spd(matrix: np.ndarray) -> np.ndarray:
    """Compute symmetric matrix logarithm by stable eigendecomposition."""
    eigenvalues, eigenvectors = np.linalg.eigh(np.asarray(matrix, float))
    if eigenvalues.min() <= 0: raise RuntimeError("matrix logarithm requires SPD input")
    return (eigenvectors * np.log(np.maximum(eigenvalues, 1e-15))) @ eigenvectors.T


def log_covariance_trials(x: np.ndarray) -> np.ndarray:
    """Deterministically transform trials to log-covariance matrices."""
    return np.asarray([matrix_log_spd(trial_covariance(trial)) for trial in np.asarray(x)])


def log_euclidean_distance(first, second) -> float:
    return float(np.linalg.norm(np.asarray(first)-np.asarray(second), ord="fro"))


def covariance_geometry(log_covariances: np.ndarray, labels: np.ndarray) -> dict:
    """Calculate exactly three frozen class-balanced covariance properties."""
    values, labels = np.asarray(log_covariances, float), np.asarray(labels)
    centroids=[]; per_class=[]
    for class_id in range(4):
        members=values[labels==class_id]
        if len(members)==0: raise RuntimeError(f"class {class_id} absent")
        centroid=members.mean(axis=0);centroids.append(centroid)
        per_class.append(float(np.mean([log_euclidean_distance(v,centroid) for v in members])))
    within=float(np.mean(per_class))
    between=float(np.mean([log_euclidean_distance(centroids[i],centroids[j])
                           for i in range(4) for j in range(i+1,4)]))
    return {"cov_within_class_dispersion":within,
            "cov_between_class_separation":between,
            "cov_separability_ratio":between/(within+1e-12),
            "cov_within_per_class":per_class}


def frozen_subset(primary_root, subject):
    """Return exact selected indices after full partition/provenance validation."""
    return reconstruct_partition(primary_root, subject)["subset_indices"]


def analyze(rows, integrity_errors=None):
    errors=list(integrity_errors or [])
    if [r.get("subject") for r in rows] != list(SUBJECTS):errors.append("subject alignment mismatch")
    if errors:
        associations=[{"feature_name":f,"feature_source":"training_data_only","spearman_rho":None,
            "kendall_tau":None,"loso_min_spearman_rho":None,"loso_max_spearman_rho":None,
            "loso_median_spearman_rho":None,"direction_stability_count":0,
            "classification":"INCOMPLETE_OR_INVALID","loso_values":[]} for f in FEATURES]
    else:
        outcomes=[r["residual_gap_pp"] for r in rows];associations=[]
        for feature in FEATURES:
            result=association([r[feature] for r in rows],outcomes,"training_data_only")
            result["feature_name"]=feature;associations.append(result)
    return {"integrity_pass":not errors,"integrity_errors":errors,"primary_target":"residual_gap_pp",
            "statistical_unit":"subject","n_subjects":len(rows),"subject_rows":rows,"associations":associations}
