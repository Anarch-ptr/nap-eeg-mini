"""Application-layer Phase II-B acquisition transaction.

This module owns orchestration and identity decisions. Network implementations
remain injected at the boundary; importing this module cannot perform I/O.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from .acquisition import (
    COMPLETE_CACHE_MARKER,
    MANAGED_CACHE_MARKER,
    AcquisitionError,
    atomic_download,
    initialize_managed_cache,
    safe_extract_archive,
    validate_cache_root,
)
from .network_policy import (
    AcquisitionAuthorization,
    DownloadTransport,
    NetworkPolicy,
    NetworkPolicyError,
)
from .raw_identity import (
    RawIdentityResult,
    RawIdentityState,
    evaluate_raw_identity_gate,
)
from .raw_manifest import (
    DATASET_NAME,
    MANIFEST_SCHEMA_VERSION,
    ArchiveRecord,
    ExtractedManifest,
    ManifestError,
    RawFileRecord,
    canonical_json_bytes,
    normalize_relative_path,
    read_manifest,
    sha256_file,
    write_manifest_atomic,
)


COMPLETE_SCHEMA = "NAP_EEG_MINI_PHASE_II_B_COMPLETE_V1"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class AcquisitionState(str, Enum):
    ABSENT = "ABSENT"
    CACHE_VALIDATED = "CACHE_VALIDATED"
    DOWNLOADING = "DOWNLOADING"
    ARCHIVE_VERIFIED = "ARCHIVE_VERIFIED"
    ARCHIVE_PUBLISHED = "ARCHIVE_PUBLISHED"
    EXTRACTING_TO_STAGING = "EXTRACTING_TO_STAGING"
    EXTRACTED_VERIFIED = "EXTRACTED_VERIFIED"
    MANIFEST_STAGED = "MANIFEST_STAGED"
    INVENTORY_VERIFIED = "INVENTORY_VERIFIED"
    GATE_PASSED = "GATE_PASSED"
    COMPLETE = "COMPLETE"
    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"


class WorkflowFailureReason(str, Enum):
    SOURCE_IDENTITY_INVALID = "SOURCE_IDENTITY_INVALID"
    INVENTORY_EXPECTATION_INVALID = "INVENTORY_EXPECTATION_INVALID"
    CONCURRENT_ACQUISITION_REFUSED = "CONCURRENT_ACQUISITION_REFUSED"
    INCOMPLETE_CACHE_REQUIRES_OPERATOR = "INCOMPLETE_CACHE_REQUIRES_OPERATOR"
    COMPLETE_MARKER_INVALID = "COMPLETE_MARKER_INVALID"
    EXPECTED_RAW_FILE_MISSING = "EXPECTED_RAW_FILE_MISSING"
    UNEXPECTED_RAW_FILE = "UNEXPECTED_RAW_FILE"
    RAW_FILE_IDENTITY_MISMATCH = "RAW_FILE_IDENTITY_MISMATCH"
    RAW_IDENTITY_GATE_FAILED = "RAW_IDENTITY_GATE_FAILED"
    COMPLETION_PUBLICATION_FAILED = "COMPLETION_PUBLICATION_FAILED"
    ACQUISITION_PRIMITIVE_FAILED = "ACQUISITION_PRIMITIVE_FAILED"
    MANIFEST_FAILED = "MANIFEST_FAILED"
    NETWORK_POLICY_FAILED = "NETWORK_POLICY_FAILED"
    WORKFLOW_IO_FAILED = "WORKFLOW_IO_FAILED"


class AcquisitionWorkflowError(RuntimeError):
    def __init__(
        self,
        reason: WorkflowFailureReason,
        *,
        state: AcquisitionState,
        transitions: tuple[AcquisitionState, ...],
        detail: str | None = None,
    ):
        self.reason = reason
        self.state = state
        self.transitions = transitions
        self.detail = detail
        suffix = f":{detail}" if detail else ""
        super().__init__(reason.value + suffix)


@dataclass(frozen=True)
class SourceIdentity:
    source_url: str
    archive_filename: str
    expected_size: int
    expected_sha256: str
    dataset_name: str = DATASET_NAME
    implementation_identifier: str | None = None

    def validate(self) -> None:
        parsed = urlsplit(self.source_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or any(ord(character) < 32 for character in self.source_url)
            or self.dataset_name != DATASET_NAME
            or Path(self.archive_filename).name != self.archive_filename
            or not self.archive_filename
            or any(ord(character) < 32 for character in self.archive_filename)
            or self.expected_size <= 0
            or _SHA256.fullmatch(self.expected_sha256.lower()) is None
        ):
            raise ValueError(WorkflowFailureReason.SOURCE_IDENTITY_INVALID.value)


@dataclass(frozen=True)
class ExpectedRawFile:
    relative_path: str
    byte_size: int
    sha256: str
    subject_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    role: str | None = None
    label_status: str | None = None
    acquisition_status: str | None = None

    def validate(self) -> None:
        try:
            path_is_canonical = (
                normalize_relative_path(self.relative_path) == self.relative_path
            )
        except ManifestError:
            path_is_canonical = False
        if (
            not path_is_canonical
            or self.byte_size < 0
            or _SHA256.fullmatch(self.sha256.lower()) is None
        ):
            raise ValueError(WorkflowFailureReason.INVENTORY_EXPECTATION_INVALID.value)


@dataclass(frozen=True)
class InventoryExpectation:
    files: tuple[ExpectedRawFile, ...]
    expected_subject_count: int

    def validate(self) -> None:
        if not self.files or self.expected_subject_count <= 0:
            raise ValueError(WorkflowFailureReason.INVENTORY_EXPECTATION_INVALID.value)
        seen: set[str] = set()
        for item in self.files:
            item.validate()
            key = item.relative_path.casefold()
            if key in seen:
                raise ValueError(
                    WorkflowFailureReason.INVENTORY_EXPECTATION_INVALID.value
                )
            seen.add(key)


@dataclass(frozen=True)
class ExtractionPolicy:
    max_total_size: int = 10 * 1024 * 1024 * 1024
    max_expansion_ratio: float = 200.0
    max_file_count: int = 100_000
    max_single_file_size: int = 2 * 1024 * 1024 * 1024

    def validate(self) -> None:
        if (
            self.max_total_size <= 0
            or self.max_expansion_ratio <= 0
            or self.max_file_count <= 0
            or self.max_single_file_size <= 0
        ):
            raise ValueError(WorkflowFailureReason.INVENTORY_EXPECTATION_INVALID.value)


@dataclass(frozen=True)
class AcquisitionRequest:
    cache_root: Path
    repository_root: Path
    source: SourceIdentity
    inventory: InventoryExpectation
    authorization: AcquisitionAuthorization = AcquisitionAuthorization()
    extraction: ExtractionPolicy = ExtractionPolicy()
    allow_temporary: bool = False


@dataclass(frozen=True)
class AcquisitionDependencies:
    transport: DownloadTransport | None
    clock: Callable[[], datetime]
    event_sink: Callable[[AcquisitionState], None] | None = None


@dataclass(frozen=True)
class AcquisitionResult:
    state: AcquisitionState
    transitions: tuple[AcquisitionState, ...]
    cache_root: Path
    archive_sha256: str
    manifest_sha256: str
    gate_result: RawIdentityResult
    transport_used: bool


def _publish_json_atomic(path: Path, payload: object) -> None:
    staging = path.with_name(path.name + ".staging")
    if path.exists() or staging.exists():
        raise OSError("completion target or staging target already exists")
    created = False
    try:
        with staging.open("xb") as stream:
            created = True
            stream.write(canonical_json_bytes(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(staging, path)
        staging.unlink()
        created = False
    finally:
        if created:
            try:
                staging.unlink()
            except FileNotFoundError:
                pass


def _completion_payload(
    request: AcquisitionRequest, manifest: ExtractedManifest
) -> dict[str, object]:
    inventory_bytes = canonical_json_bytes(
        [
            asdict(item)
            for item in sorted(
                request.inventory.files, key=lambda item: item.relative_path.casefold()
            )
        ]
    )
    return {
        "archive_filename": request.source.archive_filename,
        "archive_sha256": request.source.expected_sha256.lower(),
        "dataset_name": request.source.dataset_name,
        "expected_file_count": len(request.inventory.files),
        "expected_subject_count": request.inventory.expected_subject_count,
        "gate_state": RawIdentityState.PASS.value,
        "inventory_expectation_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
        "manifest_payload_sha256": manifest.manifest_payload_sha256,
        "schema": COMPLETE_SCHEMA,
    }


def _read_completion(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("completion marker is unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError("completion marker is not an object")
    return value


def _gate(request: AcquisitionRequest) -> RawIdentityResult:
    return evaluate_raw_identity_gate(
        request.cache_root,
        repository_root=request.repository_root,
        expected_file_count=len(request.inventory.files),
        expected_subject_count=request.inventory.expected_subject_count,
        allow_temporary=request.allow_temporary,
    )


def _verify_complete(
    request: AcquisitionRequest,
    transitions: list[AcquisitionState],
) -> AcquisitionResult:
    manifest_path = request.cache_root / "manifests" / "raw_manifest.json"
    manifest = read_manifest(manifest_path)
    expected_records = {
        item.relative_path: asdict(item) for item in request.inventory.files
    }
    observed_records = {record.relative_path: record for record in manifest.files}
    inventory_matches = set(expected_records) == set(observed_records) and all(
        all(
            getattr(observed_records[path], field) == value
            for field, value in fields.items()
        )
        and observed_records[path].source_archive_sha256
        == request.source.expected_sha256.lower()
        for path, fields in expected_records.items()
    )
    archive_record_matches = (
        manifest.dataset_name == request.source.dataset_name
        and manifest.source_archive.dataset_name == request.source.dataset_name
        and manifest.source_archive.source_url == request.source.source_url
        and manifest.source_archive.archive_filename == request.source.archive_filename
        and manifest.source_archive.downloaded_byte_count
        == request.source.expected_size
        and manifest.source_archive.sha256 == request.source.expected_sha256.lower()
        and manifest.source_archive.implementation_identifier
        == request.source.implementation_identifier
    )
    if not inventory_matches or not archive_record_matches:
        raise ValueError(WorkflowFailureReason.COMPLETE_MARKER_INVALID.value)
    expected_marker = _completion_payload(request, manifest)
    if _read_completion(request.cache_root / COMPLETE_CACHE_MARKER) != expected_marker:
        raise ValueError(WorkflowFailureReason.COMPLETE_MARKER_INVALID.value)
    archive = request.cache_root / "archives" / request.source.archive_filename
    if (
        not archive.is_file()
        or archive.is_symlink()
        or archive.stat().st_size != request.source.expected_size
        or sha256_file(archive) != request.source.expected_sha256.lower()
    ):
        raise ValueError(WorkflowFailureReason.COMPLETE_MARKER_INVALID.value)
    gate = _gate(request)
    if gate.state is not RawIdentityState.PASS:
        raise ValueError(WorkflowFailureReason.COMPLETE_MARKER_INVALID.value)
    transitions.append(AcquisitionState.VERIFIED_COMPLETE)
    return AcquisitionResult(
        state=AcquisitionState.VERIFIED_COMPLETE,
        transitions=tuple(transitions),
        cache_root=request.cache_root,
        archive_sha256=request.source.expected_sha256.lower(),
        manifest_sha256=manifest.manifest_payload_sha256 or "",
        gate_result=gate,
        transport_used=False,
    )


def run_acquisition(
    request: AcquisitionRequest, dependencies: AcquisitionDependencies
) -> AcquisitionResult:
    """Execute or verify one fail-closed acquisition transaction."""
    transitions = [AcquisitionState.ABSENT]
    state = AcquisitionState.ABSENT

    def advance(next_state: AcquisitionState) -> None:
        nonlocal state
        state = next_state
        transitions.append(next_state)
        if dependencies.event_sink is not None:
            dependencies.event_sink(next_state)

    lock_path = request.cache_root.with_name(
        request.cache_root.name + ".phase_ii_b.lock"
    )
    lock_owned = False
    try:
        request.source.validate()
        request.inventory.validate()
        request.extraction.validate()
        policy = NetworkPolicy(authorization=request.authorization)
        policy.authorize_network()
        validate_cache_root(
            request.cache_root,
            repository_root=request.repository_root,
            require_managed=False,
            allow_temporary=request.allow_temporary,
        )
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with lock_path.open("x", encoding="utf-8", newline="\n") as lock:
                lock.write("NAP_EEG_MINI_PHASE_II_B_EXCLUSIVE_LOCK\n")
                lock.flush()
                os.fsync(lock.fileno())
            lock_owned = True
        except FileExistsError as exc:
            raise AcquisitionWorkflowError(
                WorkflowFailureReason.CONCURRENT_ACQUISITION_REFUSED,
                state=state,
                transitions=tuple(transitions),
            ) from exc

        marker = request.cache_root / COMPLETE_CACHE_MARKER
        if request.cache_root.exists():
            validate_cache_root(
                request.cache_root,
                repository_root=request.repository_root,
                require_managed=True,
                allow_temporary=request.allow_temporary,
            )
            advance(AcquisitionState.CACHE_VALIDATED)
            if marker.is_file() and not marker.is_symlink():
                return _verify_complete(request, transitions)
            names = {path.name for path in request.cache_root.iterdir()}
            if names != {MANAGED_CACHE_MARKER}:
                raise AcquisitionWorkflowError(
                    WorkflowFailureReason.INCOMPLETE_CACHE_REQUIRES_OPERATOR,
                    state=state,
                    transitions=tuple(transitions),
                )
        else:
            initialize_managed_cache(
                request.cache_root,
                repository_root=request.repository_root,
                allow_temporary=request.allow_temporary,
            )
            advance(AcquisitionState.CACHE_VALIDATED)

        transport = policy.authorize_transport(dependencies.transport)
        advance(AcquisitionState.DOWNLOADING)
        receipt = atomic_download(
            source_url=request.source.source_url,
            target=request.cache_root / "archives" / request.source.archive_filename,
            policy=policy,
            transport=transport,
            expected_length=request.source.expected_size,
            expected_sha256=request.source.expected_sha256,
        )
        advance(AcquisitionState.ARCHIVE_VERIFIED)
        advance(AcquisitionState.ARCHIVE_PUBLISHED)
        advance(AcquisitionState.EXTRACTING_TO_STAGING)
        records: list[RawFileRecord] = []

        def verify_staged_raw(stage: Path, staged_files: tuple[Path, ...]) -> None:
            actual = {path.relative_to(stage).as_posix(): path for path in staged_files}
            expected = {item.relative_path: item for item in request.inventory.files}
            missing = sorted(set(expected) - set(actual))
            unexpected = sorted(set(actual) - set(expected))
            if missing:
                raise AcquisitionWorkflowError(
                    WorkflowFailureReason.EXPECTED_RAW_FILE_MISSING,
                    state=state,
                    transitions=tuple(transitions),
                    detail=missing[0],
                )
            if unexpected:
                raise AcquisitionWorkflowError(
                    WorkflowFailureReason.UNEXPECTED_RAW_FILE,
                    state=state,
                    transitions=tuple(transitions),
                    detail=unexpected[0],
                )
            for relative_path in sorted(expected, key=str.casefold):
                specification = expected[relative_path]
                path = actual[relative_path]
                if (
                    path.stat().st_size != specification.byte_size
                    or sha256_file(path) != specification.sha256.lower()
                ):
                    raise AcquisitionWorkflowError(
                        WorkflowFailureReason.RAW_FILE_IDENTITY_MISMATCH,
                        state=state,
                        transitions=tuple(transitions),
                        detail=relative_path,
                    )
                records.append(
                    RawFileRecord(
                        **asdict(specification),
                        source_archive_sha256=receipt.sha256,
                    )
                )
            advance(AcquisitionState.EXTRACTED_VERIFIED)

        safe_extract_archive(
            receipt.target,
            request.cache_root / "raw",
            max_total_size=request.extraction.max_total_size,
            max_expansion_ratio=request.extraction.max_expansion_ratio,
            max_file_count=request.extraction.max_file_count,
            max_single_file_size=request.extraction.max_single_file_size,
            expected_archive_sha256=request.source.expected_sha256,
            pre_publish_validator=verify_staged_raw,
        )
        timestamp = dependencies.clock().isoformat().replace("+00:00", "Z")
        manifest = ExtractedManifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            dataset_name=request.source.dataset_name,
            source_archive=ArchiveRecord(
                schema_version=MANIFEST_SCHEMA_VERSION,
                dataset_name=request.source.dataset_name,
                implementation_identifier=request.source.implementation_identifier,
                source_url=receipt.source_url,
                retrieval_timestamp=timestamp,
                http_status=receipt.http_status,
                content_length=receipt.content_length,
                etag=receipt.etag,
                last_modified=receipt.last_modified,
                redirect_chain=receipt.redirect_chain,
                archive_filename=request.source.archive_filename,
                downloaded_byte_count=receipt.downloaded_byte_count,
                sha256=receipt.sha256,
                transport_identifier=receipt.transport_identifier,
            ),
            generated_timestamp=timestamp,
            files=tuple(records),
        )
        advance(AcquisitionState.MANIFEST_STAGED)
        frozen = write_manifest_atomic(
            request.cache_root / "manifests" / "raw_manifest.json", manifest
        )
        advance(AcquisitionState.INVENTORY_VERIFIED)
        gate = _gate(request)
        if gate.state is not RawIdentityState.PASS:
            raise AcquisitionWorkflowError(
                WorkflowFailureReason.RAW_IDENTITY_GATE_FAILED,
                state=state,
                transitions=tuple(transitions),
                detail=gate.state.value,
            )
        advance(AcquisitionState.GATE_PASSED)
        try:
            _publish_json_atomic(marker, _completion_payload(request, frozen))
        except OSError as exc:
            raise AcquisitionWorkflowError(
                WorkflowFailureReason.COMPLETION_PUBLICATION_FAILED,
                state=state,
                transitions=tuple(transitions),
                detail=type(exc).__name__,
            ) from exc
        advance(AcquisitionState.COMPLETE)
        return AcquisitionResult(
            state=state,
            transitions=tuple(transitions),
            cache_root=request.cache_root,
            archive_sha256=receipt.sha256,
            manifest_sha256=frozen.manifest_payload_sha256 or "",
            gate_result=gate,
            transport_used=True,
        )
    except AcquisitionWorkflowError:
        raise
    except NetworkPolicyError as exc:
        raise AcquisitionWorkflowError(
            WorkflowFailureReason.NETWORK_POLICY_FAILED,
            state=state,
            transitions=tuple(transitions),
            detail=exc.reason.value,
        ) from exc
    except AcquisitionError as exc:
        raise AcquisitionWorkflowError(
            WorkflowFailureReason.ACQUISITION_PRIMITIVE_FAILED,
            state=state,
            transitions=tuple(transitions),
            detail=exc.reason.value,
        ) from exc
    except ManifestError as exc:
        raise AcquisitionWorkflowError(
            WorkflowFailureReason.MANIFEST_FAILED,
            state=state,
            transitions=tuple(transitions),
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        detail = str(exc)
        reason = (
            WorkflowFailureReason.COMPLETE_MARKER_INVALID
            if detail == WorkflowFailureReason.COMPLETE_MARKER_INVALID.value
            else (
                WorkflowFailureReason.SOURCE_IDENTITY_INVALID
                if detail == WorkflowFailureReason.SOURCE_IDENTITY_INVALID.value
                else WorkflowFailureReason.INVENTORY_EXPECTATION_INVALID
            )
        )
        raise AcquisitionWorkflowError(
            reason,
            state=state,
            transitions=tuple(transitions),
            detail=detail,
        ) from exc
    except OSError as exc:
        raise AcquisitionWorkflowError(
            WorkflowFailureReason.WORKFLOW_IO_FAILED,
            state=state,
            transitions=tuple(transitions),
            detail=type(exc).__name__,
        ) from exc
    finally:
        if lock_owned:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
