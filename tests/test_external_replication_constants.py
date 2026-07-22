from __future__ import annotations

import dataclasses
import unittest
from unittest.mock import patch

import src.external_replication.constants as constants_module

from src.external_replication.constants import (
    BUDGETS,
    CHANNELS,
    FROZEN_V1_CONSTANTS,
    IMPLEMENTATION_CONSTANTS_ROLE,
    V1_EXPECTED_CONSTANTS_PAYLOAD_SHA256,
    FatalConstantsDriftError,
    MirrorConformanceStatus,
    canonical_channel_order_bytes,
    canonical_channel_order_sha256,
    constants_payload_sha256,
    enforce_implementation_constants_or_abort,
    verify_implementation_constants_against_frozen_v1,
)
from src.external_replication.protocol_identity import ProtocolIdentityStatus, verify_protocol_identity
from src.external_replication.rng import REGISTERED_NUMPY_SEEDS, RngOwner


class ConstantsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity = verify_protocol_identity()

    def assert_drift(self, **changes):
        candidate = dataclasses.replace(FROZEN_V1_CONSTANTS, **changes)
        result = verify_implementation_constants_against_frozen_v1(candidate, self.identity)
        self.assertEqual(result.status, MirrorConformanceStatus.IMPLEMENTATION_CONSTANTS_MIRROR_DRIFT)

    def assert_synchronized_drift(self, candidate):
        with patch.object(constants_module, "FROZEN_V1_CONSTANTS", candidate):
            result = verify_implementation_constants_against_frozen_v1(
                candidate, self.identity
            )
            self.assertEqual(
                result.status,
                MirrorConformanceStatus.IMPLEMENTATION_CONSTANTS_MIRROR_DRIFT,
            )
            self.assertIn(
                "V1_CONSTANTS_PAYLOAD_SHA256_MISMATCH", result.failure_reasons
            )
            with self.assertRaises(FatalConstantsDriftError):
                enforce_implementation_constants_or_abort(candidate, self.identity)

    def test_correct_constants_pass(self):
        result = verify_implementation_constants_against_frozen_v1(protocol_result=self.identity)
        self.assertEqual(result.status, MirrorConformanceStatus.PASS)

    def test_core_frozen_values(self):
        constants = FROZEN_V1_CONSTANTS
        self.assertEqual(constants.role, IMPLEMENTATION_CONSTANTS_ROLE)
        self.assertEqual(constants.subject_count, 54)
        self.assertEqual(constants.split_seed, 42)
        self.assertEqual(constants.subset_chain_seed, 20260719)
        self.assertEqual(constants.model_seeds, (42, 43, 44))
        expected_budgets = (
            100, 95, 90, 85, 80, 75, 70, 65, 60, 55,
            50, 45, 40, 35, 30, 25, 20, 15, 10, 5,
        )
        expected_counts = (
            (100, 80), (95, 76), (90, 72), (85, 68), (80, 64),
            (75, 60), (70, 56), (65, 52), (60, 48), (55, 44),
            (50, 40), (45, 36), (40, 32), (35, 28), (30, 24),
            (25, 20), (20, 16), (15, 12), (10, 8), (5, 4),
        )
        self.assertEqual(constants.budget_percentages, expected_budgets)
        self.assertEqual(constants.budget_to_optimizer_trial_count, expected_counts)
        self.assertFalse(constants.scientific_parameter_updates_enabled)

    def test_channel_order_count_uniqueness_and_encoding(self):
        self.assertEqual(len(CHANNELS), 62)
        self.assertEqual(len(set(CHANNELS)), 62)
        encoded = canonical_channel_order_bytes()
        self.assertFalse(encoded.startswith(b"\xef\xbb\xbf"))
        self.assertFalse(encoded.endswith(b"\n"))
        self.assertEqual(
            canonical_channel_order_sha256(),
            "7994c37ca4346e26a7429c4c76056bae1c09ebe483fcacd87d98b1d61268e4cd",
        )

    def test_sampling_and_epoch_relationships(self):
        constants = FROZEN_V1_CONSTANTS
        self.assertEqual(constants.original_sampling_rate_hz // constants.decimation_factor, constants.decimated_sampling_rate_hz)
        self.assertEqual(constants.expected_predecimation_samples // constants.decimation_factor, constants.expected_postdecimation_samples)
        self.assertEqual((constants.epoch_start_seconds, constants.epoch_stop_seconds), (0.0, 4.0))
        self.assertEqual(constants.original_sampling_rate_hz, 1000)
        self.assertEqual(constants.decimated_sampling_rate_hz, 250)
        self.assertEqual(constants.decimation_factor, 4)
        self.assertEqual(constants.expected_predecimation_samples, 4000)
        self.assertEqual(constants.expected_postdecimation_samples, 1000)

    def test_expected_v1_payload_digest_is_independent_literal(self):
        expected = "52f385ceb673c9162e847760048fb83ba4897eab29bce1a822d5e7b2f4c6fced"
        self.assertEqual(V1_EXPECTED_CONSTANTS_PAYLOAD_SHA256, expected)
        self.assertEqual(constants_payload_sha256(FROZEN_V1_CONSTANTS), expected)

    def test_all_registered_rng_seeds_match_independent_literals(self):
        expected = {
            RngOwner.DATA_SPLIT: 42,
            RngOwner.SUBSET_CHAIN: 20260719,
            RngOwner.RQ2_PRIMARY_PERMUTATION: 20260721,
            RngOwner.RQ2_BASELINE_CAPABLE_PERMUTATION: 20260722,
            RngOwner.RQ2_REFINED_PERMUTATION: 20260723,
            RngOwner.RQ2_PRIMARY_BOOTSTRAP: 20260724,
            RngOwner.RQ2_BASELINE_CAPABLE_BOOTSTRAP: 20260725,
            RngOwner.RQ2_REFINED_BOOTSTRAP: 20260726,
        }
        self.assertEqual(dict(REGISTERED_NUMPY_SEEDS), expected)

    def test_immutable_mapping_and_tuples(self):
        self.assertIsInstance(BUDGETS, tuple)
        with self.assertRaises(TypeError):
            FROZEN_V1_CONSTANTS.budget_count_map[100] = 1

    def test_wrong_subject_count_fails(self):
        self.assert_drift(subject_count=53)

    def test_wrong_budget_count_fails(self):
        pairs = list(FROZEN_V1_CONSTANTS.budget_to_optimizer_trial_count)
        pairs[0] = (100, 79)
        self.assert_drift(budget_to_optimizer_trial_count=tuple(pairs))

    def test_reordered_channel_fails(self):
        self.assert_drift(canonical_channel_order=tuple(reversed(CHANNELS)))

    def test_wrong_seed_fails(self):
        self.assert_drift(split_seed=41)

    def test_wrong_sampling_rate_fails(self):
        self.assert_drift(original_sampling_rate_hz=500)

    def test_synchronized_subject_count_drift_fails(self):
        self.assert_synchronized_drift(
            dataclasses.replace(FROZEN_V1_CONSTANTS, subject_count=53)
        )

    def test_synchronized_split_seed_drift_fails(self):
        self.assert_synchronized_drift(
            dataclasses.replace(FROZEN_V1_CONSTANTS, split_seed=41)
        )

    def test_synchronized_model_seed_drift_fails(self):
        self.assert_synchronized_drift(
            dataclasses.replace(FROZEN_V1_CONSTANTS, model_seeds=(1, 2, 3))
        )

    def test_synchronized_budget_sequence_drift_fails(self):
        budgets = (99,) + FROZEN_V1_CONSTANTS.budget_percentages[1:]
        counts = ((99, 80),) + FROZEN_V1_CONSTANTS.budget_to_optimizer_trial_count[1:]
        self.assert_synchronized_drift(
            dataclasses.replace(
                FROZEN_V1_CONSTANTS,
                budget_percentages=budgets,
                budget_to_optimizer_trial_count=counts,
            )
        )

    def test_synchronized_budget_count_drift_fails(self):
        counts = list(FROZEN_V1_CONSTANTS.budget_to_optimizer_trial_count)
        counts[0] = (100, 78)
        self.assert_synchronized_drift(
            dataclasses.replace(
                FROZEN_V1_CONSTANTS,
                budget_to_optimizer_trial_count=tuple(counts),
            )
        )

    def test_synchronized_channel_swap_fails(self):
        channels = list(FROZEN_V1_CONSTANTS.canonical_channel_order)
        channels[0], channels[1] = channels[1], channels[0]
        self.assert_synchronized_drift(
            dataclasses.replace(
                FROZEN_V1_CONSTANTS, canonical_channel_order=tuple(channels)
            )
        )

    def test_synchronized_coherent_sampling_drift_fails(self):
        candidate = dataclasses.replace(
            FROZEN_V1_CONSTANTS,
            original_sampling_rate_hz=500,
            decimated_sampling_rate_hz=125,
            expected_predecimation_samples=2000,
            expected_postdecimation_samples=500,
        )
        with patch.object(constants_module, "FROZEN_V1_CONSTANTS", candidate):
            result = verify_implementation_constants_against_frozen_v1(
                candidate, self.identity
            )
        self.assertEqual(
            result.status,
            MirrorConformanceStatus.IMPLEMENTATION_CONSTANTS_MIRROR_DRIFT,
        )
        self.assertEqual(
            result.failure_reasons, ("V1_CONSTANTS_PAYLOAD_SHA256_MISMATCH",)
        )

    def test_correct_values_under_wrong_protocol_identity_fail(self):
        wrong = dataclasses.replace(
            self.identity,
            protocol_tag="future-v2",
            status=ProtocolIdentityStatus.PASS,
        )
        result = verify_implementation_constants_against_frozen_v1(
            FROZEN_V1_CONSTANTS, wrong
        )
        self.assertEqual(result.status, MirrorConformanceStatus.IMPLEMENTATION_CONSTANTS_MIRROR_DRIFT)
        self.assertIn("STRICT_V1_PROTOCOL_BINDING_FAILED", result.failure_reasons)


if __name__ == "__main__":
    unittest.main()
