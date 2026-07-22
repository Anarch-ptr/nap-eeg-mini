"""Dependency capture and fail-closed Phase-I environment enforcement."""

from __future__ import annotations

import platform
from dataclasses import dataclass
from enum import Enum
from importlib import metadata
from pathlib import Path
from typing import Callable


SCIENTIFIC_DISTRIBUTIONS = (
    ("moabb", "moabb"),
    ("mne", "mne"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("torch", "torch"),
    ("scikit-learn", "scikit_learn"),
)


class EnvironmentStatus(str, Enum):
    CONFORMANT = "CONFORMANT"
    NONCONFORMANT = "NONCONFORMANT"
    UNRESOLVED = "UNRESOLVED"


class EnvironmentFailureReason(str, Enum):
    DEPENDENCY_VERSION_MISMATCH = "DEPENDENCY_VERSION_MISMATCH"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    DEPENDENCY_LOCK_MISSING = "DEPENDENCY_LOCK_MISSING"
    DEPENDENCY_REQUIREMENT_CONFLICT = "DEPENDENCY_REQUIREMENT_CONFLICT"
    ENVIRONMENT_METADATA_UNRESOLVED = "ENVIRONMENT_METADATA_UNRESOLVED"


@dataclass(frozen=True)
class DependencyObservation:
    distribution: str
    expected_repository_requirement: str | None
    observed_runtime_version: str | None
    lock_status: str
    failure_reason: EnvironmentFailureReason | None


@dataclass(frozen=True)
class EnvironmentReport:
    status: EnvironmentStatus
    python_version: str
    platform: str
    implementation_commit: str | None
    dependencies: tuple[DependencyObservation, ...]

    def observed_version(self, distribution: str) -> str | None:
        return next(
            item.observed_runtime_version
            for item in self.dependencies
            if item.distribution == distribution
        )


class EnvironmentNotConformantError(RuntimeError):
    pass


def read_exact_requirements(requirements_path: str | Path) -> dict[str, str]:
    """Return exact ``name==version`` declarations; reject conflicting pins."""

    requirements: dict[str, str] = {}
    for raw_line in Path(requirements_path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = (part.strip() for part in line.split("==", 1))
        key = name.lower()
        if key in requirements and requirements[key] != version:
            raise EnvironmentNotConformantError(
                f"DEPENDENCY_REQUIREMENT_CONFLICT: {name}"
            )
        requirements[key] = version
    return requirements


def capture_environment(
    repo_root: str | Path | None = None,
    *,
    version_lookup: Callable[[str], str] = metadata.version,
    implementation_commit: str | None = None,
) -> EnvironmentReport:
    root = Path(repo_root or Path(__file__).resolve().parents[2]).resolve()
    try:
        exact_requirements = read_exact_requirements(root / "requirements.txt")
    except (OSError, UnicodeError, EnvironmentNotConformantError):
        exact_requirements = {}
        requirement_conflict = True
    else:
        requirement_conflict = False

    if implementation_commit is None:
        try:
            from .protocol_identity import _text

            implementation_commit = _text(root, "rev-parse", "HEAD")
        except RuntimeError:
            implementation_commit = None

    observations: list[DependencyObservation] = []
    for distribution, _field_name in SCIENTIFIC_DISTRIBUTIONS:
        expected = exact_requirements.get(distribution)
        try:
            observed = version_lookup(distribution)
        except metadata.PackageNotFoundError:
            observed = None
        except Exception:
            observations.append(
                DependencyObservation(
                    distribution,
                    expected,
                    None,
                    "UNRESOLVED",
                    EnvironmentFailureReason.ENVIRONMENT_METADATA_UNRESOLVED,
                )
            )
            continue

        if requirement_conflict:
            reason = EnvironmentFailureReason.DEPENDENCY_REQUIREMENT_CONFLICT
        elif observed is None:
            reason = EnvironmentFailureReason.DEPENDENCY_MISSING
        elif expected is not None and observed != expected:
            reason = EnvironmentFailureReason.DEPENDENCY_VERSION_MISMATCH
        elif expected is None:
            reason = EnvironmentFailureReason.DEPENDENCY_LOCK_MISSING
        else:
            reason = None
        observations.append(
            DependencyObservation(
                distribution=distribution,
                expected_repository_requirement=(
                    f"{distribution}=={expected}" if expected is not None else None
                ),
                observed_runtime_version=observed,
                lock_status="EXACT_REPOSITORY_PIN" if expected is not None else "LOCK_REQUIRED_PHASE_II",
                failure_reason=reason,
            )
        )

    fatal = {
        EnvironmentFailureReason.DEPENDENCY_VERSION_MISMATCH,
        EnvironmentFailureReason.DEPENDENCY_MISSING,
        EnvironmentFailureReason.DEPENDENCY_REQUIREMENT_CONFLICT,
        EnvironmentFailureReason.ENVIRONMENT_METADATA_UNRESOLVED,
    }
    reasons = {item.failure_reason for item in observations}
    if reasons & fatal:
        status = EnvironmentStatus.NONCONFORMANT
    elif EnvironmentFailureReason.DEPENDENCY_LOCK_MISSING in reasons:
        status = EnvironmentStatus.UNRESOLVED
    else:
        status = EnvironmentStatus.CONFORMANT
    return EnvironmentReport(
        status=status,
        python_version=platform.python_version(),
        platform=platform.platform(),
        implementation_commit=implementation_commit,
        dependencies=tuple(observations),
    )


def enforce_environment_or_abort(
    report: EnvironmentReport | None = None,
) -> EnvironmentReport:
    """Reject mismatches, missing packages, and Phase-II lock gaps."""

    result = report or capture_environment()
    if result.status is not EnvironmentStatus.CONFORMANT:
        failures = ",".join(
            item.failure_reason.value
            for item in result.dependencies
            if item.failure_reason is not None
        )
        raise EnvironmentNotConformantError(
            f"ENVIRONMENT_NOT_CONFORMANT: {failures}"
        )
    return result
