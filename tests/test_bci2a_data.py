"""Unit tests for the BCI Competition IV 2a data utilities."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.data import BCI2A_LABEL_TO_INDEX
from src.data import encode_bci2a_labels
from src.data import load_bci2a_subject
from src.data import split_bci2a_sessions


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


class TestBCI2ASessionSplit(unittest.TestCase):
    """Test official BCI IV 2a session separation without downloads."""

    def make_arrays(self) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
        x = np.arange(6 * 2 * 3, dtype=np.float32).reshape(6, 2, 3)
        y = np.asarray([0, 1, 2, 3, 0, 1], dtype=np.int64)
        metadata = pd.DataFrame(
            {
                "session": [
                    "0train",
                    "0train",
                    "1test",
                    "1test",
                    "0train",
                    "1test",
                ],
                "trial_id": [10, 11, 12, 13, 14, 15],
            }
        )

        return x, y, metadata

    def test_official_sessions_are_split_correctly(self) -> None:
        x, y, metadata = self.make_arrays()

        split = split_bci2a_sessions(x, y, metadata)

        np.testing.assert_array_equal(split.x_train, x[[0, 1, 4]])
        np.testing.assert_array_equal(split.y_train, y[[0, 1, 4]])
        np.testing.assert_array_equal(split.x_test, x[[2, 3, 5]])
        np.testing.assert_array_equal(split.y_test, y[[2, 3, 5]])

    def test_train_metadata_contains_only_train_session(self) -> None:
        x, y, metadata = self.make_arrays()

        split = split_bci2a_sessions(x, y, metadata)

        self.assertEqual(set(split.train_metadata["session"]), {"0train"})

    def test_test_metadata_contains_only_test_session(self) -> None:
        x, y, metadata = self.make_arrays()

        split = split_bci2a_sessions(x, y, metadata)

        self.assertEqual(set(split.test_metadata["session"]), {"1test"})

    def test_train_and_test_trials_do_not_overlap(self) -> None:
        x, y, metadata = self.make_arrays()

        split = split_bci2a_sessions(x, y, metadata)

        train_ids = set(split.train_metadata["trial_id"])
        test_ids = set(split.test_metadata["trial_id"])

        self.assertTrue(train_ids.isdisjoint(test_ids))

    def test_trial_order_is_preserved(self) -> None:
        x, y, metadata = self.make_arrays()

        split = split_bci2a_sessions(x, y, metadata)

        self.assertEqual(split.train_metadata["trial_id"].tolist(), [10, 11, 14])
        self.assertEqual(split.test_metadata["trial_id"].tolist(), [12, 13, 15])

    def test_missing_train_session_raises_error(self) -> None:
        x, y, metadata = self.make_arrays()
        metadata["session"] = "1test"

        with self.assertRaisesRegex(RuntimeError, "session '0train'"):
            split_bci2a_sessions(x, y, metadata)

    def test_missing_test_session_raises_error(self) -> None:
        x, y, metadata = self.make_arrays()
        metadata["session"] = "0train"

        with self.assertRaisesRegex(RuntimeError, "session '1test'"):
            split_bci2a_sessions(x, y, metadata)

    def test_length_mismatch_raises_error(self) -> None:
        x, y, metadata = self.make_arrays()

        with self.assertRaisesRegex(ValueError, "same number of trials"):
            split_bci2a_sessions(x[:-1], y, metadata)

        with self.assertRaisesRegex(ValueError, "same number of trials"):
            split_bci2a_sessions(x, y[:-1], metadata)

        with self.assertRaisesRegex(ValueError, "same number of trials"):
            split_bci2a_sessions(x, y, metadata.iloc[:-1])

    def test_inputs_are_not_modified_in_place(self) -> None:
        x, y, metadata = self.make_arrays()
        x_original = x.copy()
        y_original = y.copy()
        metadata_original = metadata.copy(deep=True)

        split = split_bci2a_sessions(x, y, metadata)
        split.x_train[0, 0, 0] = -1.0
        split.y_train[0] = 99
        split.train_metadata.loc[0, "trial_id"] = 999

        np.testing.assert_array_equal(x, x_original)
        np.testing.assert_array_equal(y, y_original)
        pd.testing.assert_frame_equal(metadata, metadata_original)

    def test_output_dtypes_are_preserved(self) -> None:
        x, y, metadata = self.make_arrays()

        split = split_bci2a_sessions(x, y, metadata)

        self.assertEqual(split.x_train.dtype, np.float32)
        self.assertEqual(split.x_test.dtype, np.float32)
        self.assertEqual(split.y_train.dtype, np.int64)
        self.assertEqual(split.y_test.dtype, np.int64)

    def test_session_metadata_lengths_match_outputs(self) -> None:
        x, y, metadata = self.make_arrays()

        split = split_bci2a_sessions(x, y, metadata)

        self.assertEqual(len(split.train_metadata), split.x_train.shape[0])
        self.assertEqual(len(split.train_metadata), split.y_train.shape[0])
        self.assertEqual(len(split.test_metadata), split.x_test.shape[0])
        self.assertEqual(len(split.test_metadata), split.y_test.shape[0])

    def test_missing_session_column_raises_error(self) -> None:
        x, y, metadata = self.make_arrays()

        with self.assertRaisesRegex(ValueError, "session"):
            split_bci2a_sessions(x, y, metadata.drop(columns=["session"]))

    def test_unknown_session_raises_error(self) -> None:
        x, y, metadata = self.make_arrays()
        metadata.loc[0, "session"] = "2calibration"

        with self.assertRaisesRegex(RuntimeError, "Unexpected BCI IV 2a sessions"):
            split_bci2a_sessions(x, y, metadata)


if __name__ == "__main__":
    unittest.main()
