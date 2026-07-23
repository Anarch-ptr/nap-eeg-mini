"""Strict Git-object binding for frozen external-replication protocol v1."""

from __future__ import annotations

import hashlib
import json
import os
import re
import zlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


PROTOCOL_PATH = "docs/external_boundary_replication.md"
FREEZE_RECORD_PATH = "manifests/external_boundary_replication_protocol_freeze_v1.json"
SUPPORTED_OBJECT_FORMAT = "sha1"
OBJECT_ID_HEX_LENGTH = 40
MAX_COMPRESSED_OBJECT_BYTES = 16 * 1024 * 1024
MAX_DECOMPRESSED_OBJECT_BYTES = 64 * 1024 * 1024
MAX_REF_DEPTH = 8
MAX_TAG_PEEL_DEPTH = 4
MAX_TREE_ENTRIES = 100_000
MAX_PATH_COMPONENTS = 16
MAX_HEADER_BYTES = 1024 * 1024
ALLOWED_TREE_MODES = {"40000", "100644", "100755"}
ALLOWED_FILE_MODES = {"100644", "100755"}
REF_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*[A-Za-z0-9]$")


class ProtocolIdentityStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class ProtocolIdentityError(RuntimeError):
    """Fatal failure of the first application-level scientific gate."""


class DuplicateKeyError(ValueError):
    """Duplicate JSON object key in an integrity-bound document."""


@dataclass(frozen=True)
class GitObject:
    object_type: str
    payload: bytes


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    name: str
    oid: str


@dataclass(frozen=True)
class TagTarget:
    oid: str
    object_type: str


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


def _repository_git_dir(repo_root: Path) -> Path:
    git_dir = (repo_root / ".git").resolve()
    if not git_dir.is_dir():
        raise ProtocolIdentityError("UNSUPPORTED_GIT_LAYOUT_NO_DIRECT_DOT_GIT_DIR")
    for relative in (
        "objects/info/alternates",
        "info/grafts",
        "shallow",
        "objects/pack",
        "refs/replace",
    ):
        path = git_dir / relative
        if path.is_file():
            raise ProtocolIdentityError(f"UNSUPPORTED_GIT_LAYOUT: {relative}")
        if path.is_dir() and any(path.iterdir()):
            raise ProtocolIdentityError(f"UNSUPPORTED_GIT_LAYOUT: {relative}")
    if (git_dir / "packed-refs").exists():
        raise ProtocolIdentityError("UNSUPPORTED_GIT_LAYOUT_PACKED_REFS")
    return git_dir


def _read_ascii_file(path: Path) -> str:
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise ProtocolIdentityError(f"GIT_OBJECT_ACCESS_FAILED: {path.name}") from exc
    except UnicodeDecodeError as exc:
        raise ProtocolIdentityError(f"GIT_TEXT_OBJECT_NON_ASCII: {path.name}") from exc


def _read_ref_file(path: Path, ref_name: str) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ProtocolIdentityError(f"REF_ACCESS_FAILED: {ref_name}") from exc
    try:
        raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ProtocolIdentityError(f"MALFORMED_REF_CONTENT: {ref_name}") from exc
    if raw.endswith(b"\n"):
        body = raw[:-1]
        if body.endswith(b"\n"):
            raise ProtocolIdentityError(f"MALFORMED_REF_CONTENT: {ref_name}")
    else:
        body = raw
    if (
        not body
        or b"\n" in body
        or b"\r" in body
        or b"\x00" in body
        or any(byte < 32 for byte in body)
    ):
        raise ProtocolIdentityError(f"MALFORMED_REF_CONTENT: {ref_name}")
    value = body.decode("ascii")
    if value.startswith("ref:") and not value.startswith("ref: "):
        raise ProtocolIdentityError(f"MALFORMED_SYMBOLIC_REF: {ref_name}")
    return value


def _validate_oid(oid: str) -> str:
    if len(oid) != OBJECT_ID_HEX_LENGTH or any(character not in "0123456789abcdef" for character in oid):
        raise ProtocolIdentityError(f"MALFORMED_SHA1_OID: {oid!r}")
    return oid


