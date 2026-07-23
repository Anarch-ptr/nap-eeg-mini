from __future__ import annotations

import unittest

import torch
from torch import nn

from src.external_replication.execution_mode import (
    DEFAULT_EXECUTION_MODE,
    FOUR_GATE_FIREWALL,
    SCIENTIFIC_PARAMETER_UPDATE_AUTHORIZATION,
    SCIENTIFIC_STARTUP_GATE_ORDER,
    STRUCTURAL_STARTUP_GATE_ORDER,
    BlindnessViolationReason,
    ExecutionMode,
    FatalBlindnessViolationError,
    ForbiddenOptimizer,
    ParameterUpdateAuthorization,
    ScientificMetric,
    StructuralExecutionGuard,
    StructuralMetadata,
    deterministic_dummy_logits,
    freeze_model_for_structural_smoke,
    model_state_digest,
    structural_forward,
    structural_model_guard,
)


def synthetic_model():
    return nn.Sequential(nn.Linear(4, 4), nn.BatchNorm1d(4), nn.ReLU(), nn.Linear(4, 2))


class ExecutionGateTests(unittest.TestCase):
    def setUp(self):
        self.guard = StructuralExecutionGuard()

    def test_default_mode_and_parameter_updates_disabled(self):
        self.assertEqual(DEFAULT_EXECUTION_MODE, ExecutionMode.OUTCOME_BLIND_STRUCTURAL_SMOKE)
        self.assertEqual(SCIENTIFIC_PARAMETER_UPDATE_AUTHORIZATION, ParameterUpdateAuthorization.DISABLED)
        self.assertEqual(
            FOUR_GATE_FIREWALL.environment_enforcement_gate,
            "IMPLEMENTED_CURRENT_PROCESS_ONLY",
        )
        self.assertEqual(FOUR_GATE_FIREWALL.raw_data_identity_gate, "NOT_IMPLEMENTED_PHASE_II")
        self.assertEqual(FOUR_GATE_FIREWALL.scientific_execution_authorization_gate, "DENY")
        self.assertEqual(SCIENTIFIC_STARTUP_GATE_ORDER[0], "PROTOCOL_IDENTITY_GATE")
        self.assertEqual(SCIENTIFIC_STARTUP_GATE_ORDER[-1], "SCIENTIFIC_EXECUTION_AUTHORIZATION_GATE")
        self.assertEqual(STRUCTURAL_STARTUP_GATE_ORDER[0], "PROTOCOL_IDENTITY_GATE")

    def test_no_real_optimizer_and_step_always_raises(self):
        with self.assertRaises(FatalBlindnessViolationError):
            self.guard.request_real_optimizer()
        with self.assertRaisesRegex(FatalBlindnessViolationError, "OPTIMIZER_STEP_REQUESTED"):
            ForbiddenOptimizer().step()

    def test_backward_is_blocked(self):
        with self.assertRaisesRegex(FatalBlindnessViolationError, "BACKWARD_REQUESTED"):
            self.guard.request_backward()

    def test_scientific_loss_is_blocked(self):
        with self.assertRaisesRegex(FatalBlindnessViolationError, "SCIENTIFIC_LOSS_REQUESTED"):
            self.guard.request_scientific_loss()

    def test_all_scientific_metrics_are_blocked(self):
        for metric in ScientificMetric:
            with self.subTest(metric=metric):
                with self.assertRaisesRegex(FatalBlindnessViolationError, "SCIENTIFIC_METRIC_REQUESTED"):
                    self.guard.request_scientific_metric(metric)

    def test_s2_scientific_prediction_is_blocked(self):
        with self.assertRaisesRegex(FatalBlindnessViolationError, "S2_SCIENTIFIC_PREDICTION_REQUESTED"):
            self.guard.request_s2_scientific_prediction()

    def test_checkpoint_selection_is_blocked(self):
        with self.assertRaisesRegex(FatalBlindnessViolationError, "CHECKPOINT_SELECTION_REQUESTED"):
            self.guard.request_checkpoint_selection()

    def test_structural_metadata_and_dummy_logits_are_allowed(self):
        item = self.guard.emit_structural_metadata(StructuralMetadata.SHAPE, (3, 2))
        self.assertEqual(item, (StructuralMetadata.SHAPE, (3, 2)))
        logits = deterministic_dummy_logits(3, 2)
        self.assertEqual(tuple(logits.shape), (3, 2))
        self.assertTrue(torch.equal(logits, torch.zeros_like(logits)))

    def test_model_is_eval_and_parameters_are_frozen(self):
        model = freeze_model_for_structural_smoke(synthetic_model())
        self.assertFalse(model.training)
        self.assertTrue(all(not parameter.requires_grad for parameter in model.parameters()))

    def test_forward_preserves_parameter_and_buffer_digests(self):
        model = synthetic_model()
        with structural_model_guard(model) as guarded:
            before = model_state_digest(guarded)
            output = structural_forward(guarded, torch.zeros(3, 4))
            after = model_state_digest(guarded)
        self.assertEqual(tuple(output.shape), (3, 2))
        self.assertEqual(before, after)

    def test_train_mode_request_is_detected(self):
        model = synthetic_model()
        with self.assertRaisesRegex(FatalBlindnessViolationError, "MODEL_TRAIN_MODE_REQUESTED"):
            with structural_model_guard(model):
                model.train()

    def test_adversarial_parameter_mutation_is_detected(self):
        model = synthetic_model()
        with self.assertRaisesRegex(FatalBlindnessViolationError, "MODEL_PARAMETER_STATE_CHANGED"):
            with structural_model_guard(model):
                with torch.no_grad():
                    next(model.parameters()).add_(1.0)

    def test_adversarial_buffer_mutation_is_detected(self):
        model = synthetic_model()
        with self.assertRaisesRegex(FatalBlindnessViolationError, "MODEL_BUFFER_STATE_CHANGED"):
            with structural_model_guard(model):
                with torch.no_grad():
                    next(model.buffers()).add_(1.0)


if __name__ == "__main__":
    unittest.main()
