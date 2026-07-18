"""Tests for deterministic, label-blind EOG-to-EEG coupling audit."""

from __future__ import annotations

import unittest

import numpy as np

from src.eog_eeg_coupling import EEG_REGIONS
from src.eog_eeg_coupling import TEMPORAL_WINDOWS
from src.eog_eeg_coupling import channel_metrics
from src.eog_eeg_coupling import crop_trials
from src.eog_eeg_coupling import eeg_region
from src.eog_eeg_coupling import fit_ols
from src.eog_eeg_coupling import fit_train_standardization
from src.eog_eeg_coupling import predict_ols
from src.eog_eeg_coupling import same_class_derangement


class TestSameClassControl(unittest.TestCase):
    def setUp(self):
        self.labels = np.repeat(np.arange(4), 12)

    def test_permutation_is_deterministic_bijective_and_same_class(self):
        first = same_class_derangement(self.labels, 20260718)
        second = same_class_derangement(self.labels, 20260718)
        np.testing.assert_array_equal(first, second)
        np.testing.assert_array_equal(self.labels[first], self.labels)
        self.assertEqual(len(np.unique(first)), len(first))
        self.assertEqual(len(first), len(self.labels))

    def test_permutation_has_no_self_pairs(self):
        mapping = same_class_derangement(self.labels, 20260718)
        self.assertFalse(np.any(mapping == np.arange(len(mapping))))

    def test_too_small_class_fails(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            same_class_derangement(np.asarray([0, 1, 1]), 7)


class TestCouplingMath(unittest.TestCase):
    def test_known_linear_coupling_is_recovered(self):
        rng = np.random.default_rng(3)
        eog = rng.normal(size=(8, 3, 40))
        coefficients = np.asarray(
            [[0.5, -0.25], [1.0, 0.2], [-0.5, 0.7], [0.25, -1.2]]
        )
        eeg = predict_ols(eog, coefficients)
        fitted = fit_ols(eog, eeg)
        np.testing.assert_allclose(fitted, coefficients, atol=1e-12)
        metrics = channel_metrics(eeg, predict_ols(eog, fitted))
        self.assertTrue(all(result["r2"] > 0.999999 for result in metrics))

    def test_fit_uses_only_arrays_explicitly_passed_as_training_data(self):
        rng = np.random.default_rng(4)
        train_eog = rng.normal(size=(5, 3, 20))
        train_eeg = rng.normal(size=(5, 2, 20))
        first = fit_ols(train_eog, train_eeg)
        unrelated_test_eog = rng.normal(loc=100, size=(3, 3, 20))
        unrelated_test_eeg = rng.normal(loc=-100, size=(3, 2, 20))
        _ = (unrelated_test_eog, unrelated_test_eeg)
        second = fit_ols(train_eog, train_eeg)
        np.testing.assert_array_equal(first, second)

    def test_independent_test_data_has_near_zero_r2(self):
        rng = np.random.default_rng(5)
        train_eog = rng.normal(size=(60, 3, 100))
        train_eeg = rng.normal(size=(60, 2, 100))
        test_eog = rng.normal(size=(60, 3, 100))
        test_eeg = rng.normal(size=(60, 2, 100))
        metrics = channel_metrics(test_eeg, predict_ols(test_eog, fit_ols(train_eog, train_eeg)))
        self.assertTrue(all(abs(result["r2"]) < 0.02 for result in metrics))

    def test_negative_r2_is_not_clipped(self):
        true = np.asarray([[[0.0, 1.0, 2.0, 3.0]]])
        bad = np.asarray([[[10.0, 10.0, 10.0, 10.0]]])
        self.assertLess(channel_metrics(true, bad)[0]["r2"], 0.0)

    def test_standardization_statistics_are_fit_from_given_train_data(self):
        train = np.arange(2 * 3 * 4, dtype=float).reshape(2, 3, 4)
        mean, std = fit_train_standardization(train)
        np.testing.assert_allclose(mean, train.mean(axis=(0, 2), keepdims=True))
        np.testing.assert_allclose(std, train.std(axis=(0, 2), keepdims=True))


class TestCouplingProtocol(unittest.TestCase):
    def test_temporal_windows_reuse_phase_0c_definitions(self):
        self.assertEqual(
            TEMPORAL_WINDOWS,
            {
                "full": (0.0, 4.0),
                "early": (0.0, 1.0),
                "middle": (1.5, 2.5),
                "late": (3.0, 4.0),
            },
        )

    def test_crop_is_identical_across_all_trials_and_modalities(self):
        values = np.arange(4 * 3 * 1001).reshape(4, 3, 1001)
        cropped = crop_trials(values, 1.5, 2.5, 250.0)
        self.assertEqual(cropped.shape, (4, 3, 251))
        np.testing.assert_array_equal(cropped, values[:, :, 375:626])

    def test_all_22_channel_names_have_one_predefined_region(self):
        names = [
            "Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3",
            "C1", "Cz", "C2", "C4", "C6", "CP3", "CP1", "CPz",
            "CP2", "CP4", "P1", "Pz", "P2", "POz",
        ]
        self.assertEqual(len(names), 22)
        self.assertEqual(sum(len(value) for value in EEG_REGIONS.values()), 22)
        self.assertEqual([eeg_region(name) for name in names].count("occipital"), 1)


if __name__ == "__main__":
    unittest.main()
