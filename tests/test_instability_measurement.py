"""Synthetic measurement-validity safeguards, without EEG scientific analysis."""

import unittest

import numpy as np

from src.failure_cartography import representation_shift
from src.instability_measurement import (
    centered_linear_cka,
    cka_validity_diagnostics,
    deterministic_domain_subsamples,
    deterministic_subsample_indices,
    representation_degeneracy_diagnostics,
)


class CenteredLinearCKATests(unittest.TestCase):
    def test_identity_across_representative_eegnet_shapes(self):
        rng = np.random.default_rng(20260720)
        for feature_dimension in (16, 32, 496, 4):
            x = rng.normal(size=(58, feature_dimension))
            self.assertAlmostEqual(centered_linear_cka(x, x.copy()), 1.0, places=12)

    def test_rejects_mismatched_or_invalid_inputs(self):
        with self.assertRaises(ValueError):
            centered_linear_cka(np.ones((4, 2)), np.ones((5, 2)))
        with self.assertRaises(ValueError):
            centered_linear_cka(np.ones((1, 2)), np.ones((1, 2)))
        with self.assertRaises(ValueError):
            centered_linear_cka(np.array([[0.0], [np.nan]]), np.ones((2, 1)))
        with self.assertRaises(ValueError):
            centered_linear_cka(np.ones((4, 2)), np.ones((4, 3)))

    def test_different_feature_widths_are_supported(self):
        rng = np.random.default_rng(30)
        self.assertTrue(np.isfinite(centered_linear_cka(
            rng.normal(size=(20, 4)), rng.normal(size=(20, 7))
        )))

    def test_joint_permutation_invariance_and_one_sided_sensitivity(self):
        rng = np.random.default_rng(31)
        x = rng.normal(size=(80, 12))
        y = x + 0.05 * rng.normal(size=x.shape)
        permutation = rng.permutation(len(x))
        original = centered_linear_cka(x, y)
        joint = centered_linear_cka(x[permutation], y[permutation])
        one_sided = centered_linear_cka(x[permutation], y)
        self.assertAlmostEqual(original, joint, places=12)
        self.assertLess(one_sided, original)

    def test_isotropic_scaling_invariance(self):
        x = np.random.default_rng(32).normal(size=(64, 10))
        for scale in (0.25, 3.0, -2.0):
            self.assertAlmostEqual(centered_linear_cka(x, scale * x), 1.0, places=12)

    def test_orthogonal_feature_transform_invariance(self):
        rng = np.random.default_rng(33)
        x = rng.normal(size=(64, 10))
        q, _ = np.linalg.qr(rng.normal(size=(10, 10)))
        self.assertAlmostEqual(centered_linear_cka(x, x @ q), 1.0, places=12)

    def test_fixed_additive_perturbation_levels_reduce_cka(self):
        rng = np.random.default_rng(34)
        levels = (0.0, 0.1, 0.5, 1.0)
        for feature_dimension in (4, 16, 32, 44, 496):
            x = rng.normal(size=(58, feature_dimension))
            noise = rng.normal(size=x.shape)
            values = [centered_linear_cka(x, x + level * noise) for level in levels]
            self.assertTrue(all(a > b for a, b in zip(values, values[1:])))

    def test_independent_random_features_differ_at_actual_stage_dimensions(self):
        rng = np.random.default_rng(35)
        for feature_dimension in (4, 16, 32, 44, 496):
            x = rng.normal(size=(58, feature_dimension))
            y = rng.normal(size=x.shape)
            self.assertLess(centered_linear_cka(x, y), centered_linear_cka(x, x))

    def test_validity_diagnostics_report_rank_and_denominator(self):
        x = np.random.default_rng(36).normal(size=(20, 40))
        result = cka_validity_diagnostics(x, x)
        self.assertEqual(result["sample_count"], 20)
        self.assertLessEqual(result["left_centered_rank"], 19)
        self.assertGreater(result["denominator"], 0.0)


class ShiftMetricValidityTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(20260720)
        self.x = rng.normal(size=(80, 8))

    def test_all_shift_metrics_repeat_within_frozen_tolerance(self):
        y = self.x + 0.2 * np.random.default_rng(37).normal(size=self.x.shape)
        first = representation_shift(self.x, y)
        second = representation_shift(self.x.copy(), y.copy())
        for metric in first:
            self.assertAlmostEqual(first[metric], second[metric], delta=1e-12)

    def test_frozen_mean_offset_control(self):
        shifted = representation_shift(self.x, self.x + 0.5)
        self.assertAlmostEqual(shifted["feature_mean_shift"], 0.5, places=12)
        self.assertGreater(shifted["rbf_mmd2"], 0.0)

    def test_frozen_variance_scaling_control(self):
        centered = self.x - self.x.mean(axis=0, keepdims=True)
        shifted = representation_shift(centered, 1.5 * centered)
        self.assertGreater(shifted["feature_variance_shift"], 0.0)
        self.assertGreater(shifted["covariance_difference"], 0.0)
        self.assertGreater(shifted["coral_distance"], 0.0)

    def test_frozen_off_diagonal_covariance_mixing_control(self):
        mixing = np.eye(self.x.shape[1])
        mixing[0, 1] = 0.5
        shifted = representation_shift(self.x, self.x @ mixing)
        self.assertGreater(shifted["covariance_difference"], 0.0)
        self.assertGreater(shifted["coral_distance"], 0.0)


class DeterministicSubsamplingTests(unittest.TestCase):
    def test_frozen_fractions_and_seeds_are_deterministic(self):
        for fraction in (0.50, 0.75, 1.00):
            for seed in range(20260721, 20260741):
                first = deterministic_subsample_indices(58, fraction, seed)
                second = deterministic_subsample_indices(58, fraction, seed)
                np.testing.assert_array_equal(first, second)
                self.assertEqual(len(first), max(2, int(np.floor(58 * fraction))))
                self.assertEqual(len(np.unique(first)), len(first))
                self.assertTrue(((0 <= first) & (first < 58)).all())

    def test_same_indices_preserve_matched_correspondence(self):
        x = np.arange(120).reshape(30, 4)
        y = x.copy()
        indices = deterministic_subsample_indices(30, 0.5, 20260721)
        self.assertEqual(centered_linear_cka(x[indices], y[indices]), 1.0)

    def test_domain_streams_are_reproducible_and_independent(self):
        first = deterministic_domain_subsamples(58, 288, 0.5, 20260721)
        second = deterministic_domain_subsamples(58, 288, 0.5, 20260721)
        np.testing.assert_array_equal(first[0], second[0])
        np.testing.assert_array_equal(first[1], second[1])
        self.assertEqual((len(first[0]), len(first[1])), (29, 144))
        self.assertFalse(np.array_equal(first[0], first[1][:29]))


class RepresentationDegeneracyTests(unittest.TestCase):
    def test_equal_covariance_directions_have_full_effective_dimension(self):
        x = np.vstack((np.eye(4), -np.eye(4)))
        result = representation_degeneracy_diagnostics(x)
        self.assertEqual(result["matrix_rank"], 4)
        self.assertAlmostEqual(
            result["effective_dimension_participation_ratio"], 4.0, places=12
        )

    def test_rank_one_representation_has_unit_effective_dimension(self):
        base = np.arange(10, dtype=float)[:, None]
        x = base @ np.array([[1.0, 2.0, 3.0]])
        result = representation_degeneracy_diagnostics(x)
        self.assertEqual(result["matrix_rank"], 1)
        self.assertAlmostEqual(
            result["effective_dimension_participation_ratio"], 1.0, places=12
        )

    def test_exact_zero_variance_features_are_reported(self):
        x = np.column_stack((np.arange(8, dtype=float), np.ones(8), np.zeros(8)))
        result = representation_degeneracy_diagnostics(x)
        self.assertEqual(result["zero_variance_feature_count"], 2)
        self.assertAlmostEqual(result["zero_variance_feature_fraction"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
