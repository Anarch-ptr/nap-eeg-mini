"""Controlled, transport-injected download and safe extraction primitives."""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import shutil
import stat
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Iterable

from .network_policy import DownloadTransport, NetworkPolicy


MANAGED_CACHE_MARKER = ".phase_ii_b_managed.json"
MANAGED_CACHE_SCHEMA = "NAP_EEG_MINI_PHASE_II_B_CACHE_V1"
MANAGED_TOP_LEVEL = frozenset(
    {MANAGED_CACHE_MARKER, "archives", "raw", "manifests"}
)


class AcquisitionFailureReason(str, Enum):
    CACHE_ROOT_REQUIRED = "CACHE_ROOT_REQUIRED"
    CACHE_ROOT_INSIDE_REPOSITORY = "CACHE_ROOT_INSIDE_REPOSITORY"
    GLOBAL_CACHE_PATH_REJECTED = "GLOBAL_CACHE_PATH_REJECTED"
    PERSISTENT_SYSTEM_TEMP_REJECTED = "PERSISTENT_SYSTEM_TEMP_REJECTED"
    CACHE_ROOT_NOT_DIRECTORY = "CACHE_ROOT_NOT_DIRECTORY"
    CACHE_ROOT_UNMANAGED = "CACHE_ROOT_UNMANAGED"
    CACHE_ROOT_CONTAINS_UNEXPECTED_FILES = "CACHE_ROOT_CONTAINS_UNEXPECTED_FILES"
    SOURCE_IDENTITY_INVALID = "SOURCE_IDENTITY_INVALID"
    FINAL_TARGET_EXISTS = "FINAL_TARGET_EXISTS"
    PARTIAL_TARGET_EXISTS = "PARTIAL_TARGET_EXISTS"
    HTTP_STATUS_ERROR = "HTTP_STATUS_ERROR"
    ZERO_BYTE_PAYLOAD = "ZERO_BYTE_PAYLOAD"
    BYTE_COUNT_MISMATCH = "BYTE_COUNT_MISMATCH"
    HASH_MISMATCH = "HASH_MISMATCH"
    HTML_OR_ERROR_PAYLOAD = "HTML_OR_ERROR_PAYLOAD"
    STREAM_FAILURE = "STREAM_FAILURE"
    UNSAFE_ARCHIVE_PATH = "UNSAFE_ARCHIVE_PATH"
    ARCHIVE_LINK_REJECTED = "ARCHIVE_LINK_REJECTED"
    DUPLICATE_ARCHIVE_TARGET = "DUPLICATE_ARCHIVE_TARGET"
    CASE_COLLISION = "CASE_COLLISION"
    EXTRACTION_TARGET_EXISTS = "EXTRACTION_TARGET_EXISTS"
    EXTRACTION_SIZE_LIMIT_EXCEEDED = "EXTRACTION_SIZE_LIMIT_EXCEEDED"
    EXPANSION_RATIO_EXCEEDED = "EXPANSION_RATIO_EXCEEDED"
    UNSUPPORTED_ARCHIVE = "UNSUPPORTED_ARCHIVE"
    UNSUPPORTED_ARCHIVE_MEMBER = "UNSUPPORTED_ARCHIVE_MEMBER"
    ILLEGAL_FILENAME = "ILLEGAL_FILENAME"


class AcquisitionError(RuntimeError):
    def __init__(
        self,
        reason: AcquisitionFailureReason,
        *,
        affected_path: str | None = None,
    ):
        self.reason = reason
        self.affected_path = affected_path
        suffix = f":{affected_path}" if affected_path else ""
        super().__init__(reason.value + suffix)