def _validate_ref_name(ref_name: str) -> str:
    if ref_name == "HEAD":
        return ref_name
    if "\\" in ref_name or "\x00" in ref_name or any(ord(ch) < 32 for ch in ref_name):
        raise ProtocolIdentityError(f"MALFORMED_REF_NAME: {ref_name!r}")
    if (
        ref_name.startswith("/")
        or ref_name.endswith("/")
        or "//" in ref_name
        or ".." in ref_name.split("/")
        or ":" in ref_name
    ):
        raise ProtocolIdentityError(f"MALFORMED_REF_NAME: {ref_name!r}")
    if not (
        ref_name.startswith("refs/heads/")
        or ref_name.startswith("refs/tags/")
    ):
        raise ProtocolIdentityError(f"UNSUPPORTED_REF_NAMESPACE: {ref_name!r}")
    if not REF_NAME_PATTERN.fullmatch(ref_name):
        raise ProtocolIdentityError(f"MALFORMED_REF_NAME: {ref_name!r}")
    return ref_name


def _ref_file(git_dir: Path, ref_name: str) -> Path:
    ref_name = _validate_ref_name(ref_name)
    path = (git_dir / ref_name) if ref_name != "HEAD" else (git_dir / "HEAD")
    resolved = path.resolve()
    git_root = git_dir.resolve()
    if not os.path.normcase(str(resolved)).startswith(os.path.normcase(str(git_root)) + os.sep):
        raise ProtocolIdentityError(f"REF_PATH_ESCAPE: {ref_name!r}")
    if path.is_symlink() or not path.is_file():
        raise ProtocolIdentityError(f"REF_FILE_UNSUPPORTED: {ref_name!r}")
    return path


def _resolve_ref(git_dir: Path, ref_name: str) -> str:
    current = "refs/tags/" + ref_name if not ref_name.startswith("refs/") and ref_name != "HEAD" else ref_name
    visited: set[str] = set()
    for _depth in range(MAX_REF_DEPTH):
        current = _validate_ref_name(current)
        if current in visited:
            raise ProtocolIdentityError(f"SYMBOLIC_REF_CYCLE: {current}")
        visited.add(current)
        value = _read_ref_file(_ref_file(git_dir, current), current)
        if value.startswith("ref: "):
            target = value[5:]
            if not target:
                raise ProtocolIdentityError(f"MALFORMED_SYMBOLIC_REF: {current}")
            current = target
            continue
        return _validate_oid(value)
    raise ProtocolIdentityError("SYMBOLIC_REF_DEPTH_EXCEEDED")


