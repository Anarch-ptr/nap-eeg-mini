"""Immutable, nonauthoritative mirror of frozen protocol v1 constants."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .protocol_identity import (
    FROZEN_PROTOCOL_V1,
    ProtocolIdentityResult,
    ProtocolIdentityStatus,
    verify_protocol_identity,
)


IMPLEMENTATION_CONSTANTS_ROLE = (
    "NONAUTHORITATIVE_MACHINE_READABLE_MIRROR_OF_FROZEN_PROTOCOL"
)
IMPLEMENTATION_CONSTANTS_SCHEMA = "EXTERNAL_REPLICATION_IMPLEMENTATION_CONSTANTS_V1"


class DatasetIdentity(str, Enum):
    LEE2019_MI = "Lee2019_MI"


class ScientificModeLabel(str, Enum):
    RQ1A_CONFIRMATORY = "RQ1A_CONFIRMATORY"
    RQ1B_EXPLORATORY = "RQ1B_EXPLORATORY"
    RQ2_ASSOCIATIONAL = "RQ2_ASSOCIATIONAL"


@dataclass(frozen=True)
class ImplementationConstants:
    schema: str
    role: str
    dataset: DatasetIdentity
    subject_count: int
    split_seed: int
    subset_chain_seed: int
    model_seeds: tuple[int, ...]
    budget_percentages: tuple[int, ...]
    budget_to_optimizer_trial_count: tuple[tuple[int, int], ...]
    canonical_channel_order: tuple[str, ...]
    original_sampling_rate_hz: int
    decimated_sampling_rate_hz: int
    decimation_factor: int
    epoch_start_seconds: float
    epoch_stop_seconds: float
    expected_predecimation_samples: int
    expected_postdecimation_samples: int
    bandpass_low_hz: float
    bandpass_high_hz: float
    butterworth_design_n: int
    filter_output: str
    filter_application: str
    filter_padtype: str
    filter_padlen: int
    rq2_permutation_seeds: tuple[tuple[str, int], ...]
    rq2_bootstrap_seeds: tuple[tuple[str, int], ...]
    rq_modes: tuple[ScientificModeLabel, ...]
    scientific_parameter_updates_enabled: bool

    @property
    def channel_count(self) -> int:
        return len(self.canonical_channel_order)

    @property
    def budget_count_map(self) -> Mapping[int, int]:
        return MappingProxyType(dict(self.budget_to_optimizer_trial_count))


CHANNELS = tuple(
    "Fp1 Fp2 F7 F3 Fz F4 F8 FC5 FC1 FC2 FC6 T7 C3 Cz C4 T8 TP9 CP5 CP1 CP2 "
    "CP6 TP10 P7 P3 Pz P4 P8 PO9 O1 Oz O2 PO10 FC3 FC4 C5 C1 C2 C6 CP3 CPz "
    "CP4 P1 P2 POz FT9 FTT9h TTP7h TP7 TPP9h FT10 FTT10h TPP8h TP8 TPP10h "
    "F9 F10 AF7 AF3 AF4 AF8 PO3 PO4".split()
)
BUDGETS = tuple(range(100, 0, -5))
BUDGET_COUNTS = tuple(zip(BUDGETS, range(80, 0, -4)))

FROZEN_V1_CONSTANTS = ImplementationConstants(
    schema=IMPLEMENTATION_CONSTANTS_SCHEMA,
    role=IMPLEMENTATION_CONSTANTS_ROLE,
    dataset=DatasetIdentity.LEE2019_MI,
    subject_count=54,
    split_seed=42,
    subset_chain_seed=20260719,
    model_seeds=(42, 43, 44),
    budget_percentages=BUDGETS,
    budget_to_optimizer_trial_count=BUDGET_COUNTS,
    canonical_channel_order=CHANNELS,
    original_sampling_rate_hz=1000,
    decimated_sampling_rate_hz=250,
    decimation_factor=4,
    epoch_start_seconds=0.0,
    epoch_stop_seconds=4.0,
    expected_predecimation_samples=4000,
    expected_postdecimation_samples=1000,
    bandpass_low_hz=8.0,
    bandpass_high_hz=32.0,
    butterworth_design_n=4,
    filter_output="SOS",
    filter_application="SOSFILTFILT",
    filter_padtype="ODD",
    filter_padlen=27,
    rq2_permutation_seeds=(
        ("RQ2_PRIMARY_PERMUTATION", 20260721),
        ("RQ2_BASELINE_CAPABLE_PERMUTATION", 20260722),
        ("RQ2_REFINED_PERMUTATION", 20260723),
    ),
    rq2_bootstrap_seeds=(
        ("RQ2_PRIMARY_BOOTSTRAP", 20260724),
        ("RQ2_BASELINE_CAPABLE_BOOTSTRAP", 20260725),
        ("RQ2_REFINED_BOOTSTRAP", 20260726),
    ),
    rq_modes=(
        ScientificModeLabel.RQ1A_CONFIRMATORY,
        ScientificModeLabel.RQ1B_EXPLORATORY,
        ScientificModeLabel.RQ2_ASSOCIATIONAL,
    ),
    scientific_parameter_updates_enabled=False,
)


class MirrorConformanceStatus(str, Enum):
    PASS = "PASS"
    IMPLEMENTATION_CONSTANTS_MIRROR_DRIFT = "IMPLEMENTATION_CONSTANTS_MIRROR_DRIFT"


@dataclass(frozen=True)
class MirrorConformanceResult:
    status: MirrorConformanceStatus
    failure_reasons: tuple[str, ...]


class FatalConstantsDriftError(RuntimeError):
    pass


ImplementationConstantsMirrorDriftError = FatalConstantsDriftError


V1_CONSTANTS_ANCHOR_ROLE = (
    "NONAUTHORITATIVE_IMPLEMENTATION_CONFORMANCE_ANCHOR_BOUND_TO_FROZEN_PROTOCOL_V1"
)

# Fixed after independent comparison with the frozen protocol-v1 Git blob.  This
# literal is deliberately not derived from FROZEN_V1_CONSTANTS at validation
# time.  The frozen preregistration remains the semantic scientific authority.
V1_EXPECTED_CONSTANTS_PAYLOAD_SHA256 = (
    "52f385ceb673c9162e847760048fb83ba4897eab29bce1a822d5e7b2f4c6fced"
)


def canonical_channel_order_bytes(
    channels: tuple[str, ...] = CHANNELS,
) -> bytes:
    return json.dumps(
        channels, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_channel_order_sha256(
    channels: tuple[str, ...] = CHANNELS,
) -> str:
    return hashlib.sha256(canonical_channel_order_bytes(channels)).hexdigest()


def constants_payload(constants: ImplementationConstants) -> dict[str, object]:
    """Return the JSON-safe Phase-I scientific-constants payload."""

    return {
        "bandpass_high_hz": constants.bandpass_high_hz,
        "bandpass_low_hz": constants.bandpass_low_hz,
        "budget_percentages": list(constants.budget_percentages),
        "budget_to_optimizer_trial_count": [
            [budget, count]
            for budget, count in constants.budget_to_optimizer_trial_count
        ],
        "butterworth_design_n": constants.butterworth_design_n,
        "canonical_channel_order": list(constants.canonical_channel_order),
        "dataset": constants.dataset.value,
        "decimated_sampling_rate_hz": constants.decimated_sampling_rate_hz,
        "decimation_factor": constants.decimation_factor,
        "epoch_start_seconds": constants.epoch_start_seconds,
        "epoch_stop_seconds": constants.epoch_stop_seconds,
        "expected_postdecimation_samples": constants.expected_postdecimation_samples,
        "expected_predecimation_samples": constants.expected_predecimation_samples,
        "filter_application": constants.filter_application,
        "filter_output": constants.filter_output,
        "filter_padlen": constants.filter_padlen,
        "filter_padtype": constants.filter_padtype,
        "model_seeds": list(constants.model_seeds),
        "original_sampling_rate_hz": constants.original_sampling_rate_hz,
        "rq2_bootstrap_seeds": dict(constants.rq2_bootstrap_seeds),
        "rq2_permutation_seeds": dict(constants.rq2_permutation_seeds),
        "rq_modes": [mode.value for mode in constants.rq_modes],
        "scientific_parameter_updates_enabled": constants.scientific_parameter_updates_enabled,
        "split_seed": constants.split_seed,
        "subject_count": constants.subject_count,
        "subset_chain_seed": constants.subset_chain_seed,
    }


def canonical_constants_payload_bytes(constants: ImplementationConstants) -> bytes:
    return (
        json.dumps(
            constants_payload(constants),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def constants_payload_sha256(constants: ImplementationConstants) -> str:
    return hashlib.sha256(canonical_constants_payload_bytes(constants)).hexdigest()


def verify_implementation_constants_against_frozen_v1(
    constants: ImplementationConstants = FROZEN_V1_CONSTANTS,
    protocol_result: ProtocolIdentityResult | None = None,
) -> MirrorConformanceResult:
    identity = protocol_result or verify_protocol_identity()
    reasons: list[str] = []
    if identity.status is not ProtocolIdentityStatus.PASS:
        reasons.append("FROZEN_PROTOCOL_IDENTITY_FAILED")
    identity_fields = (
        (identity.protocol_tag, FROZEN_PROTOCOL_V1.protocol_tag),
        (identity.freeze_commit, FROZEN_PROTOCOL_V1.freeze_commit),
        (identity.protocol_blob_oid, FROZEN_PROTOCOL_V1.protocol_blob_oid),
        (identity.protocol_blob_sha256, FROZEN_PROTOCOL_V1.protocol_blob_sha256),
    )
    if any(observed != expected for observed, expected in identity_fields):
        reasons.append("STRICT_V1_PROTOCOL_BINDING_FAILED")
    try:
        payload_digest = constants_payload_sha256(constants)
    except (TypeError, ValueError, OverflowError) as exc:
        reasons.append(f"CANONICAL_CONSTANTS_PAYLOAD_INVALID: {type(exc).__name__}")
    else:
        if payload_digest != V1_EXPECTED_CONSTANTS_PAYLOAD_SHA256:
            reasons.append("V1_CONSTANTS_PAYLOAD_SHA256_MISMATCH")
    if constants.channel_count != 62 or len(set(constants.canonical_channel_order)) != 62:
        reasons.append("CANONICAL_CHANNEL_ORDER_COUNT_OR_UNIQUENESS_FAILED")
    if constants.budget_percentages != tuple(range(100, 0, -5)):
        reasons.append("BUDGET_PERCENTAGE_SEQUENCE_FAILED")
    budget_keys = tuple(
        budget for budget, _count in constants.budget_to_optimizer_trial_count
    )
    budget_counts = tuple(
        count for _budget, count in constants.budget_to_optimizer_trial_count
    )
    if budget_keys != constants.budget_percentages:
        reasons.append("BUDGET_COUNT_KEYS_FAILED")
    if budget_counts != tuple(range(80, 0, -4)) or any(
        count <= 0 or count % 2 for count in budget_counts
    ):
        reasons.append("BUDGET_ABSOLUTE_COUNTS_FAILED")
    if constants.original_sampling_rate_hz // constants.decimation_factor != constants.decimated_sampling_rate_hz:
        reasons.append("SAMPLING_RATE_DECIMATION_RELATIONSHIP_FAILED")
    if constants.expected_predecimation_samples // constants.decimation_factor != constants.expected_postdecimation_samples:
        reasons.append("EPOCH_SAMPLE_DECIMATION_RELATIONSHIP_FAILED")
    epoch_duration = constants.epoch_stop_seconds - constants.epoch_start_seconds
    if epoch_duration * constants.original_sampling_rate_hz != constants.expected_predecimation_samples:
        reasons.append("EPOCH_DURATION_SAMPLE_RELATIONSHIP_FAILED")
    return MirrorConformanceResult(
        status=(MirrorConformanceStatus.IMPLEMENTATION_CONSTANTS_MIRROR_DRIFT if reasons else MirrorConformanceStatus.PASS),
        failure_reasons=tuple(reasons),
    )


def enforce_implementation_constants_or_abort(
    constants: ImplementationConstants = FROZEN_V1_CONSTANTS,
    protocol_result: ProtocolIdentityResult | None = None,
) -> MirrorConformanceResult:
    result = verify_implementation_constants_against_frozen_v1(
        constants, protocol_result
    )
    if result.status is not MirrorConformanceStatus.PASS:
        raise FatalConstantsDriftError(
            f"IMPLEMENTATION_CONSTANTS_MIRROR_DRIFT: {'; '.join(result.failure_reasons)}"
        )
    return result
