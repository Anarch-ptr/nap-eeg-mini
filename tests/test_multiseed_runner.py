"""Tests for the BCI2a multi-seed baseline runner."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.run_bci2a_multiseed import build_seed_summary
from scripts.run_bci2a_multiseed import save_csv
from scripts.run_bci2a_multiseed import validate_seeds


class TestSeedValidation(unittest.TestCase):
    """Test random seed validation."""

    def test_preserves_order_and_removes_duplicates(self) -> None:
        """Duplicate seeds should be removed without reordering."""

        self.assertEqual(
            validate_seeds([44, 42, 44, 43]),
            [44, 42, 43],
        )

    def test_rejects_empty_and_negative_seeds(self) -> None:
        """Empty seed lists and negative seeds should fail."""

        with self.assertRaises(ValueError):
            validate_seeds([])

        with self.assertRaises(ValueError):
            validate_seeds([-1])


class TestSeedSummary(unittest.TestCase):
    """Test seed-level aggregate statistics."""

    def test_build_seed_summary_computes_statistics(self) -> None:
        """Mean and sample standard deviation should be correct."""

        subject_rows = [
            {
                "final_test_accuracy": 0.5,
            },
            {
                "final_test_accuracy": 0.7,
            },
        ]

        summary = build_seed_summary(
            seed=42,
            subject_rows=subject_rows,
        )

        self.assertEqual(summary["seed"], 42)
        self.assertEqual(summary["num_subjects"], 2)
        self.assertAlmostEqual(
            summary["mean_test_accuracy"],
            0.6,
        )
        self.assertAlmostEqual(
            summary["std_test_accuracy"],
            0.1414213562373095,
        )

    def test_single_subject_standard_deviation_is_zero(self) -> None:
        """A one-subject smoke run should report zero spread."""

        summary = build_seed_summary(
            seed=42,
            subject_rows=[
                {
                    "final_test_accuracy": 0.64,
                }
            ],
        )

        self.assertEqual(
            summary["std_test_accuracy"],
            0.0,
        )


class TestCSVOutput(unittest.TestCase):
    """Test generic multi-seed CSV persistence."""

    def test_save_csv_writes_expected_rows(self) -> None:
        """CSV output should preserve requested fields."""

        rows = [
            {
                "seed": 42,
                "accuracy": 0.64,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "summary.csv"

            save_csv(
                rows=rows,
                fieldnames=[
                    "seed",
                    "accuracy",
                ],
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

        self.assertEqual(len(loaded_rows), 1)
        self.assertEqual(
            loaded_rows[0]["seed"],
            "42",
        )
        self.assertEqual(
            loaded_rows[0]["accuracy"],
            "0.64",
        )


if __name__ == "__main__":
    unittest.main()

