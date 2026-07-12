"""Data loading utilities for public EEG benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from moabb import set_download_dir
from moabb.datasets import BNCI2014_001
from moabb.paradigms import MotorImagery


BCI2A_LABEL_TO_INDEX = {
    "left_hand": 0,
    "right_hand": 1,
    "feet": 2,
    "tongue": 3,
}


@dataclass
class BCI2ASubjectData:
    """Train/test data for one BCI Competition IV 2a subject."""

    x_train: np.ndarray
    y_train: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray

    train_metadata: pd.DataFrame
    test_metadata: pd.DataFrame

    channel_names: list[str]
    sampling_rate: float


def encode_bci2a_labels(labels: np.ndarray) -> np.ndarray:
    """Convert MOABB string labels into integer class indices."""

    unknown_labels = set(labels.tolist()) - set(BCI2A_LABEL_TO_INDEX)

    if unknown_labels:
        raise ValueError(
            f"Unknown BCI IV 2a labels: {sorted(unknown_labels)}"
        )

    encoded = np.asarray(
        [BCI2A_LABEL_TO_INDEX[label] for label in labels],
        dtype=np.int64,
    )

    return encoded


def load_bci2a_subject(
    subject_id: int,
    data_dir: str | Path = "data/moabb",
    fmin: float = 8.0,
    fmax: float = 32.0,
    tmin: float = 0.0,
    tmax: float = 4.0,
) -> BCI2ASubjectData:
    """Load one BCI Competition IV 2a subject.

    Parameters
    ----------
    subject_id:
        Subject number from 1 to 9.
    data_dir:
        Local directory used by MOABB for downloaded EEG data.
    fmin:
        High-pass cutoff frequency in Hz.
    fmax:
        Low-pass cutoff frequency in Hz.
    tmin:
        Start of the epoch relative to the paradigm event.
    tmax:
        End of the epoch relative to the paradigm event.

    Returns
    -------
    BCI2ASubjectData
        Session-separated train and test arrays.

    Notes
    -----
    The official train session is kept separate from the evaluation
    session. The two sessions must not be mixed before test evaluation.
    """

    if subject_id not in range(1, 10):
        raise ValueError(
            f"subject_id must be between 1 and 9, got {subject_id}"
        )

    if fmin >= fmax:
        raise ValueError(
            f"Expected fmin < fmax, got fmin={fmin}, fmax={fmax}"
        )

    if tmin >= tmax:
        raise ValueError(
            f"Expected tmin < tmax, got tmin={tmin}, tmax={tmax}"
        )

    resolved_data_dir = Path(data_dir).resolve()
    resolved_data_dir.mkdir(parents=True, exist_ok=True)

    set_download_dir(str(resolved_data_dir))

    dataset = BNCI2014_001()

    # Keep preprocessing explicit so benchmark settings are reproducible.
    paradigm = MotorImagery(
        n_classes=4,
        fmin=fmin,
        fmax=fmax,
        tmin=tmin,
        tmax=tmax,
    )

    epochs, string_labels, metadata = paradigm.get_data(
        dataset=dataset,
        subjects=[subject_id],
        return_epochs=True,
    )

    # PyTorch models normally use float32. The MOABB/MNE output is float64.
    x = epochs.get_data(copy=True).astype(np.float32)
    y = encode_bci2a_labels(string_labels)

    session_names = metadata["session"].astype(str)

    train_mask = session_names == "0train"
    test_mask = session_names == "1test"

    if not train_mask.any():
        raise RuntimeError("No trials found for session '0train'.")

    if not test_mask.any():
        raise RuntimeError("No trials found for session '1test'.")

    x_train = x[train_mask.to_numpy()]
    y_train = y[train_mask.to_numpy()]

    x_test = x[test_mask.to_numpy()]
    y_test = y[test_mask.to_numpy()]

    train_metadata = metadata.loc[train_mask].reset_index(drop=True)
    test_metadata = metadata.loc[test_mask].reset_index(drop=True)

    if x_train.shape[0] != 288:
        raise RuntimeError(
            f"Expected 288 training trials, got {x_train.shape[0]}"
        )

    if x_test.shape[0] != 288:
        raise RuntimeError(
            f"Expected 288 test trials, got {x_test.shape[0]}"
        )

    if x_train.shape[1] != 22 or x_test.shape[1] != 22:
        raise RuntimeError(
            "Expected 22 EEG channels for BCI Competition IV 2a."
        )

    if not np.isfinite(x_train).all():
        raise RuntimeError("Training data contains NaN or Inf values.")

    if not np.isfinite(x_test).all():
        raise RuntimeError("Test data contains NaN or Inf values.")

    return BCI2ASubjectData(
        x_train=x_train,
        y_train=y_train,
        x_test=x_test,
        y_test=y_test,
        train_metadata=train_metadata,
        test_metadata=test_metadata,
        channel_names=list(epochs.ch_names),
        sampling_rate=float(epochs.info["sfreq"]),
    )
