"""Frozen zero-training diagnostics for the EEGNet instability review."""

from __future__ import annotations

import hashlib
import json
import math
from itertools import combinations

import numpy as np
from sklearn.metrics import cohen_kappa_score, confusion_matrix
from sklearn.metrics import precision_recall_fscore_support


TRAINING_SEEDS = (42, 43, 44)
SEED_PAIRS = tuple(combinations(TRAINING_SEEDS, 2))
BN_MODULES = ("block1.1", "block1.3", "block2.2")
LEARNED_STAGES = (
    "temporal_conv",
    "depthwise_spatial_conv",
    "separable_pointwise_conv",
    "final_latent",
    "classifier_logits",
)


def descriptive_summary(values, prefix: str = "") -> dict:
    """Return the frozen mean/SD/min/max/range descriptive summary."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.isfinite(array).all():
        raise ValueError("summary values must be a finite non-empty vector")
    stem = f"{prefix}_" if prefix else ""
    return {
        f"{stem}mean": float(array.mean()),
        f"{stem}sample_sd": float(array.std(ddof=1)) if array.size > 1 else 0.0,
        f"{stem}minimum": float(array.min()),
        f"{stem}maximum": float(array.max()),
        f"{stem}range": float(array.max() - array.min()),
    }


def stable_identity_hash(session: str, indices) -> str:
    """Hash explicit session-local trial identities in their matched order."""
    payload = json.dumps(
        {"session": str(session), "indices": [int(v) for v in indices]},
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def softmax_probabilities(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("logits must be a finite two-dimensional matrix")
    shifted = values - values.max(axis=1, keepdims=True)
    probabilities = np.exp(shifted)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    return probabilities


def jensen_shannon_rows(
    probabilities_a: np.ndarray,
    probabilities_b: np.ndarray,
    epsilon: float = 1e-12,
) -> np.ndarray:
    """Calculate matched-trial JS divergence using natural logarithms."""
    left = np.asarray(probabilities_a, dtype=np.float64)
    right = np.asarray(probabilities_b, dtype=np.float64)
    if left.shape != right.shape or left.ndim != 2:
        raise ValueError("JS inputs must be matched matrices with equal shape")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("JS inputs must be finite")
    left = np.clip(left, epsilon, 1.0)
    right = np.clip(right, epsilon, 1.0)
    left /= left.sum(axis=1, keepdims=True)
    right /= right.sum(axis=1, keepdims=True)
    midpoint = 0.5 * (left + right)
    return 0.5 * np.sum(left * np.log(left / midpoint), axis=1) + 0.5 * np.sum(
        right * np.log(right / midpoint), axis=1
    )


def prediction_pair_diagnostics(
    logits_a: np.ndarray, logits_b: np.ndarray, targets: np.ndarray
) -> dict:
    """Compute frozen matched prediction, error, probability, and margin data."""
    left = np.asarray(logits_a, dtype=np.float64)
    right = np.asarray(logits_b, dtype=np.float64)
    labels = np.asarray(targets, dtype=np.int64)
    if left.shape != right.shape or left.ndim != 2 or len(labels) != len(left):
        raise ValueError("pair diagnostics require matched logits and targets")
    pa, pb = softmax_probabilities(left), softmax_probabilities(right)
    pred_a, pred_b = pa.argmax(axis=1), pb.argmax(axis=1)
    agreement = float(np.mean(pred_a == pred_b))
    errors_a = set(np.flatnonzero(pred_a != labels).tolist())
    errors_b = set(np.flatnonzero(pred_b != labels).tolist())
    intersection, union = errors_a & errors_b, errors_a | errors_b
    if not union:
        jaccard = 1.0
    elif not errors_a or not errors_b:
        jaccard = 0.0
    else:
        jaccard = len(intersection) / len(union)
    margins_a = np.sort(left, axis=1)[:, -1] - np.sort(left, axis=1)[:, -2]
    margins_b = np.sort(right, axis=1)[:, -1] - np.sort(right, axis=1)[:, -2]
    return {
        "agreement_rate": agreement,
        "disagreement_rate": 1.0 - agreement,
        "prediction_cohen_kappa": float(cohen_kappa_score(pred_a, pred_b)),
        "predictions_a": pred_a,
        "predictions_b": pred_b,
        "error_count_a": len(errors_a),
        "error_count_b": len(errors_b),
        "error_intersection_count": len(intersection),
        "error_union_count": len(union),
        "error_jaccard": float(jaccard),
        "js_divergence": jensen_shannon_rows(pa, pb),
        "absolute_predicted_confidence_difference": np.abs(
            pa.max(axis=1) - pb.max(axis=1)
        ),
        "absolute_logit_margin_difference": np.abs(margins_a - margins_b),
    }


def correctness_stability(predictions, targets: np.ndarray) -> dict:
    """Classify matched trials as all-correct, all-wrong, or mixed."""
    matrix = np.asarray(predictions, dtype=np.int64)
    labels = np.asarray(targets, dtype=np.int64)
    if matrix.ndim != 2 or matrix.shape[1] != len(labels):
        raise ValueError("predictions must have shape seeds by matched trials")
    correct = matrix == labels[None, :]
    all_correct = correct.all(axis=0)
    all_wrong = (~correct).all(axis=0)
    mixed = ~(all_correct | all_wrong)
    return {
        "sample_count": int(len(labels)),
        "all_seeds_correct_count": int(all_correct.sum()),
        "all_seeds_wrong_count": int(all_wrong.sum()),
        "mixed_correctness_count": int(mixed.sum()),
        "all_seeds_correct_fraction": float(all_correct.mean()),
        "all_seeds_wrong_fraction": float(all_wrong.mean()),
        "mixed_correctness_fraction": float(mixed.mean()),
    }


def classwise_diagnostics(logits: np.ndarray, targets: np.ndarray) -> list[dict]:
    labels = np.asarray(targets, dtype=np.int64)
    predictions = np.asarray(logits).argmax(axis=1)
    matrix = confusion_matrix(labels, predictions, labels=[0, 1, 2, 3])
    precision, recall, _, support = precision_recall_fscore_support(
        labels, predictions, labels=[0, 1, 2, 3], zero_division=0
    )
    return [
        {
            "class_id": class_id,
            "precision": float(precision[class_id]),
            "recall": float(recall[class_id]),
            "support": int(support[class_id]),
            "confusion_row": json.dumps(matrix[class_id].tolist()),
        }
        for class_id in range(4)
    ]


def batchnorm_vector_diagnostics(a: np.ndarray, b: np.ndarray) -> dict:
    """Compare two frozen BN vectors with the preregistered descriptors."""
    left = np.asarray(a, dtype=np.float64).reshape(-1)
    right = np.asarray(b, dtype=np.float64).reshape(-1)
    if left.shape != right.shape or not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("BatchNorm vectors must be finite with equal shape")
    norm_a, norm_b = float(np.linalg.norm(left)), float(np.linalg.norm(right))
    relative_l2 = float(
        np.linalg.norm(left - right) / max(norm_a, norm_b, 1e-12)
    )
    if norm_a == 0.0 and norm_b == 0.0:
        cosine = 1.0
    elif norm_a == 0.0 or norm_b == 0.0:
        cosine = 0.0
    else:
        cosine = float(np.dot(left, right) / (norm_a * norm_b))
    return {
        "vector_length": int(left.size),
        "norm_a": norm_a,
        "norm_b": norm_b,
        "relative_l2_difference": relative_l2,
        "cosine_similarity": cosine,
    }


def efficient_representation_shift(source: np.ndarray, evaluation: np.ndarray) -> dict:
    """Calculate the five frozen shift metrics without materializing d-by-d covariance."""
    x = np.asarray(source, dtype=np.float64)
    y = np.asarray(evaluation, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 2 or x.shape[1] != y.shape[1]:
        raise ValueError("source/evaluation embeddings must be 2D with equal width")
    if len(x) < 2 or len(y) < 2 or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("shift inputs require finite matrices with at least two samples")
    dimension = x.shape[1]
    xc = x - x.mean(axis=0, keepdims=True)
    yc = y - y.mean(axis=0, keepdims=True)
    x_scale, y_scale = len(x) - 1, len(y) - 1
    covariance_norm_squared = (
        np.sum((xc @ xc.T) ** 2) / x_scale**2
        + np.sum((yc @ yc.T) ** 2) / y_scale**2
        - 2.0 * np.sum((xc @ yc.T) ** 2) / (x_scale * y_scale)
    )
    covariance_difference = float(math.sqrt(max(float(covariance_norm_squared), 0.0)))
    combined = np.vstack((x, y))
    norms = np.sum(combined**2, axis=1)
    squared = np.maximum(norms[:, None] + norms[None, :] - 2 * combined @ combined.T, 0)
    positive = squared[squared > 0]
    bandwidth = float(np.median(positive)) if positive.size else 1.0
    kernel = np.exp(-squared / max(2 * bandwidth, 1e-12))
    n = len(x)
    mmd = float(
        kernel[:n, :n].mean()
        + kernel[n:, n:].mean()
        - 2 * kernel[:n, n:].mean()
    )
    return {
        "feature_mean_shift": float(np.linalg.norm(x.mean(0) - y.mean(0)) / math.sqrt(dimension)),
        "feature_variance_shift": float(np.linalg.norm(x.var(0) - y.var(0)) / math.sqrt(dimension)),
        "covariance_difference": covariance_difference,
        "coral_distance": covariance_difference**2 / (4 * dimension**2),
        "rbf_mmd2": mmd,
    }
