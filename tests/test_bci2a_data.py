"""Unit tests for the BCI Competition IV 2a data utilities."""

from __future__ import annotations

import unittest

import numpy as np

from src.data import BCI2A_LABEL_TO_INDEX
from src.data import encode_bci2a_labels
from src.data import load_bci2a_subject


class TestBCI2ALabelEncoding(unittest.TestCase):
    """Test BCI IV 2a label conversion."""

    def test_encode_all_known_labels(self) -> None:
        labels = np.asarray(
            [
                "left_hand",
                "right_hand",
                "feet",
                "tongue",
            ]
        )

        encoded = encode_bci2a_labels(labels)

        expected = np.asarray([0, 1, 2, 3], dtype=np.int64)

        np.testing.assert_array_equal(encoded, expected)
        self.assertEqual(encoded.dtype, np.int64)

    def test_label_mapping_is_stable(self) -> None:
        self.assertEqual(
            BCI2A_LABEL_TO_INDEX,
            {
                "left_hand": 0,
                "right_hand": 1,
                "feet": 2,
                "tongue": 3,
            },
        )

    def test_unknown_label_raises_error(self) -> None:
        labels = np.asarray(["left_hand", "unknown_class"])

        with self.assertRaisesRegex(
            ValueError,
            "Unknown BCI IV 2a labels",
        ):
            encode_bci2a_labels(labels)


class TestBCI2ALoaderValidation(unittest.TestCase):
    """Test arguments before any dataset download is attempted."""

    def test_invalid_subject_id_raises_error(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "subject_id must be between 1 and 9",
        ):
            load_bci2a_subject(subject_id=0)

        with self.assertRaisesRegex(
            ValueError,
            "subject_id must be between 1 and 9",
        ):
            load_bci2a_subject(subject_id=10)

    def test_invalid_frequency_range_raises_error(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Expected fmin < fmax",
        ):
            load_bci2a_subject(
                subject_id=1,
                fmin=32.0,
                fmax=8.0,
            )

    def test_invalid_time_window_raises_error(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Expected tmin < tmax",
        ):
            load_bci2a_subject(
                subject_id=1,
                tmin=4.0,
                tmax=0.0,
            )


if __name__ == "__main__":
    unittest.main()git add scripts/inspect_bci2a.py
git add tests/test_bci2a_data.py