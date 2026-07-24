"""Fail-closed raw-data identity gate for controlled synthetic caches."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .acquisition import (
    AcquisitionError,
    AcquisitionFailureReason,
    MANAGED_CACHE_MARKER,
    known_global_cache_paths,
    validate_cache_root,
)
from .raw_manifest import (
    ExtractedManifest,
    Inventory,
    ManifestError,
    build_inventory,
    read_manifest,
    sha256_file,
)


class RawIdentityState(str, Enum):
    NOT_ACQUIRED = "NOT_ACQUIRED"
    PARTIAL = "PARTIAL"
    HASH_MISMATCH = "HASH_MISMATCH"
    INVENTORY_MISMATCH = "INVENTORY_MISMATCH"
    UNEXPECTED_FILE = "UNEXPECTED_FILE"
    GLOBAL_CACHE_CONTAMINATION = "GLOBAL_CACHE_CONTAMINATION"
    SOURCE_IDENTITY_AMBIGUOUS = "SOURCE_IDENTITY_AMBIGUOUS"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    PASS = "PASS"


@dataclass(frozen=True)
class RawIdentityResult:
    state: RawIdentityState
    reason_codes: tuple[str, ...]
    affected_relative_paths: tuple[str, ...] = ()
    manifest_sha256: str | None = None
    observed_file_count: int = 0
    expected_file_count: int = 0


def _result(
    state: RawIdentityState,
    *reasons: str,
    paths: tuple[str, ...] = (),
    manifest: ExtractedManifest | None = None,
    observed: int = 0,
) -> RawIdentityResult:
    return RawIdentityResult(
        state=state,
        reason_codes=tuple(reasons),
        affected_relative_paths=paths,
        manifest_sha256=(
            manifest.manifest_payload_sha256 if manifest is not None else None
        ),
        observed_file_count=observed,
        expected_file_count=len(manifest.files) if manifest is not None else 0,
    )


def not_acquired_result() -> RawIdentityResult:
    return _result(RawIdentityState.NOT_ACQUIRED, "REAL_DATA_NOT_ACQUIRED")


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
        str(right.resolve(strict=False))
    )


def evaluate_raw_identity_gate(
    cache_root: str | Path | None,
    *,
    repository_root: str | Path,
    manifest_relative_path: str = "manifests/raw_manifest.json",
    raw_relative_path: str = "raw",
    expected_file_count: int | None = None,
    expected_subject_count: int | None = 54,
    allow_temporary: bool = False,
    home: str | Path | None = None,
) -> RawIdentityResult:
    if cache_root is None:
        return not_acquired_result()
    candidate = Path(cache_root).expanduser().resolve(strict=False)
    if any(
        _same_path(candidate, global_path)
        or global_path in candidate.parents
        for global_path in known_global_cache_paths(home)
    ):
        return _result(
            RawIdentityState.GLOBAL_CACHE_CONTAMINATION,
            "GLOBAL_CACHE_PATH_REJECTED",
        )
    try:
        root = validate_cache_root(
            candidate,
            repository_root=repository_root,
            require_managed=True,
            allow_temporary=allow_temporary,
            home=home,
        )
    except AcquisitionError as exc:
        if exc.reason is AcquisitionFailureReason.GLOBAL_CACHE_PATH_REJECTED:
            state = RawIdentityState.GLOBAL_CACHE_CONTAMINATION
        elif exc.reason in {
            AcquisitionFailureReason.CACHE_ROOT_REQUIRED,
            AcquisitionFailureReason.CACHE_ROOT_UNMANAGED,
        } and not candidate.exists():
            state = RawIdentityState.NOT_ACQUIRED
        elif exc.reason is AcquisitionFailureReason.CACHE_ROOT_CONTAINS_UNEXPECTED_FILES:
            state = RawIdentityState.UNEXPECTED_FILE
        else:
            state = RawIdentityState.MANIFEST_INVALID
        paths = (exc.affected_path,) if exc.affected_path else ()
        return _result(state, exc.reason.value, paths=paths)
    manifest_path = root / manifest_relative_path
    if manifest_path.is_symlink():
        return _result(
            RawIdentityState.UNEXPECTED_FILE,
            "MANIFEST_SYMLINK_REJECTED",
            paths=(manifest_relative_path,),
        )
    if not manifest_path.is_file():
        return _result(
            RawIdentityState.NOT_ACQUIRED,
            "RAW_MANIFEST_MISSING",
            paths=(manifest_relative_path,),
        )
    try:
        manifest = read_manifest(manifest_path)
    except ManifestError as exc:
        return _result(RawIdentityState.MANIFEST_INVALID, str(exc))
    archive_dir = root / "archives"
    if not archive_dir.is_dir() or archive_dir.is_symlink():
        return _result(
            RawIdentityState.SOURCE_IDENTITY_AMBIGUOUS,
            "SOURCE_ARCHIVE_DIRECTORY_MISSING_OR_UNSAFE",
            paths=("archives",),
            manifest=manifest,
        )
    archive_files = [
        path
        for path in archive_dir.rglob("*")
        if path.is_file() or path.is_symlink()
    ]
    expected_archive_relative = manifest.source_archive.archive_filename
    unexpected_archives = tuple(
        sorted(
            f"archives/{path.relative_to(archive_dir).as_posix()}"
            for path in archive_files
            if path.is_symlink()
            or path.relative_to(archive_dir).as_posix() != expected_archive_relative
        )
    )
    if unexpected_archives:
        return _result(
            RawIdentityState.UNEXPECTED_FILE,
            "UNMANAGED_ARCHIVE_FILE_PRESENT",
            paths=unexpected_archives,
            manifest=manifest,
        )
    matching_archives = [
        path
        for path in archive_files
        if path.relative_to(archive_dir).as_posix() == expected_archive_relative
    ]
    if len(matching_archives) != 1:
        return _result(
            RawIdentityState.SOURCE_IDENTITY_AMBIGUOUS,
            "SOURCE_ARCHIVE_COUNT_NOT_ONE",
            manifest=manifest,
        )
    if sha256_file(matching_archives[0]) != manifest.source_archive.sha256:
        return _result(
            RawIdentityState.SOURCE_IDENTITY_AMBIGUOUS,
            "SOURCE_ARCHIVE_HASH_MISMATCH",
            paths=(f"archives/{matching_archives[0].name}",),
            manifest=manifest,
        )
    manifest_dir = root / "manifests"
    expected_manifest_relative = Path(manifest_relative_path).relative_to(
        "manifests"
    ).as_posix()
    manifest_files = [
        path
        for path in manifest_dir.rglob("*")
        if path.is_file() or path.is_symlink()
    ]
    unexpected_manifests = tuple(
        sorted(
            f"manifests/{path.relative_to(manifest_dir).as_posix()}"
            for path in manifest_files
            if path.is_symlink()
            or path.relative_to(manifest_dir).as_posix() != expected_manifest_relative
        )
    )
    if unexpected_manifests:
        return _result(
            RawIdentityState.UNEXPECTED_FILE,
            "UNMANAGED_MANIFEST_FILE_PRESENT",
            paths=unexpected_manifests,
            manifest=manifest,
        )
    raw_root = root / raw_relative_path
    if not raw_root.is_dir() or raw_root.is_symlink():
        return _result(
            RawIdentityState.PARTIAL,
            "RAW_DIRECTORY_MISSING",
            paths=(raw_relative_path,),
            manifest=manifest,
        )
    symlinks = tuple(
        sorted(
            path.relative_to(raw_root).as_posix()
            for path in raw_root.rglob("*")
            if path.is_symlink()
        )
    )
    if symlinks:
        return _result(
            RawIdentityState.UNEXPECTED_FILE,
            "RAW_SYMLINK_REJECTED",
            paths=symlinks,
            manifest=manifest,
        )
    actual = {
        path.relative_to(raw_root).as_posix(): path
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    expected = {record.relative_path: record for record in manifest.files}
    missing = tuple(sorted(set(expected) - set(actual)))
    if missing:
        return _result(
            RawIdentityState.PARTIAL,
            "EXPECTED_RAW_FILE_MISSING",
            paths=missing,
            manifest=manifest,
            observed=len(actual),
        )
    unexpected = tuple(sorted(set(actual) - set(expected)))
    if unexpected:
        return _result(
            RawIdentityState.UNEXPECTED_FILE,
            "UNMANAGED_RAW_FILE_PRESENT",
            paths=unexpected,
            manifest=manifest,
            observed=len(actual),
        )
    mismatched = tuple(
        sorted(
            relative
            for relative, record in expected.items()
            if actual[relative].stat().st_size != record.byte_size
            or sha256_file(actual[relative]) != record.sha256
        )
    )
    if mismatched:
        return _result(
            RawIdentityState.HASH_MISMATCH,
            "RAW_FILE_IDENTITY_MISMATCH",
            paths=mismatched,
            manifest=manifest,
            observed=len(actual),
        )
    inventory: Inventory = build_inventory(
        manifest.files,
        expected_file_count=expected_file_count,
        expected_subject_count=expected_subject_count,
    )
    if not inventory.matches_expectations:
        return _result(
            RawIdentityState.INVENTORY_MISMATCH,
            "EXPECTED_OBSERVED_INVENTORY_MISMATCH",
            manifest=manifest,
            observed=len(actual),
        )
    if not (root / MANAGED_CACHE_MARKER).is_file():
        return _result(
            RawIdentityState.MANIFEST_INVALID,
            "MANAGED_CACHE_MARKER_MISSING",
            manifest=manifest,
            observed=len(actual),
        )
    return _result(
        RawIdentityState.PASS,
        "CONTROLLED_SYNTHETIC_IDENTITY_VERIFIED",
        manifest=manifest,
        observed=len(actual),
    )
