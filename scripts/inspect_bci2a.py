"""Inspect the reusable BCI Competition IV 2a loader."""

from __future__ import annotations

import numpy as np

from src.data import BCI2A_LABEL_TO_INDEX
from src.data import load_bci2a_subject


def summarize_labels(labels: np.ndarray) -> dict[int, int]:
    """Count integer class labels."""

    values, counts = np.unique(labels, return_counts=True)

    return dict(zip(values.tolist(), counts.tolist()))


def main() -> None:
    """Load Subject 1 and inspect the official session split."""

    subject_data = load_bci2a_subject(subject_id=1)

    print()
    print("BCI Competition IV 2a - Subject 1")
    print("----------------------------------")
    print(f"Train shape:         {subject_data.x_train.shape}")
    print(f"Test shape:          {subject_data.x_test.shape}")
    print(f"Train dtype:         {subject_data.x_train.dtype}")
    print(f"Test dtype:          {subject_data.x_test.dtype}")
    print(f"Sampling rate:       {subject_data.sampling_rate} Hz")
    print(f"Channel names:       {subject_data.channel_names}")
    print(f"Label mapping:       {BCI2A_LABEL_TO_INDEX}")
    print(
        f"Train label counts:  "
        f"{summarize_labels(subject_data.y_train)}"
    )
    print(
        f"Test label counts:   "
        f"{summarize_labels(subject_data.y_test)}"
    )
    print(
        f"Train sessions:      "
        f"{subject_data.train_metadata['session'].unique().tolist()}"
    )
    print(
        f"Test sessions:       "
        f"{subject_data.test_metadata['session'].unique().tolist()}"
    )
    print(
        f"Train finite:        "
        f"{bool(np.isfinite(subject_data.x_train).all())}"
    )
    print(
        f"Test finite:         "
        f"{bool(np.isfinite(subject_data.x_test).all())}"
    )

    assert subject_data.x_train.shape == (288, 22, 1001)
    assert subject_data.x_test.shape == (288, 22, 1001)

    assert subject_data.x_train.dtype == np.float32
    assert subject_data.x_test.dtype == np.float32

    assert set(subject_data.y_train.tolist()) == {0, 1, 2, 3}
    assert set(subject_data.y_test.tolist()) == {0, 1, 2, 3}

    assert set(subject_data.train_metadata["session"]) == {"0train"}
    assert set(subject_data.test_metadata["session"]) == {"1test"}

    print()
    print("Reusable BCI IV 2a loader inspection passed.")


if __name__ == "__main__":
    main()
