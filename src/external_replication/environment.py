"""Fail-closed enforcement of the reviewed Lee2019_MI environment identity."""

from __future__ import annotations

import hashlib
import os
import platform
import re
import sys
from dataclasses import dataclass
from enum import Enum
from importlib import metadata
from pathlib import Path

from .constants import (
    MirrorConformanceStatus,
    verify_implementation_constants_against_frozen_v1,
)
from .protocol_identity import (
    FROZEN_PROTOCOL_V1,
    ProtocolIdentityStatus,
    parse_strict_json,
    verify_protocol_identity,
)


ENVIRONMENT_LOCK_RELATIVE_PATH = Path("requirements/lee2019_mi.lock.txt")
ENVIRONMENT_MANIFEST_RELATIVE_PATH = Path(
    "manifests/external_boundary_replication_environment_v1.json"
)
ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH = Path(
    "manifests/external_boundary_replication_environment_artifacts_v1.json"
)

# Fixed reviewed byte identities. Never derive these from runtime file contents.
EXPECTED_ENVIRONMENT_LOCK_SHA256 = (
    "f079f7a40243ad365dfa984980da1e825932b0d317adc94c36da78b3cd5ac121"
)
EXPECTED_ENVIRONMENT_ARTIFACT_MANIFEST_SHA256 = (
    "49bea1b78a6f290a09e39049bc4116f044837dd85d0d98449d50e00eb3a6fd65"
)
# Finalized after the environment manifest is regenerated below.
EXPECTED_ENVIRONMENT_MANIFEST_SHA256 = (
    "dd0ca1c0a1229a79c35a040741e351efd4fe134a91b203c750292c552d921b0a"
)

ENVIRONMENT_LOCK_SCHEMA_VERSION = "EXTERNAL_BOUNDARY_REPLICATION_ENVIRONMENT_V1"
ENVIRONMENT_LOCK_ROLE = "POST_FREEZE_IMPLEMENTATION_ENVIRONMENT_LOCK"
ENVIRONMENT_ARTIFACT_SCHEMA_VERSION = (
    "EXTERNAL_BOUNDARY_REPLICATION_ENVIRONMENT_ARTIFACTS_V1"
)
ENVIRONMENT_ARTIFACT_ROLE = "POST_FREEZE_ENVIRONMENT_ARTIFACT_PROVENANCE"
ENVIRONMENT_ENFORCEMENT_GATE_STATUS = "IMPLEMENTED_CURRENT_PROCESS_ONLY"
SYNTHETIC_EVALUATOR_ROLE = "TEST_AND_PURE_LOGIC_ONLY"
PRODUCTION_AUTHORIZATION_ROLE = "CURRENT_PROCESS_ONLY"
PRODUCTION_REPOSITORY_ROOT_ROLE = "EXECUTING_MODULE_PHYSICAL_ROOT"
CALLER_REPOSITORY_ROOT_ROLE = "OPTIONAL_TRUSTED_ROOT_CONSISTENCY_ASSERTION"

CORE_SCIENTIFIC_DISTRIBUTIONS = (
    "moabb",
    "mne",
    "numpy",
    "scipy",
    "torch",
    "scikit-learn",
)

_PACKAGE_ENTRY = re.compile(
    r"(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"=="
    r"(?P<version>[0-9]+(?:\.[0-9A-Za-z]+)*(?:\+[0-9A-Za-z]+(?:[._-][0-9A-Za-z]+)*)?)"
)


class EnvironmentStatus(str, Enum):
    CONFORMANT = "CONFORMANT"
    NONCONFORMANT = "NONCONFORMANT"
    UNRESOLVED = "UNRESOLVED"


