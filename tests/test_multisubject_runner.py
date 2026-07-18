"""Tests for the BCI2a multi-subject baseline runner."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.run_bci2a_multisubject import build_subject_config
from scripts.run_bci2a_multisubject import save_aggregate_summary
from scripts.run_bci2a_multisubject import summary_to_row
from scripts.run_bci2a_multisubject import validate_subjects


class TestSubjectValidation(unittest.TestCase):
    """Test BCI2a subject identifier handling."""

    def test_preserves_order_and_removes_duplicates(self) -> None:
        """Duplicate subjects should be removed without reordering."""

        self.assertEqual(
            validate_subjects([3, 1, 3, 2]),
            [3, 1, 2],
        )

    def test_rejects_empty_or_invalid_subjects(self) -> None:
        """Empty lists and invalid identifiers should fail."""

        with self.assertRaises(ValueError):
            validate_subjects([])

        with self.assertRaises(ValueError):
            validate_subjects([0])

        with self.assertRaises(ValueError):
            validate_subjects([10])


class TestSubjectConfiguration(unittest.TestCase):
    """Test isolated subject configurations."""

    def test_build_subject_config_does_not_modify_base(self) -> None:
        """Subject-specific changes should not mutate the base config."""

        base_config = {
            "data": {"subject_id": 1},
            "output": {"table_dir": "original"},
        }

        config = build_subject_config(
            base_config=base_config,
            subject_id=4,
            output_root=Path("results/test"),
        )

        self.assertEqual(config["data"]["subject_id"], 4)
        self.assertEqual(
            Path(config["output"]["table_dir"]),
            Path("results/test/subject_04"),
        )
        self.assertEqual(base_config["data"]["subject_id"], 1)
        self.assertEqual(
            base_config["output"]["table_dir"],
            "original",
        )


class TestAggregateSummary(unittest.TestCase):
    """Test aggregate result formatting and persistence."""

    def test_summary_row_and_csv_are_correct(self) -> None:
        """One subject summary should produce a stable CSV row."""

        summary = {
            "best_epoch": 36,
            "best_validation_metrics": {
                "loss": 0.7,
                "accuracy": 0.67,
            },
            "final_test_metrics": {
                "loss": 0.78,
                "accuracy": 0.64,
            },
        }

        row = summary_to_row(
            subject_id=1,
            summary=summary,
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "subjects_summary.csv"

            save_aggregate_summary(
                rows=[row],
                output_path=output_path,
            )

            with output_path.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as file:
                rows = list(csv.DictReader(file))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject_id"], "1")
        self.assertEqual(rows[0]["best_epoch"], "36")
        self.assertEqual(
            rows[0]["final_test_accuracy"],
            "0.64",
        )


if __name__ == "__main__":
    unittest.main()

