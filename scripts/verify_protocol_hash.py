"""Validate protocol bytes and hash exact Git blobs without text conversion."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


UTF8_BOM = b"\xef\xbb\xbf"
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class ProtocolVerificationError(RuntimeError):
    """Base class for deterministic validation and Git-access failures."""

    exit_code = 2


class ByteValidationError(ProtocolVerificationError):
    """Raised when bytes violate the canonical protocol byte contract."""


class RepositoryPathError(ProtocolVerificationError):
    """Raised when a path is absolute or escapes the repository root."""

    exit_code = 3


class GitAccessError(ProtocolVerificationError):
    """Raised when Git cannot resolve or return the requested blob."""

    exit_code = 4


class ExpectedHashMismatch(ProtocolVerificationError):
    """Raised when an explicitly supplied expected SHA-256 does not match."""

    exit_code = 5


def validate_canonical_bytes(data: bytes) -> dict[str, Any]:
    """Validate bytes without modifying them and return canonical metadata."""
    if data.startswith(UTF8_BOM):
        raise ByteValidationError("UTF8_BOM_PRESENT: UTF-8 BOM is prohibited")

    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ByteValidationError(
            f"STRICT_UTF8_DECODE_FAILED: {error}"
        ) from error

    cr_count = data.count(b"\r")
    if cr_count:
        crlf_count = data.count(b"\r\n")
        bare_cr_count = cr_count - crlf_count
        raise ByteValidationError(
            "CANONICAL_PROTOCOL_BARE_CR_COUNT_VIOLATION: "
            f"CR={cr_count}, CRLF={crlf_count}, bare_CR={bare_cr_count}"
        )

    if not data.endswith(b"\n"):
        raise ByteValidationError(
            "CANONICAL_PROTOCOL_TERMINAL_NEWLINE_MISSING: exactly one LF required"
        )
    if data.endswith(b"\n\n"):
        raise ByteValidationError(
            "CANONICAL_PROTOCOL_TERMINAL_NEWLINE_EXTRA: multiple terminal LF bytes"
        )

    trailing_lines = [
        line_number
        for line_number, line in enumerate(data.split(b"\n")[:-1], start=1)
        if line.endswith((b" ", b"\t"))
    ]
    if trailing_lines:
        rendered = ",".join(str(value) for value in trailing_lines)
        raise ByteValidationError(
            "CANONICAL_PROTOCOL_TRAILING_SPACE_OR_TAB_VIOLATION: "
            f"lines={rendered}"
        )

    return {
        "byte_length": len(data),
        "encoding": "UTF-8",
        "bom": "ABSENT",
        "strict_utf8": "PASS",
        "lf_count": data.count(b"\n"),
        "cr_count": 0,
        "line_endings": "LF_ONLY",
        "terminal_newline": "EXACTLY_ONE_LF",
        "trailing_whitespace_lines": [],
        "validation_status": "PASS",
    }


def sha256_bytes(data: bytes) -> str:
    """Return SHA-256 of the exact supplied bytes."""
    return hashlib.sha256(data).hexdigest()


def _run_git(repo_root: Path, arguments: Sequence[str]) -> bytes:
    """Run Git without a shell and return stdout as untouched bytes."""
    command = ["git", "-C", str(repo_root), *arguments]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise GitAccessError(
            f"GIT_SUBPROCESS_FAILURE ({completed.returncode}): {message}"
        )
    return completed.stdout


def discover_repository_root(start: Path | None = None) -> Path:
    """Resolve the containing Git worktree root."""
    location = (start or Path.cwd()).resolve()
    output = _run_git(location, ["rev-parse", "--show-toplevel"])
    return Path(output.decode("utf-8", errors="strict").strip()).resolve()


def normalize_repository_path(repo_root: Path, supplied_path: str) -> str:
    """Return a Git-style relative path, rejecting absolute and escaping paths."""
    raw_path = Path(supplied_path)
    if raw_path.is_absolute() or raw_path.drive or raw_path.root:
        raise RepositoryPathError(
            f"REPOSITORY_RELATIVE_PATH_REQUIRED: {supplied_path}"
        )
    if not raw_path.parts or any(part == ".." for part in raw_path.parts):
        raise RepositoryPathError(
            f"REPOSITORY_PATH_ESCAPE_REJECTED: {supplied_path}"
        )

    root = repo_root.resolve()
    resolved = (root / raw_path).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise RepositoryPathError(
            f"REPOSITORY_PATH_ESCAPE_REJECTED: {supplied_path}"
        ) from error
    if relative == Path("."):
        raise RepositoryPathError("REPOSITORY_FILE_PATH_REQUIRED")
    return relative.as_posix()


def resolve_blob_oid(repo_root: Path, object_spec: str) -> str:
    """Resolve an object spec and require that it denotes a Git blob."""
    oid = _run_git(
        repo_root,
        ["rev-parse", "--verify", "--end-of-options", object_spec],
    ).decode("ascii", errors="strict").strip()
    object_type = _run_git(repo_root, ["cat-file", "-t", oid]).decode(
        "ascii", errors="strict"
    ).strip()
    if object_type != "blob":
        raise GitAccessError(
            f"GIT_OBJECT_IS_NOT_BLOB: spec={object_spec}, type={object_type}"
        )
    return oid


def read_git_blob(repo_root: Path, blob_oid: str) -> bytes:
    """Read exact Git blob bytes through binary subprocess output."""
    return _run_git(repo_root, ["cat-file", "blob", blob_oid])


def _check_expected_sha256(actual: str, expected: str | None) -> None:
    if expected is None:
        return
    if not SHA256_PATTERN.fullmatch(expected):
        raise ExpectedHashMismatch("EXPECTED_SHA256_FORMAT_INVALID")
    if actual.lower() != expected.lower():
        raise ExpectedHashMismatch(
            f"EXPECTED_SHA256_MISMATCH: expected={expected.lower()}, actual={actual}"
        )


def inspect_worktree(
    supplied_path: str,
    *,
    repo_root: Path | None = None,
    validate_only: bool = False,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate exact worktree bytes and optionally calculate their SHA-256."""
    root = (repo_root or discover_repository_root()).resolve()
    relative = normalize_repository_path(root, supplied_path)
    target = root / Path(relative)
    try:
        data = target.read_bytes()
    except OSError as error:
        raise RepositoryPathError(
            f"WORKTREE_PATH_UNREADABLE: {relative}: {error}"
        ) from error
    record = {"mode": "worktree", "path": relative}
    record.update(validate_canonical_bytes(data))
    if validate_only and expected_sha256 is None:
        record["sha256"] = None
    else:
        digest = sha256_bytes(data)
        _check_expected_sha256(digest, expected_sha256)
        record["sha256"] = None if validate_only else digest
    return record