class EnvironmentFailureReason(str, Enum):
    DEPENDENCY_VERSION_MISMATCH = "DEPENDENCY_VERSION_MISMATCH"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    DEPENDENCY_REQUIREMENT_CONFLICT = "DEPENDENCY_REQUIREMENT_CONFLICT"
    ENVIRONMENT_METADATA_UNRESOLVED = "ENVIRONMENT_METADATA_UNRESOLVED"
    ACTIVE_DEPENDENCY_CLOSURE_INCOMPLETE = "ACTIVE_DEPENDENCY_CLOSURE_INCOMPLETE"
    PYTHON_VERSION_MISMATCH = "PYTHON_VERSION_MISMATCH"
    PYTHON_IMPLEMENTATION_MISMATCH = "PYTHON_IMPLEMENTATION_MISMATCH"
    PYTHON_EXECUTABLE_MISMATCH = "PYTHON_EXECUTABLE_MISMATCH"
    VENV_PREFIX_MISMATCH = "VENV_PREFIX_MISMATCH"
    PLATFORM_SYSTEM_MISMATCH = "PLATFORM_SYSTEM_MISMATCH"
    PLATFORM_MACHINE_MISMATCH = "PLATFORM_MACHINE_MISMATCH"
    ENVIRONMENT_LOCK_FILE_MISSING = "ENVIRONMENT_LOCK_FILE_MISSING"
    ENVIRONMENT_LOCK_CORRUPT = "ENVIRONMENT_LOCK_CORRUPT"
    ENVIRONMENT_LOCK_SHA256_MISMATCH = "ENVIRONMENT_LOCK_SHA256_MISMATCH"
    ENVIRONMENT_MANIFEST_MISSING = "ENVIRONMENT_MANIFEST_MISSING"
    ENVIRONMENT_MANIFEST_CORRUPT = "ENVIRONMENT_MANIFEST_CORRUPT"
    ENVIRONMENT_MANIFEST_SHA256_MISMATCH = "ENVIRONMENT_MANIFEST_SHA256_MISMATCH"
    ENVIRONMENT_ARTIFACT_MANIFEST_MISSING = "ENVIRONMENT_ARTIFACT_MANIFEST_MISSING"
    ENVIRONMENT_ARTIFACT_MANIFEST_CORRUPT = "ENVIRONMENT_ARTIFACT_MANIFEST_CORRUPT"
    ENVIRONMENT_ARTIFACT_MANIFEST_SHA256_MISMATCH = (
        "ENVIRONMENT_ARTIFACT_MANIFEST_SHA256_MISMATCH"
    )
    ENVIRONMENT_ARTIFACT_LOCK_MISMATCH = "ENVIRONMENT_ARTIFACT_LOCK_MISMATCH"
    ENVIRONMENT_LOCK_MANIFEST_MISMATCH = "ENVIRONMENT_LOCK_MANIFEST_MISMATCH"
    IMPLEMENTATION_CONSTANTS_MISMATCH = "IMPLEMENTATION_CONSTANTS_MISMATCH"
    PROTOCOL_IDENTITY_MISMATCH = "PROTOCOL_IDENTITY_MISMATCH"


class EnvironmentNotConformantError(RuntimeError):
    pass


class FatalTrustedRepositoryRootMismatch(EnvironmentNotConformantError):
    pass


class EnvironmentLockIntegrityError(EnvironmentNotConformantError):
    def __init__(self, reason: EnvironmentFailureReason):
        self.reason = reason
        super().__init__(reason.value)


@dataclass(frozen=True)
class DependencyObservation:
    distribution: str
    expected_repository_requirement: str
    observed_runtime_version: str | None
    lock_status: str
    failure_reason: EnvironmentFailureReason | None


@dataclass(frozen=True)
class EnvironmentLockSpec:
    python_implementation: str
    python_requirement: str
    dependencies: tuple[tuple[str, str], ...]
    canonical_platform: tuple[tuple[str, str], ...]
    protocol_tag: str
    protocol_commit: str
    implementation_commit_at_lock_creation: str
    lock_file_sha256: str
    manifest_sha256: str
    artifact_manifest_sha256: str
    artifact_record_count: int
    reference_execution_mode: str
    torch_build_identity: str


@dataclass(frozen=True)
class EnvironmentSnapshot:
    executable: str
    python_version: str
    python_version_info: tuple[int, int, int]
    python_implementation: str
    prefix: str
    base_prefix: str
    system: str
    machine: str
    platform_description: str
    installed_versions: tuple[tuple[str, str | None], ...]
    active_dependency_names: tuple[str, ...]
    implementation_commit: str | None


@dataclass(frozen=True)
class EnvironmentReport:
    status: EnvironmentStatus
    executable: str
    python_version: str
    python_implementation: str
    python_requirement: str | None
    prefix: str
    base_prefix: str
    platform: str
    machine: str
    implementation_commit: str | None
    implementation_commit_at_lock_creation: str | None
    protocol_commit: str | None
    environment_lock_sha256: str | None
    environment_manifest_sha256: str | None
    environment_artifact_manifest_sha256: str | None
    reference_execution_mode: str | None
    dependencies: tuple[DependencyObservation, ...]
    failure_reasons: tuple[EnvironmentFailureReason, ...]

    def observed_version(self, distribution: str) -> str | None:
        normalized = _normalize_distribution_name(distribution)
        return next(
            item.observed_runtime_version
            for item in self.dependencies
            if item.distribution == normalized
        )


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def trusted_repository_root() -> Path:
    """Return the physical repository root containing this executing module."""

    return Path(__file__).resolve().parents[2]


