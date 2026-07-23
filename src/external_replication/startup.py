"""Executable fail-closed composition for pre-scientific startup gates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .constants import enforce_implementation_constants_or_abort
from .environment import (
    EnvironmentNotConformantError,
    EnvironmentStatus,
    _capture_current_environment_after_prerequisites,
    resolve_production_repository_root,
)
from .protocol_identity import (
    ProtocolIdentityError,
    ProtocolIdentityStatus,
    verify_protocol_identity,
)


@dataclass(frozen=True)
class PreScientificStartupResult:
    status: str
    protocol_identity_gate: str
    implementation_constants_conformance_gate: str
    environment_enforcement_gate: str
    raw_data_identity_gate: str
    scientific_execution_authorization: str


def enforce_pre_scientific_startup_or_abort(
    repo_root: str | Path | None = None,
) -> PreScientificStartupResult:
    """Execute protocol -> constants -> environment; never authorize science.

    ``repo_root`` is only a physical-root consistency assertion.
    """

    root = resolve_production_repository_root(repo_root)
    identity = verify_protocol_identity(root)
    if identity.status is not ProtocolIdentityStatus.PASS:
        raise ProtocolIdentityError(
            "PROTOCOL_IDENTITY_GATE_FAILED: " + ";".join(identity.failure_reasons)
        )
    enforce_implementation_constants_or_abort(protocol_result=identity)
    environment = _capture_current_environment_after_prerequisites(root)
    if environment.status is not EnvironmentStatus.CONFORMANT:
        reasons = ",".join(
            dict.fromkeys(reason.value for reason in environment.failure_reasons)
        )
        raise EnvironmentNotConformantError(
            f"ENVIRONMENT_NOT_CONFORMANT: {reasons}"
        )
    return PreScientificStartupResult(
        status="PASS_THROUGH_ENVIRONMENT_STAGE",
        protocol_identity_gate="PASS",
        implementation_constants_conformance_gate="PASS",
        environment_enforcement_gate="PASS",
        raw_data_identity_gate="NOT_IMPLEMENTED_PHASE_II_B",
        scientific_execution_authorization="DENY",
    )