def inspect_index(
    supplied_path: str,
    *,
    repo_root: Path | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate and hash the exact blob currently represented by the Git index."""
    root = (repo_root or discover_repository_root()).resolve()
    relative = normalize_repository_path(root, supplied_path)
    oid = resolve_blob_oid(root, f":{relative}")
    data = read_git_blob(root, oid)
    digest = sha256_bytes(data)
    _check_expected_sha256(digest, expected_sha256)
    record = {
        "mode": "index",
        "path": relative,
        "revision": "INDEX",
        "blob_oid": oid,
        "sha256": digest,
    }
    record.update(validate_canonical_bytes(data))
    return record


def inspect_revision(
    revision: str,
    supplied_path: str,
    *,
    repo_root: Path | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate and hash exact blob bytes at ``revision:path``."""
    root = (repo_root or discover_repository_root()).resolve()
    relative = normalize_repository_path(root, supplied_path)
    if not revision:
        raise GitAccessError("GIT_REVISION_REQUIRED")
    oid = resolve_blob_oid(root, f"{revision}:{relative}")
    data = read_git_blob(root, oid)
    digest = sha256_bytes(data)
    _check_expected_sha256(digest, expected_sha256)
    record = {
        "mode": "revision",
        "path": relative,
        "revision": revision,
        "blob_oid": oid,
        "sha256": digest,
    }
    record.update(validate_canonical_bytes(data))
    return record


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate canonical protocol bytes and exact Git blobs."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    worktree = subparsers.add_parser("worktree")
    worktree.add_argument("path")
    worktree.add_argument("--validate-only", action="store_true")
    worktree.add_argument("--expected-sha256")
    worktree.add_argument("--json", action="store_true")

    index = subparsers.add_parser("index")
    index.add_argument("path")
    index.add_argument("--expected-sha256")
    index.add_argument("--json", action="store_true")

    revision = subparsers.add_parser("revision")
    revision.add_argument("revision")
    revision.add_argument("path")
    revision.add_argument("--expected-sha256")
    revision.add_argument("--json", action="store_true")
    return parser


def _render_record(record: dict[str, Any], as_json: bool) -> str:
    if as_json:
        return json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    return "\n".join(f"{key}: {record[key]}" for key in sorted(record))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line verifier and return a deterministic exit code."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.mode == "worktree":
            record = inspect_worktree(
                arguments.path,
                validate_only=arguments.validate_only,
                expected_sha256=arguments.expected_sha256,
            )
        elif arguments.mode == "index":
            record = inspect_index(
                arguments.path,
                expected_sha256=arguments.expected_sha256,
            )
        else:
            record = inspect_revision(
                arguments.revision,
                arguments.path,
                expected_sha256=arguments.expected_sha256,
            )
    except ProtocolVerificationError as error:
        failure = {
            "error": str(error),
            "mode": getattr(arguments, "mode", None),
            "validation_status": "FAIL",
        }
        rendered = _render_record(failure, getattr(arguments, "json", False))
        print(rendered, file=sys.stderr)
        return error.exit_code

    print(_render_record(record, arguments.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