def resolve_production_repository_root(
    declared_repo_root: str | Path | None = None,
) -> Path:
    """Resolve the trusted root; a caller path is only a consistency assertion."""

    authoritative = trusted_repository_root().resolve()
    if declared_repo_root is None:
        return authoritative
    declared = Path(declared_repo_root).resolve()
    if os.path.normcase(str(declared)) != os.path.normcase(str(authoritative)):
        raise FatalTrustedRepositoryRootMismatch(
            "TRUSTED_REPOSITORY_ROOT_MISMATCH: "
            f"authoritative={authoritative}; declared={declared}"
        )
    return authoritative


def read_exact_requirements(requirements_path: str | Path) -> dict[str, str]:
    """Read the authoritative strict name==exact-version scientific lock."""

    requirements: dict[str, str] = {}
    for raw_line in Path(requirements_path).read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        match = _PACKAGE_ENTRY.fullmatch(raw_line)
        if match is None:
            raise EnvironmentLockIntegrityError(
                EnvironmentFailureReason.ENVIRONMENT_LOCK_CORRUPT
            )
        key = _normalize_distribution_name(match.group("name"))
        version = match.group("version")
        if key in requirements:
            reason = (
                EnvironmentFailureReason.DEPENDENCY_REQUIREMENT_CONFLICT
                if requirements[key] != version
                else EnvironmentFailureReason.ENVIRONMENT_LOCK_CORRUPT
            )
            raise EnvironmentLockIntegrityError(reason)
        requirements[key] = version
    if not requirements:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_LOCK_CORRUPT
        )
    return requirements


def _manifest_dependency_map(manifest: dict[str, object]) -> dict[str, str]:
    groups = manifest.get("dependencies")
    expected_groups = {
        "data_acquisition_dependency",
        "direct_scientific_lock",
        "operational_only",
        "transitive_required_lock",
    }
    if not isinstance(groups, dict) or set(groups) != expected_groups:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_MANIFEST_CORRUPT
        )
    dependencies: dict[str, str] = {}
    for group_name in sorted(groups):
        group = groups[group_name]
        if not isinstance(group, dict):
            raise EnvironmentLockIntegrityError(
                EnvironmentFailureReason.ENVIRONMENT_MANIFEST_CORRUPT
            )
        for raw_name, version in group.items():
            if not isinstance(raw_name, str) or not isinstance(version, str):
                raise EnvironmentLockIntegrityError(
                    EnvironmentFailureReason.ENVIRONMENT_MANIFEST_CORRUPT
                )
            name = _normalize_distribution_name(raw_name)
            if name in dependencies:
                raise EnvironmentLockIntegrityError(
                    EnvironmentFailureReason.ENVIRONMENT_MANIFEST_CORRUPT
                )
            dependencies[name] = version
    return dependencies


