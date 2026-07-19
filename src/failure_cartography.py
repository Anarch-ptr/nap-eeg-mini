"""Post-hoc EEGNet failure-cartography diagnostics without model adaptation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             cohen_kappa_score, f1_score, log_loss,
                             roc_auc_score)


LAYER_MODULES = {
    "temporal_conv": "block1.0",
    "depthwise_spatial_conv": "block1.2",
    "separable_pointwise_conv": "block2.1",
    "final_latent": "block2",
    "classifier_logits": "classifier",
}


def _stage_embedding(tensor: torch.Tensor, layer_name: str) -> torch.Tensor:
    """Create a bounded diagnostic vector per trial, never used for prediction."""
    x = tensor.detach().float()
    if layer_name in {"model_input", "temporal_conv", "depthwise_spatial_conv",
                      "separable_pointwise_conv"}:
        if x.ndim == 3:  # input: preserve channels, summarize time
            return torch.cat((x.mean(-1), x.std(-1, unbiased=False)), dim=1)
        if x.ndim == 4:  # convolution: preserve feature maps
            dims = tuple(range(2, x.ndim))
            return torch.cat((x.mean(dims), x.std(dims, unbiased=False)), dim=1)
    return x.reshape(x.shape[0], -1)


@dataclass
class ActivationCapture:
    """Non-invasive hooks for actual EEGNet module names."""

    model: torch.nn.Module

    def __post_init__(self):
        modules = dict(self.model.named_modules())
        missing = sorted(set(LAYER_MODULES.values()) - set(modules))
        if missing:
            raise RuntimeError(f"EEGNet instrumentation modules missing: {missing}")
        self._chunks = {name: [] for name in ("model_input", *LAYER_MODULES)}
        self._handles = []
        for layer_name, module_name in LAYER_MODULES.items():
            self._handles.append(modules[module_name].register_forward_hook(
                self._hook(layer_name)))

    def _hook(self, layer_name):
        def capture(_module, _inputs, output):
            self._chunks[layer_name].append(
                _stage_embedding(output, layer_name).cpu())
        return capture

    def record_input(self, x: torch.Tensor):
        self._chunks["model_input"].append(
            _stage_embedding(x, "model_input").cpu())

    def arrays(self) -> dict[str, np.ndarray]:
        return {name: torch.cat(chunks).numpy() for name, chunks in self._chunks.items()}

    def close(self):
        for handle in self._handles: handle.remove()
        self._handles.clear()


def risk_coverage(confidence: np.ndarray, correct: np.ndarray) -> dict:
    order = np.argsort(-confidence, kind="stable")
    errors = 1.0 - correct[order].astype(float)
    coverage = np.arange(1, len(errors) + 1, dtype=float) / len(errors)
    risk = np.cumsum(errors) / np.arange(1, len(errors) + 1)
    aurc = float(risk.mean())
    return {"coverage": coverage.tolist(), "risk": risk.tolist(), "aurc": aurc}


def diagnostic_metrics(logits: np.ndarray, targets: np.ndarray, ece_bins: int = 15) -> dict:
    logits, targets = np.asarray(logits, float), np.asarray(targets, int)
    shifted = logits - logits.max(axis=1, keepdims=True)
    probabilities = np.exp(shifted); probabilities /= probabilities.sum(axis=1, keepdims=True)
    predictions = probabilities.argmax(axis=1)
    correct = predictions == targets
    confidence = probabilities.max(axis=1)
    one_hot = np.eye(probabilities.shape[1])[targets]
    edges = np.linspace(0, 1, ece_bins + 1); ece = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        selected = (confidence > lower) & (confidence <= upper)
        if selected.any():
            ece += selected.mean() * abs(correct[selected].mean() - confidence[selected].mean())
    if correct.all() or (~correct).all():
        error_auroc = None
    else:
        error_auroc = float(roc_auc_score(~correct, 1.0 - confidence))
    curve = risk_coverage(confidence, correct)
    return {
        "accuracy": float(accuracy_score(targets, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(targets, predictions)),
        "macro_f1": float(f1_score(targets, predictions, average="macro", zero_division=0)),
        "cohen_kappa": float(cohen_kappa_score(targets, predictions)),
        "nll": float(log_loss(targets, probabilities, labels=list(range(probabilities.shape[1])))),
        "brier_score": float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))),
        "ece": float(ece),
        "mean_confidence_correct": float(confidence[correct].mean()) if correct.any() else None,
        "mean_confidence_incorrect": float(confidence[~correct].mean()) if (~correct).any() else None,
        "error_detection_auroc": error_auroc,
        "aurc": curve["aurc"],
        "risk_coverage": curve,
    }


def infer_diagnostics(model, dataloader, device) -> tuple[dict, dict[str, np.ndarray]]:
    model.eval(); capture = ActivationCapture(model); logits, targets = [], []
    try:
        with torch.no_grad():
            for x, y in dataloader:
                capture.record_input(x)
                logits.append(model(x.to(device)).cpu())
                targets.append(y.cpu())
    finally:
        capture.close()
    logits_array = torch.cat(logits).numpy(); targets_array = torch.cat(targets).numpy()
    return diagnostic_metrics(logits_array, targets_array), capture.arrays()


def _covariance(x: np.ndarray) -> np.ndarray:
    return np.atleast_2d(np.cov(x, rowvar=False, ddof=1))


def _rbf_mmd2(x: np.ndarray, y: np.ndarray) -> float:
    combined = np.vstack((x, y)); squared = np.maximum(
        np.sum(combined**2, axis=1)[:, None] + np.sum(combined**2, axis=1)[None, :]
        - 2 * combined @ combined.T, 0)
    positive = squared[squared > 0]
    bandwidth = float(np.median(positive)) if positive.size else 1.0
    kernel = np.exp(-squared / max(2 * bandwidth, 1e-12)); n = len(x)
    return float(kernel[:n, :n].mean() + kernel[n:, n:].mean() - 2*kernel[:n, n:].mean())


def representation_shift(source: np.ndarray, evaluation: np.ndarray) -> dict:
    x, y = np.asarray(source, float), np.asarray(evaluation, float)
    if x.ndim != 2 or y.ndim != 2 or x.shape[1] != y.shape[1]:
        raise ValueError("source/evaluation embeddings must be 2D with equal width")
    dimension = x.shape[1]; cx, cy = _covariance(x), _covariance(y)
    covariance_difference = float(np.linalg.norm(cx-cy, ord="fro"))
    return {
        "feature_dimension": dimension,
        "feature_mean_shift": float(np.linalg.norm(x.mean(0)-y.mean(0))/np.sqrt(dimension)),
        "feature_variance_shift": float(np.linalg.norm(x.var(0)-y.var(0))/np.sqrt(dimension)),
        "covariance_difference": covariance_difference,
        "coral_distance": covariance_difference**2/(4*dimension**2),
        "rbf_mmd2": _rbf_mmd2(x, y),
    }


def embedding_validity(embedding: np.ndarray) -> dict:
    """Describe numerical/rank validity without judging scientific strength."""
    x = np.asarray(embedding, float)
    if x.ndim != 2 or len(x) < 2:
        raise ValueError("embedding must contain at least two 2D samples")
    covariance = _covariance(x)
    rank = int(np.linalg.matrix_rank(covariance))
    max_rank = min(x.shape[0] - 1, x.shape[1])
    return {
        "sample_count": int(x.shape[0]), "feature_dimension": int(x.shape[1]),
        "all_finite": bool(np.isfinite(x).all()),
        "feature_value_std": float(np.std(x)),
        "covariance_rank": rank, "maximum_possible_sample_rank": int(max_rank),
        "covariance_rank_fraction": float(rank / max_rank) if max_rank else None,
    }


def assert_frozen_split(bundle, split_path: Path) -> None:
    import json
    frozen = json.loads(split_path.read_text(encoding="utf-8"))
    expected_train = frozen.get("small_sample", {}).get("selected_training_indices",
                                                        frozen.get("train_indices"))
    if list(bundle.train_indices) != expected_train:
        raise RuntimeError("training subset differs from frozen checkpoint provenance")
    if list(bundle.val_indices) != frozen["validation_indices"]:
        raise RuntimeError("validation identities differ from frozen provenance")
    if list(bundle.test_indices) != frozen["test_indices"]:
        raise RuntimeError("official evaluation identities differ from frozen provenance")
