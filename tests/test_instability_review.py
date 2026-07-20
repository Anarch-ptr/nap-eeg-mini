"""Synthetic safeguards for the zero-training instability review."""

import unittest

import numpy as np

from src.instability_review import (
    batchnorm_vector_diagnostics,
    correctness_stability,
    descriptive_summary,
    efficient_representation_shift,
    jensen_shannon_rows,
    prediction_pair_diagnostics,
    stable_identity_hash,
)
from src.failure_cartography import representation_shift


class InstabilityReviewTests(unittest.TestCase):
    def test_descriptive_summary_uses_sample_sd(self):
        result = descriptive_summary([1.0, 2.0, 3.0])
        self.assertEqual(result["mean"], 2.0)
        self.assertEqual(result["sample_sd"], 1.0)
        self.assertEqual(result["range"], 2.0)

    def test_identity_hash_preserves_order_and_session(self):
        value = stable_identity_hash("validation", [1, 2, 3])
        self.assertEqual(value, stable_identity_hash("validation", [1, 2, 3]))
        self.assertNotEqual(value, stable_identity_hash("validation", [3, 2, 1]))
        self.assertNotEqual(value, stable_identity_hash("official_evaluation", [1, 2, 3]))

    def test_js_identity_and_symmetry(self):
        p = np.array([[0.8, 0.2], [0.3, 0.7]])
        q = np.array([[0.6, 0.4], [0.9, 0.1]])
        np.testing.assert_allclose(jensen_shannon_rows(p, p), 0.0, atol=1e-12)
        np.testing.assert_allclose(jensen_shannon_rows(p, q), jensen_shannon_rows(q, p))

    def test_pair_diagnostics_and_error_jaccard_edges(self):
        targets = np.array([0, 1, 0, 1])
        logits = np.array([[4, 0], [0, 4], [3, 0], [0, 3]], dtype=float)
        same = prediction_pair_diagnostics(logits, logits, targets)
        self.assertEqual(same["agreement_rate"], 1.0)
        self.assertEqual(same["error_jaccard"], 1.0)
        other = logits.copy(); other[0] = [0, 4]
        mixed = prediction_pair_diagnostics(logits, other, targets)
        self.assertEqual(mixed["error_jaccard"], 0.0)

    def test_correctness_partition_is_exhaustive(self):
        targets = np.array([0, 0, 0])
        predictions = np.array([[0, 1, 0], [0, 1, 1], [0, 1, 0]])
        result = correctness_stability(predictions, targets)
        self.assertEqual(result["all_seeds_correct_count"], 1)
        self.assertEqual(result["all_seeds_wrong_count"], 1)
        self.assertEqual(result["mixed_correctness_count"], 1)

    def test_batchnorm_descriptors(self):
        same = batchnorm_vector_diagnostics(np.array([1.0, 2.0]), np.array([1.0, 2.0]))
        self.assertEqual(same["relative_l2_difference"], 0.0)
        self.assertAlmostEqual(same["cosine_similarity"], 1.0)
        zeros = batchnorm_vector_diagnostics(np.zeros(2), np.zeros(2))
        self.assertEqual(zeros["cosine_similarity"], 1.0)

    def test_efficient_shift_matches_frozen_implementation(self):
        rng = np.random.default_rng(41)
        x, y = rng.normal(size=(12, 9)), rng.normal(size=(15, 9))
        expected = representation_shift(x, y)
        observed = efficient_representation_shift(x, y)
        for metric in expected:
            self.assertAlmostEqual(expected[metric], observed[metric], delta=1e-12)


if __name__ == "__main__":
    unittest.main()
