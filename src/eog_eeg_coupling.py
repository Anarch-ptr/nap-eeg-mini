"""Label-blind linear EOG-to-EEG coupling audit utilities."""

from __future__ import annotations

import numpy as np


TEMPORAL_WINDOWS = {
    "full": (0.0, 4.0),
    "early": (0.0, 1.0),
    "middle": (1.5, 2.5),
    "late": (3.0, 4.0),
}

EEG_REGIONS = {
    "frontal": {"Fz", "FC3", "FC1", "FCz", "FC2", "FC4"},
    "central": {"C5", "C3", "C1", "Cz", "C2", "C4", "C6"},
    "parietal": {"CP3", "CP1", "CPz", "CP2", "CP4", "P1", "Pz", "P2"},
    "occipital": {"POz"},
}


def same_class_derangement(labels: np.ndarray, seed: int) -> np.ndarray:
    """Return a deterministic, class-preserving bijection without self-pairs."""

    labels = np.asarray(labels)
    mapping = np.empty(len(labels), dtype=np.int64)
    rng = np.random.default_rng(seed)
    for class_id in np.unique(labels):
        indices = np.flatnonzero(labels == class_id)
        if len(indices) < 2:
            raise ValueError("Each class needs at least two trials for derangement.")
        ordered = rng.permutation(indices)
        shift = int(rng.integers(1, len(ordered)))
        mapping[ordered] = np.roll(ordered, shift)
    if np.any(mapping == np.arange(len(labels))):
        raise RuntimeError("Same-class control contains a self-pair.")
    if not np.array_equal(labels[mapping], labels):
        raise RuntimeError("Same-class control changed class identity.")
    if len(np.unique(mapping)) != len(mapping):
        raise RuntimeError("Same-class control is not one-to-one.")
    return mapping


def crop_trials(
    values: np.ndarray,
    tmin: float,
    tmax: float,
    sampling_rate: float,
) -> np.ndarray:
    """Crop all trials and channels using inclusive Phase 0C boundaries."""

    start = round(tmin * sampling_rate)
    stop = round(tmax * sampling_rate) + 1
    if start < 0 or stop > values.shape[2] or stop <= start:
        raise ValueError("Temporal crop falls outside the full epoch.")
    return np.array(values[:, :, start:stop], copy=True)


def fit_train_standardization(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit channel-wise statistics using official training data only."""

    mean = values.mean(axis=(0, 2), keepdims=True)
    std = values.std(axis=(0, 2), keepdims=True)
    std = np.maximum(std, 1e-12)
    return mean, std


def apply_standardization(values, mean, std):
    return (values - mean) / std


def fit_ols(eog_train: np.ndarray, eeg_train: np.ndarray) -> np.ndarray:
    """Fit one joint OLS mapping from three EOG to all EEG channels."""

    x = eog_train.transpose(0, 2, 1).reshape(-1, eog_train.shape[1])
    y = eeg_train.transpose(0, 2, 1).reshape(-1, eeg_train.shape[1])
    design = np.column_stack([np.ones(len(x)), x])
    coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    return coefficients


def predict_ols(eog: np.ndarray, coefficients: np.ndarray) -> np.ndarray:
    x = eog.transpose(0, 2, 1).reshape(-1, eog.shape[1])
    prediction = np.column_stack([np.ones(len(x)), x]) @ coefficients
    return prediction.reshape(eog.shape[0], eog.shape[2], -1).transpose(0, 2, 1)


def channel_metrics(true_eeg: np.ndarray, predicted_eeg: np.ndarray) -> list[dict]:
    """Compute held-out channel-wise R2 and correlation, preserving negatives."""

    results = []
    for channel in range(true_eeg.shape[1]):
        true = true_eeg[:, channel, :].reshape(-1)
        predicted = predicted_eeg[:, channel, :].reshape(-1)
        denominator = np.square(true - true.mean()).sum()
        r2 = 1.0 - np.square(true - predicted).sum() / denominator
        if np.std(true) == 0 or np.std(predicted) == 0:
            correlation = 0.0
        else:
            correlation = np.corrcoef(true, predicted)[0, 1]
        results.append({"r2": float(r2), "correlation": float(correlation)})
    return results


def eeg_region(channel_name: str) -> str:
    matches = [name for name, channels in EEG_REGIONS.items() if channel_name in channels]
    if len(matches) != 1:
        raise ValueError(f"Channel {channel_name!r} has no unique predefined region.")
    return matches[0]
