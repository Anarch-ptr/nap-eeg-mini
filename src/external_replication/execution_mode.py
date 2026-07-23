"""Fail-closed outcome-blind structural execution primitives."""

from __future__ import annotations

import contextlib
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Iterator


class ExecutionMode(str, Enum):
    OUTCOME_BLIND_STRUCTURAL_SMOKE = "OUTCOME_BLIND_STRUCTURAL_SMOKE"


class ParameterUpdateAuthorization(str, Enum):
    DISABLED = "DISABLED"


DEFAULT_EXECUTION_MODE = ExecutionMode.OUTCOME_BLIND_STRUCTURAL_SMOKE
SCIENTIFIC_PARAMETER_UPDATE_AUTHORIZATION = ParameterUpdateAuthorization.DISABLED

SCIENTIFIC_STARTUP_GATE_ORDER = (
    "PROTOCOL_IDENTITY_GATE",
    "IMPLEMENTATION_CONSTANTS_CONFORMANCE_GATE",
    "ENVIRONMENT_ENFORCEMENT_GATE",
    "RAW_DATA_IDENTITY_GATE",
    "EXPLICIT_RNG_OWNERSHIP_GATE",
    "SCIENTIFIC_EXECUTION_AUTHORIZATION_GATE",
)
STRUCTURAL_STARTUP_GATE_ORDER = (
    "PROTOCOL_IDENTITY_GATE",
    "IMPLEMENTATION_CONSTANTS_CONFORMANCE_GATE",
    "AVAILABLE_ENVIRONMENT_CHECKS",
    "GLOBAL_RNG_POISON_GUARD",
    "OUTCOME_BLIND_STRUCTURAL_SMOKE",
    "STRUCTURAL_TENSOR_OPERATIONS",
    "MODEL_EVAL_INFERENCE_SHAPE_CHECK_WHEN_REQUIRED",
    "MODEL_STATE_DIGEST_EQUALITY_VERIFICATION",
)


class BlindnessViolationReason(str, Enum):
    REAL_OPTIMIZER_CONSTRUCTED_IN_STRUCTURAL_MODE = "REAL_OPTIMIZER_CONSTRUCTED_IN_STRUCTURAL_MODE"
    OPTIMIZER_STEP_REQUESTED = "OPTIMIZER_STEP_REQUESTED"
    BACKWARD_REQUESTED = "BACKWARD_REQUESTED"
    MODEL_TRAIN_MODE_REQUESTED = "MODEL_TRAIN_MODE_REQUESTED"
    MODEL_PARAMETER_STATE_CHANGED = "MODEL_PARAMETER_STATE_CHANGED"
    MODEL_BUFFER_STATE_CHANGED = "MODEL_BUFFER_STATE_CHANGED"
    SCIENTIFIC_LOSS_REQUESTED = "SCIENTIFIC_LOSS_REQUESTED"
    SCIENTIFIC_METRIC_REQUESTED = "SCIENTIFIC_METRIC_REQUESTED"
    S2_SCIENTIFIC_PREDICTION_REQUESTED = "S2_SCIENTIFIC_PREDICTION_REQUESTED"
    CHECKPOINT_SELECTION_REQUESTED = "CHECKPOINT_SELECTION_REQUESTED"


class FatalBlindnessViolationError(RuntimeError):
    def __init__(self, reason: BlindnessViolationReason):
        self.reason = reason
        super().__init__(reason.value)


ScientificParameterUpdateForbiddenError = FatalBlindnessViolationError


class ScientificMetric(str, Enum):
    ACCURACY = "accuracy"
    BALANCED_ACCURACY = "balanced_accuracy"
    CONFUSION_MATRIX = "confusion_matrix"
    P_S_B = "P_s(B)"
    F_S_B = "F_s(B)"
    AUFC = "AUFC"
    LOCAL_SLOPE = "local_slope"
    FINITE_CCP = "finite_CCP"
    SNC_OUTCOME_SUMMARY = "SNC_outcome_summary"
    RQ1 = "RQ1"
    RQ2 = "RQ2"


class StructuralMetadata(str, Enum):
    SHAPE = "shape"
    COUNTS = "counts"
    CHANNEL_IDENTITIES = "channel_identities"
    PROVENANCE = "provenance"
    DTYPE = "dtype"
    FINITENESS = "finiteness"


@dataclass(frozen=True)
class ExecutionFirewallStatus:
    protocol_identity_gate: str = "IMPLEMENTED"
    implementation_constants_conformance_gate: str = "IMPLEMENTED"
    environment_enforcement_gate: str = "IMPLEMENTED_CURRENT_PROCESS_ONLY"
    raw_data_identity_gate: str = "NOT_IMPLEMENTED_PHASE_II"
    explicit_rng_ownership_gate: str = "FOUNDATION_IMPLEMENTED"
    outcome_blind_implementation_gate: str = "STRUCTURALLY_ENFORCED"
    scientific_execution_authorization_gate: str = "DENY"


