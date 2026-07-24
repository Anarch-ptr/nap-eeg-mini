"""Fail-closed opaque-byte acquisition for an exact multi-object collection.

This module is deliberately separate from the archive workflow.  It has no
scientific-format dependencies and constructs no network transport.
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import urlsplit

from .acquisition import (
    AcquisitionError,
    atomic_download,
    initialize_managed_cache,
    validate_cache_root,
)
from .network_policy import (
    AcquisitionAuthorization,
    AuthorizationState,
    DownloadTransport,
    NetworkPolicy,
    NetworkPolicyError,
    TransportResponse,
)
from .raw_manifest import canonical_json_bytes, sha256_file


GIGADB_ORIGINAL_MAT_OBJECTS = "GIGADB_ORIGINAL_MAT_OBJECTS"
NEMAR_BIDS_DERIVATIVE = "NEMAR_BIDS_DERIVATIVE"
CANDIDATE_MANIFEST_NAME = "candidate_collection_manifest.json"
CANDIDATE_MARKER_NAME = ".phase_ii_b_collection_candidate.json"
COLLECTION_LOCK_NAME = ".phase_ii_b_collection.lock"
COLLECTION_MANIFEST_SCHEMA_VERSION = 1
COLLECTION_MANAGED_TOP_LEVEL = frozenset({
    ".phase_ii_b_managed.json",
    CANDIDATE_MARKER_NAME,
    COLLECTION_LOCK_NAME,
    "manifests",
    "objects",
})
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class CollectionState(str, Enum):
    ABSENT = "ABSENT"
    PLAN_VALIDATED = "PLAN_VALIDATED"
    CACHE_VALIDATED = "CACHE_VALIDATED"
    COLLECTION_LOCKED = "COLLECTION_LOCKED"
    OBJECT_STAGING = "OBJECT_STAGING"
    OBJECT_VERIFIED = "OBJECT_VERIFIED"
    OBJECT_PUBLISHED = "OBJECT_PUBLISHED"
    COLLECTION_OBJECTS_COMPLETE = "COLLECTION_OBJECTS_COMPLETE"
    CANDIDATE_MANIFEST_STAGED = "CANDIDATE_MANIFEST_STAGED"
    CANDIDATE_MANIFEST_VERIFIED = "CANDIDATE_MANIFEST_VERIFIED"
    CANDIDATE_COLLECTION_COMPLETE = "CANDIDATE_COLLECTION_COMPLETE"
    AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
    APPROVED_COLLECTION_VERIFIED = "APPROVED_COLLECTION_VERIFIED"


class CollectionGateState(str, Enum):
    NOT_ACQUIRED = "NOT_ACQUIRED"
    PARTIAL_COLLECTION = "PARTIAL_COLLECTION"
    OBJECT_MISSING = "OBJECT_MISSING"
    OBJECT_UNEXPECTED = "OBJECT_UNEXPECTED"
    OBJECT_SIZE_MISMATCH = "OBJECT_SIZE_MISMATCH"
    OBJECT_HASH_MISMATCH = "OBJECT_HASH_MISMATCH"
    PLAN_IDENTITY_MISMATCH = "PLAN_IDENTITY_MISMATCH"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    MANIFEST_IDENTITY_MISMATCH = "MANIFEST_IDENTITY_MISMATCH"
    OBJECT_COUNT_MISMATCH = "OBJECT_COUNT_MISMATCH"
    SUBJECT_COUNT_MISMATCH = "SUBJECT_COUNT_MISMATCH"
    SESSION_COUNT_MISMATCH = "SESSION_COUNT_MISMATCH"
    SOURCE_REPRESENTATION_MISMATCH = "SOURCE_REPRESENTATION_MISMATCH"
    SOURCE_URL_MISMATCH = "SOURCE_URL_MISMATCH"
    UNMANAGED_FILE = "UNMANAGED_FILE"
    ACTIVE_LOCK = "ACTIVE_LOCK"
    AMBIGUOUS_INCOMPLETE_STATE = "AMBIGUOUS_INCOMPLETE_STATE"
    UNAPPROVED_CANDIDATE = "UNAPPROVED_CANDIDATE"
    APPROVED_COLLECTION_PASS = "APPROVED_COLLECTION_PASS"
    SOURCE_IDENTITY_CHANGED = "SOURCE_IDENTITY_CHANGED"
    SOURCE_MIGRATION_CANDIDATE = "SOURCE_MIGRATION_CANDIDATE"


class CollectionFailureReason(str, Enum):
    PLAN_INVALID = "PLAN_INVALID"
    SOURCE_POLICY_VIOLATION = "SOURCE_POLICY_VIOLATION"
    RESOURCE_LIMIT_INVALID = "RESOURCE_LIMIT_INVALID"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    LOCK_REFUSED = "LOCK_REFUSED"
    INCOMPLETE_STATE = "INCOMPLETE_STATE"
    EXISTING_OBJECT_MISMATCH = "EXISTING_OBJECT_MISMATCH"
    TRANSPORT_FAILED = "TRANSPORT_FAILED"
    MANIFEST_PUBLICATION_FAILED = "MANIFEST_PUBLICATION_FAILED"
    MARKER_PUBLICATION_FAILED = "MARKER_PUBLICATION_FAILED"
    LOCK_CLEANUP_FAILED = "LOCK_CLEANUP_FAILED"
    APPROVAL_INVALID = "APPROVAL_INVALID"


class CollectionAcquisitionError(RuntimeError):
    def __init__(
        self,
        reason: CollectionFailureReason,
        *,
        state: CollectionState,
        detail: str | None = None,
    ):
        self.reason = reason
        self.state = state
        self.detail = detail
        super().__init__(reason.value + (f":{detail}" if detail else ""))


def _canonical_relative_path(value: str, maximum: int) -> str:
    if not value or len(value) > maximum or "\\" in value:
        raise ValueError("NON_CANONICAL_RELATIVE_PATH")
    drive, _ = ntpath.splitdrive(value)
    if drive or value.startswith(("/", "\\", "//", "\\\\")):
        raise ValueError("ABSOLUTE_OR_DRIVE_PATH")
    path = PurePosixPath(value)
    if path.as_posix() != value or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("PATH_TRAVERSAL_OR_AMBIGUITY")
    for part in path.parts:
        stem = part.split(".", 1)[0].upper()
        if (
            stem in _WINDOWS_RESERVED
            or part.endswith((" ", "."))
            or ":" in part
            or any(ord(character) < 32 for character in part)
            or any(character in '<>"|?*' for character in part)
        ):
            raise ValueError("WINDOWS_PATH_AMBIGUITY")
    return value


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def _validate_object_target(objects_root: Path, target: Path) -> None:
    if objects_root.exists() and (
        _is_link_or_junction(objects_root) or not objects_root.is_dir()
    ):
        raise ValueError("UNTRUSTED_OBJECT_ROOT")
    relative = target.relative_to(objects_root)
    current = objects_root
    for part in relative.parts[:-1]:
        current = current / part
        if current.exists() and (
            _is_link_or_junction(current) or not current.is_dir()
        ):
            raise ValueError("UNTRUSTED_OBJECT_ANCESTOR")
    if target.exists() and (
        _is_link_or_junction(target) or not target.is_file()
    ):
        raise ValueError("UNTRUSTED_OBJECT_TARGET")


@dataclass(frozen=True)
class CollectionObjectPlan:
    object_id: str
    relative_path: str
    source_url: str
    expected_size: int | None
    expected_sha256: str | None
    subject_id: str | None
    session_id: str | None
    source_role: str
    content_kind: str


@dataclass(frozen=True)
class MultiObjectResourceLimits:
    maximum_total_object_count: int
    maximum_bytes_per_object: int
    maximum_total_downloaded_bytes: int
    maximum_redirects_per_object: int
    maximum_url_length: int
    maximum_relative_path_length: int
    maximum_concurrent_object_transfers: int
    timeout_seconds: float
    maximum_retry_count: int

    def validate(self) -> None:
        if (
            self.maximum_total_object_count <= 0
            or self.maximum_bytes_per_object <= 0
            or self.maximum_total_downloaded_bytes <= 0
            or self.maximum_redirects_per_object < 0
            or self.maximum_url_length <= 0
            or self.maximum_relative_path_length <= 0
            or self.maximum_concurrent_object_transfers != 1
            or self.timeout_seconds <= 0
            or self.maximum_retry_count < 0
        ):
            raise ValueError(CollectionFailureReason.RESOURCE_LIMIT_INVALID.value)


@dataclass(frozen=True)
class MultiObjectAcquisitionRequest:
    dataset_id: str
    source_representation: str
    cache_root: Path
    repository_root: Path
    collection_objects: tuple[CollectionObjectPlan, ...]
    authorization: AcquisitionAuthorization
    scientific_execution_authorization: AuthorizationState
    expected_object_count: int
    expected_subject_count: int
    expected_session_count: int
    collection_schema_version: int
    resource_limits: MultiObjectResourceLimits
    approved_scheme: str
    approved_host: str
    approved_path_prefixes: tuple[str, ...]
    authorization_id: str
    baseline_commit: str
    allow_temporary: bool = False


@dataclass(frozen=True)
class MultiObjectDependencies:
    transport: DownloadTransport | None
    clock: Callable[[], datetime]
    event_sink: Callable[[CollectionState], None] | None = None


@dataclass(frozen=True)
class CandidateObjectRecord:
    object_id: str
    relative_path: str
    source_url: str
    final_url: str
    redirect_chain: tuple[str, ...]
    downloaded_bytes: int
    sha256: str
    subject_id: str | None
    session_id: str | None
    source_role: str
    content_kind: str
    transport_status: int | None
    transport_identifier: str | None
    etag: str | None
    last_modified: str | None
    retrieved_at: str | None
    candidate_approval_state: str = "UNAPPROVED_CANDIDATE"


@dataclass(frozen=True)
class CandidateCollectionManifest:
    schema_version: int
    dataset_id: str
    source_representation: str
    plan_sha256: str
    expected_object_count: int
    observed_object_count: int
    expected_subject_count: int
    observed_subject_count: int
    expected_session_count: int
    observed_session_count: int
    objects: tuple[CandidateObjectRecord, ...]
    generated_at: str
    baseline_commit: str
    authorization_id: str
    approval_state: str
    manifest_payload_sha256: str


@dataclass(frozen=True)
class ApprovedCollectionIdentity:
    dataset_id: str
    source_representation: str
    plan_sha256: str
    candidate_manifest_sha256: str
    object_identities: tuple[tuple[str, int, str], ...]
    approval_id: str
    approver: str
    approval_timestamp: str
    baseline_commit: str
    destination: str
    source_authenticity_evidence_reference: str
    license_review_reference: str


@dataclass(frozen=True)
class CollectionGateResult:
    state: CollectionGateState
    reason_codes: tuple[str, ...]
    plan_sha256: str
    candidate_manifest_sha256: str | None = None


@dataclass(frozen=True)
class MultiObjectAcquisitionResult:
    state: CollectionState
    transitions: tuple[CollectionState, ...]
    cache_root: Path
    plan_sha256: str
    candidate_manifest_sha256: str
    gate_result: CollectionGateResult
    transport_call_count: int
    source_representation: str
    baseline_commit: str
    approval_state: str = "UNAPPROVED_CANDIDATE"


def classify_source_change(
    *,
    approved_url: str,
    approved_size: int,
    approved_sha256: str,
    candidate_url: str,
    candidate_size: int,
    candidate_sha256: str,
) -> CollectionGateState:
    """Classify a candidate against an approved opaque-byte source identity."""
    if candidate_url == approved_url and (
        candidate_size != approved_size or candidate_sha256 != approved_sha256
    ):
        return CollectionGateState.SOURCE_IDENTITY_CHANGED
    if (
        candidate_url != approved_url
        and candidate_size == approved_size
        and candidate_sha256 == approved_sha256
    ):
        return CollectionGateState.SOURCE_MIGRATION_CANDIDATE
    if (
        candidate_url == approved_url
        and candidate_size == approved_size
        and candidate_sha256 == approved_sha256
    ):
        return CollectionGateState.APPROVED_COLLECTION_PASS
    return CollectionGateState.SOURCE_IDENTITY_CHANGED


def _object_payload(item: CollectionObjectPlan) -> dict[str, object]:
    return asdict(item)


def collection_plan_sha256(request: MultiObjectAcquisitionRequest) -> str:
    payload = {
        "collection_schema_version": request.collection_schema_version,
        "dataset_id": request.dataset_id,
        "source_representation": request.source_representation,
        "objects": [
            _object_payload(item)
            for item in sorted(
                request.collection_objects,
                key=lambda value: (value.relative_path.casefold(), value.relative_path),
            )
        ],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _validate_url(request: MultiObjectAcquisitionRequest, url: str) -> None:
    if len(url) > request.resource_limits.maximum_url_length:
        raise ValueError("URL_TOO_LONG")
    parsed = urlsplit(url)
    if (
        parsed.scheme != request.approved_scheme
        or parsed.hostname != request.approved_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or any(character in request.approved_host for character in "*?")
        or not any(parsed.path.startswith(prefix) for prefix in request.approved_path_prefixes)
    ):
        raise ValueError(CollectionFailureReason.SOURCE_POLICY_VIOLATION.value)


def validate_collection_plan(request: MultiObjectAcquisitionRequest) -> tuple[CollectionObjectPlan, ...]:
    request.resource_limits.validate()
    if (
        request.dataset_id != "Lee2019_MI"
        or request.source_representation != GIGADB_ORIGINAL_MAT_OBJECTS
        or request.scientific_execution_authorization is not AuthorizationState.DENY
        or request.authorization.scientific_execution is not AuthorizationState.DENY
        or request.collection_schema_version <= 0
        or request.expected_object_count != len(request.collection_objects)
        or request.expected_object_count > request.resource_limits.maximum_total_object_count
        or request.expected_object_count <= 0
        or request.expected_subject_count <= 0
        or request.expected_session_count <= 0
        or not request.authorization_id
        or _GIT_COMMIT.fullmatch(request.baseline_commit.lower()) is None
        or not request.approved_path_prefixes
    ):
        raise ValueError(CollectionFailureReason.PLAN_INVALID.value)
    ordered = tuple(sorted(
        request.collection_objects,
        key=lambda value: (value.relative_path.casefold(), value.relative_path),
    ))
    ids: set[str] = set()
    paths: set[str] = set()
    urls: set[str] = set()
    pairs: set[tuple[str | None, str | None]] = set()
    subjects: set[str] = set()
    sessions: set[str] = set()
    for item in ordered:
        path = _canonical_relative_path(
            item.relative_path,
            request.resource_limits.maximum_relative_path_length,
        )
        normalized_path = unicodedata.normalize("NFC", path).casefold()
        _validate_url(request, item.source_url)
        if (
            not item.object_id
            or item.object_id in ids
            or normalized_path in paths
            or item.source_url in urls
            or (item.subject_id, item.session_id) in pairs
            or not item.source_role
            or not item.content_kind
            or item.expected_size is not None and item.expected_size <= 0
            or item.expected_size is not None
            and item.expected_size > request.resource_limits.maximum_bytes_per_object
            or item.expected_sha256 is not None
            and _SHA256.fullmatch(item.expected_sha256.lower()) is None
        ):
            raise ValueError(CollectionFailureReason.PLAN_INVALID.value)
        ids.add(item.object_id)
        paths.add(normalized_path)
        urls.add(item.source_url)
        pairs.add((item.subject_id, item.session_id))
        if item.subject_id is not None:
            subjects.add(item.subject_id)
        if item.session_id is not None:
            sessions.add(item.session_id)
    if (
        len(subjects) != request.expected_subject_count
        or len(sessions) != request.expected_session_count
    ):
        raise ValueError(CollectionFailureReason.PLAN_INVALID.value)
    known_total = sum(item.expected_size or 0 for item in ordered)
    if known_total > request.resource_limits.maximum_total_downloaded_bytes:
        raise ValueError(CollectionFailureReason.RESOURCE_LIMIT_EXCEEDED.value)
    return ordered


def _publish_json_atomic(path: Path, payload: object) -> None:
    stage = path.with_name(path.name + ".staging")
    if path.exists() or stage.exists():
        raise FileExistsError(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    owned = False
    try:
        with stage.open("xb") as stream:
            owned = True
            stream.write(canonical_json_bytes(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(stage, path)
        stage.unlink()
        owned = False
    finally:
        if owned:
            try:
                stage.unlink()
            except FileNotFoundError:
                pass


def _manifest_payload(manifest: CandidateCollectionManifest) -> dict[str, object]:
    payload = asdict(manifest)
    payload.pop("manifest_payload_sha256")
    payload["objects"] = [asdict(item) for item in manifest.objects]
    return payload


def _manifest_with_identity(**kwargs: object) -> CandidateCollectionManifest:
    provisional = CandidateCollectionManifest(
        **kwargs, manifest_payload_sha256=""  # type: ignore[arg-type]
    )
    digest = hashlib.sha256(canonical_json_bytes(_manifest_payload(provisional))).hexdigest()
    return CandidateCollectionManifest(
        **kwargs, manifest_payload_sha256=digest  # type: ignore[arg-type]
    )


def _parse_manifest(path: Path) -> CandidateCollectionManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = tuple(CandidateObjectRecord(**item) for item in payload.pop("objects"))
    manifest = CandidateCollectionManifest(objects=records, **payload)
    observed = hashlib.sha256(
        canonical_json_bytes(_manifest_payload(manifest))
    ).hexdigest()
    if observed != manifest.manifest_payload_sha256:
        raise ValueError(CollectionGateState.MANIFEST_IDENTITY_MISMATCH.value)
    return manifest


def _allowed_cache_files(request: MultiObjectAcquisitionRequest) -> tuple[set[str], set[str]]:
    object_paths = {item.relative_path for item in request.collection_objects}
    top = {
        ".phase_ii_b_managed.json",
        CANDIDATE_MARKER_NAME,
        COLLECTION_LOCK_NAME,
        f"manifests/{CANDIDATE_MANIFEST_NAME}",
    }
    return object_paths, top


def evaluate_candidate_collection_gate(
    request: MultiObjectAcquisitionRequest,
    approved_identity: ApprovedCollectionIdentity | None = None,
) -> CollectionGateResult:
    try:
        ordered = validate_collection_plan(request)
        plan_sha = collection_plan_sha256(request)
    except ValueError as exc:
        return CollectionGateResult(
            CollectionGateState.PLAN_IDENTITY_MISMATCH, (str(exc),), ""
        )
    root = request.cache_root
    if not root.exists():
        return CollectionGateResult(CollectionGateState.NOT_ACQUIRED, (), plan_sha)
    try:
        validate_cache_root(
            root,
            repository_root=request.repository_root,
            allow_temporary=request.allow_temporary,
            allowed_top_level=COLLECTION_MANAGED_TOP_LEVEL,
        )
    except AcquisitionError as exc:
        return CollectionGateResult(
            CollectionGateState.UNMANAGED_FILE,
            (exc.reason.value,),
            plan_sha,
        )
    lock = root / COLLECTION_LOCK_NAME
    if lock.exists():
        return CollectionGateResult(CollectionGateState.ACTIVE_LOCK, (), plan_sha)
    objects_root = root / "objects"
    manifest_path = root / "manifests" / CANDIDATE_MANIFEST_NAME
    marker_path = root / CANDIDATE_MARKER_NAME
    if not objects_root.exists() and not manifest_path.exists() and not marker_path.exists():
        unexpected_top = {
            child.name for child in root.iterdir()
            if child.name != ".phase_ii_b_managed.json"
        }
        if unexpected_top:
            return CollectionGateResult(
                CollectionGateState.UNMANAGED_FILE,
                tuple(sorted(unexpected_top)),
                plan_sha,
            )
        return CollectionGateResult(CollectionGateState.NOT_ACQUIRED, (), plan_sha)
    unexpected_top = {
        child.name
        for child in root.iterdir()
        if child.name not in {
            ".phase_ii_b_managed.json",
            CANDIDATE_MARKER_NAME,
            "manifests",
            "objects",
        }
    }
    if unexpected_top:
        return CollectionGateResult(
            CollectionGateState.UNMANAGED_FILE,
            tuple(sorted(unexpected_top)),
            plan_sha,
        )
    if any(_is_link_or_junction(path) for path in root.rglob("*")):
        return CollectionGateResult(
            CollectionGateState.UNMANAGED_FILE, ("LINK_OR_JUNCTION",), plan_sha
        )
    if (root / "manifests").exists():
        unexpected_manifests = {
            path.name
            for path in (root / "manifests").iterdir()
            if path.name != CANDIDATE_MANIFEST_NAME
        }
        if unexpected_manifests:
            state = (
                CollectionGateState.AMBIGUOUS_INCOMPLETE_STATE
                if all(name.endswith(".staging") for name in unexpected_manifests)
                else CollectionGateState.UNMANAGED_FILE
            )
            return CollectionGateResult(
                state, tuple(sorted(unexpected_manifests)), plan_sha
            )
    expected_paths = {item.relative_path for item in ordered}
    actual_paths = {
        path.relative_to(objects_root).as_posix()
        for path in objects_root.rglob("*")
        if path.is_file()
    } if objects_root.exists() else set()
    if any(path.name.endswith((".partial", ".staging")) for path in root.rglob("*")):
        return CollectionGateResult(
            CollectionGateState.AMBIGUOUS_INCOMPLETE_STATE, (), plan_sha
        )
    if actual_paths - expected_paths:
        return CollectionGateResult(
            CollectionGateState.OBJECT_UNEXPECTED,
            tuple(sorted(actual_paths - expected_paths)),
            plan_sha,
        )
    if expected_paths - actual_paths:
        state = (
            CollectionGateState.OBJECT_MISSING
            if manifest_path.exists() or marker_path.exists()
            else CollectionGateState.PARTIAL_COLLECTION
        )
        return CollectionGateResult(state, tuple(sorted(expected_paths - actual_paths)), plan_sha)
    if not manifest_path.exists() or not marker_path.exists():
        return CollectionGateResult(
            CollectionGateState.PARTIAL_COLLECTION, (), plan_sha
        )
    try:
        manifest = _parse_manifest(manifest_path)
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, KeyError, ValueError):
        return CollectionGateResult(CollectionGateState.MANIFEST_INVALID, (), plan_sha)
    if manifest.plan_sha256 != plan_sha or marker.get("plan_sha256") != plan_sha:
        return CollectionGateResult(CollectionGateState.PLAN_IDENTITY_MISMATCH, (), plan_sha)
    if (
        manifest.dataset_id != request.dataset_id
        or marker.get("dataset_id") != request.dataset_id
        or manifest.baseline_commit != request.baseline_commit
        or marker.get("baseline_commit") != request.baseline_commit
        or manifest.authorization_id != request.authorization_id
        or manifest.approval_state != "UNAPPROVED_CANDIDATE"
        or marker.get("approval_state") != "UNAPPROVED_CANDIDATE"
    ):
        return CollectionGateResult(CollectionGateState.MANIFEST_INVALID, (), plan_sha)
    if (
        manifest.source_representation != request.source_representation
        or marker.get("source_representation") != request.source_representation
    ):
        return CollectionGateResult(
            CollectionGateState.SOURCE_REPRESENTATION_MISMATCH, (), plan_sha
        )
    if (
        len(manifest.objects) != request.expected_object_count
        or manifest.expected_object_count != request.expected_object_count
        or manifest.observed_object_count != request.expected_object_count
    ):
        return CollectionGateResult(CollectionGateState.OBJECT_COUNT_MISMATCH, (), plan_sha)
    actual_subjects = {item.subject_id for item in manifest.objects}
    if (
        manifest.expected_subject_count != request.expected_subject_count
        or manifest.observed_subject_count != request.expected_subject_count
        or len(actual_subjects) != request.expected_subject_count
    ):
        return CollectionGateResult(CollectionGateState.SUBJECT_COUNT_MISMATCH, (), plan_sha)
    actual_sessions = {item.session_id for item in manifest.objects}
    if (
        manifest.expected_session_count != request.expected_session_count
        or manifest.observed_session_count != request.expected_session_count
        or len(actual_sessions) != request.expected_session_count
    ):
        return CollectionGateResult(CollectionGateState.SESSION_COUNT_MISMATCH, (), plan_sha)
    record_by_id = {item.object_id: item for item in manifest.objects}
    if len(record_by_id) != len(manifest.objects):
        return CollectionGateResult(CollectionGateState.MANIFEST_INVALID, (), plan_sha)
    for planned in ordered:
        record = record_by_id.get(planned.object_id)
        if record is None:
            return CollectionGateResult(CollectionGateState.OBJECT_MISSING, (planned.object_id,), plan_sha)
        if (
            record.relative_path != planned.relative_path
            or record.source_url != planned.source_url
            or record.subject_id != planned.subject_id
            or record.session_id != planned.session_id
            or record.source_role != planned.source_role
            or record.content_kind != planned.content_kind
            or record.candidate_approval_state != "UNAPPROVED_CANDIDATE"
        ):
            return CollectionGateResult(CollectionGateState.SOURCE_URL_MISMATCH, (planned.object_id,), plan_sha)
        try:
            _validate_url(request, record.final_url)
            if len(record.redirect_chain) > request.resource_limits.maximum_redirects_per_object:
                raise ValueError("REDIRECT_LIMIT")
            for redirect_url in record.redirect_chain:
                _validate_url(request, redirect_url)
        except ValueError:
            return CollectionGateResult(
                CollectionGateState.SOURCE_URL_MISMATCH,
                (planned.object_id,),
                plan_sha,
            )
        target = objects_root / planned.relative_path
        size = target.stat().st_size
        digest = sha256_file(target)
        if size != record.downloaded_bytes:
            return CollectionGateResult(CollectionGateState.OBJECT_SIZE_MISMATCH, (planned.object_id,), plan_sha)
        if digest != record.sha256:
            return CollectionGateResult(CollectionGateState.OBJECT_HASH_MISMATCH, (planned.object_id,), plan_sha)
        if planned.expected_size is not None and size != planned.expected_size:
            return CollectionGateResult(CollectionGateState.OBJECT_SIZE_MISMATCH, (planned.object_id,), plan_sha)
        if planned.expected_sha256 is not None and digest != planned.expected_sha256:
            return CollectionGateResult(CollectionGateState.OBJECT_HASH_MISMATCH, (planned.object_id,), plan_sha)
    manifest_sha = manifest.manifest_payload_sha256
    if marker.get("candidate_manifest_sha256") != manifest_sha:
        return CollectionGateResult(CollectionGateState.MANIFEST_IDENTITY_MISMATCH, (), plan_sha)
    if approved_identity is None:
        return CollectionGateResult(
            CollectionGateState.UNAPPROVED_CANDIDATE, (), plan_sha, manifest_sha
        )
    expected_identities = tuple(
        (item.object_id, item.downloaded_bytes, item.sha256) for item in manifest.objects
    )
    if (
        not approved_identity.approval_id
        or not approved_identity.approver
        or not approved_identity.approval_timestamp
        or not approved_identity.destination
        or not approved_identity.source_authenticity_evidence_reference
        or not approved_identity.license_review_reference
        or approved_identity.dataset_id != request.dataset_id
        or approved_identity.source_representation != request.source_representation
        or approved_identity.plan_sha256 != plan_sha
        or approved_identity.candidate_manifest_sha256 != manifest_sha
        or approved_identity.baseline_commit != request.baseline_commit
        or approved_identity.object_identities != expected_identities
    ):
        return CollectionGateResult(CollectionGateState.MANIFEST_INVALID, (), plan_sha, manifest_sha)
    return CollectionGateResult(
        CollectionGateState.APPROVED_COLLECTION_PASS, (), plan_sha, manifest_sha
    )


def run_multi_object_acquisition(
    request: MultiObjectAcquisitionRequest,
    dependencies: MultiObjectDependencies,
) -> MultiObjectAcquisitionResult:
    transitions: list[CollectionState] = [CollectionState.ABSENT]
    state = CollectionState.ABSENT

    def transition(next_state: CollectionState) -> None:
        nonlocal state
        state = next_state
        transitions.append(next_state)
        if dependencies.event_sink is not None:
            dependencies.event_sink(next_state)

    try:
        ordered = validate_collection_plan(request)
        plan_sha = collection_plan_sha256(request)
        transition(CollectionState.PLAN_VALIDATED)
        policy = NetworkPolicy(authorization=request.authorization)
        policy.authorize_network()
        if request.cache_root.exists():
            validate_cache_root(
                request.cache_root,
                repository_root=request.repository_root,
                allow_temporary=request.allow_temporary,
                allowed_top_level=COLLECTION_MANAGED_TOP_LEVEL,
            )
        else:
            initialize_managed_cache(
                request.cache_root,
                repository_root=request.repository_root,
                allow_temporary=request.allow_temporary,
                allowed_top_level=COLLECTION_MANAGED_TOP_LEVEL,
            )
        transition(CollectionState.CACHE_VALIDATED)
        pre_gate = evaluate_candidate_collection_gate(request)
        if pre_gate.state is CollectionGateState.UNAPPROVED_CANDIDATE:
            manifest = _parse_manifest(
                request.cache_root / "manifests" / CANDIDATE_MANIFEST_NAME
            )
            return MultiObjectAcquisitionResult(
                CollectionState.AWAITING_HUMAN_APPROVAL,
                tuple((*transitions, CollectionState.AWAITING_HUMAN_APPROVAL)),
                request.cache_root,
                plan_sha,
                manifest.manifest_payload_sha256,
                pre_gate,
                0,
                request.source_representation,
                request.baseline_commit,
            )
        if pre_gate.state not in {
            CollectionGateState.NOT_ACQUIRED,
            CollectionGateState.PARTIAL_COLLECTION,
        }:
            raise CollectionAcquisitionError(
                CollectionFailureReason.INCOMPLETE_STATE,
                state=state,
                detail=pre_gate.state.value,
            )
        transport = policy.authorize_transport(dependencies.transport)
        lock_path = request.cache_root / COLLECTION_LOCK_NAME
        lock_payload = {
            "dataset_id": request.dataset_id,
            "plan_sha256": plan_sha,
            "schema_version": 1,
        }
        lock_bytes = canonical_json_bytes(lock_payload)
        try:
            with lock_path.open("xb") as stream:
                stream.write(lock_bytes)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise CollectionAcquisitionError(
                CollectionFailureReason.LOCK_REFUSED,
                state=state,
                detail=str(lock_path),
            ) from exc
        transition(CollectionState.COLLECTION_LOCKED)
        records: list[CandidateObjectRecord] = []
        calls = 0
        total_bytes = 0
        lock_cleanup_error: OSError | None = None
        try:
            objects_root = request.cache_root / "objects"
            expected_paths = {item.relative_path for item in ordered}
            if objects_root.exists():
                unknown = {
                    path.relative_to(objects_root).as_posix()
                    for path in objects_root.rglob("*")
                    if path.is_file()
                } - expected_paths
                if unknown:
                    raise CollectionAcquisitionError(
                        CollectionFailureReason.INCOMPLETE_STATE,
                        state=state,
                        detail=CollectionGateState.OBJECT_UNEXPECTED.value,
                    )
            for item in ordered:
                target = objects_root / item.relative_path
                _validate_object_target(objects_root, target)
                if target.exists():
                    size = target.stat().st_size
                    digest = sha256_file(target)
                    if (
                        size <= 0
                        or item.expected_size is not None and size != item.expected_size
                        or item.expected_sha256 is not None and digest != item.expected_sha256
                    ):
                        raise CollectionAcquisitionError(
                            CollectionFailureReason.EXISTING_OBJECT_MISMATCH,
                            state=state,
                            detail=item.object_id,
                        )
                    record = CandidateObjectRecord(
                        item.object_id, item.relative_path, item.source_url,
                        item.source_url, (), size, digest, item.subject_id,
                        item.session_id, item.source_role, item.content_kind,
                        None, None, None, None, None,
                    )
                else:
                    transition(CollectionState.OBJECT_STAGING)
                    def validate_response(response: TransportResponse) -> None:
                        if (
                            len(response.redirect_chain)
                            > request.resource_limits.maximum_redirects_per_object
                        ):
                            raise ValueError("MAXIMUM_REDIRECTS_PER_OBJECT")
                        for redirect_url in response.redirect_chain:
                            _validate_url(request, redirect_url)

                    receipt = atomic_download(
                        source_url=item.source_url,
                        target=target,
                        policy=policy,
                        transport=transport,
                        expected_length=item.expected_size,
                        expected_sha256=item.expected_sha256,
                        maximum_length=min(
                            request.resource_limits.maximum_bytes_per_object,
                            request.resource_limits.maximum_total_downloaded_bytes
                            - total_bytes,
                        ),
                        response_validator=validate_response,
                    )
                    calls += 1
                    final_url = (
                        receipt.redirect_chain[-1]
                        if receipt.redirect_chain else item.source_url
                    )
                    total_bytes += receipt.downloaded_byte_count
                    if (
                        receipt.downloaded_byte_count > request.resource_limits.maximum_bytes_per_object
                        or total_bytes > request.resource_limits.maximum_total_downloaded_bytes
                    ):
                        raise CollectionAcquisitionError(
                            CollectionFailureReason.RESOURCE_LIMIT_EXCEEDED,
                            state=state,
                            detail=item.object_id,
                        )
                    transition(CollectionState.OBJECT_VERIFIED)
                    transition(CollectionState.OBJECT_PUBLISHED)
                    record = CandidateObjectRecord(
                        item.object_id, item.relative_path, item.source_url,
                        final_url, receipt.redirect_chain,
                        receipt.downloaded_byte_count, receipt.sha256,
                        item.subject_id, item.session_id, item.source_role,
                        item.content_kind, receipt.http_status,
                        receipt.transport_identifier, receipt.etag,
                        receipt.last_modified, dependencies.clock().isoformat(),
                    )
                total_bytes += 0 if record.transport_status is not None else record.downloaded_bytes
                if total_bytes > request.resource_limits.maximum_total_downloaded_bytes:
                    raise CollectionAcquisitionError(
                        CollectionFailureReason.RESOURCE_LIMIT_EXCEEDED,
                        state=state,
                        detail="MAXIMUM_TOTAL_DOWNLOADED_BYTES",
                    )
                records.append(record)
            transition(CollectionState.COLLECTION_OBJECTS_COMPLETE)
            now = dependencies.clock().isoformat()
            manifest = _manifest_with_identity(
                schema_version=COLLECTION_MANIFEST_SCHEMA_VERSION,
                dataset_id=request.dataset_id,
                source_representation=request.source_representation,
                plan_sha256=plan_sha,
                expected_object_count=request.expected_object_count,
                observed_object_count=len(records),
                expected_subject_count=request.expected_subject_count,
                observed_subject_count=len({item.subject_id for item in records}),
                expected_session_count=request.expected_session_count,
                observed_session_count=len({item.session_id for item in records}),
                objects=tuple(records),
                generated_at=now,
                baseline_commit=request.baseline_commit,
                authorization_id=request.authorization_id,
                approval_state="UNAPPROVED_CANDIDATE",
            )
            manifest_path = request.cache_root / "manifests" / CANDIDATE_MANIFEST_NAME
            transition(CollectionState.CANDIDATE_MANIFEST_STAGED)
            try:
                _publish_json_atomic(manifest_path, asdict(manifest))
            except OSError as exc:
                raise CollectionAcquisitionError(
                    CollectionFailureReason.MANIFEST_PUBLICATION_FAILED,
                    state=state,
                ) from exc
            parsed = _parse_manifest(manifest_path)
            if parsed.manifest_payload_sha256 != manifest.manifest_payload_sha256:
                raise CollectionAcquisitionError(
                    CollectionFailureReason.MANIFEST_PUBLICATION_FAILED,
                    state=state,
                )
            transition(CollectionState.CANDIDATE_MANIFEST_VERIFIED)
            marker_payload = {
                "approval_state": "UNAPPROVED_CANDIDATE",
                "baseline_commit": request.baseline_commit,
                "candidate_manifest_sha256": manifest.manifest_payload_sha256,
                "dataset_id": request.dataset_id,
                "plan_sha256": plan_sha,
                "source_representation": request.source_representation,
            }
            try:
                _publish_json_atomic(
                    request.cache_root / CANDIDATE_MARKER_NAME, marker_payload
                )
            except OSError as exc:
                raise CollectionAcquisitionError(
                    CollectionFailureReason.MARKER_PUBLICATION_FAILED,
                    state=state,
                ) from exc
            transition(CollectionState.CANDIDATE_COLLECTION_COMPLETE)
        finally:
            try:
                if lock_path.read_bytes() != lock_bytes:
                    raise OSError("collection lock ownership changed")
                lock_path.unlink()
            except OSError as exc:
                lock_cleanup_error = exc
        if lock_cleanup_error is not None:
            raise CollectionAcquisitionError(
                CollectionFailureReason.LOCK_CLEANUP_FAILED,
                state=state,
                detail=str(lock_cleanup_error),
            )
        gate = evaluate_candidate_collection_gate(request)
        if gate.state is not CollectionGateState.UNAPPROVED_CANDIDATE:
            raise CollectionAcquisitionError(
                CollectionFailureReason.INCOMPLETE_STATE,
                state=state,
                detail=gate.state.value,
            )
        transition(CollectionState.AWAITING_HUMAN_APPROVAL)
        return MultiObjectAcquisitionResult(
            state, tuple(transitions), request.cache_root, plan_sha,
            manifest.manifest_payload_sha256, gate, calls,
            request.source_representation, request.baseline_commit,
        )
    except CollectionAcquisitionError:
        raise
    except NetworkPolicyError as exc:
        raise CollectionAcquisitionError(
            CollectionFailureReason.AUTHORIZATION_FAILED,
            state=state,
            detail=exc.reason.value,
        ) from exc
    except AcquisitionError as exc:
        raise CollectionAcquisitionError(
            CollectionFailureReason.TRANSPORT_FAILED,
            state=state,
            detail=exc.reason.value,
        ) from exc
    except (OSError, ValueError, TypeError) as exc:
        raise CollectionAcquisitionError(
            CollectionFailureReason.PLAN_INVALID,
            state=state,
            detail=str(exc),
        ) from exc
