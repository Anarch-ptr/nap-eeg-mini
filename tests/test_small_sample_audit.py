"""Focused tests for Small-Sample Robustness Audit v1 infrastructure."""

import copy
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.run_bci2a_small_sample_audit import upsert_row
from src.data import BCI2ASubjectData
from src.small_sample_audit import build_subset_provenance
from src.small_sample_audit import class_counts
from src.small_sample_audit import select_nested_training_indices
from src.train import build_dataloaders


def mock_subject():
    trials, channels, samples = 40, 22, 16
    x_train = np.arange(
        trials * channels * samples, dtype=np.float32
    ).reshape(trials, channels, samples)
    x_test = np.full((12, channels, samples), 1_000_000, dtype=np.float32)
    return BCI2ASubjectData(
        x_train=x_train,
        y_train=np.tile(np.arange(4), 10),
        x_test=x_test,
        y_test=np.tile(np.arange(4), 3),
        train_metadata=pd.DataFrame({"session": ["0train"] * trials}),
        test_metadata=pd.DataFrame({"session": ["1test"] * 12}),
        channel_names=[f"EEG-{i}" for i in range(channels)],
        sampling_rate=250.0,
    )


def config(output, budget, training_seed):
    return {
        "seed": training_seed,
        "data": {
            "name": "bci2a", "subject_id": 1, "data_dir": "unused",
            "train_ratio": 0.8, "split_seed": 42, "normalize": True,
            "num_channels": 22, "num_samples": 16, "num_classes": 4,
        },
        "small_sample": {
            "enabled": True, "budget": budget, "subset_seed": 20260719,
        },
        "training": {"batch_size": 8, "epochs": 1, "learning_rate": .001},
        "output": {
            "table_dir": output, "split_indices_file": "split.json",
            "resolved_config_file": "config.yaml",
        },
    }


class SmallSampleSubsetTests(unittest.TestCase):
    def setUp(self):
        self.labels = np.tile(np.arange(4), 10)
        self.pool = np.arange(32)

    def test_determinism_and_training_seed_independence(self):
        first = select_nested_training_indices(self.pool, self.labels, .25, 7)
        second = select_nested_training_indices(self.pool, self.labels, .25, 7)
        np.testing.assert_array_equal(first, second)
        for _training_seed in (42, 43, 44):
            np.testing.assert_array_equal(
                first,
                select_nested_training_indices(self.pool, self.labels, .25, 7),
            )

    def test_nested_and_stratified_with_explicit_floor_rule(self):
        full = select_nested_training_indices(self.pool, self.labels, 1, 9)
        half = select_nested_training_indices(self.pool, self.labels, .5, 9)
        quarter = select_nested_training_indices(self.pool, self.labels, .25, 9)
        self.assertTrue(set(quarter) < set(half) < set(full))
        self.assertEqual(class_counts(half, self.labels), {str(i): 4 for i in range(4)})
        self.assertEqual(class_counts(quarter, self.labels), {str(i): 2 for i in range(4)})

    def test_provenance_fields(self):
        selected = select_nested_training_indices(self.pool, self.labels, .25, 5)
        value = build_subset_provenance(
            subject=3, budget=.25, subset_seed=5, split_seed=42,
            training_seed=44, training_pool_indices=self.pool,
            selected_indices=selected, validation_indices=np.arange(32, 40),
            test_indices=np.arange(12), labels=self.labels,
        )
        self.assertEqual(value["budget"], .25)
        self.assertEqual(value["subset_seed"], 5)
        self.assertEqual(value["training_seed"], 44)
        self.assertEqual(value["train_sample_count"], 8)
        self.assertEqual(value["train_class_counts"], {str(i): 2 for i in range(4)})

    def test_result_upsert_preserves_other_runs(self):
        fields = {
            "subject": 1, "budget": .25, "subset_seed": 7,
            "split_seed": 42, "training_seed": 42,
        }
        rows = upsert_row([], fields | {"test_accuracy": .4})
        rows = upsert_row(rows, fields | {"test_accuracy": .5})
        rows = upsert_row(
            rows,
            fields | {"training_seed": 43, "test_accuracy": .6},
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["test_accuracy"], .5)


class SmallSamplePipelineTests(unittest.TestCase):
    def build(self, budget, training_seed):
        with tempfile.TemporaryDirectory() as output:
            with patch("src.train.load_bci2a_subject", return_value=mock_subject()):
                return build_dataloaders(config(output, budget, training_seed))

    def test_validation_test_and_subset_are_seed_invariant(self):
        bundles = [self.build(.25, seed) for seed in (42, 43, 44)]
        self.assertTrue(all(x.train_indices == bundles[0].train_indices for x in bundles))
        self.assertTrue(all(x.val_indices == bundles[0].val_indices for x in bundles))
        self.assertTrue(all(x.test_indices == list(range(12)) for x in bundles))

    def test_budget_nesting_and_validation_invariance(self):
        full, half, quarter = [self.build(b, 42) for b in (1, .5, .25)]
        self.assertTrue(set(quarter.train_indices) < set(half.train_indices))
        self.assertTrue(set(half.train_indices) < set(full.train_indices))
        self.assertEqual(full.val_indices, half.val_indices)
        self.assertEqual(half.val_indices, quarter.val_indices)
        self.assertEqual(full.test_indices, half.test_indices)

    def test_normalization_uses_only_budget_subset_and_test_is_transform_only(self):
        bundle = self.build(.25, 44)
        source = mock_subject()
        expected = source.x_train[bundle.train_indices]
        np.testing.assert_allclose(
            bundle.normalization["mean"], expected.mean(axis=(0, 2)), rtol=1e-5
        )
        test_x, _ = bundle.test_loader.dataset.tensors
        self.assertFalse(np.allclose(test_x.numpy(), source.x_test))
        self.assertTrue(all(index < len(source.x_train) for index in bundle.train_indices))

    def test_full_budget_matches_sealed_seed42_training_pool(self):
        full = self.build(1.0, 44)
        baseline_config = config("unused", 1.0, 42)
        baseline_config.pop("small_sample")
        with patch("src.train.load_bci2a_subject", return_value=mock_subject()):
            baseline = build_dataloaders(copy.deepcopy(baseline_config))
        self.assertEqual(full.train_indices, baseline.train_indices)
        self.assertEqual(full.val_indices, baseline.val_indices)


if __name__ == "__main__":
    unittest.main()