def _validate_artifact_manifest(
    root: Path,
    manifest: dict[str, object],
    lock_dependencies: dict[str, str],
) -> tuple[str, int]:
    artifact_path = root / ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH
    if not artifact_path.is_file():
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_MANIFEST_MISSING
        )
    try:
        artifact_bytes = artifact_path.read_bytes()
    except OSError as exc:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_MANIFEST_CORRUPT
        ) from exc
    artifact_sha = _sha256(artifact_bytes)
    if artifact_sha != EXPECTED_ENVIRONMENT_ARTIFACT_MANIFEST_SHA256:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_MANIFEST_SHA256_MISMATCH
        )
    if (
        manifest.get("artifact_manifest_path")
        != ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH.as_posix()
        or manifest.get("artifact_manifest_sha256") != artifact_sha
    ):
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_MANIFEST_CORRUPT
        )
    try:
        artifact = parse_strict_json(artifact_bytes)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_MANIFEST_CORRUPT
        ) from exc
    if (
        not isinstance(artifact, dict)
        or artifact.get("schema_version") != ENVIRONMENT_ARTIFACT_SCHEMA_VERSION
        or artifact.get("role") != ENVIRONMENT_ARTIFACT_ROLE
        or artifact.get("artifact_identity_status") != "COMPLETE"
        or artifact.get("canonical_platform") != manifest.get("canonical_platform")
        or not isinstance(artifact.get("records"), list)
    ):
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_MANIFEST_CORRUPT
        )
    records = artifact["records"]
    record_map: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise EnvironmentLockIntegrityError(
                EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_MANIFEST_CORRUPT
            )
        name = record.get("normalized_name")
        version = record.get("version")
        digest = record.get("artifact_sha256")
        if (
            not isinstance(name, str)
            or name != _normalize_distribution_name(name)
            or not isinstance(version, str)
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or record.get("artifact_type") != "wheel"
            or not isinstance(record.get("artifact_filename"), str)
            or not isinstance(record.get("source_index_or_repository"), str)
            or not isinstance(record.get("exact_source_url"), str)
            or record.get("provenance_resolution_status") is None
            or name in record_map
        ):
            raise EnvironmentLockIntegrityError(
                EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_MANIFEST_CORRUPT
            )
        record_map[name] = version
    if (
        record_map != lock_dependencies
        or artifact.get("record_count") != len(records)
        or manifest.get("artifact_record_count") != len(records)
    ):
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_LOCK_MISMATCH
        )
    return artifact_sha, len(records)


def _read_environment_lock_after_prerequisites(root: Path) -> EnvironmentLockSpec:
    manifest_path = root / ENVIRONMENT_MANIFEST_RELATIVE_PATH
    if not manifest_path.is_file():
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_MANIFEST_MISSING
        )
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_MANIFEST_CORRUPT
        ) from exc
    manifest_sha = _sha256(manifest_bytes)
    if manifest_sha != EXPECTED_ENVIRONMENT_MANIFEST_SHA256:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_MANIFEST_SHA256_MISMATCH
        )
    try:
        manifest = parse_strict_json(manifest_bytes)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_MANIFEST_CORRUPT
        ) from exc
    fixed_fields = {
        "schema_version": ENVIRONMENT_LOCK_SCHEMA_VERSION,
        "role": ENVIRONMENT_LOCK_ROLE,
        "protocol_tag": FROZEN_PROTOCOL_V1.protocol_tag,
        "protocol_commit": FROZEN_PROTOCOL_V1.freeze_commit,
        "lock_file_path": ENVIRONMENT_LOCK_RELATIVE_PATH.as_posix(),
        "lock_file_sha256": EXPECTED_ENVIRONMENT_LOCK_SHA256,
        "artifact_manifest_path": ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH.as_posix(),
        "artifact_manifest_sha256": EXPECTED_ENVIRONMENT_ARTIFACT_MANIFEST_SHA256,
        "serialization": "UTF8_JSON_SORT_KEYS_INDENT_2_LF",
        "environment_reconstruction_status": "PASS",
    }
    if not isinstance(manifest, dict) or any(
        manifest.get(key) != value for key, value in fixed_fields.items()
    ):
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_MANIFEST_CORRUPT
        )
    lock_path = root / ENVIRONMENT_LOCK_RELATIVE_PATH
    if not lock_path.is_file():
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_LOCK_FILE_MISSING
        )
    try:
        lock_bytes = lock_path.read_bytes()
    except OSError as exc:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_LOCK_CORRUPT
        ) from exc
    lock_sha = _sha256(lock_bytes)
    if lock_sha != EXPECTED_ENVIRONMENT_LOCK_SHA256:
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_LOCK_SHA256_MISMATCH
        )
    lock_dependencies = read_exact_requirements(lock_path)
    if lock_dependencies != _manifest_dependency_map(manifest):
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_LOCK_MANIFEST_MISMATCH
        )
    artifact_sha, artifact_count = _validate_artifact_manifest(
        root, manifest, lock_dependencies
    )
    canonical_platform = manifest.get("canonical_platform")
    reference = manifest.get("reference_execution")
    if (
        manifest.get("python_implementation") != "CPython"
        or manifest.get("python_requirement") != "==3.12.10"
        or not isinstance(canonical_platform, dict)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in canonical_platform.items())
        or not isinstance(manifest.get("implementation_commit_at_lock_creation"), str)
        or not isinstance(reference, dict)
        or reference.get("mode") != "CPU_ONLY"
        or reference.get("torch_build_identity") != lock_dependencies.get("torch")
        or reference.get("cuda_numerical_equivalence_validated") is not False
    ):
        raise EnvironmentLockIntegrityError(
            EnvironmentFailureReason.ENVIRONMENT_MANIFEST_CORRUPT
        )
    return EnvironmentLockSpec(
        python_implementation="CPython",
        python_requirement="==3.12.10",
        dependencies=tuple(lock_dependencies.items()),
        canonical_platform=tuple(sorted(canonical_platform.items())),
        protocol_tag=manifest["protocol_tag"],
        protocol_commit=manifest["protocol_commit"],
        implementation_commit_at_lock_creation=manifest[
            "implementation_commit_at_lock_creation"
        ],
        lock_file_sha256=lock_sha,
        manifest_sha256=manifest_sha,
        artifact_manifest_sha256=artifact_sha,
        artifact_record_count=artifact_count,
        reference_execution_mode=reference["mode"],
        torch_build_identity=reference["torch_build_identity"],
    )


