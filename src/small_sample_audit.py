"""Deterministic subset utilities for Small-Sample Robustness Audit v1."""

from __future__ import annotations

from collections import Counter

import numpy as np


ALLOWED_BUDGETS = (1.0, 0.5, 0.25)


def validate_budget(budget: float) -> float:
    """Validate and canonicalize a pre-registered training-data budget."""

    value = float(budget)
    if value not in ALLOWED_BUDGETS:
        raise ValueError(
            f"budget must be one of {ALLOWED_BUDGETS}, got {value}"
        )
    return value


def select_nested_training_indices(
    training_pool_indices,
    labels,
    budget: float,
    subset_seed: int,
) -> np.ndarray:
    """Select a nested, deterministic, class-stratified budget subset.

    For each class, one fixed permutation is generated from ``subset_seed``.
    A budget retains ``max(1, floor(class_count * budget))`` members from the
    permutation prefix. Selected trials are returned in the original training
    pool order. The full-budget path returns the pool unchanged.
    """

    budget = validate_budget(budget)
    pool = np.asarray(training_pool_indices, dtype=np.int64)
    labels = np.asarray(labels)
    if pool.ndim != 1 or len(pool) == 0:
        raise ValueError("training_pool_indices must be a non-empty 1D array")
    if len(np.unique(pool)) != len(pool):
        raise ValueError("training pool contains duplicate trial indices")
    if np.any(pool < 0) or np.any(pool >= len(labels)):
        raise ValueError("training pool contains an out-of-range trial index")
    if budget == 1.0:
        return pool.copy()

    rng = np.random.default_rng(int(subset_seed))
    selected: set[int] = set()
    pool_labels = labels[pool]
    for class_id in np.unique(pool_labels):
        members = pool[pool_labels == class_id]
        ordered = rng.permutation(members)
        retained = max(1, int(np.floor(len(members) * budget)))
        selected.update(int(index) for index in ordered[:retained])
    result = np.asarray(
        [int(index) for index in pool if int(index) in selected],
        dtype=np.int64,
    )
    if set(np.unique(labels[pool])) != set(np.unique(labels[result])):
        raise RuntimeError("a class disappeared from the budget subset")
    return result


def class_counts(indices, labels) -> dict[str, int]:
    """Return stable string-keyed class counts for provenance logging."""

    labels = np.asarray(labels)
    counts = Counter(int(value) for value in labels[np.asarray(indices)])
    return {str(class_id): counts[class_id] for class_id in sorted(counts)}


def build_subset_provenance(
    *,
    subject: int,
    budget: float,
    subset_seed: int,
    split_seed: int,
    training_seed: int,
    training_pool_indices,
    selected_indices,
    validation_indices,
    test_indices,
    labels,
) -> dict:
    """Build reconstructable run metadata without treating seeds as subjects."""

    return {
        "subject": int(subject),
        "budget": validate_budget(budget),
        "subset_seed": int(subset_seed),
        "split_seed": int(split_seed),
        "training_seed": int(training_seed),
        "training_pool_sample_count": len(training_pool_indices),
        "train_sample_count": len(selected_indices),
        "train_class_counts": class_counts(selected_indices, labels),
        "validation_sample_count": len(validation_indices),
        "test_sample_count": len(test_indices),
        "training_pool_indices": [int(x) for x in training_pool_indices],
        "selected_training_indices": [int(x) for x in selected_indices],
        "validation_indices": [int(x) for x in validation_indices],
        "test_indices": [int(x) for x in test_indices],
    }