def _read_loose_object(git_dir: Path, oid: str) -> GitObject:
    oid = _validate_oid(oid)
    if _object_format(git_dir) != SUPPORTED_OBJECT_FORMAT:
        raise ProtocolIdentityError("UNSUPPORTED_REPOSITORY_OBJECT_FORMAT")
    path = git_dir / "objects" / oid[:2] / oid[2:]
    objects_root = (git_dir / "objects").resolve()
    resolved = path.resolve()
    if not os.path.normcase(str(resolved)).startswith(os.path.normcase(str(objects_root)) + os.sep):
        raise ProtocolIdentityError(f"GIT_OBJECT_PATH_ESCAPE: {oid}")
    if path.is_symlink() or not path.is_file():
        raise ProtocolIdentityError(f"GIT_OBJECT_MISSING: {oid}")
    try:
        compressed = path.read_bytes()
    except OSError as exc:
        raise ProtocolIdentityError(f"GIT_OBJECT_MISSING: {oid}") from exc
    if len(compressed) > MAX_COMPRESSED_OBJECT_BYTES:
        raise ProtocolIdentityError(f"GIT_OBJECT_COMPRESSED_SIZE_EXCEEDED: {oid}")
    decompressor = zlib.decompressobj()
    try:
        raw = decompressor.decompress(compressed, MAX_DECOMPRESSED_OBJECT_BYTES + 1)
        raw += decompressor.flush(MAX_DECOMPRESSED_OBJECT_BYTES + 1)
    except zlib.error as exc:
        raise ProtocolIdentityError(f"GIT_OBJECT_MALFORMED: {oid}") from exc
    if not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail:
        raise ProtocolIdentityError(f"GIT_OBJECT_ZLIB_STREAM_INVALID: {oid}")
    if len(raw) > MAX_DECOMPRESSED_OBJECT_BYTES:
        raise ProtocolIdentityError(f"GIT_OBJECT_DECOMPRESSED_SIZE_EXCEEDED: {oid}")
    if hashlib.sha1(raw).hexdigest() != oid:
        raise ProtocolIdentityError(f"GIT_OBJECT_IDENTITY_MISMATCH: {oid}")
    header, separator, payload = raw.partition(b"\x00")
    if not separator:
        raise ProtocolIdentityError(f"GIT_OBJECT_HEADER_MISSING: {oid}")
    if len(header) > MAX_HEADER_BYTES:
        raise ProtocolIdentityError(f"GIT_OBJECT_HEADER_TOO_LARGE: {oid}")
    try:
        object_type, size_text = header.decode("ascii").split(" ", 1)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProtocolIdentityError(f"GIT_OBJECT_HEADER_INVALID: {oid}") from exc
    if not size_text or (len(size_text) > 1 and size_text.startswith("0")) or not size_text.isdecimal():
        raise ProtocolIdentityError(f"GIT_OBJECT_SIZE_INVALID: {oid}")
    declared_size = int(size_text)
    if declared_size != len(payload):
        raise ProtocolIdentityError(f"GIT_OBJECT_SIZE_MISMATCH: {oid}")
    if object_type not in {"blob", "commit", "tag", "tree"}:
        raise ProtocolIdentityError(f"GIT_OBJECT_TYPE_UNSUPPORTED: {object_type}")
    return GitObject(object_type=object_type, payload=payload)


def _validate_tree_name(raw_name: bytes) -> str:
    if not raw_name:
        raise ProtocolIdentityError("TREE_ENTRY_NAME_EMPTY")
    if b"/" in raw_name or b"\\" in raw_name or b"\x00" in raw_name:
        raise ProtocolIdentityError("TREE_ENTRY_NAME_SEPARATOR")
    if any(byte < 32 or byte == 127 for byte in raw_name):
        raise ProtocolIdentityError("TREE_ENTRY_NAME_CONTROL")
    try:
        name = raw_name.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolIdentityError("TREE_ENTRY_NAME_NON_UTF8") from exc
    if name in {".", ".."} or ":" in name or name.startswith(("/", "\\")):
        raise ProtocolIdentityError(f"TREE_ENTRY_NAME_UNSAFE: {name!r}")
    return name


def _tree_entries(payload: bytes) -> dict[str, TreeEntry]:
    entries: dict[str, TreeEntry] = {}
    normalized_names: set[str] = set()
    offset = 0
    count = 0
    while offset < len(payload):
        count += 1
        if count > MAX_TREE_ENTRIES:
            raise ProtocolIdentityError("TREE_ENTRY_COUNT_EXCEEDED")
        mode_end = payload.find(b" ", offset)
        name_end = payload.find(b"\x00", mode_end + 1)
        if mode_end < 0 or name_end < 0 or name_end + 21 > len(payload):
            raise ProtocolIdentityError("TREE_OBJECT_MALFORMED")
        mode_bytes = payload[offset:mode_end]
        if not mode_bytes:
            raise ProtocolIdentityError("TREE_ENTRY_MODE_EMPTY")
        try:
            mode = mode_bytes.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ProtocolIdentityError("TREE_ENTRY_MODE_NON_ASCII") from exc
        if mode not in ALLOWED_TREE_MODES:
            raise ProtocolIdentityError(f"TREE_ENTRY_MODE_UNSUPPORTED: {mode!r}")
        name = _validate_tree_name(payload[mode_end + 1 : name_end])
        normalized = name.casefold()
        if name in entries or normalized in normalized_names:
            raise ProtocolIdentityError(f"TREE_ENTRY_NAME_DUPLICATE: {name!r}")
        child_oid = payload[name_end + 1 : name_end + 21].hex()
        _validate_oid(child_oid)
        entries[name] = TreeEntry(mode=mode, name=name, oid=child_oid)
        normalized_names.add(normalized)
        offset = name_end + 21
    return entries


