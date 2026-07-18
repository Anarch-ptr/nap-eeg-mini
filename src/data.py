"""Data loading utilities for public EEG benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


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


@dataclass
class BCI2AEOGSubjectData:
    """Session-separated, audit-only EOG data aligned to BCI2a EEG trials."""

    x_train: np.ndarray
    y_train: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray

    train_metadata: pd.DataFrame
    test_metadata: pd.DataFrame

    channel_names: list[str]
    channel_types: list[str]
    sampling_rate: float
    subject_id: int


@dataclass
class BCI2ASessionSplit:
    """Official train/test session split for BCI Competition IV 2a."""

    x_train: np.ndarray
    y_train: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray

    train_metadata: pd.DataFrame
    test_metadata: pd.DataFrame


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


def split_bci2a_sessions(
    x: np.ndarray,
    y: np.ndarray,
    metadata: pd.DataFrame,
) -> BCI2ASessionSplit:
    """Split BCI2a arrays into official train and test sessions.

    Parameters
    ----------
    x:
        Trial array with the trial dimension first.
    y:
        Label array with one label per trial.
    metadata:
        Trial metadata containing a ``session`` column.

    Returns
    -------
    BCI2ASessionSplit
        Copies of arrays and metadata for ``0train`` and ``1test``.
    """

    if "session" not in metadata.columns:
        raise ValueError("metadata must contain a 'session' column.")

    if x.shape[0] != len(y) or x.shape[0] != len(metadata):
        raise ValueError(
            "x, y, and metadata must contain the same number of trials."
        )

    session_names = metadata["session"].astype(str)
    expected_sessions = {"0train", "1test"}
    observed_sessions = set(session_names.unique().tolist())
    unknown_sessions = observed_sessions - expected_sessions

    if unknown_sessions:
        raise RuntimeError(
            f"Unexpected BCI IV 2a sessions: {sorted(unknown_sessions)}"
        )

    train_mask = (session_names == "0train").to_numpy()
    test_mask = (session_names == "1test").to_numpy()

    if not train_mask.any():
        raise RuntimeError("No trials found for session '0train'.")

    if not test_mask.any():
        raise RuntimeError("No trials found for session '1test'.")

    if np.any(train_mask & test_mask):
        raise RuntimeError("Train and test session masks overlap.")

    return BCI2ASessionSplit(
        x_train=np.array(x[train_mask], copy=True),
        y_train=np.array(y[train_mask], copy=True),
        x_test=np.array(x[test_mask], copy=True),
        y_test=np.array(y[test_mask], copy=True),
        train_metadata=metadata.loc[train_mask].copy().reset_index(drop=True),
        test_metadata=metadata.loc[test_mask].copy().reset_index(drop=True),
    )


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

    from moabb import set_download_dir
    from moabb.datasets import BNCI2014_001
    from moabb.paradigms import MotorImagery

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

    session_split = split_bci2a_sessions(
        x=x,
        y=y,
        metadata=metadata,
    )

    if session_split.x_train.shape[0] != 288:
        raise RuntimeError(
            "Expected 288 training trials, got "
            f"{session_split.x_train.shape[0]}"
        )

    if session_split.x_test.shape[0] != 288:
        raise RuntimeError(
            f"Expected 288 test trials, got {session_split.x_test.shape[0]}"
        )

    if session_split.x_train.shape[1] != 22 or session_split.x_test.shape[1] != 22:
        raise RuntimeError(
            "Expected 22 EEG channels for BCI Competition IV 2a."
        )

    if not np.isfinite(session_split.x_train).all():
        raise RuntimeError("Training data contains NaN or Inf values.")

    if not np.isfinite(session_split.x_test).all():
        raise RuntimeError("Test data contains NaN or Inf values.")

    return BCI2ASubjectData(
        x_train=session_split.x_train,
        y_train=session_split.y_train,
        x_test=session_split.x_test,
        y_test=session_split.y_test,
        train_metadata=session_split.train_metadata,
        test_metadata=session_split.test_metadata,
        channel_names=list(epochs.ch_names),
        sampling_rate=float(epochs.info["sfreq"]),
    )


def _add_bci2a_trial_identity(
    metadata: pd.DataFrame,
    events: np.ndarray,
) -> pd.DataFrame:
    """Add the strongest trial identity exposed by the MOABB 1.5 API."""

    if len(metadata) != len(events):
        raise RuntimeError("Metadata and MNE events have different lengths.")
    if "run" not in metadata.columns:
        raise RuntimeError("BCI2a metadata must contain a 'run' column.")

    identified = metadata.copy().reset_index(drop=True)
    identified["trial_in_run"] = identified.groupby(
        ["subject", "session", "run"],
        sort=False,
    ).cumcount()
    identified["event_sample"] = events[:, 0].astype(np.int64)
    identified["event_code"] = events[:, 2].astype(np.int64)
    return identified


def _validate_bci2a_eeg_eog_alignment(
    eeg_epochs,
    eeg_labels: np.ndarray,
    eeg_metadata: pd.DataFrame,
    multimodal_epochs,
    multimodal_labels: np.ndarray,
    multimodal_metadata: pd.DataFrame,
) -> pd.DataFrame:
    """Validate that default EEG and all-modality epochs are trial-aligned."""

    if not np.array_equal(eeg_labels, multimodal_labels):
        raise RuntimeError("EEG/EOG label alignment failed.")
    if not eeg_metadata.reset_index(drop=True).equals(
        multimodal_metadata.reset_index(drop=True)
    ):
        raise RuntimeError("EEG/EOG subject/session/run metadata alignment failed.")
    if not np.array_equal(eeg_epochs.events, multimodal_epochs.events):
        raise RuntimeError("EEG/EOG MNE event alignment failed.")

    multimodal_eeg = multimodal_epochs.copy().pick("eeg").get_data(copy=True)
    baseline_eeg = eeg_epochs.get_data(copy=True)
    if baseline_eeg.shape != multimodal_eeg.shape or not np.array_equal(
        baseline_eeg,
        multimodal_eeg,
    ):
        raise RuntimeError("All-modality loading changed the aligned EEG epochs.")

    return _add_bci2a_trial_identity(
        multimodal_metadata,
        multimodal_epochs.events,
    )


def load_bci2a_eog_subject(
    subject_id: int,
    data_dir: str | Path = "data/moabb",
    fmin: float = 8.0,
    fmax: float = 32.0,
    tmin: float = 0.0,
    tmax: float = 4.0,
) -> BCI2AEOGSubjectData:
    """Load the three official EOG channels for audit-only classification.

    The frozen baseline loader remains EEG-only. This function independently
    loads both the default EEG epochs and all modalities, then requires exact
    label, metadata, event, and EEG-sample equality before returning EOG.
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

    from moabb import set_download_dir
    from moabb.datasets import BNCI2014_001
    from moabb.paradigms import MotorImagery

    set_download_dir(str(resolved_data_dir))
    paradigm = MotorImagery(
        n_classes=4,
        fmin=fmin,
        fmax=fmax,
        tmin=tmin,
        tmax=tmax,
    )

    eeg_epochs, eeg_string_labels, eeg_metadata = paradigm.get_data(
        dataset=BNCI2014_001(),
        subjects=[subject_id],
        return_epochs=True,
    )
    multimodal_epochs, multimodal_string_labels, multimodal_metadata = (
        paradigm.get_data(
            dataset=BNCI2014_001(return_all_modalities=True),
            subjects=[subject_id],
            return_epochs=True,
        )
    )

    eeg_labels = encode_bci2a_labels(eeg_string_labels)
    multimodal_labels = encode_bci2a_labels(multimodal_string_labels)
    aligned_metadata = _validate_bci2a_eeg_eog_alignment(
        eeg_epochs,
        eeg_labels,
        eeg_metadata,
        multimodal_epochs,
        multimodal_labels,
        multimodal_metadata,
    )

    eog_epochs = multimodal_epochs.copy().pick("eog")
    eog_channel_names = list(eog_epochs.ch_names)
    eog_channel_types = list(eog_epochs.get_channel_types())
    if len(eog_channel_names) != 3 or eog_channel_types != ["eog"] * 3:
        raise RuntimeError(
            "Expected exactly three EOG channels, got "
            f"{list(zip(eog_channel_names, eog_channel_types))}"
        )

    eog = eog_epochs.get_data(copy=True).astype(np.float32)
    session_split = split_bci2a_sessions(
        x=eog,
        y=multimodal_labels,
        metadata=aligned_metadata,
    )
    if session_split.x_train.shape[0] != 288 or session_split.x_test.shape[0] != 288:
        raise RuntimeError("Expected 288 EOG trials in each official session.")
    if session_split.x_train.shape[1] != 3 or session_split.x_test.shape[1] != 3:
        raise RuntimeError("Expected three EOG channels for BCI2a audit data.")
    if not np.isfinite(session_split.x_train).all() or not np.isfinite(
        session_split.x_test
    ).all():
        raise RuntimeError("EOG data contains NaN or Inf values.")

    return BCI2AEOGSubjectData(
        x_train=session_split.x_train,
        y_train=session_split.y_train,
        x_test=session_split.x_test,
        y_test=session_split.y_test,
        train_metadata=session_split.train_metadata,
        test_metadata=session_split.test_metadata,
        channel_names=eog_channel_names,
        channel_types=eog_channel_types,
        sampling_rate=float(eog_epochs.info["sfreq"]),
        subject_id=subject_id,
    )
