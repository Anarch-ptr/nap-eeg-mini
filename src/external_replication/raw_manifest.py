"""Deterministic Phase II-B archive, raw-file, and inventory manifests."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


MANIFEST_SCHEMA_VERSION = 1
DATASET_NAME = "Lee2019_MI"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ManifestError(ValueError):
    pass


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def normalize_relative_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if (
        not normalized
        or candidate.is_absolute()
        or any(part in ("", ".", "..") for part in candidate.parts)
        or ":" in candidate.parts[0]
    ):
        raise ManifestError("UNSAFE_RELATIVE_PATH")
    return candidate.as_posix()


@dataclass(frozen=True)
class ArchiveRecord:
    schema_version: int
    dataset_name: str
    implementation_identifier: str | None
    source_url: str | None
    retrieval_timestamp: str
    http_status: int | None
    content_length: int | None
    etag: str | None
    last_modified: str | None
    redirect_chain: tuple[str, ...]
    archive_filename: str
    downloaded_byte_count: int
    sha256: str
    transport_identifier: str

    def validate(self) -> None:
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise ManifestError("UNSUPPORTED_SCHEMA_VERSION")
        if self.dataset_name != DATASET_NAME:
            raise ManifestError("DATASET_IDENTITY_MISMATCH")
        if (
            not self.archive_filename
            or Path(self.archive_filename).name != self.archive_filename
            or self.downloaded_byte_count <= 0
            or _SHA256.fullmatch(self.sha256) is None
            or not self.retrieval_timestamp
            or not self.transport_identifier
        ):
            raise ManifestError("ARCHIVE_RECORD_INVALID")


@dataclass(frozen=True)
class RawFileRecord:
    relative_path: str
    byte_size: int
    sha256: str
    source_archive_sha256: str
    subject_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    role: str | None = None
    label_status: str | None = None
    acquisition_status: str | None = None

    def normalized(self) -> "RawFileRecord":
        return replace(self, relative_path=normalize_relative_path(self.relative_path))

    def validate(self) -> None:
        normalized = self.normalized()
        if normalized.relative_path != self.relative_path:
            raise ManifestError("NONCANONICAL_RELATIVE_PATH")
        if (
            self.byte_size < 0
            or _SHA256.fullmatch(self.sha256) is None
            or _SHA256.fullmatch(self.source_archive_sha256) is None
        ):
            raise ManifestError("RAW_FILE_RECORD_INVALID")


@dataclass(frozen=True)
class ExtractedManifest:
    schema_version: int
    dataset_name: str
    source_archive: ArchiveRecord
    generated_timestamp: str
    files: tuple[RawFileRecord, ...]
    manifest_payload_sha256: str | None = None

    def ordered(self) -> "ExtractedManifest":
        normalized = tuple(record.normalized() for record in self.files)
        return replace(
            self,
            files=tuple(
                sorted(normalized, key=lambda record: record.relative_path.casefold())
            ),
        )

    def payload(self) -> dict[str, object]:
        ordered = self.ordered()
        return {
            "dataset_name": ordered.dataset_name,
            "files": [asdict(record) for record in ordered.files],
            "generated_timestamp": ordered.generated_timestamp,
            "schema_version": ordered.schema_version,
            "source_archive": asdict(ordered.source_archive),
        }

    def payload_sha256(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.payload())).hexdigest()

    def frozen(self) -> "ExtractedManifest":
        ordered = self.ordered()
        return replace(ordered, manifest_payload_sha256=ordered.payload_sha256())

    def validate(self, *, verify_identity: bool = True) -> None:
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise ManifestError("UNSUPPORTED_SCHEMA_VERSION")
        if self.dataset_name != DATASET_NAME or not self.generated_timestamp:
            raise ManifestError("MANIFEST_REQUIRED_FIELD_INVALID")
        self.source_archive.validate()
        seen: set[str] = set()
        for record in self.files:
            record.validate()
            key = record.relative_path.casefold()
            if key in seen:
                raise ManifestError("DUPLICATE_RAW_FILE_RECORD")
            seen.add(key)
            if record.source_archive_sha256 != self.source_archive.sha256:
                raise ManifestError("ARCHIVE_FILE_MAPPING_INCOMPLETE")
        if verify_identity and (
            _SHA256.fullmatch(self.manifest_payload_sha256 or "") is None
            or self.manifest_payload_sha256 != self.payload_sha256()
        ):
            raise ManifestError("MANIFEST_PAYLOAD_SHA256_MISMATCH")

    def to_bytes(self) -> bytes:
        frozen = self.frozen()
        frozen.validate()
        payload = frozen.payload()
        payload["manifest_payload_sha256"] = frozen.manifest_payload_sha256
        return canonical_json_bytes(payload)


def manifest_from_dict(payload: Any) -> ExtractedManifest:
    if not isinstance(payload, dict):
        raise ManifestError("MANIFEST_ROOT_NOT_OBJECT")
    required = {
        "schema_version",
        "dataset_name",
        "source_archive",
        "generated_timestamp",
        "files",
        "manifest_payload_sha256",
    }
    if set(payload) != required:
        raise ManifestError("MANIFEST_REQUIRED_FIELDS_MISMATCH")
    try:
        archive_payload = payload["source_archive"]
        files_payload = payload["files"]
        if not isinstance(archive_payload, dict) or not isinstance(files_payload, list):
            raise TypeError
        archive = ArchiveRecord(
            **{
                **archive_payload,
                "redirect_chain": tuple(archive_payload["redirect_chain"]),
            }
        )
        files = tuple(RawFileRecord(**record) for record in files_payload)
        manifest = ExtractedManifest(
            schema_version=payload["schema_version"],
            dataset_name=payload["dataset_name"],
            source_archive=archive,
            generated_timestamp=payload["generated_timestamp"],
            files=files,
            manifest_payload_sha256=payload["manifest_payload_sha256"],
        )
    except (KeyError, TypeError) as exc:
        raise ManifestError("MANIFEST_STRUCTURE_INVALID") from exc
    manifest.validate()
    return manifest


def read_manifest(path: str | Path) -> ExtractedManifest:
    try:
        payload = json.loads(Path(path).read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("MANIFEST_JSON_INVALID") from exc
    return manifest_from_dict(payload)


def write_manifest(path: str | Path, manifest: ExtractedManifest) -> None:
    target = Path(path)
    if target.exists():
        raise ManifestError("MANIFEST_TARGET_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(manifest.to_bytes())


def write_manifest_atomic(
    path: str | Path, manifest: ExtractedManifest
) -> ExtractedManifest:
    """Stage, fsync, self-verify, and publish without overwriting."""
    target = Path(path)
    staging = target.with_name(target.name + ".staging")
    if target.exists():
        raise ManifestError("MANIFEST_TARGET_EXISTS")
    if staging.exists():
        raise ManifestError("MANIFEST_STAGING_TARGET_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    frozen = manifest.frozen()
    created_staging = False
    try:
        with staging.open("xb") as stream:
            created_staging = True
            stream.write(frozen.to_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        verified = read_manifest(staging)
        if verified != frozen:
            raise ManifestError("MANIFEST_STAGING_VERIFICATION_FAILED")
        os.link(staging, target)
        staging.unlink()
        created_staging = False
        return verified
    finally:
        if created_staging:
            try:
                staging.unlink()
            except FileNotFoundError:
                pass


def raw_file_record(
    path: str | Path,
    *,
    relative_to: str | Path,
    source_archive_sha256: str,
    subject_id: str | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
    role: str | None = None,
    label_status: str | None = None,
    acquisition_status: str | None = None,
) -> RawFileRecord:
    file_path = Path(path)
    relative = file_path.relative_to(Path(relative_to)).as_posix()
    return RawFileRecord(
        relative_path=normalize_relative_path(relative),
        byte_size=file_path.stat().st_size,
        sha256=sha256_file(file_path),
        source_archive_sha256=source_archive_sha256,
        subject_id=subject_id,
        session_id=session_id,
        run_id=run_id,
        role=role,
        label_status=label_status,
        acquisition_status=acquisition_status,
    )


@dataclass(frozen=True)
class Inventory:
    subject_ids: tuple[str, ...]
    session_ids: tuple[str, ...]
    run_ids: tuple[str, ...]
    source_file_mapping: tuple[tuple[str, str | None, str | None, str | None], ...]
    label_status_counts: tuple[tuple[str, int], ...]
    acquisition_status_counts: tuple[tuple[str, int], ...]
    observed_file_count: int
    expected_file_count: int | None
    expected_subject_count: int | None

    @property
    def matches_expectations(self) -> bool:
        return (
            (self.expected_file_count is None or self.observed_file_count == self.expected_file_count)
            and (
                self.expected_subject_count is None
                or len(self.subject_ids) == self.expected_subject_count
            )
        )


def build_inventory(
    records: Iterable[RawFileRecord],
    *,
    expected_file_count: int | None = None,
    expected_subject_count: int | None = None,
) -> Inventory:
    ordered = sorted(
        (record.normalized() for record in records),
        key=lambda record: record.relative_path.casefold(),
    )
    label_counts: dict[str, int] = {}
    acquisition_counts: dict[str, int] = {}
    for record in ordered:
        label = record.label_status or "UNKNOWN"
        acquisition = record.acquisition_status or "UNKNOWN"
        label_counts[label] = label_counts.get(label, 0) + 1
        acquisition_counts[acquisition] = acquisition_counts.get(acquisition, 0) + 1
    return Inventory(
        subject_ids=tuple(sorted({r.subject_id for r in ordered if r.subject_id})),
        session_ids=tuple(sorted({r.session_id for r in ordered if r.session_id})),
        run_ids=tuple(sorted({r.run_id for r in ordered if r.run_id})),
        source_file_mapping=tuple(
            (r.relative_path, r.subject_id, r.session_id, r.run_id) for r in ordered
        ),
        label_status_counts=tuple(sorted(label_counts.items())),
        acquisition_status_counts=tuple(sorted(acquisition_counts.items())),
        observed_file_count=len(ordered),
        expected_file_count=expected_file_count,
        expected_subject_count=expected_subject_count,
    )