def _parse_headers(payload: bytes, label: str) -> list[str]:
    header_bytes, separator, _message = payload.partition(b"\n\n")
    if not separator:
        raise ProtocolIdentityError(f"{label}_HEADER_BOUNDARY_MISSING")
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise ProtocolIdentityError(f"{label}_HEADER_TOO_LARGE")
    try:
        lines = header_bytes.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ProtocolIdentityError(f"{label}_HEADER_NON_ASCII") from exc
    if not lines:
        raise ProtocolIdentityError(f"{label}_HEADER_EMPTY")
    if any(line.startswith((" ", "\t")) for line in lines):
        raise ProtocolIdentityError(f"{label}_HEADER_CONTINUATION_UNSUPPORTED")
    return lines


def _commit_tree_oid(commit_payload: bytes) -> str:
    lines = _parse_headers(commit_payload, "COMMIT")
    tree_lines = [line for line in lines if line.startswith("tree ")]
    if len(tree_lines) != 1:
        raise ProtocolIdentityError("COMMIT_TREE_HEADER_MISSING")
    return _validate_oid(tree_lines[0][5:])


def _parse_tag_target(tag_payload: bytes) -> TagTarget:
    lines = _parse_headers(tag_payload, "TAG")
    object_lines = [line for line in lines if line.startswith("object ")]
    type_lines = [line for line in lines if line.startswith("type ")]
    if len(object_lines) != 1:
        raise ProtocolIdentityError("TAG_OBJECT_HEADER_INVALID")
    if len(type_lines) != 1:
        raise ProtocolIdentityError("TAG_TYPE_HEADER_INVALID")
    target_type = type_lines[0][5:]
    if target_type not in {"commit", "tree", "blob", "tag"}:
        raise ProtocolIdentityError(f"TAG_TARGET_TYPE_UNSUPPORTED: {target_type!r}")
    return TagTarget(oid=_validate_oid(object_lines[0][7:]), object_type=target_type)


def _peel_tag_to_commit(git_dir: Path, tag_oid: str) -> str:
    current_oid = _validate_oid(tag_oid)
    visited: set[str] = set()
    for _depth in range(MAX_TAG_PEEL_DEPTH):
        if current_oid in visited:
            raise ProtocolIdentityError("TAG_PEEL_CYCLE")
        visited.add(current_oid)
        tag_object = _read_loose_object(git_dir, current_oid)
        if tag_object.object_type != "tag":
            raise ProtocolIdentityError("TAG_OBJECT_TYPE_NOT_TAG")
        target = _parse_tag_target(tag_object.payload)
        target_object = _read_loose_object(git_dir, target.oid)
        if target_object.object_type != target.object_type:
            raise ProtocolIdentityError("TAG_TARGET_TYPE_MISMATCH")
        if target.object_type == "commit":
            return target.oid
        if target.object_type == "tag":
            current_oid = target.oid
            continue
        raise ProtocolIdentityError(f"TAG_TARGET_NOT_COMMIT: {target.object_type}")
    raise ProtocolIdentityError("TAG_PEEL_DEPTH_EXCEEDED")


