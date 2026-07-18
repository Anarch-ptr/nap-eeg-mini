"""Frozen EEGNet dependency interventions for EOG-coupled EEG components."""

from __future__ import annotations

import numpy as np

from src.eog_eeg_coupling import same_class_derangement


WINDOWS = {"full": (0.0, 4.0), "early": (0.0, 1.0), "middle": (1.5, 2.5), "late": (3.0, 4.0)}
ALPHAS = (1.0, 0.5)


def validate_split(split: dict, num_train: int, num_test: int) -> np.ndarray:
    train = np.asarray(split["train_indices"], dtype=np.int64)
    validation = np.asarray(split["validation_indices"], dtype=np.int64)
    test = np.asarray(split["test_indices"], dtype=np.int64)
    if len(np.unique(np.r_[train, validation])) != num_train or set(np.r_[train, validation]) != set(range(num_train)):
        raise RuntimeError("Saved training/validation split does not partition official 0train.")
    if not np.array_equal(test, np.arange(num_test)):
        raise RuntimeError("Saved test split does not match the complete official 1test session.")
    return train


def verify_normalization(eeg_train: np.ndarray, train_indices: np.ndarray, saved: dict, atol=1e-10):
    if saved.get("source") != "train_subset":
        raise RuntimeError("EEG normalization provenance is not train_subset.")
    subset = eeg_train[train_indices]
    mean = subset.mean(axis=(0, 2), keepdims=True)
    std = subset.std(axis=(0, 2), ddof=1, keepdims=True)
    expected_mean = np.asarray(saved["mean"])[None, :, None]
    expected_std = np.asarray(saved["std"])[None, :, None]
    if not np.allclose(mean, expected_mean, rtol=1e-5, atol=atol) or not np.allclose(std, expected_std, rtol=1e-5, atol=atol):
        raise RuntimeError("Saved EEG normalization does not reproduce from the baseline training subset.")
    return expected_mean, expected_std


def fit_mapping(eeg_raw: np.ndarray, eog_raw: np.ndarray, train_indices: np.ndarray, eeg_mean, eeg_std):
    """Fit EOG normalization and EOG-dependent OLS term on training subset only."""
    eeg = (eeg_raw[train_indices] - eeg_mean) / eeg_std
    eog_source = eog_raw[train_indices]
    eog_mean = eog_source.mean(axis=(0, 2), keepdims=True)
    eog_std = np.maximum(eog_source.std(axis=(0, 2), keepdims=True), 1e-12)
    eog = (eog_source - eog_mean) / eog_std
    x = eog.transpose(0, 2, 1).reshape(-1, eog.shape[1])
    y = eeg.transpose(0, 2, 1).reshape(-1, eeg.shape[1])
    design = np.column_stack((np.ones(len(x)), x))
    coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    return coefficients[0], coefficients[1:], eog_mean, eog_std


def predict_component(eog_raw: np.ndarray, slopes: np.ndarray, eog_mean, eog_std) -> np.ndarray:
    eog = (eog_raw - eog_mean) / eog_std
    flat = eog.transpose(0, 2, 1).reshape(-1, eog.shape[1]) @ slopes
    return flat.reshape(eog.shape[0], eog.shape[2], -1).transpose(0, 2, 1)


def window_slice(name: str, sampling_rate: float, num_samples: int) -> slice:
    tmin, tmax = WINDOWS[name]
    start, stop = round(tmin * sampling_rate), round(tmax * sampling_rate) + 1
    if stop > num_samples:
        raise ValueError("Window exceeds epoch.")
    return slice(start, stop)


def remove_component(clean: np.ndarray, component: np.ndarray, window: str, alpha: float, sampling_rate: float):
    if clean.shape != component.shape:
        raise ValueError("Clean input and component shapes differ.")
    result = clean.copy()
    selected = window_slice(window, sampling_rate, clean.shape[2])
    result[:, :, selected] -= alpha * component[:, :, selected]
    return result


def energy_match(true_component: np.ndarray, control_component: np.ndarray, selected: slice, epsilon=1e-12):
    result = control_component.copy()
    true_flat = true_component[:, :, selected].reshape(len(true_component), -1)
    control_flat = control_component[:, :, selected].reshape(len(control_component), -1)
    true_norm = np.linalg.norm(true_flat, axis=1)
    control_norm = np.linalg.norm(control_flat, axis=1)
    if np.any((control_norm <= epsilon) & (true_norm > epsilon)):
        raise RuntimeError("Cannot energy-match a nonzero true component to zero control component.")
    scale = np.divide(true_norm, control_norm, out=np.ones_like(true_norm), where=control_norm > epsilon)
    result[:, :, selected] *= scale[:, None, None]
    return result


def orthogonal_rotation(num_channels: int, seed: int) -> np.ndarray:
    matrix = np.random.default_rng(seed).normal(size=(num_channels, num_channels))
    q, r = np.linalg.qr(matrix)
    q *= np.sign(np.diag(r))[None, :]
    return q


def rotate_channels(component: np.ndarray, q: np.ndarray) -> np.ndarray:
    return np.einsum("nct,cd->ndt", component, q)


def component_magnitude(eeg: np.ndarray, component: np.ndarray, selected: slice) -> dict:
    eeg_rms = float(np.sqrt(np.mean(np.square(eeg[:, :, selected]))))
    component_rms = float(np.sqrt(np.mean(np.square(component[:, :, selected]))))
    return {"eeg_rms": eeg_rms, "component_rms": component_rms, "component_eeg_rms_ratio": component_rms / eeg_rms}


def paired_effect(clean: float, true: float, control: float) -> dict:
    delta_true, delta_control = true - clean, control - clean
    return {"delta_true": delta_true, "delta_control": delta_control, "dependency_contrast": delta_true - delta_control}


def make_test_control_mapping(labels: np.ndarray, seed: int) -> np.ndarray:
    return same_class_derangement(labels, seed)
