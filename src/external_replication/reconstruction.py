"""Command-auditable Phase II-A environment reconstruction support.

This module reconstructs packages only.  It is not a scientific execution
entry point and contains no Lee2019_MI acquisition or EEG processing code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import struct
import sys
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from .environment import (
    ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH,
    ENVIRONMENT_LOCK_RELATIVE_PATH,
    ENVIRONMENT_MANIFEST_RELATIVE_PATH,
    EXPECTED_ENVIRONMENT_ARTIFACT_MANIFEST_SHA256,
    EXPECTED_ENVIRONMENT_LOCK_SHA256,
    EXPECTED_ENVIRONMENT_MANIFEST_SHA256,
    _read_environment_lock_after_prerequisites,
    resolve_production_repository_root,
)
from .protocol_identity import FROZEN_PROTOCOL_V1, parse_strict_json


RECONSTRUCTION_ROLE = "POST_FREEZE_ENVIRONMENT_RECONSTRUCTION_VERIFIER"
RECONSTRUCTION_RECORD_ROLE = "EVIDENCE_ONLY"
RECONSTRUCTION_SCHEMA = "EXTERNAL_BOUNDARY_REPLICATION_ENVIRONMENT_RECONSTRUCTION_V2"
BOOTSTRAP_METHOD = "PYTHON_VENV_ENSUREPIP"
HASH_ENFORCEMENT_AT_INSTALL = "PREVERIFIED_EXACT_ARTIFACT_PATHS"
EXPECTED_ARTIFACT_COUNT = 62
SUPPORTED_ARCHITECTURE_ALIASES = {
    "amd64": "AMD64",
    "x86_64": "AMD64",
}


class ReconstructionIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovedArtifact:
    normalized_name: str
    version: str
    filename: str
    byte_length: int
    sha256: str
    source_url: str


@dataclass(frozen=True)
class ArtifactVerification:
    filename: str
    normalized_name: str
    expected_sha256: str
    observed_sha256: str | None
    expected_bytes: int
    observed_bytes: int | None
    filename_match: bool
    sha_match: bool
    length_match: bool
    verification_status: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
            length += len(chunk)
    return digest.hexdigest(), length


def load_approved_artifacts() -> tuple[Path, tuple[ApprovedArtifact, ...]]:
    """Load only the static artifact authority beside this executing module."""

    root = resolve_production_repository_root()
    lock = _read_environment_lock_after_prerequisites(root)
    path = root / ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH
    document = parse_strict_json(path.read_bytes())
    if not isinstance(document, dict) or not isinstance(document.get("records"), list):
        raise ReconstructionIntegrityError("ARTIFACT_MANIFEST_STRUCTURE_INVALID")
    artifacts = tuple(
        ApprovedArtifact(
            normalized_name=record["normalized_name"],
            version=record["version"],
            filename=record["artifact_filename"],
            byte_length=record["artifact_byte_length"],
            sha256=record["artifact_sha256"],
            source_url=record["exact_source_url"],
        )
        for record in document["records"]
    )
    if (
        len(artifacts) != EXPECTED_ARTIFACT_COUNT
        or lock.artifact_record_count != EXPECTED_ARTIFACT_COUNT
        or len({item.normalized_name for item in artifacts}) != EXPECTED_ARTIFACT_COUNT
        or len({item.filename for item in artifacts}) != EXPECTED_ARTIFACT_COUNT
        or any(item.byte_length <= 0 for item in artifacts)
    ):
        raise ReconstructionIntegrityError("APPROVED_ARTIFACT_SET_INVALID")
    return root, artifacts


def _load_committed_platform_contract() -> dict[str, str]:
    root = resolve_production_repository_root()
    manifest_path = root / ENVIRONMENT_MANIFEST_RELATIVE_PATH
    manifest_bytes = manifest_path.read_bytes()
    if _sha256_bytes(manifest_bytes) != EXPECTED_ENVIRONMENT_MANIFEST_SHA256:
        raise ReconstructionIntegrityError("ENVIRONMENT_MANIFEST_SHA256_MISMATCH")
    document = parse_strict_json(manifest_bytes)
    if not isinstance(document, dict):
        raise ReconstructionIntegrityError("ENVIRONMENT_MANIFEST_STRUCTURE_INVALID")
    platform_contract = document.get("canonical_platform")
    if not isinstance(platform_contract, dict):
        raise ReconstructionIntegrityError("CANONICAL_PLATFORM_MISSING")
    required = {
        "abi_tag",
        "machine_architecture",
        "os",
        "platform_tag",
        "python_implementation",
        "python_tag",
        "python_version",
    }
    missing = sorted(required - set(platform_contract))
    if missing:
        raise ReconstructionIntegrityError(
            "CANONICAL_PLATFORM_FIELDS_MISSING: " + ",".join(missing)
        )
    return {key: str(platform_contract[key]) for key in required}


def _normalize_architecture(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_ARCHITECTURE_ALIASES:
        raise ReconstructionIntegrityError(
            f"REFERENCE_ARCHITECTURE_UNSUPPORTED: {value!r}"
        )
    return SUPPORTED_ARCHITECTURE_ALIASES[normalized]


def _platform_observations() -> dict[str, object]:
    return {
        "os_name": os.name,
        "sys_platform": sys.platform,
        "platform_system": platform.system(),
        "machine": platform.machine(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_cache_tag": sys.implementation.cache_tag,
        "pointer_bits": 8 * struct.calcsize("P"),
    }


def enforce_reference_platform_compatibility(
    artifacts: Sequence[ApprovedArtifact],
) -> dict[str, object]:
    """Reject non-reference runtimes and incompatible wheels before pip."""

    contract = _load_committed_platform_contract()
    observations = _platform_observations()
    expected_machine = _normalize_architecture(contract["machine_architecture"])
    expected = {
        "os_name": "nt",
        "sys_platform": "win32",
        "platform_system": contract["os"],
        "machine": expected_machine,
        "python_implementation": contract["python_implementation"],
        "python_version": contract["python_version"],
        "python_cache_tag": "cpython-" + contract["python_tag"].removeprefix("cp"),
        "pointer_bits": 64,
    }
    observed_machine = _normalize_architecture(str(observations["machine"]))
    observations = {**observations, "machine": observed_machine}
    mismatches = {
        key: {"expected": expected[key], "observed": value}
        for key, value in observations.items()
        if value != expected[key]
    }
    if mismatches:
        raise ReconstructionIntegrityError(
            "REFERENCE_PLATFORM_MISMATCH: "
            + json.dumps(mismatches, sort_keys=True)
        )

    from packaging.tags import sys_tags
    from packaging.utils import InvalidWheelFilename, parse_wheel_filename

    compatible_tags = frozenset(sys_tags())
    incompatible: list[str] = []
    torch_identity_seen = False
    for artifact in artifacts:
        if artifact.normalized_name == "torch":
            torch_identity_seen = (
                artifact.version == "2.12.1+cu130"
                and contract["python_tag"] in artifact.filename
                and contract["abi_tag"] in artifact.filename
                and contract["platform_tag"] in artifact.filename
            )
        try:
            _name, _version, _build, wheel_tags = parse_wheel_filename(
                artifact.filename
            )
        except InvalidWheelFilename as exc:
            raise ReconstructionIntegrityError(
                f"APPROVED_WHEEL_FILENAME_INVALID: {artifact.filename}"
            ) from exc
        if compatible_tags.isdisjoint(wheel_tags):
            incompatible.append(artifact.filename)
    if incompatible:
        raise ReconstructionIntegrityError(
            "APPROVED_WHEEL_TAG_INCOMPATIBLE: " + ",".join(incompatible)
        )
    if len(artifacts) == EXPECTED_ARTIFACT_COUNT and not torch_identity_seen:
        raise ReconstructionIntegrityError("TORCH_WHEEL_IDENTITY_MISMATCH")
    return {
        **observations,
        "manifest_sha256": EXPECTED_ENVIRONMENT_MANIFEST_SHA256,
        "python_tag": contract["python_tag"],
        "abi_tag": contract["abi_tag"],
        "platform_tag": contract["platform_tag"],
        "compatible_wheel_count": len(artifacts),
        "compatibility_status": "PASS_FROZEN_WINDOWS_AMD64_CP312",
    }


def download_approved_artifacts(
    wheelhouse: Path,
    artifacts: Sequence[ApprovedArtifact],
) -> None:
    """Acquire only exact reviewed URLs into an initially clean work directory."""

    wheelhouse = wheelhouse.resolve()
    wheelhouse.mkdir(parents=True, exist_ok=True)
    approved_by_filename = {artifact.filename: artifact for artifact in artifacts}
    existing = tuple(path for path in wheelhouse.iterdir() if path.is_file())
    if any(path.name not in approved_by_filename for path in existing):
        raise ReconstructionIntegrityError("DOWNLOAD_DIRECTORY_HAS_UNAPPROVED_FILE")
    for index, artifact in enumerate(artifacts, start=1):
        destination = wheelhouse / artifact.filename
        if destination.exists():
            observed_sha, observed_bytes = _sha256_file(destination)
            if (
                observed_sha != artifact.sha256
                or observed_bytes != artifact.byte_length
            ):
                raise ReconstructionIntegrityError(
                    f"EXISTING_DOWNLOAD_ARTIFACT_INVALID: {artifact.filename}"
                )
            print(
                f"ACQUIRE {index}/{len(artifacts)} VERIFIED_EXISTING "
                f"{artifact.filename}",
                flush=True,
            )
            continue
        partial = destination.with_suffix(destination.suffix + ".part")
        print(f"ACQUIRE {index}/{len(artifacts)} {artifact.filename}", flush=True)
        request = urllib.request.Request(
            artifact.source_url,
            headers={"User-Agent": "pip/25.0.1 Phase-II-A-reconstruction"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as source, partial.open(
                "wb"
            ) as target:
                shutil.copyfileobj(source, target, length=8 * 1024 * 1024)
            partial.replace(destination)
        finally:
            if partial.exists():
                partial.unlink()


def verify_wheelhouse(
    wheelhouse: Path,
    artifacts: Sequence[ApprovedArtifact],
) -> tuple[tuple[dict[str, object], ...], tuple[ArtifactVerification, ...]]:
    """Inventory and verify every candidate before any installer is called."""

    wheelhouse = wheelhouse.resolve()
    candidates = tuple(sorted(path for path in wheelhouse.iterdir() if path.is_file()))
    approved_by_filename = {artifact.filename: artifact for artifact in artifacts}
    inventory: list[dict[str, object]] = []
    for candidate in candidates:
        observed_sha, observed_bytes = _sha256_file(candidate)
        approved = approved_by_filename.get(candidate.name)
        inventory.append(
            {
                "filename": candidate.name,
                "byte_length": observed_bytes,
                "sha256": observed_sha,
                "normalized_name": (
                    approved.normalized_name if approved is not None else None
                ),
                "approved": approved is not None,
            }
        )
    candidate_names = {path.name for path in candidates}
    expected_names = set(approved_by_filename)
    if candidate_names - expected_names:
        raise ReconstructionIntegrityError("UNAPPROVED_WHEELHOUSE_CANDIDATE")
    if expected_names - candidate_names:
        raise ReconstructionIntegrityError("APPROVED_WHEEL_MISSING")
    if len(candidates) != len(artifacts):
        raise ReconstructionIntegrityError("WHEELHOUSE_CANDIDATE_COUNT_MISMATCH")

    results: list[ArtifactVerification] = []
    for artifact in artifacts:
        path = wheelhouse / artifact.filename
        observed_sha, observed_bytes = _sha256_file(path)
        result = ArtifactVerification(
            filename=path.name,
            normalized_name=artifact.normalized_name,
            expected_sha256=artifact.sha256,
            observed_sha256=observed_sha,
            expected_bytes=artifact.byte_length,
            observed_bytes=observed_bytes,
            filename_match=path.name == artifact.filename,
            sha_match=observed_sha == artifact.sha256,
            length_match=observed_bytes == artifact.byte_length,
            verification_status=(
                "PASS"
                if observed_sha == artifact.sha256
                and observed_bytes == artifact.byte_length
                else "FAIL"
            ),
        )
        results.append(result)
    if any(result.verification_status != "PASS" for result in results):
        raise ReconstructionIntegrityError("APPROVED_ARTIFACT_VERIFICATION_FAILED")
    return tuple(inventory), tuple(results)


def build_install_argv(
    venv_python: Path,
    wheelhouse: Path,
    artifacts: Sequence[ApprovedArtifact],
) -> tuple[str, ...]:
    """Build a resolver-free install command over exact local wheel paths."""

    return (
        str(venv_python.resolve()),
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-cache-dir",
        "--no-deps",
        *(str((wheelhouse / artifact.filename).resolve()) for artifact in artifacts),
    )


def normalized_install_argv(
    artifacts: Sequence[ApprovedArtifact],
) -> tuple[str, ...]:
    return (
        "<TEMP_VENV_PYTHON>",
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-cache-dir",
        "--no-deps",
        *(
            f"<APPROVED_WHEELHOUSE>/{artifact.filename}"
            for artifact in artifacts
        ),
    )


def _command_evidence(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment_overrides: dict[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    started = _utc_now()
    overrides = dict(environment_overrides or {})
    command_environment = os.environ.copy()
    command_environment.update(overrides)
    completed = runner(
        list(argv),
        cwd=cwd,
        env=command_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    ended = _utc_now()
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    evidence = {
        "argv": list(argv),
        "cwd": str(cwd.resolve()),
        "environment_overrides": overrides,
        "return_code": completed.returncode,
        "stdout_sha256": _sha256_bytes(stdout.encode("utf-8")),
        "stderr_sha256": _sha256_bytes(stderr.encode("utf-8")),
        "start_timestamp_utc": started,
        "end_timestamp_utc": ended,
    }
    return completed, evidence


def install_preverified_artifacts(
    venv_python: Path,
    wheelhouse: Path,
    artifacts: Sequence[ApprovedArtifact],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[
    tuple[dict[str, object], ...],
    tuple[ArtifactVerification, ...],
    dict[str, object],
]:
    """Verify the complete candidate set before making exactly one pip call."""

    enforce_reference_platform_compatibility(artifacts)
    inventory, verifications = verify_wheelhouse(wheelhouse, artifacts)
    argv = build_install_argv(venv_python, wheelhouse, artifacts)
    completed, evidence = _command_evidence(
        argv, cwd=resolve_production_repository_root(), runner=runner
    )
    if completed.returncode != 0:
        raise ReconstructionIntegrityError(
            f"PIP_INSTALL_FAILED: return_code={completed.returncode}"
        )
    return inventory, verifications, evidence


def _python_identity(python: Path, cwd: Path) -> dict[str, object]:
    code = (
        "import json,platform,sys;"
        "print(json.dumps({'executable':sys.executable,"
        "'implementation':platform.python_implementation(),"
        "'version':platform.python_version(),"
        "'prefix':sys.prefix,'base_prefix':sys.base_prefix}))"
    )
    completed = subprocess.run(
        [str(python), "-c", code],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise ReconstructionIntegrityError("BOOTSTRAP_PYTHON_IDENTITY_FAILED")
    return json.loads(completed.stdout)


def _pip_identity(python: Path, cwd: Path) -> dict[str, object]:
    completed = subprocess.run(
        [str(python), "-m", "pip", "--version"],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise ReconstructionIntegrityError("BOOTSTRAP_PIP_IDENTITY_FAILED")
    parts = completed.stdout.strip().split()
    return {
        "python_executable": str(python.resolve()),
        "pip_executable": str(
            (python.parent / ("pip.exe" if os.name == "nt" else "pip")).resolve()
        ),
        "pip_version": parts[1],
        "pip_version_output": completed.stdout.strip(),
    }


def _required_test_commands(python: Path) -> dict[str, tuple[str, ...]]:
    base = (
        str(python.resolve()),
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
    )
    return {
        "frozen_protocol": (*base, "tests/test_verify_protocol_hash.py"),
        "phase_i": (
            *base,
            "tests/test_external_replication_protocol_identity.py",
            "tests/test_external_replication_constants.py",
            "tests/test_external_replication_rng.py",
            "tests/test_external_replication_execution_gates.py",
        ),
        "phase_ii_a": (
            *base,
            "tests/test_external_replication_protocol_identity.py",
            "tests/test_external_replication_constants.py",
            "tests/test_external_replication_environment.py",
            "tests/test_external_replication_rng.py",
            "tests/test_external_replication_execution_gates.py",
            "tests/test_external_replication_startup.py",
            "tests/test_external_replication_reconstruction.py",
        ),
        "full_repository": base,
    }


def _isolated_startup_argv(root: Path, python: Path) -> tuple[str, ...]:
    return (
        str(python.resolve()),
        "-I",
        "-E",
        "-B",
        "-S",
        str((root / "scripts" / "verify_external_replication_startup.py").resolve()),
    )


def run_clean_reconstruction(
    wheelhouse: Path,
    evidence_output: Path,
    *,
    bootstrap_python: Path | None = None,
) -> dict[str, object]:
    """Reconstruct the executing clone's fresh `.venv` and persist evidence."""

    root, artifacts = load_approved_artifacts()
    venv = root / ".venv"
    if venv.exists():
        raise ReconstructionIntegrityError(
            "TRUSTED_ROOT_VENV_ALREADY_EXISTS_REFUSING_TO_MODIFY"
        )
    bootstrap = Path(
        bootstrap_python or getattr(sys, "_base_executable", sys.executable)
    ).resolve()
    bootstrap_identity = {
        "executable": str(bootstrap),
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
    }
    if (
        bootstrap_identity["implementation"] != "CPython"
        or bootstrap_identity["version"] != "3.12.10"
    ):
        raise ReconstructionIntegrityError("BOOTSTRAP_PYTHON_IDENTITY_MISMATCH")

    platform_compatibility = enforce_reference_platform_compatibility(artifacts)
    bootstrap_argv = (str(bootstrap), "-m", "venv", str(venv.resolve()))
    bootstrap_completed, bootstrap_command = _command_evidence(
        bootstrap_argv, cwd=root
    )
    if bootstrap_completed.returncode:
        raise ReconstructionIntegrityError("VENV_BOOTSTRAP_FAILED")
    venv_python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    venv_python_identity = _python_identity(venv_python, root)
    initial_pip = _pip_identity(venv_python, root)

    inventory, verifications, install_command = install_preverified_artifacts(
        venv_python, wheelhouse, artifacts
    )
    post_install_pip = _pip_identity(venv_python, root)

    pip_check_completed, pip_check = _command_evidence(
        (str(venv_python.resolve()), "-m", "pip", "check"), cwd=root
    )
    if pip_check_completed.returncode:
        raise ReconstructionIntegrityError("PIP_CHECK_FAILED")

    git_safe_environment = {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "safe.directory",
        "GIT_CONFIG_VALUE_0": str(root.resolve()).replace("\\", "/"),
    }
    startup_completed, startup_command = _command_evidence(
        _isolated_startup_argv(root, venv_python),
        cwd=root,
        environment_overrides=git_safe_environment,
    )
    if startup_completed.returncode:
        raise ReconstructionIntegrityError(
            "PRODUCTION_STARTUP_FAILED: "
            + (startup_completed.stderr or "").strip()
        )
    startup_result = json.loads(startup_completed.stdout)
    if (
        startup_result.get("status") != "PASS_THROUGH_ENVIRONMENT_STAGE"
        or startup_result.get("raw_data_identity_gate") != "NOT_IMPLEMENTED_PHASE_II_B"
        or startup_result.get("scientific_execution_authorization") != "DENY"
    ):
        raise ReconstructionIntegrityError("PRODUCTION_STARTUP_RESULT_INVALID")

    test_results: dict[str, object] = {}
    for label, argv in _required_test_commands(venv_python).items():
        print(f"TEST {label}", flush=True)
        completed, command = _command_evidence(
            argv,
            cwd=root,
            environment_overrides=git_safe_environment,
        )
        command["summary_tail"] = "\n".join(
            (completed.stdout or "").strip().splitlines()[-2:]
        )
        test_results[label] = command
        if completed.returncode:
            raise ReconstructionIntegrityError(f"TEST_COMMAND_FAILED: {label}")

    record: dict[str, object] = {
        "schema_version": RECONSTRUCTION_SCHEMA,
        "role": RECONSTRUCTION_ROLE,
        "record_trust_role": RECONSTRUCTION_RECORD_ROLE,
        "protocol_identity": {
            "tag": FROZEN_PROTOCOL_V1.protocol_tag,
            "freeze_commit": FROZEN_PROTOCOL_V1.freeze_commit,
            "protocol_blob_sha256": FROZEN_PROTOCOL_V1.protocol_blob_sha256,
        },
        "environment_manifest": {
            "path": ENVIRONMENT_MANIFEST_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_ENVIRONMENT_MANIFEST_SHA256,
        },
        "lock": {
            "path": ENVIRONMENT_LOCK_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_ENVIRONMENT_LOCK_SHA256,
        },
        "artifact_manifest": {
            "path": ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_ENVIRONMENT_ARTIFACT_MANIFEST_SHA256,
        },
        "reconstruction_timestamp_utc": _utc_now(),
        "temporary_root_semantics": {
            "root": str(root),
            "description": "FRESH_LOCAL_CLONE_EXECUTING_ITS_OWN_SOURCE_MODULE",
            "canonical_repository_venv_modified": False,
        },
        "reference_platform_compatibility": platform_compatibility,
        "bootstrap": {
            "method": BOOTSTRAP_METHOD,
            "command": bootstrap_command,
            "bootstrap_python": bootstrap_identity,
            "venv_python": venv_python_identity,
            "initial_pip": initial_pip,
            "pip_before_package_installation": initial_pip,
            "post_install_pip": post_install_pip,
        },
        "wheelhouse": {
            "path": str(wheelhouse.resolve()),
            "approved_expected_artifacts": len(artifacts),
            "approved_present_artifacts": sum(
                bool(item["approved"]) for item in inventory
            ),
            "unapproved_candidate_files": sum(
                not bool(item["approved"]) for item in inventory
            ),
            "alternate_approved_candidates": 0,
            "inventory": list(inventory),
        },
        "preinstall_artifact_verification": {
            "verified_count": len(verifications),
            "failure_count": sum(
                item.verification_status != "PASS" for item in verifications
            ),
            "results": [asdict(item) for item in verifications],
        },
        "installation": {
            "command": install_command,
            "portable_argv": list(normalized_install_argv(artifacts)),
            "no_index": True,
            "no_cache_dir": True,
            "no_deps": True,
            "require_hashes": False,
            "hash_enforcement_at_install": HASH_ENFORCEMENT_AT_INSTALL,
            "network_fallback": "IMPOSSIBLE_BY_INSTALL_COMMAND",
            "cache_fallback": "DISABLED_BY_COMMAND",
            "dependency_resolution": "DISABLED_BY_COMMAND",
        },
        "post_install": {
            "pip_check": pip_check,
            "pip_check_status": "PASS_NO_BROKEN_REQUIREMENTS",
            "startup_command": startup_command,
            "startup_result": startup_result,
            "test_commands": test_results,
        },
        "scientific_execution": "NOT_STARTED",
        "raw_data_identity": "NOT_ACQUIRED",
        "lee_data_access": "NONE",
    }
    evidence_output.parent.mkdir(parents=True, exist_ok=True)
    evidence_output.write_text(
        json.dumps(record, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--bootstrap-python", type=Path)
    args = parser.parse_args(argv)

    _root, artifacts = load_approved_artifacts()
    enforce_reference_platform_compatibility(artifacts)
    if args.download:
        download_approved_artifacts(args.wheelhouse, artifacts)
    run_clean_reconstruction(
        args.wheelhouse,
        args.evidence_output,
        bootstrap_python=args.bootstrap_python,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