def _blob_oid_at_path(git_dir: Path, commit_oid: str, relative_path: str) -> str:
    if len(relative_path.split("/")) > MAX_PATH_COMPONENTS:
        raise ProtocolIdentityError("GIT_PATH_COMPONENT_LIMIT_EXCEEDED")
    if any(part in {"", ".", ".."} or "\\" in part or ":" in part for part in relative_path.split("/")):
        raise ProtocolIdentityError(f"GIT_PATH_UNSAFE: {relative_path}")
    commit = _read_loose_object(git_dir, commit_oid)
    if commit.object_type != "commit":
        raise ProtocolIdentityError("FREEZE_TARGET_NOT_COMMIT")
    current_oid = _commit_tree_oid(commit.payload)
    parts = relative_path.split("/")
    for index, part in enumerate(parts):
        tree = _read_loose_object(git_dir, current_oid)
        if tree.object_type != "tree":
            raise ProtocolIdentityError("PATH_COMPONENT_NOT_TREE")
        entries = _tree_entries(tree.payload)
        if part not in entries:
            raise ProtocolIdentityError(f"GIT_PATH_NOT_FOUND: {relative_path}")
        entry = entries[part]
        current_oid = entry.oid
        if index == len(parts) - 1:
            if entry.mode not in ALLOWED_FILE_MODES:
                raise ProtocolIdentityError(f"GIT_PATH_NOT_FILE_MODE: {relative_path}")
            blob = _read_loose_object(git_dir, current_oid)
            if blob.object_type != "blob":
                raise ProtocolIdentityError(f"GIT_PATH_NOT_BLOB: {relative_path}")
            return current_oid
        if entry.mode != "40000":
            raise ProtocolIdentityError(f"GIT_PATH_INTERMEDIATE_NOT_TREE: {relative_path}")
    raise ProtocolIdentityError(f"GIT_PATH_NOT_FOUND: {relative_path}")


def _object_format(git_dir: Path) -> str:
    config = git_dir / "config"
    if not config.exists():
        return "sha1"
    for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().lower().startswith("objectformat"):
            _key, _equals, value = line.partition("=")
            return value.strip()
    return "sha1"


def _blob(git_dir: Path, oid: str) -> bytes:
    obj = _read_loose_object(git_dir, oid)
    if obj.object_type != "blob":
        raise ProtocolIdentityError(f"GIT_OBJECT_NOT_BLOB: {oid}")
    return obj.payload


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
        git_dir = _repository_git_dir(root)
        tag_oid = _resolve_ref(git_dir, expected.protocol_tag)
        values["tag_object_oid"] = tag_oid
        tag_target = _peel_tag_to_commit(git_dir, tag_oid)
        values["freeze_commit"] = tag_target
        _reason(reasons, "PEELED_FREEZE_COMMIT", tag_target, expected.freeze_commit)

        protocol_oid = _blob_oid_at_path(git_dir, expected.freeze_commit, PROTOCOL_PATH)
        values["protocol_blob_oid"] = protocol_oid
        _reason(reasons, "PROTOCOL_BLOB_OID", protocol_oid, expected.protocol_blob_oid)
        protocol_bytes = _blob(git_dir, protocol_oid)
        values["protocol_blob_sha256"] = _sha256(protocol_bytes)
        values["protocol_byte_length"] = len(protocol_bytes)
        _reason(reasons, "PROTOCOL_SHA256", values["protocol_blob_sha256"], expected.protocol_blob_sha256)
        _reason(reasons, "PROTOCOL_BYTE_LENGTH", len(protocol_bytes), expected.protocol_byte_length)

        freeze_oid = _blob_oid_at_path(git_dir, expected.freeze_commit, FREEZE_RECORD_PATH)
        values["freeze_record_blob_oid"] = freeze_oid
        _reason(reasons, "FREEZE_RECORD_BLOB_OID", freeze_oid, expected.freeze_record_blob_oid)
        freeze_bytes = _blob(git_dir, freeze_oid)
        values["freeze_record_sha256"] = _sha256(freeze_bytes)
        values["freeze_record_byte_length"] = len(freeze_bytes)
        _reason(reasons, "FREEZE_RECORD_SHA256", values["freeze_record_sha256"], expected.freeze_record_sha256)
        _reason(reasons, "FREEZE_RECORD_BYTE_LENGTH", len(freeze_bytes), expected.freeze_record_byte_length)
        _verify_freeze_record_binding(freeze_bytes, expected, reasons)

        object_format = _object_format(git_dir)
        values["repository_object_format"] = object_format
        _reason(reasons, "REPOSITORY_OBJECT_FORMAT", object_format, expected.repository_object_format)
        values["implementation_commit"] = _resolve_ref(git_dir, "HEAD")
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
