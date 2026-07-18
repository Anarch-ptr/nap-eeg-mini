"""Tests for BCI2a multi-seed result analysis."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_bci2a_multiseed import build_seed_mean_statistics
from scripts.analyze_bci2a_multiseed import build_subject_statistics
from scripts.analyze_bci2a_multiseed import save_subject_statistics


class TestSubjectStatistics(unittest.TestCase):
    """Test per-subject aggregation across seeds."""

    def test_build_subject_statistics(self) -> None:
        """Subject statistics should use all available seeds."""

        rows = [
            {
                "seed": "42",
                "subject_id": "1",
                "final_test_accuracy": "0.5",
            },
            {
                "seed": "43",
                "subject_id": "1",
                "final_test_accuracy": "0.7",
            },
            {
                "seed": "42",
                "subject_id": "2",
                "final_test_accuracy": "0.25",
            },
            {
                "seed": "43",
                "subject_id": "2",
                "final_test_accuracy": "0.25",
            },
        ]

        statistics_rows = build_subject_statistics(
            rows
        )

        self.assertEqual(
            len(statistics_rows),
            2,
        )

        subject_01 = statistics_rows[0]
        subject_02 = statistics_rows[1]

        self.assertEqual(
            subject_01["subject_id"],
            1,
        )
        self.assertEqual(
            subject_01["num_seeds"],
            2,
        )
        self.assertAlmostEqual(
            subject_01["mean_test_accuracy"],
            0.6,
        )
        self.assertAlmostEqual(
            subject_01["std_test_accuracy"],
            0.1414213562373095,
        )
        self.assertAlmostEqual(
            subject_01["min_test_accuracy"],
            0.5,
        )
        self.assertAlmostEqual(
            subject_01["max_test_accuracy"],
            0.7,
        )

        self.assertEqual(
            subject_02["subject_id"],
            2,
        )
        self.assertAlmostEqual(
            subject_02["mean_test_accuracy"],
            0.25,
        )
        self.assertAlmostEqual(
            subject_02["std_test_accuracy"],
            0.0,
        )


class TestSeedMeanStatistics(unittest.TestCase):
    """Test variation across seed-level subject means."""

    def test_build_seed_mean_statistics(self) -> None:
        """Seed-level mean and sample SD should be correct."""

        rows = [
            {
                "seed": "42",
                "subject_id": "1",
                "final_test_accuracy": "0.5",
            },
            {
                "seed": "42",
                "subject_id": "2",
                "final_test_accuracy": "0.7",
            },
            {
                "seed": "43",
                "subject_id": "1",
                "final_test_accuracy": "0.4",
            },
            {
                "seed": "43",
                "subject_id": "2",
                "final_test_accuracy": "0.6",
            },
        ]

        mean_accuracy, std_accuracy = (
            build_seed_mean_statistics(rows)
        )

        self.assertAlmostEqual(
            mean_accuracy,
            0.55,
        )
        self.assertAlmostEqual(
            std_accuracy,
            0.07071067811865474,
        )


class TestSubjectStatisticsCSV(unittest.TestCase):
    """Test persistence of subject-level statistics."""

    def test_save_subject_statistics(self) -> None:
        """Saved CSV should preserve the aggregate fields."""

        rows = [
            {
                "subject_id": 1,
                "num_seeds": 3,
                "mean_test_accuracy": 0.65,
                "std_test_accuracy": 0.02,
                "min_test_accuracy": 0.63,
                "max_test_accuracy": 0.68,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "subject_statistics.csv"
            )

            save_subject_statistics(
                rows=rows,
                output_path=output_path,
            )

            with output_path.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as file:
                loaded_rows = list(
                    csv.DictReader(file)
                )

        self.assertEqual(
            len(loaded_rows),
            1,
        )
        self.assertEqual(
            loaded_rows[0]["subject_id"],
            "1",
        )
        self.assertEqual(
            loaded_rows[0]["num_seeds"],
            "3",
        )


if __name__ == "__main__":
    unittest.main()

