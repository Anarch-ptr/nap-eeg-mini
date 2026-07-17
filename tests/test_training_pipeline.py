"""Unit tests for the training pipeline's BCI2a protocol handling."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

from src.data import BCI2ASubjectData
from src.train import build_dataloaders
from src.train import run_training
from src.train import set_seed


def make_mock_bci2a_subject(
    train_trials: int = 12,
    test_trials: int = 5,
    samples: int = 64,
) -> BCI2ASubjectData:
    """Create deterministic BCI2a-shaped data without downloading MOABB data."""

    channels = 22
    x_train = np.arange(
        train_trials * channels * samples,
        dtype=np.float32,
    ).reshape(train_trials, channels, samples)
    x_test = (
        np.arange(
            test_trials * channels * samples,
            dtype=np.float32,
        ).reshape(test_trials, channels, samples)
        + 100_000.0
    )

    y_train = np.asarray(
        [index % 4 for index in range(train_trials)],
        dtype=np.int64,
    )
    y_test = np.asarray(
        [index % 4 for index in range(test_trials)],
        dtype=np.int64,
    )

    train_metadata = pd.DataFrame(
        {
            "session": ["0train"] * train_trials,
            "trial_id": list(range(train_trials)),
        }
    )
    test_metadata = pd.DataFrame(
        {
            "session": ["1test"] * test_trials,
            "trial_id": list(range(test_trials)),
        }
    )

    return BCI2ASubjectData(
        x_train=x_train,
        y_train=y_train,
        x_test=x_test,
        y_test=y_test,
        train_metadata=train_metadata,
        test_metadata=test_metadata,
        channel_names=[f"EEG-{index:02d}" for index in range(channels)],
        sampling_rate=250.0,
    )


def make_config(output_dir: str, seed: int = 7) -> dict:
    """Return a tiny BCI2a config for unit tests."""

    return {
        "seed": seed,
        "data": {
            "name": "bci2a",
            "subject_id": 1,
            "data_dir": "unused",
            "train_ratio": 0.5,
            "normalize": True,
            "num_channels": 22,
            "num_samples": 64,
            "num_classes": 4,
        },
        "model": {
            "name": "eegnet",
            "f1": 2,
            "d": 1,
            "f2": 2,
            "kernel_length": 8,
            "dropout": 0.0,
        },
        "training": {
            "batch_size": 4,
            "epochs": 3,
            "learning_rate": 0.001,
            "weight_decay": 0.0,
        },
        "audit": {
            "enabled": False,
            "artifact_channels": [],
        },
        "output": {
            "table_dir": output_dir,
            "training_history_file": "training_history.csv",
            "audit_summary_file": "audit_summary.csv",
            "split_indices_file": "split_indices.json",
            "resolved_config_file": "resolved_config.yaml",
            "run_summary_file": "run_summary.json",
            "best_checkpoint_file": "best_validation_checkpoint.pt",
        },
    }


def make_synthetic_config(seed: int = 7) -> dict:
    """Return a tiny synthetic config for compatibility tests."""

    return {
        "seed": seed,
        "data": {
            "name": "synthetic",
            "num_trials": 20,
            "num_channels": 4,
            "num_samples": 64,
            "num_classes": 3,
            "train_ratio": 0.6,
        },
        "training": {
            "batch_size": 5,
            "epochs": 1,
            "learning_rate": 0.001,
        },
    }


class TestSeedHandling(unittest.TestCase):
    """Test unified seeding behavior."""

    def test_set_seed_covers_python_numpy_and_torch(self) -> None:
        set_seed(123)
        python_value = __import__("random").random()
        numpy_value = np.random.rand()
        torch_value = torch.rand(1).item()

        set_seed(123)

        self.assertEqual(__import__("random").random(), python_value)
        self.assertEqual(np.random.rand(), numpy_value)
        self.assertEqual(torch.rand(1).item(), torch_value)
        self.assertTrue(torch.backends.cudnn.deterministic)
        self.assertFalse(torch.backends.cudnn.benchmark)


class TestBCI2ATrainingData(unittest.TestCase):
    """Test BCI2a train/validation/test construction with mock data."""

    def build_with_subject(self, config: dict, subject: BCI2ASubjectData):
        with patch("src.train.load_bci2a_subject", return_value=subject):
            return build_dataloaders(config)

    def test_train_validation_and_test_sessions_are_isolated(self) -> None:
        subject = make_mock_bci2a_subject()

        with tempfile.TemporaryDirectory() as output_dir:
            config = make_config(output_dir)
            config["data"]["normalize"] = False

            bundle = self.build_with_subject(config, subject)

            self.assertEqual(len(bundle.train_loader.dataset), 6)
            self.assertEqual(len(bundle.val_loader.dataset), 6)
            self.assertEqual(len(bundle.test_loader.dataset), 5)
            self.assertTrue(set(bundle.train_indices).isdisjoint(bundle.val_indices))
            self.assertTrue(all(index < 12 for index in bundle.train_indices))
            self.assertTrue(all(index < 12 for index in bundle.val_indices))
            self.assertEqual(bundle.test_indices, [0, 1, 2, 3, 4])

    def test_normalization_statistics_come_from_train_subset_only(self) -> None:
        subject = make_mock_bci2a_subject()

        with tempfile.TemporaryDirectory() as output_dir:
            config = make_config(output_dir)
            bundle = self.build_with_subject(config, subject)

            source_train = torch.from_numpy(subject.x_train).float()
            expected_train = source_train[bundle.train_indices]
            expected_mean = expected_train.mean(dim=(0, 2), keepdim=True)
            expected_std = expected_train.std(dim=(0, 2), keepdim=True)

            self.assertEqual(bundle.normalization["source"], "train_subset")
            np.testing.assert_allclose(
                np.asarray(bundle.normalization["mean"]),
                expected_mean.squeeze().numpy(),
            )
            np.testing.assert_allclose(
                np.asarray(bundle.normalization["std"]),
                expected_std.squeeze().numpy(),
            )

            train_x, _ = bundle.train_loader.dataset.tensors
            val_x, _ = bundle.val_loader.dataset.tensors
            test_x, _ = bundle.test_loader.dataset.tensors

            expected_val = (
                source_train[bundle.val_indices] - expected_mean
            ) / expected_std
            expected_test = (
                torch.from_numpy(subject.x_test).float() - expected_mean
            ) / expected_std

            torch.testing.assert_close(
                train_x.mean(dim=(0, 2)),
                torch.zeros(22),
                atol=1e-5,
                rtol=1e-5,
            )
            torch.testing.assert_close(val_x, expected_val)
            torch.testing.assert_close(test_x, expected_test)

    def test_same_seed_produces_same_split(self) -> None:
        subject = make_mock_bci2a_subject()

        with tempfile.TemporaryDirectory() as output_dir:
            config = make_config(output_dir, seed=99)
            first = self.build_with_subject(copy.deepcopy(config), subject)
            second = self.build_with_subject(copy.deepcopy(config), subject)

            self.assertEqual(first.train_indices, second.train_indices)
            self.assertEqual(first.val_indices, second.val_indices)

    def test_different_seed_produces_different_split(self) -> None:
        subject = make_mock_bci2a_subject()

        with tempfile.TemporaryDirectory() as output_dir:
            first_config = make_config(output_dir, seed=11)
            second_config = make_config(output_dir, seed=29)

            first = self.build_with_subject(first_config, subject)
            second = self.build_with_subject(second_config, subject)

            self.assertEqual(first.train_indices, [9, 4, 2, 11, 5, 8])
            self.assertEqual(second.train_indices, [5, 10, 6, 4, 2, 11])
            self.assertTrue(
                first.train_indices != second.train_indices
                or first.val_indices != second.val_indices
            )

    def test_shapes_label_dtype_channels_and_classes_are_correct(self) -> None:
        subject = make_mock_bci2a_subject(samples=80)

        with tempfile.TemporaryDirectory() as output_dir:
            config = make_config(output_dir)
            bundle = self.build_with_subject(config, subject)

            for loader in (
                bundle.train_loader,
                bundle.val_loader,
                bundle.test_loader,
            ):
                x_tensor, y_tensor = loader.dataset.tensors
                self.assertEqual(x_tensor.shape[1], 22)
                self.assertEqual(x_tensor.shape[2], 80)
                self.assertEqual(y_tensor.dtype, torch.int64)

            self.assertEqual(config["data"]["num_channels"], 22)
            self.assertEqual(config["data"]["num_samples"], 80)
            self.assertEqual(config["data"]["num_classes"], 4)


class TestSyntheticCompatibility(unittest.TestCase):
    """Test that the synthetic path still builds train/validation only."""

    def test_synthetic_dataloaders_have_no_test_loader_and_reproducible_split(self) -> None:
        first = build_dataloaders(make_synthetic_config(seed=17))
        second = build_dataloaders(make_synthetic_config(seed=17))

        self.assertEqual(len(first.train_loader.dataset), 12)
        self.assertEqual(len(first.val_loader.dataset), 8)
        self.assertIsNone(first.test_loader)
        self.assertEqual(first.train_indices, second.train_indices)
        self.assertEqual(first.val_indices, second.val_indices)


class TestTrainingProtocol(unittest.TestCase):
    """Test validation-only model selection and final official test behavior."""

    def test_test_loader_does_not_select_model_and_is_evaluated_once(self) -> None:
        subject = make_mock_bci2a_subject()

        with tempfile.TemporaryDirectory() as output_dir:
            config = make_config(output_dir)
            calls = []
            validation_metrics = iter(
                [
                    (0.9, 0.40),
                    (0.8, 0.65),
                    (0.7, 0.55),
                ]
            )

            def fake_train_epoch(model, dataloader, criterion, optimizer, device):
                return 1.0, 0.25

            def fake_evaluate(model, dataloader, criterion, device):
                dataset_len = len(dataloader.dataset)
                if dataset_len == 6:
                    calls.append("validation")
                    return next(validation_metrics)
                if dataset_len == 5:
                    calls.append("test")
                    return 0.1, 0.99
                raise AssertionError(f"Unexpected dataloader length: {dataset_len}")

            with patch("src.train.load_bci2a_subject", return_value=subject):
                result = run_training(
                    config=config,
                    device=torch.device("cpu"),
                    train_epoch_fn=fake_train_epoch,
                    evaluate_fn=fake_evaluate,
                )

            self.assertEqual(calls, ["validation", "validation", "validation", "test"])
            self.assertEqual(result["summary"]["best_epoch"], 2)
            self.assertEqual(
                result["summary"]["best_validation_metrics"],
                {"loss": 0.8, "accuracy": 0.65},
            )
            self.assertEqual(
                result["summary"]["final_test_metrics"],
                {"loss": 0.1, "accuracy": 0.99},
            )

            output_path = Path(output_dir)
            self.assertTrue((output_path / "best_validation_checkpoint.pt").exists())
            self.assertTrue((output_path / "resolved_config.yaml").exists())
            self.assertTrue((output_path / "split_indices.json").exists())
            self.assertTrue((output_path / "run_summary.json").exists())

            with open(output_path / "split_indices.json", encoding="utf-8") as file:
                saved_indices = json.load(file)

            self.assertEqual(saved_indices["train_indices"], result["data_bundle"].train_indices)
            self.assertEqual(
                saved_indices["validation_indices"],
                result["data_bundle"].val_indices,
            )
            self.assertEqual(saved_indices["test_indices"], [0, 1, 2, 3, 4])

    def test_best_checkpoint_is_restored_before_final_test(self) -> None:
        subject = make_mock_bci2a_subject()

        with tempfile.TemporaryDirectory() as output_dir:
            config = make_config(output_dir)
            epoch_counter = {"value": 0}
            validation_metrics = iter(
                [
                    (0.9, 0.40),
                    (0.8, 0.65),
                    (0.7, 0.55),
                ]
            )

            def fake_train_epoch(model, dataloader, criterion, optimizer, device):
                epoch_counter["value"] += 1
                epoch_value = float(epoch_counter["value"])
                with torch.no_grad():
                    for parameter in model.parameters():
                        parameter.fill_(epoch_value)
                return 1.0, 0.25

            def fake_evaluate(model, dataloader, criterion, device):
                dataset_len = len(dataloader.dataset)
                if dataset_len == 6:
                    return next(validation_metrics)
                if dataset_len == 5:
                    first_parameter = next(model.parameters()).detach()
                    expected = torch.full_like(first_parameter, 2.0)
                    torch.testing.assert_close(first_parameter, expected)
                    return 0.1, 0.99
                raise AssertionError(f"Unexpected dataloader length: {dataset_len}")

            with patch("src.train.load_bci2a_subject", return_value=subject):
                result = run_training(
                    config=config,
                    device=torch.device("cpu"),
                    train_epoch_fn=fake_train_epoch,
                    evaluate_fn=fake_evaluate,
                )

            self.assertEqual(result["summary"]["best_epoch"], 2)


if __name__ == "__main__":
    unittest.main()
