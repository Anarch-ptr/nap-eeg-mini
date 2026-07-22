"""Strict Git-object binding for frozen external-replication protocol v1."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


PROTOCOL_PATH = "docs/external_boundary_replication.md"
FREEZE_RECORD_PATH = "manifests/external_boundary_replication_protocol_freeze_v1.json"


class ProtocolIdentityStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class ProtocolIdentityError(RuntimeError):
    """Fatal failure of the first application-level scientific gate."""


class DuplicateKeyError(ValueError):
    """Duplicate JSON object key in an integrity-bound document."""


@dataclass(frozen=True)
class FrozenProtocolIdentity:
    protocol_tag: str
    freeze_commit: str
    protocol_blob_oid: str
    protocol_blob_sha256: str
    protocol_byte_length: int
    freeze_record_blob_oid: str
    freeze_record_sha256: str
    freeze_record_byte_length: int
    repository_object_format: str


FROZEN_PROTOCOL_V1 = FrozenProtocolIdentity(
    protocol_tag="external-boundary-replication-preregistration-pre-execution-v1",
    freeze_commit="9f8ad53f2f7eaf393b60310b945b31fa1f53d228",
    protocol_blob_oid="ca664e257d8bd14338312922404c24d3cc52e795",
    protocol_blob_sha256="2b4fd30506414c0a7d79a5ad6ac861cdf61912818dfdc339da54f306d3615c9d",
    protocol_byte_length=453595,
    freeze_record_blob_oid="14a8f58501e120501489a3e16b646c9caaaadab2",
    freeze_record_sha256="bbc1e4f560e0f4b469cd6c8708368792539073869c0847707e9dea35e3c97335",
    freeze_record_byte_length=4556,
    repository_object_format="sha1",
)


@dataclass(frozen=True)
class ProtocolIdentityResult:
    status: ProtocolIdentityStatus
    protocol_tag: str
    tag_object_oid: str | None
    freeze_commit: str | None
    protocol_blob_oid: str | None
    protocol_blob_sha256: str | None
    protocol_byte_length: int | None
    freeze_record_blob_oid: str | None
    freeze_record_sha256: str | None
    freeze_record_byte_length: int | None
    repository_object_format: str | None
    implementation_commit: str | None
    failure_reasons: tuple[str, ...]


def _git(repo_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ProtocolIdentityError(f"GIT_OBJECT_ACCESS_FAILED: {detail}")
    return completed.stdout


def _text(repo_root: Path, *arguments: str) -> str:
    return _git(repo_root, *arguments).decode("ascii").strip()


def _blob(repo_root: Path, oid: str) -> bytes:
    return _git(repo_root, "cat-file", "blob", oid)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reason(reasons: list[str], label: str, observed: object, expected: object) -> None:
    if observed != expected:
        reasons.append(f"{label}: expected={expected!r}, observed={observed!r}")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"DUPLICATE_JSON_KEY: {key}")
        result[key] = value
    return result


def parse_strict_json(data: bytes) -> object:
    """Parse UTF-8 JSON while rejecting duplicate keys at every object depth."""

    return json.loads(
        data.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )


def _verify_freeze_record_binding(
    record_bytes: bytes,
    expected: FrozenProtocolIdentity,
    reasons: list[str],
) -> None:
    try:
        record = parse_strict_json(record_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        reasons.append(f"FREEZE_RECORD_JSON_INVALID: {exc}")
        return
    bindings = {
        item.get("path"): item for item in record.get("audit_binding_table", [])
    }
    protocol_binding = bindings.get(PROTOCOL_PATH, {})
    checks = (
        ("FREEZE_RECORD_PROTOCOL_PATH", record.get("protocol_path"), PROTOCOL_PATH),
        ("FREEZE_RECORD_PROTOCOL_OID", record.get("protocol_blob_oid"), expected.protocol_blob_oid),
        ("FREEZE_RECORD_PROTOCOL_SHA256", record.get("protocol_blob_sha256"), expected.protocol_blob_sha256),
        ("FREEZE_RECORD_PROTOCOL_BYTES", record.get("protocol_blob_byte_length"), expected.protocol_byte_length),
        ("FREEZE_RECORD_TAG", record.get("intended_freeze_tag"), expected.protocol_tag),
        ("FREEZE_RECORD_OBJECT_FORMAT", record.get("repository_object_format"), expected.repository_object_format),
        ("FREEZE_RECORD_BINDING_OID", protocol_binding.get("expected_committed_blob_oid"), expected.protocol_blob_oid),
        ("FREEZE_RECORD_BINDING_SHA256", protocol_binding.get("expected_committed_blob_sha256"), expected.protocol_blob_sha256),
        ("FREEZE_RECORD_BINDING_BYTES", protocol_binding.get("expected_committed_byte_length"), expected.protocol_byte_length),
    )
    for label, observed, wanted in checks:
        _reason(reasons, label, observed, wanted)


def verify_protocol_identity(
    repo_root: str | Path | None = None,
    expected: FrozenProtocolIdentity = FROZEN_PROTOCOL_V1,
) -> ProtocolIdentityResult:
    """Verify v1 from raw Git objects; never use worktree text as authority."""

    root = Path(repo_root or Path(__file__).resolve().parents[2]).resolve()
    reasons: list[str] = []
    values: dict[str, object | None] = {
        "tag_object_oid": None,
        "freeze_commit": None,
        "protocol_blob_oid": None,
        "protocol_blob_sha256": None,
        "protocol_byte_length": None,
        "freeze_record_blob_oid": None,
        "freeze_record_sha256": None,
        "freeze_record_byte_length": None,
        "repository_object_format": None,
        "implementation_commit": None,
    }
    try:
        tag_oid = _text(root, "rev-parse", expected.protocol_tag)
        values["tag_object_oid"] = tag_oid
        tag_type = _text(root, "cat-file", "-t", tag_oid)
        _reason(reasons, "TAG_OBJECT_TYPE", tag_type, "tag")
        tag_bytes = _git(root, "cat-file", "-p", tag_oid)
        tag_target = next(
            (line[7:] for line in tag_bytes.decode("utf-8", errors="replace").splitlines() if line.startswith("object ")),
            None,
        )
        values["freeze_commit"] = tag_target
        _reason(reasons, "PEELED_FREEZE_COMMIT", tag_target, expected.freeze_commit)

        protocol_oid = _text(root, "rev-parse", f"{expected.freeze_commit}:{PROTOCOL_PATH}")
        values["protocol_blob_oid"] = protocol_oid
        _reason(reasons, "PROTOCOL_BLOB_OID", protocol_oid, expected.protocol_blob_oid)
        protocol_bytes = _blob(root, protocol_oid)
        values["protocol_blob_sha256"] = _sha256(protocol_bytes)
        values["protocol_byte_length"] = len(protocol_bytes)
        _reason(reasons, "PROTOCOL_SHA256", values["protocol_blob_sha256"], expected.protocol_blob_sha256)
        _reason(reasons, "PROTOCOL_BYTE_LENGTH", len(protocol_bytes), expected.protocol_byte_length)

        freeze_oid = _text(root, "rev-parse", f"{expected.freeze_commit}:{FREEZE_RECORD_PATH}")
        values["freeze_record_blob_oid"] = freeze_oid
        _reason(reasons, "FREEZE_RECORD_BLOB_OID", freeze_oid, expected.freeze_record_blob_oid)
        freeze_bytes = _blob(root, freeze_oid)
        values["freeze_record_sha256"] = _sha256(freeze_bytes)
        values["freeze_record_byte_length"] = len(freeze_bytes)
        _reason(reasons, "FREEZE_RECORD_SHA256", values["freeze_record_sha256"], expected.freeze_record_sha256)
        _reason(reasons, "FREEZE_RECORD_BYTE_LENGTH", len(freeze_bytes), expected.freeze_record_byte_length)
        _verify_freeze_record_binding(freeze_bytes, expected, reasons)

        object_format = _text(root, "rev-parse", "--show-object-format")
        values["repository_object_format"] = object_format
        _reason(reasons, "REPOSITORY_OBJECT_FORMAT", object_format, expected.repository_object_format)
        values["implementation_commit"] = _text(root, "rev-parse", "HEAD")
    except (ProtocolIdentityError, DuplicateKeyError, StopIteration) as exc:
        reasons.append(str(exc))

    return ProtocolIdentityResult(
        status=ProtocolIdentityStatus.FAIL if reasons else ProtocolIdentityStatus.PASS,
        protocol_tag=expected.protocol_tag,
        failure_reasons=tuple(reasons),
        **values,
    )


def enforce_protocol_identity_or_abort(
    repo_root: str | Path | None = None,
) -> ProtocolIdentityResult:
    result = verify_protocol_identity(repo_root)
    if result.status is not ProtocolIdentityStatus.PASS:
        detail = "; ".join(result.failure_reasons)
        raise ProtocolIdentityError(
            f"PROTOCOL_IDENTITY_NOT_SUPPORTED_BY_IMPLEMENTATION: {detail}"
        )
    return result