def _canonical(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def known_global_cache_paths(home: str | Path | None = None) -> tuple[Path, ...]:
    root = _canonical(home if home is not None else Path.home())
    return tuple(
        _canonical(root / relative)
        for relative in ("mne_data", ".mne", "moabb", ".moabb")
    )


def _system_temp_root() -> Path:
    return _canonical(tempfile.gettempdir())


def validate_cache_root(
    cache_root: str | Path | None,
    *,
    repository_root: str | Path,
    require_managed: bool = True,
    allow_temporary: bool = False,
    home: str | Path | None = None,
) -> Path:
    if cache_root is None or not str(cache_root).strip():
        raise AcquisitionError(AcquisitionFailureReason.CACHE_ROOT_REQUIRED)
    root = _canonical(cache_root)
    repository = _canonical(repository_root)
    if _inside(root, repository):
        raise AcquisitionError(
            AcquisitionFailureReason.CACHE_ROOT_INSIDE_REPOSITORY,
            affected_path=str(root),
        )
    if any(_same_path(root, candidate) or _inside(root, candidate) for candidate in known_global_cache_paths(home)):
        raise AcquisitionError(
            AcquisitionFailureReason.GLOBAL_CACHE_PATH_REJECTED,
            affected_path=str(root),
        )
    if not allow_temporary and _inside(root, _system_temp_root()):
        raise AcquisitionError(
            AcquisitionFailureReason.PERSISTENT_SYSTEM_TEMP_REJECTED,
            affected_path=str(root),
        )
    if root.exists() and not root.is_dir():
        raise AcquisitionError(
            AcquisitionFailureReason.CACHE_ROOT_NOT_DIRECTORY,
            affected_path=str(root),
        )
    if not root.exists():
        if require_managed:
            raise AcquisitionError(
                AcquisitionFailureReason.CACHE_ROOT_UNMANAGED,
                affected_path=str(root),
            )
        return root
    names = {child.name for child in root.iterdir()}
    unexpected = sorted(names - MANAGED_TOP_LEVEL)
    if unexpected:
        raise AcquisitionError(
            AcquisitionFailureReason.CACHE_ROOT_CONTAINS_UNEXPECTED_FILES,
            affected_path=unexpected[0],
        )
    symlinks = sorted(child.name for child in root.iterdir() if child.is_symlink())
    if symlinks:
        raise AcquisitionError(
            AcquisitionFailureReason.CACHE_ROOT_CONTAINS_UNEXPECTED_FILES,
            affected_path=symlinks[0],
        )
    marker = root / MANAGED_CACHE_MARKER
    if require_managed:
        try:
            if marker.is_symlink() or not marker.is_file():
                raise OSError("managed-cache marker is not a regular file")
            marker_payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AcquisitionError(
                AcquisitionFailureReason.CACHE_ROOT_UNMANAGED,
                affected_path=str(marker),
            ) from exc
        if marker_payload != {"schema": MANAGED_CACHE_SCHEMA}:
            raise AcquisitionError(
                AcquisitionFailureReason.CACHE_ROOT_UNMANAGED,
                affected_path=str(marker),
            )
    return root


def initialize_managed_cache(
    cache_root: str | Path,
    *,
    repository_root: str | Path,
    allow_temporary: bool = False,
    home: str | Path | None = None,
) -> Path:
    root = validate_cache_root(
        cache_root,
        repository_root=repository_root,
        require_managed=False,
        allow_temporary=allow_temporary,
        home=home,
    )
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise AcquisitionError(
            AcquisitionFailureReason.CACHE_ROOT_CONTAINS_UNEXPECTED_FILES,
            affected_path=str(root),
        )
    marker = root / MANAGED_CACHE_MARKER
    marker.write_text(
        json.dumps({"schema": MANAGED_CACHE_SCHEMA}, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return root


@dataclass(frozen=True)
class DownloadReceipt:
    source_url: str
    target: Path
    downloaded_byte_count: int
    sha256: str
    http_status: int
    content_length: int | None
    content_type: str | None
    etag: str | None
    last_modified: str | None
    redirect_chain: tuple[str, ...]
    transport_identifier: str


def _header(headers: dict[str, str], name: str) -> str | None:
    wanted = name.casefold()
    return next((value for key, value in headers.items() if key.casefold() == wanted), None)


def _looks_like_html(prefix: bytes) -> bool:
    lowered = prefix.lstrip().lower()
    return (
        lowered.startswith(b"<!doctype html")
        or lowered.startswith(b"<html")
        or lowered.startswith(b"<?xml")
        or b"<html" in lowered[:512]
    )


def atomic_download(
    *,
    source_url: str,
    target: str | Path,
    policy: NetworkPolicy,
    transport: DownloadTransport | None,
    expected_length: int | None = None,
    expected_sha256: str | None = None,
) -> DownloadReceipt:
    authorized_transport = policy.authorize_transport(transport)
    destination = Path(target)
    partial = destination.with_name(destination.name + ".partial")
    if destination.exists():
        raise AcquisitionError(
            AcquisitionFailureReason.FINAL_TARGET_EXISTS,
            affected_path=str(destination),
        )
    if partial.exists():
        raise AcquisitionError(
            AcquisitionFailureReason.PARTIAL_TARGET_EXISTS,
            affected_path=str(partial),
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    created_partial = False
    try:
        response = authorized_transport.open(source_url)
        if response.status < 200 or response.status >= 300:
            raise AcquisitionError(AcquisitionFailureReason.HTTP_STATUS_ERROR)
        headers = dict(response.headers or {})
        content_type = _header(headers, "Content-Type")
        if content_type and ("text/html" in content_type.casefold() or "application/xhtml" in content_type.casefold()):
            raise AcquisitionError(AcquisitionFailureReason.HTML_OR_ERROR_PAYLOAD)
        digest = hashlib.sha256()
        byte_count = 0
        prefix = bytearray()
        with partial.open("xb") as stream:
            created_partial = True
            for chunk in response.chunks:
                if not isinstance(chunk, bytes):
                    raise TypeError("transport chunks must be bytes")
                if chunk:
                    if len(prefix) < 512:
                        prefix.extend(chunk[: 512 - len(prefix)])
                    stream.write(chunk)
                    digest.update(chunk)
                    byte_count += len(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if byte_count == 0:
            raise AcquisitionError(AcquisitionFailureReason.ZERO_BYTE_PAYLOAD)
        if _looks_like_html(bytes(prefix)):
            raise AcquisitionError(AcquisitionFailureReason.HTML_OR_ERROR_PAYLOAD)
        content_length_text = _header(headers, "Content-Length")
        try:
            content_length = (
                int(content_length_text) if content_length_text is not None else None
            )
        except ValueError:
            content_length = None
        if expected_length is not None and byte_count != expected_length:
            raise AcquisitionError(AcquisitionFailureReason.BYTE_COUNT_MISMATCH)
        if content_length is not None and byte_count != content_length:
            raise AcquisitionError(AcquisitionFailureReason.BYTE_COUNT_MISMATCH)
        observed_sha256 = digest.hexdigest()
        if expected_sha256 is not None and observed_sha256 != expected_sha256.lower():
            raise AcquisitionError(AcquisitionFailureReason.HASH_MISMATCH)
        # Hard-link publication is atomic on the same filesystem and, unlike
        # os.replace, cannot overwrite a target introduced by a concurrent process.
        os.link(partial, destination)
        partial.unlink()
        created_partial = False
        return DownloadReceipt(
            source_url=source_url,
            target=destination,
            downloaded_byte_count=byte_count,
            sha256=observed_sha256,
            http_status=response.status,
            content_length=content_length,
            content_type=content_type,
            etag=_header(headers, "ETag"),
            last_modified=_header(headers, "Last-Modified"),
            redirect_chain=tuple(response.redirect_chain),
            transport_identifier=response.transport_identifier,
        )
    except AcquisitionError:
        raise
    except Exception as exc:
        raise AcquisitionError(AcquisitionFailureReason.STREAM_FAILURE) from exc
    finally:
        if created_partial:
            try:
                partial.unlink()
            except FileNotFoundError:
                pass


_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def _safe_member_path(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    drive, _tail = ntpath.splitdrive(name)
    if (
        not normalized
        or normalized.startswith(("/", "//"))
        or drive
        or name.startswith("\\\\")
    ):
        raise AcquisitionError(
            AcquisitionFailureReason.UNSAFE_ARCHIVE_PATH,
            affected_path=name,
        )
    path = PurePosixPath(normalized)
    if any(part in ("", ".", "..") for part in path.parts):
        raise AcquisitionError(
            AcquisitionFailureReason.UNSAFE_ARCHIVE_PATH,
            affected_path=name,
        )
    for part in path.parts:
        stem = part.split(".", 1)[0].upper()
        if (
            stem in _WINDOWS_RESERVED
            or part.endswith((" ", "."))
            or any(ord(character) < 32 for character in part)
            or any(character in '<>:"|?*' for character in part)
        ):
            raise AcquisitionError(
                AcquisitionFailureReason.ILLEGAL_FILENAME,
                affected_path=name,
            )
    return path


@dataclass(frozen=True)
class _ArchiveMember:
    name: str
    path: PurePosixPath
    size: int
    is_directory: bool
    source: object


def _zip_members(archive: zipfile.ZipFile) -> list[_ArchiveMember]:
    members: list[_ArchiveMember] = []
    for info in archive.infolist():
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise AcquisitionError(
                AcquisitionFailureReason.ARCHIVE_LINK_REJECTED,
                affected_path=info.filename,
            )
        file_type = stat.S_IFMT(mode)
        if file_type and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise AcquisitionError(
                AcquisitionFailureReason.UNSUPPORTED_ARCHIVE_MEMBER,
                affected_path=info.filename,
            )
        members.append(
            _ArchiveMember(
                name=info.filename,
                path=_safe_member_path(info.filename.rstrip("/")),
                size=info.file_size,
                is_directory=info.is_dir(),
                source=info,
            )
        )
    return members


def _tar_members(archive: tarfile.TarFile) -> list[_ArchiveMember]:
    members: list[_ArchiveMember] = []
    for info in archive.getmembers():
        if info.issym() or info.islnk():
            raise AcquisitionError(
                AcquisitionFailureReason.ARCHIVE_LINK_REJECTED,
                affected_path=info.name,
            )
        if not (info.isfile() or info.isdir()):
            raise AcquisitionError(
                AcquisitionFailureReason.UNSUPPORTED_ARCHIVE_MEMBER,
                affected_path=info.name,
            )
        members.append(
            _ArchiveMember(
                name=info.name,
                path=_safe_member_path(info.name.rstrip("/")),
                size=info.size,
                is_directory=info.isdir(),
                source=info,
            )
        )
    return members


def _validate_member_set(
    members: Iterable[_ArchiveMember],
    *,
    archive_size: int,
    max_total_size: int,
    max_expansion_ratio: float,
) -> None:
    exact: set[str] = set()
    folded: set[str] = set()
    total = 0
    for member in members:
        target = member.path.as_posix()
        folded_target = target.casefold()
        if target in exact:
            raise AcquisitionError(
                AcquisitionFailureReason.DUPLICATE_ARCHIVE_TARGET,
                affected_path=target,
            )
        if folded_target in folded:
            raise AcquisitionError(
                AcquisitionFailureReason.CASE_COLLISION,
                affected_path=target,
            )
        exact.add(target)
        folded.add(folded_target)
        total += member.size
    if total > max_total_size:
        raise AcquisitionError(
            AcquisitionFailureReason.EXTRACTION_SIZE_LIMIT_EXCEEDED
        )
    if archive_size <= 0 or total / archive_size > max_expansion_ratio:
        raise AcquisitionError(AcquisitionFailureReason.EXPANSION_RATIO_EXCEEDED)


def safe_extract_archive(
    archive_path: str | Path,
    destination: str | Path,
    *,
    max_total_size: int = 10 * 1024 * 1024 * 1024,
    max_expansion_ratio: float = 200.0,
) -> tuple[Path, ...]:
    source = Path(archive_path)
    target = Path(destination)
    if target.exists():
        raise AcquisitionError(
            AcquisitionFailureReason.EXTRACTION_TARGET_EXISTS,
            affected_path=str(target),
        )
    stage = target.with_name(target.name + ".extracting")
    if stage.exists():
        raise AcquisitionError(
            AcquisitionFailureReason.EXTRACTION_TARGET_EXISTS,
            affected_path=str(stage),
        )
    archive_size = source.stat().st_size
    stage.mkdir(parents=True)
    created: list[Path] = []
    try:
        if zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as archive:
                members = _zip_members(archive)
                _validate_member_set(
                    members,
                    archive_size=archive_size,
                    max_total_size=max_total_size,
                    max_expansion_ratio=max_expansion_ratio,
                )
                for member in members:
                    output = stage.joinpath(*member.path.parts)
                    if member.is_directory:
                        output.mkdir(parents=True, exist_ok=True)
                        continue
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member.source) as incoming, output.open("xb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                    created.append(output)
        elif tarfile.is_tarfile(source):
            with tarfile.open(source, mode="r:*") as archive:
                members = _tar_members(archive)
                _validate_member_set(
                    members,
                    archive_size=archive_size,
                    max_total_size=max_total_size,
                    max_expansion_ratio=max_expansion_ratio,
                )
                for member in members:
                    output = stage.joinpath(*member.path.parts)
                    if member.is_directory:
                        output.mkdir(parents=True, exist_ok=True)
                        continue
                    output.parent.mkdir(parents=True, exist_ok=True)
                    incoming = archive.extractfile(member.source)
                    if incoming is None:
                        raise AcquisitionError(
                            AcquisitionFailureReason.UNSUPPORTED_ARCHIVE_MEMBER,
                            affected_path=member.name,
                        )
                    with incoming, output.open("xb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                    created.append(output)
        else:
            raise AcquisitionError(AcquisitionFailureReason.UNSUPPORTED_ARCHIVE)
        stage.rename(target)
        return tuple(
            target / path.relative_to(stage)
            for path in sorted(created, key=lambda item: item.as_posix().casefold())
        )
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
