"""Tests for the independent BCI2a EOG-only Artifact Audit path."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

from scripts.run_bci2a_eog_only import save_eog_summary
from src.data import BCI2AEOGSubjectData
from src.data import _add_bci2a_trial_identity
from src.data import _validate_bci2a_eeg_eog_alignment
from src.train import build_dataloaders


class FakeEpochs:
    """Small MNE Epochs stand-in for alignment unit tests."""

    def __init__(self, data, names, types, events):
        self._data = np.asarray(data)
        self.ch_names = list(names)
        self._types = list(types)
        self.events = np.asarray(events)

    def copy(self):
        return copy.deepcopy(self)

    def pick(self, channel_type):
        indices = [i for i, value in enumerate(self._types) if value == channel_type]
        self._data = self._data[:, indices, :]
        self.ch_names = [self.ch_names[i] for i in indices]
        self._types = [self._types[i] for i in indices]
        return self

    def get_data(self, copy=True):
        return self._data.copy() if copy else self._data


def make_metadata() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "subject": [1, 1, 1, 1],
            "session": ["0train", "0train", "1test", "1test"],
            "run": ["0", "0", "0", "0"],
        }
    )


def make_eog_subject(samples: int = 64) -> BCI2AEOGSubjectData:
    rng = np.random.default_rng(7)
    x_train = rng.normal(size=(12, 3, samples)).astype(np.float32)
    x_test = rng.normal(size=(5, 3, samples)).astype(np.float32)
    return BCI2AEOGSubjectData(
        x_train=x_train,
        y_train=np.asarray([i % 4 for i in range(12)], dtype=np.int64),
        x_test=x_test,
        y_test=np.asarray([i % 4 for i in range(5)], dtype=np.int64),
        train_metadata=pd.DataFrame({"session": ["0train"] * 12}),
        test_metadata=pd.DataFrame({"session": ["1test"] * 5}),
        channel_names=["EOG1", "EOG2", "EOG3"],
        channel_types=["eog", "eog", "eog"],
        sampling_rate=250.0,
        subject_id=1,
    )


def make_eog_config(output_dir: str, seed: int = 42) -> dict:
    return {
        "experiment": "bci2a_eog_only_artifact_audit_smoke_test",
        "seed": seed,
        "data": {
            "name": "bci2a_eog_only",
            "subject_id": 1,
            "train_ratio": 0.5,
            "normalize": True,
            "num_channels": 3,
            "num_samples": 64,
            "num_classes": 4,
        },
        "training": {"batch_size": 4, "epochs": 1, "learning_rate": 0.001},
        "output": {
            "table_dir": output_dir,
            "experiment_summary_file": "eog_only_summary.csv",
        },
    }


class TestEOGAlignment(unittest.TestCase):
    def test_trial_identity_uses_session_run_event_and_ordinal(self) -> None:
        events = np.asarray([[10, 0, 1], [20, 0, 2], [10, 0, 3], [20, 0, 4]])
        identified = _add_bci2a_trial_identity(make_metadata(), events)
        self.assertEqual(identified["trial_in_run"].tolist(), [0, 1, 0, 1])
        self.assertEqual(identified["event_sample"].tolist(), [10, 20, 10, 20])
        self.assertEqual(identified["event_code"].tolist(), [1, 2, 3, 4])

    def test_eeg_and_eog_trials_require_exact_alignment(self) -> None:
        eeg = np.arange(4 * 2 * 8, dtype=np.float32).reshape(4, 2, 8)
        eog = np.ones((4, 3, 8), dtype=np.float32)
        events = np.asarray([[10, 0, 1], [20, 0, 2], [10, 0, 3], [20, 0, 4]])
        labels = np.asarray([0, 1, 2, 3])
        eeg_epochs = FakeEpochs(eeg, ["Fz", "Cz"], ["eeg", "eeg"], events)
        all_epochs = FakeEpochs(
            np.concatenate([eeg, eog], axis=1),
            ["Fz", "Cz", "EOG1", "EOG2", "EOG3"],
            ["eeg", "eeg", "eog", "eog", "eog"],
            events,
        )
        aligned = _validate_bci2a_eeg_eog_alignment(
            eeg_epochs,
            labels,
            make_metadata(),
            all_epochs,
            labels.copy(),
            make_metadata(),
        )
        self.assertEqual(len(aligned), 4)

        bad_labels = labels.copy()
        bad_labels[0] = 3
        with self.assertRaisesRegex(RuntimeError, "label alignment"):
            _validate_bci2a_eeg_eog_alignment(
                eeg_epochs,
                labels,
                make_metadata(),
                all_epochs,
                bad_labels,
                make_metadata(),
            )


class TestEOGTrainingPath(unittest.TestCase):
    def build_bundle(self, config, subject):
        with patch("src.train.load_bci2a_eog_subject", return_value=subject):
            return build_dataloaders(config)

    def test_three_channel_shape_and_train_only_normalization(self) -> None:
        subject = make_eog_subject()
        with tempfile.TemporaryDirectory() as output_dir:
            config = make_eog_config(output_dir)
            bundle = self.build_bundle(config, subject)
            self.assertEqual(bundle.modality, "eog")
            self.assertEqual(bundle.channel_names, ["EOG1", "EOG2", "EOG3"])
            self.assertEqual(bundle.normalization["source"], "train_subset")
            self.assertEqual(len(bundle.train_loader.dataset), 6)
            self.assertEqual(len(bundle.val_loader.dataset), 6)
            self.assertEqual(len(bundle.test_loader.dataset), 5)
            for loader in (bundle.train_loader, bundle.val_loader, bundle.test_loader):
                x, _ = loader.dataset.tensors
                self.assertEqual(x.shape[1:], (3, 64))

            source = torch.from_numpy(subject.x_train)
            expected = source[bundle.train_indices]
            expected_mean = expected.mean(dim=(0, 2), keepdim=True)
            expected_std = expected.std(dim=(0, 2), keepdim=True)
            np.testing.assert_allclose(bundle.normalization["mean"], expected_mean.squeeze())
            np.testing.assert_allclose(bundle.normalization["std"], expected_std.squeeze())

    def test_split_is_deterministic_and_baseline_channel_config_is_untouched(self) -> None:
        subject = make_eog_subject()
        with tempfile.TemporaryDirectory() as output_dir:
            first = self.build_bundle(make_eog_config(output_dir), subject)
            second = self.build_bundle(make_eog_config(output_dir), subject)
            self.assertEqual(first.train_indices, second.train_indices)
            self.assertEqual(first.val_indices, second.val_indices)

        baseline_path = Path("configs/bci2a_eegnet_baseline.yaml")
        self.assertIn("num_channels: 22", baseline_path.read_text(encoding="utf-8"))

    def test_summary_records_audit_identity_and_interpretation_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            config = make_eog_config(output_dir)
            summary = {
                "experiment": config["experiment"],
                "subject": 1,
                "seed": 42,
                "modality": "eog",
                "channels": 3,
                "channel_names": ["EOG1", "EOG2", "EOG3"],
                "train_samples": 230,
                "validation_samples": 58,
                "test_samples": 288,
                "best_epoch": 1,
                "best_validation_metrics": {"accuracy": 0.25},
                "final_test_metrics": {"accuracy": 0.25},
                "best_checkpoint": "checkpoint.pt",
                "normalization": {"source": "train_subset"},
            }
            output_path = save_eog_summary(summary, config)
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("EOG1,EOG2,EOG3", content)
            self.assertIn("does not prove", content)


if __name__ == "__main__":
    unittest.main()