def _active_dependency_names(roots: tuple[str, ...]) -> tuple[str, ...]:
    from packaging.requirements import Requirement

    seen: set[str] = set()
    pending = list(roots)
    while pending:
        name = _normalize_distribution_name(pending.pop())
        if name in seen:
            continue
        seen.add(name)
        try:
            requirements = metadata.distribution(name).requires or []
        except metadata.PackageNotFoundError:
            continue
        for raw_requirement in requirements:
            requirement = Requirement(raw_requirement)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            child = _normalize_distribution_name(requirement.name)
            if child not in seen:
                pending.append(child)
    return tuple(sorted(seen))


def _current_environment_snapshot(root: Path, lock: EnvironmentLockSpec) -> EnvironmentSnapshot:
    versions: list[tuple[str, str | None]] = []
    for distribution, _expected in lock.dependencies:
        try:
            observed = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            observed = None
        versions.append((distribution, observed))
    try:
        from .protocol_identity import _text

        implementation_commit = _text(root, "rev-parse", "HEAD")
    except RuntimeError:
        implementation_commit = None
    return EnvironmentSnapshot(
        executable=sys.executable,
        python_version=platform.python_version(),
        python_version_info=tuple(sys.version_info[:3]),
        python_implementation=platform.python_implementation(),
        prefix=sys.prefix,
        base_prefix=sys.base_prefix,
        system=platform.system(),
        machine=platform.machine(),
        platform_description=platform.platform(),
        installed_versions=tuple(versions),
        active_dependency_names=_active_dependency_names(
            tuple(name for name, _version in lock.dependencies)
        ),
        implementation_commit=implementation_commit,
    )


def _evaluate_environment_snapshot(
    root: Path,
    lock: EnvironmentLockSpec,
    snapshot: EnvironmentSnapshot,
) -> EnvironmentReport:
    """SYNTHETIC_EVALUATOR: TEST_AND_PURE_LOGIC_ONLY."""

    expected_platform = dict(lock.canonical_platform)
    failures: list[EnvironmentFailureReason] = []
    expected_version = lock.python_requirement.removeprefix("==")
    if snapshot.python_implementation != lock.python_implementation:
        failures.append(EnvironmentFailureReason.PYTHON_IMPLEMENTATION_MISMATCH)
    if (
        snapshot.python_version != expected_version
        or snapshot.python_version_info != (3, 12, 10)
    ):
        failures.append(EnvironmentFailureReason.PYTHON_VERSION_MISMATCH)
    expected_venv = (root / ".venv").resolve()
    expected_executable = (expected_venv / "Scripts" / "python.exe").resolve()
    if os.path.normcase(str(Path(snapshot.executable).resolve())) != os.path.normcase(
        str(expected_executable)
    ):
        failures.append(EnvironmentFailureReason.PYTHON_EXECUTABLE_MISMATCH)
    if os.path.normcase(str(Path(snapshot.prefix).resolve())) != os.path.normcase(
        str(expected_venv)
    ):
        failures.append(EnvironmentFailureReason.VENV_PREFIX_MISMATCH)
    if snapshot.system != expected_platform.get("os"):
        failures.append(EnvironmentFailureReason.PLATFORM_SYSTEM_MISMATCH)
    if snapshot.machine != expected_platform.get("machine_architecture"):
        failures.append(EnvironmentFailureReason.PLATFORM_MACHINE_MISMATCH)
    observed_versions = dict(snapshot.installed_versions)
    observations: list[DependencyObservation] = []
    for distribution, expected in lock.dependencies:
        observed = observed_versions.get(distribution)
        if observed is None:
            reason = EnvironmentFailureReason.DEPENDENCY_MISSING
        elif observed != expected:
            reason = EnvironmentFailureReason.DEPENDENCY_VERSION_MISMATCH
        else:
            reason = None
        observations.append(
            DependencyObservation(
                distribution=distribution,
                expected_repository_requirement=f"{distribution}=={expected}",
                observed_runtime_version=observed,
                lock_status="EXACT_ENVIRONMENT_AND_ARTIFACT_LOCK",
                failure_reason=reason,
            )
        )
        if reason is not None:
            failures.append(reason)
    if set(snapshot.active_dependency_names) - set(dict(lock.dependencies)):
        failures.append(EnvironmentFailureReason.ACTIVE_DEPENDENCY_CLOSURE_INCOMPLETE)
    return EnvironmentReport(
        status=EnvironmentStatus.CONFORMANT if not failures else EnvironmentStatus.NONCONFORMANT,
        executable=snapshot.executable,
        python_version=snapshot.python_version,
        python_implementation=snapshot.python_implementation,
        python_requirement=lock.python_requirement,
        prefix=snapshot.prefix,
        base_prefix=snapshot.base_prefix,
        platform=snapshot.platform_description,
        machine=snapshot.machine,
        implementation_commit=snapshot.implementation_commit,
        implementation_commit_at_lock_creation=lock.implementation_commit_at_lock_creation,
        protocol_commit=lock.protocol_commit,
        environment_lock_sha256=lock.lock_file_sha256,
        environment_manifest_sha256=lock.manifest_sha256,
        environment_artifact_manifest_sha256=lock.artifact_manifest_sha256,
        reference_execution_mode=lock.reference_execution_mode,
        dependencies=tuple(observations),
        failure_reasons=tuple(failures),
    )