FOUR_GATE_FIREWALL = ExecutionFirewallStatus()


class StructuralExecutionGuard:
    mode = DEFAULT_EXECUTION_MODE
    parameter_update_authorization = SCIENTIFIC_PARAMETER_UPDATE_AUTHORIZATION

    def request_real_optimizer(self) -> None:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.REAL_OPTIMIZER_CONSTRUCTED_IN_STRUCTURAL_MODE
        )

    def request_optimizer_step(self) -> None:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.OPTIMIZER_STEP_REQUESTED
        )

    def request_backward(self) -> None:
        raise FatalBlindnessViolationError(BlindnessViolationReason.BACKWARD_REQUESTED)

    def request_train_mode(self) -> None:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.MODEL_TRAIN_MODE_REQUESTED
        )

    def request_scientific_loss(self) -> None:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.SCIENTIFIC_LOSS_REQUESTED
        )

    def request_scientific_metric(self, _metric: ScientificMetric) -> None:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.SCIENTIFIC_METRIC_REQUESTED
        )

    def request_s2_scientific_prediction(self) -> None:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.S2_SCIENTIFIC_PREDICTION_REQUESTED
        )

    def request_checkpoint_selection(self) -> None:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.CHECKPOINT_SELECTION_REQUESTED
        )

    def emit_structural_metadata(self, kind: StructuralMetadata, value: object) -> tuple[StructuralMetadata, object]:
        return kind, value


class ForbiddenOptimizer:
    """Structural deprivation object; never wraps a real optimizer."""

    def step(self, *_args: object, **_kwargs: object) -> None:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.OPTIMIZER_STEP_REQUESTED
        )

    def zero_grad(self, *_args: object, **_kwargs: object) -> None:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.OPTIMIZER_STEP_REQUESTED
        )


def deterministic_dummy_logits(batch_size: int, class_count: int):
    """Fixed synthetic logits for tensor-flow checks; never consumes labels."""

    import torch

    if batch_size < 0 or class_count <= 0:
        raise ValueError("invalid structural tensor shape")
    return torch.zeros((batch_size, class_count), dtype=torch.float32)


@dataclass(frozen=True)
class ModelStateDigest:
    parameter_digest: str
    buffer_digest: str
    combined_digest: str


def _named_tensor_digest(named_tensors) -> str:
    import torch

    digest = hashlib.sha256()
    for name, tensor in sorted(named_tensors, key=lambda item: item[0]):
        value = tensor.detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(str(tuple(value.shape)).encode("ascii"))
        raw_bytes = value.reshape(-1).view(dtype=torch.uint8).numpy().tobytes(order="C")
        digest.update(raw_bytes)
    return digest.hexdigest()


def model_state_digest(model) -> ModelStateDigest:
    parameter_digest = _named_tensor_digest(model.named_parameters())
    buffer_digest = _named_tensor_digest(model.named_buffers())
    combined = hashlib.sha256(
        f"{parameter_digest}:{buffer_digest}".encode("ascii")
    ).hexdigest()
    return ModelStateDigest(parameter_digest, buffer_digest, combined)


def freeze_model_for_structural_smoke(model):
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model


@contextlib.contextmanager
def structural_model_guard(model) -> Iterator[object]:
    """Freeze model state and prove parameters and buffers remain byte-identical."""

    freeze_model_for_structural_smoke(model)
    before = model_state_digest(model)
    try:
        yield model
    finally:
        after = model_state_digest(model)
        if model.training:
            raise FatalBlindnessViolationError(
                BlindnessViolationReason.MODEL_TRAIN_MODE_REQUESTED
            )
        if any(parameter.requires_grad for parameter in model.parameters()):
            raise FatalBlindnessViolationError(
                BlindnessViolationReason.MODEL_PARAMETER_STATE_CHANGED
            )
        if before.parameter_digest != after.parameter_digest:
            raise FatalBlindnessViolationError(
                BlindnessViolationReason.MODEL_PARAMETER_STATE_CHANGED
            )
        if before.buffer_digest != after.buffer_digest:
            raise FatalBlindnessViolationError(
                BlindnessViolationReason.MODEL_BUFFER_STATE_CHANGED
            )


def structural_forward(model, inputs):
    import torch

    if model.training:
        raise FatalBlindnessViolationError(
            BlindnessViolationReason.MODEL_TRAIN_MODE_REQUESTED
        )
    with torch.inference_mode():
        return model(inputs)
