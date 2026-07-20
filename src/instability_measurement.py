"""Measurement-validity utilities for the preregistered instability review.

These functions validate measurement behavior only.  They do not train a
model, compare training seeds, or assign a scientific outcome.
"""

from __future__ import annotations

import math

import numpy as np


def _matched_feature_matrices(
    x: np.ndarray, y: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return validated float64 matrices with an identical sample dimension."""
    left = np.asarray(x, dtype=np.float64)
    right = np.asarray(y, dtype=np.float64)
    if left.ndim != 2 or right.ndim != 2:
        raise ValueError("CKA inputs must be two-dimensional feature matrices")
    if left.shape[0] != right.shape[0]:
        raise ValueError("CKA inputs must contain the same matched samples")
    if left.shape[0] < 2:
        raise ValueError("CKA requires at least two matched samples")
    if left.shape[1] < 1 or right.shape[1] < 1:
        raise ValueError("CKA inputs must contain at least one feature")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("CKA inputs must contain only finite values")
    return left, right


def centered_linear_cka(x: np.ndarray, y: np.ndarray) -> float:
    """Calculate centered linear CKA for two matched feature matrices.

    Feature widths may differ, but sample identities and order must match.
    A zero or non-finite denominator is an integrity error rather than a
    zero-similarity result.
    """
    left, right = _matched_feature_matrices(x, y)
    left = left - left.mean(axis=0, keepdims=True)
    right = right - right.mean(axis=0, keepdims=True)

    cross_norm_squared = float(np.sum((left.T @ right) ** 2))
    left_norm_squared = float(np.sum((left.T @ left) ** 2))
    right_norm_squared = float(np.sum((right.T @ right) ** 2))
    denominator = math.sqrt(left_norm_squared * right_norm_squared)
    if not math.isfinite(denominator) or denominator <= np.finfo(np.float64).tiny:
        raise ValueError("CKA denominator is zero or non-finite")

    value = cross_norm_squared / denominator
    if not math.isfinite(value):
        raise ValueError("CKA result is non-finite")
    # Roundoff can place a theoretically unit-valued result just above one.
    if 1.0 < value <= 1.0 + 1e-12:
        value = 1.0
    return float(value)


def cka_validity_diagnostics(x: np.ndarray, y: np.ndarray) -> dict:
    """Report rank and conditioning inputs used to assess CKA validity."""
    left, right = _matched_feature_matrices(x, y)
    left_centered = left - left.mean(axis=0, keepdims=True)
    right_centered = right - right.mean(axis=0, keepdims=True)
    left_norm_squared = float(np.sum((left_centered.T @ left_centered) ** 2))
    right_norm_squared = float(np.sum((right_centered.T @ right_centered) ** 2))
    denominator = math.sqrt(left_norm_squared * right_norm_squared)
    return {
        "cka": centered_linear_cka(left, right),
        "sample_count": int(left.shape[0]),
        "left_feature_dimension": int(left.shape[1]),
        "right_feature_dimension": int(right.shape[1]),
        "left_centered_rank": int(np.linalg.matrix_rank(left_centered)),
        "right_centered_rank": int(np.linalg.matrix_rank(right_centered)),
        "maximum_sample_rank": int(left.shape[0] - 1),
        "denominator": float(denominator),
    }


def deterministic_subsample_indices(
    sample_count: int, fraction: float, seed: int
) -> np.ndarray:
    """Generate the frozen without-replacement diagnostic subsample indices."""
    if sample_count < 2:
        raise ValueError("subsampling requires at least two source samples")
    if not math.isfinite(fraction) or not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must be finite and in (0, 1]")
    selected_count = max(2, math.floor(sample_count * fraction))
    selected_count = min(sample_count, selected_count)
    rng = np.random.default_rng(int(seed))
    return np.sort(rng.choice(sample_count, size=selected_count, replace=False))


def deterministic_domain_subsamples(
    validation_count: int,
    evaluation_count: int,
    fraction: float,
    repeat_seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw reproducible, independent validation/evaluation subsamples.

    The preregistered repeat seed is combined with a frozen domain stream id
    through ``SeedSequence``.  Stream 0 is validation and stream 1 is official
    evaluation.  This prevents accidental index reuse across domains while
    preserving exact reproducibility.
    """
    streams = []
    for sample_count, stream_id in (
        (validation_count, 0),
        (evaluation_count, 1),
    ):
        if sample_count < 2:
            raise ValueError("domain subsampling requires at least two samples")
        if not math.isfinite(fraction) or not 0.0 < fraction <= 1.0:
            raise ValueError("fraction must be finite and in (0, 1]")
        selected_count = min(sample_count, max(2, math.floor(sample_count * fraction)))
        rng = np.random.default_rng(np.random.SeedSequence([int(repeat_seed), stream_id]))
        streams.append(np.sort(rng.choice(
            sample_count, size=selected_count, replace=False
        )))
    return streams[0], streams[1]


def representation_degeneracy_diagnostics(features: np.ndarray) -> dict:
    """Describe feature variance, rank, spectrum, and effective dimension.

    Effective dimension is the covariance participation ratio

    ``(sum(lambda))**2 / sum(lambda**2)``,

    where ``lambda = singular_value**2 / (n - 1)`` are non-negative covariance
    eigenvalues.  No collapse threshold or scientific endpoint is defined.
    """
    x = np.asarray(features, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] < 2 or x.shape[1] < 1:
        raise ValueError("features must be a non-empty 2D matrix with two samples")
    if not np.isfinite(x).all():
        raise ValueError("features must contain only finite values")
    centered = x - x.mean(axis=0, keepdims=True)
    variances = np.var(x, axis=0, ddof=1)
    singular_values = np.linalg.svd(centered, compute_uv=False)
    eigenvalues = np.maximum(singular_values**2 / (x.shape[0] - 1), 0.0)
    eigenvalue_sum = float(eigenvalues.sum())
    squared_sum = float(np.sum(eigenvalues**2))
    if not math.isfinite(eigenvalue_sum) or not math.isfinite(squared_sum):
        raise ValueError("representation spectrum is non-finite")
    effective_dimension = (
        eigenvalue_sum**2 / squared_sum if squared_sum > np.finfo(float).tiny else 0.0
    )
    zero_variance = int(np.count_nonzero(variances == 0.0))
    quantiles = np.quantile(variances, (0.0, 0.25, 0.5, 0.75, 1.0))
    singular_sum = float(singular_values.sum())
    return {
        "sample_count": int(x.shape[0]),
        "feature_dimension": int(x.shape[1]),
        "matrix_rank": int(np.linalg.matrix_rank(centered)),
        "zero_variance_feature_count": zero_variance,
        "zero_variance_feature_fraction": float(zero_variance / x.shape[1]),
        "variance_minimum": float(quantiles[0]),
        "variance_q25": float(quantiles[1]),
        "variance_median": float(quantiles[2]),
        "variance_q75": float(quantiles[3]),
        "variance_maximum": float(quantiles[4]),
        "variance_mean": float(variances.mean()),
        "singular_value_maximum": float(singular_values.max(initial=0.0)),
        "singular_value_median": float(np.median(singular_values)),
        "singular_value_sum": singular_sum,
        "leading_singular_value_fraction": (
            float(singular_values[0] / singular_sum) if singular_sum > 0.0 else 0.0
        ),
        "covariance_eigenvalue_sum": eigenvalue_sum,
        "effective_dimension_participation_ratio": float(effective_dimension),
    }