def _gate_failure_report(reason: EnvironmentFailureReason) -> EnvironmentReport:
    return EnvironmentReport(
        status=EnvironmentStatus.NONCONFORMANT,
        executable=sys.executable,
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        python_requirement=None,
        prefix=sys.prefix,
        base_prefix=sys.base_prefix,
        platform=platform.platform(),
        machine=platform.machine(),
        implementation_commit=None,
        implementation_commit_at_lock_creation=None,
        protocol_commit=None,
        environment_lock_sha256=None,
        environment_manifest_sha256=None,
        environment_artifact_manifest_sha256=None,
        reference_execution_mode=None,
        dependencies=(),
        failure_reasons=(reason,),
    )


def _capture_current_environment_after_prerequisites(root: Path) -> EnvironmentReport:
    try:
        lock = _read_environment_lock_after_prerequisites(root)
        snapshot = _current_environment_snapshot(root, lock)
    except EnvironmentLockIntegrityError as exc:
        return _gate_failure_report(exc.reason)
    except Exception:
        return _gate_failure_report(
            EnvironmentFailureReason.ENVIRONMENT_METADATA_UNRESOLVED
        )
    return _evaluate_environment_snapshot(root, lock, snapshot)


def capture_current_environment(repo_root: str | Path | None = None) -> EnvironmentReport:
    """Observe the current process under the executing module's physical root.

    ``repo_root`` is an optional trusted-root consistency assertion.  It never
    selects the protocol, manifest, lock, artifact, Git, or virtualenv root.
    """

    root = resolve_production_repository_root(repo_root)
    identity = verify_protocol_identity(root)
    if identity.status is not ProtocolIdentityStatus.PASS:
        return _gate_failure_report(EnvironmentFailureReason.PROTOCOL_IDENTITY_MISMATCH)
    constants = verify_implementation_constants_against_frozen_v1(
        protocol_result=identity
    )
    if constants.status is not MirrorConformanceStatus.PASS:
        return _gate_failure_report(
            EnvironmentFailureReason.IMPLEMENTATION_CONSTANTS_MISMATCH
        )
    return _capture_current_environment_after_prerequisites(root)


def enforce_environment_or_abort(
    repo_root: str | Path | None = None,
) -> EnvironmentReport:
    """Authorize the current process; ``repo_root`` cannot select authority."""

    result = capture_current_environment(repo_root)
    if result.status is not EnvironmentStatus.CONFORMANT:
        failures = [reason.value for reason in result.failure_reasons]
        raise EnvironmentNotConformantError(
            f"ENVIRONMENT_NOT_CONFORMANT: {','.join(dict.fromkeys(failures))}"
        )
    return result
