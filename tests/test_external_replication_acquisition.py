from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import warnings
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.external_replication.acquisition import (
    AcquisitionError,
    AcquisitionFailureReason,
    atomic_download,
    initialize_managed_cache,
    safe_extract_archive,
    validate_cache_root,
)
from src.external_replication.network_policy import (
    AcquisitionAuthorization,
    AcquisitionMode,
    AuthorizationState,
    NetworkFailureReason,
    NetworkPolicy,
    NetworkPolicyError,
    TransportResponse,
)
from src.external_replication.raw_identity import (
    RawIdentityState,
    evaluate_raw_identity_gate,
)
from src.external_replication.raw_manifest import (
    ArchiveRecord,
    ExtractedManifest,
    ManifestError,
    RawFileRecord,
    build_inventory,
    canonical_json_bytes,
    manifest_from_dict,
    raw_file_record,
    read_manifest,
    write_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "acquire_lee2019_mi.py"
FIXED_TIME = "2026-07-24T00:00:00Z"


class FakeTransport:
    def __init__(
        self,
        payload: bytes = b"synthetic archive bytes",
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        redirects: tuple[str, ...] = (),
        chunks=None,
    ):
        self.payload = payload
        self.status = status
        self.headers = headers or {}
        self.redirects = redirects
        self.custom_chunks = chunks
        self.calls = 0

    def open(self, _source_url: str) -> TransportResponse:
        self.calls += 1
        chunks = self.custom_chunks if self.custom_chunks is not None else (self.payload,)
        return TransportResponse(
            status=self.status,
            chunks=chunks,
            headers=self.headers,
            redirect_chain=self.redirects,
            transport_identifier="SYNTHETIC_FAKE_TRANSPORT",
        )


def authorized_policy() -> NetworkPolicy:
    return NetworkPolicy(
        authorization=AcquisitionAuthorization.explicitly_authorized_for_acquisition()
    )


def archive_record(archive_path: Path) -> ArchiveRecord:
    payload = archive_path.read_bytes()
    return ArchiveRecord(
        schema_version=1,
        dataset_name="Lee2019_MI",
        implementation_identifier="synthetic-test",
        source_url="https://example.invalid/synthetic.zip",
        retrieval_timestamp=FIXED_TIME,
        http_status=200,
        content_length=len(payload),
        etag=None,
        last_modified=None,
        redirect_chain=(),
        archive_filename=archive_path.name,
        downloaded_byte_count=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        transport_identifier="SYNTHETIC_FAKE_TRANSPORT",
    )


class PhaseIIBFixture(unittest.TestCase):
    def make_directory(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def managed_cache(self) -> Path:
        root = self.make_directory() / "controlled-cache"
        return initialize_managed_cache(
            root,
            repository_root=REPO_ROOT,
            allow_temporary=True,
        )

    def frozen_cache(
        self,
        *,
        files: dict[str, bytes] | None = None,
        expected_subjects: int = 2,
    ) -> tuple[Path, ExtractedManifest]:
        cache = self.managed_cache()
        archive_path = cache / "archives" / "synthetic.zip"
        archive_path.parent.mkdir()
        archive_path.write_bytes(b"synthetic archive identity")
        raw_root = cache / "raw"
        records = []
        items = files or {
            "subject-01/session-1/run-1.bin": b"alpha",
            "subject-02/session-1/run-1.bin": b"beta",
        }
        for index, (relative, payload) in enumerate(sorted(items.items()), 1):
            path = raw_root / Path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            records.append(
                raw_file_record(
                    path,
                    relative_to=raw_root,
                    source_archive_sha256=archive_record(archive_path).sha256,
                    subject_id=f"{index:02d}",
                    session_id="S1",
                    run_id="R1",
                    role="TRAINING_VALIDATION_SOURCE",
                    label_status="LABELED",
                    acquisition_status="OFFLINE",
                )
            )
        manifest = ExtractedManifest(
            schema_version=1,
            dataset_name="Lee2019_MI",
            source_archive=archive_record(archive_path),
            generated_timestamp=FIXED_TIME,
            files=tuple(records),
        )
        path = cache / "manifests" / "raw_manifest.json"
        write_manifest(path, manifest)
        frozen = read_manifest(path)
        self.assertEqual(len(frozen.files), expected_subjects)
        return cache, frozen

    def write_zip(
        self,
        entries: list[tuple[str | zipfile.ZipInfo, bytes]],
        *,
        compression: int = zipfile.ZIP_STORED,
    ) -> Path:
        path = self.make_directory() / "fixture.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "w", compression=compression) as archive:
                for name, payload in entries:
                    archive.writestr(name, payload)
        return path


class DownloadAndPolicyTests(PhaseIIBFixture):
    def test_01_02_03_successful_fake_atomic_download_count_and_sha256(self):
        root = self.make_directory()
        payload = b"controlled synthetic payload"
        target = root / "archive.bin"
        receipt = atomic_download(
            source_url="https://example.invalid/archive",
            target=target,
            policy=authorized_policy(),
            transport=FakeTransport(
                payload,
                headers={"Content-Length": str(len(payload))},
            ),
            expected_length=len(payload),
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )
        self.assertEqual(target.read_bytes(), payload)
        self.assertFalse((root / "archive.bin.partial").exists())
        self.assertEqual(receipt.downloaded_byte_count, len(payload))
        self.assertEqual(receipt.sha256, hashlib.sha256(payload).hexdigest())

    def test_14_interrupted_stream_removes_only_created_partial(self):
        def interrupted():
            yield b"prefix"
            raise OSError("synthetic interruption")

        root = self.make_directory()
        target = root / "archive.bin"
        with self.assertRaisesRegex(AcquisitionError, "STREAM_FAILURE"):
            atomic_download(
                source_url="https://example.invalid/archive",
                target=target,
                policy=authorized_policy(),
                transport=FakeTransport(chunks=interrupted()),
            )
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name("archive.bin.partial").exists())

    def test_15_16_17_zero_length_count_and_hash_mismatches(self):
        cases = (
            (FakeTransport(b""), {}, AcquisitionFailureReason.ZERO_BYTE_PAYLOAD),
            (
                FakeTransport(b"abc"),
                {"expected_length": 4},
                AcquisitionFailureReason.BYTE_COUNT_MISMATCH,
            ),
            (
                FakeTransport(b"abc"),
                {"expected_sha256": "0" * 64},
                AcquisitionFailureReason.HASH_MISMATCH,
            ),
        )
        for index, (transport, kwargs, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                target = self.make_directory() / f"archive-{index}.bin"
                with self.assertRaises(AcquisitionError) as caught:
                    atomic_download(
                        source_url="https://example.invalid/archive",
                        target=target,
                        policy=authorized_policy(),
                        transport=transport,
                        **kwargs,
                    )
                self.assertEqual(caught.exception.reason, reason)
                self.assertFalse(target.exists())

    def test_18_html_payload_rejected_by_content_type_and_prefix(self):
        for transport in (
            FakeTransport(b"not html", headers={"Content-Type": "text/html"}),
            FakeTransport(b"  <!DOCTYPE html><html>error</html>"),
        ):
            with self.subTest(headers=transport.headers):
                target = self.make_directory() / "archive.bin"
                with self.assertRaisesRegex(AcquisitionError, "HTML_OR_ERROR_PAYLOAD"):
                    atomic_download(
                        source_url="https://example.invalid/archive",
                        target=target,
                        policy=authorized_policy(),
                        transport=transport,
                    )

    def test_19_20_existing_final_and_stale_partial_conflicts(self):
        root = self.make_directory()
        final = root / "archive.bin"
        final.write_bytes(b"preserve")
        with self.assertRaisesRegex(AcquisitionError, "FINAL_TARGET_EXISTS"):
            atomic_download(
                source_url="https://example.invalid",
                target=final,
                policy=authorized_policy(),
                transport=FakeTransport(),
            )
        self.assertEqual(final.read_bytes(), b"preserve")
        final.unlink()
        partial = root / "archive.bin.partial"
        partial.write_bytes(b"preserve partial")
        with self.assertRaisesRegex(AcquisitionError, "PARTIAL_TARGET_EXISTS"):
            atomic_download(
                source_url="https://example.invalid",
                target=final,
                policy=authorized_policy(),
                transport=FakeTransport(),
            )
        self.assertEqual(partial.read_bytes(), b"preserve partial")

    def test_21_redirect_metadata_is_recorded(self):
        target = self.make_directory() / "archive.bin"
        receipt = atomic_download(
            source_url="https://example.invalid/original",
            target=target,
            policy=authorized_policy(),
            transport=FakeTransport(
                redirects=(
                    "https://example.invalid/first",
                    "https://example.invalid/final",
                )
            ),
        )
        self.assertEqual(len(receipt.redirect_chain), 2)

    def test_22_identical_filename_different_content_is_not_overwritten(self):
        target = self.make_directory() / "same.bin"
        target.write_bytes(b"first")
        with self.assertRaisesRegex(AcquisitionError, "FINAL_TARGET_EXISTS"):
            atomic_download(
                source_url="https://example.invalid/second",
                target=target,
                policy=authorized_policy(),
                transport=FakeTransport(b"second"),
            )
        self.assertEqual(target.read_bytes(), b"first")

    def test_23_fake_http_error_status(self):
        transport = FakeTransport(status=503)
        with self.assertRaisesRegex(AcquisitionError, "HTTP_STATUS_ERROR"):
            atomic_download(
                source_url="https://example.invalid",
                target=self.make_directory() / "archive.bin",
                policy=authorized_policy(),
                transport=transport,
            )

    def test_54_scientific_mode_cannot_request_acquisition(self):
        policy = NetworkPolicy(
            authorization=AcquisitionAuthorization.explicitly_authorized_for_acquisition(),
            mode=AcquisitionMode.SCIENTIFIC_EXECUTION,
        )
        with self.assertRaises(NetworkPolicyError) as caught:
            policy.authorize_transport(FakeTransport())
        self.assertEqual(
            caught.exception.reason,
            NetworkFailureReason.SCIENTIFIC_EXECUTION_FORBIDS_ACQUISITION,
        )

    def test_55_default_authorization_remains_deny(self):
        authorization = AcquisitionAuthorization()
        self.assertEqual(authorization.acquisition, AuthorizationState.DENY)
        self.assertEqual(authorization.network, AuthorizationState.DENY)
        self.assertEqual(
            authorization.scientific_execution, AuthorizationState.DENY
        )
        with self.assertRaisesRegex(NetworkPolicyError, "ACQUISITION_NOT_AUTHORIZED"):
            NetworkPolicy().authorize_transport(FakeTransport())


class ManifestAndInventoryTests(PhaseIIBFixture):
    def test_04_05_06_30_deterministic_round_trip_and_self_identity(self):
        cache, manifest = self.frozen_cache()
        reversed_manifest = replace(manifest, files=tuple(reversed(manifest.files)))
        first = manifest.to_bytes()
        second = reversed_manifest.to_bytes()
        self.assertEqual(first, second)
        round_trip = read_manifest(cache / "manifests" / "raw_manifest.json")
        self.assertEqual(round_trip.to_bytes(), first)
        self.assertEqual(round_trip.manifest_payload_sha256, round_trip.payload_sha256())

    def test_08_extracted_file_hashing(self):
        root = self.make_directory()
        path = root / "raw.bin"
        path.write_bytes(b"synthetic")
        record = raw_file_record(
            path,
            relative_to=root,
            source_archive_sha256="a" * 64,
        )
        self.assertEqual(record.byte_size, 9)
        self.assertEqual(record.sha256, hashlib.sha256(b"synthetic").hexdigest())

    def test_09_synthetic_inventory_generation(self):
        _cache, manifest = self.frozen_cache()
        inventory = build_inventory(
            manifest.files,
            expected_file_count=2,
            expected_subject_count=2,
        )
        self.assertTrue(inventory.matches_expectations)
        self.assertEqual(inventory.subject_ids, ("01", "02"))
        self.assertEqual(inventory.label_status_counts, (("LABELED", 2),))
        self.assertEqual(inventory.acquisition_status_counts, (("OFFLINE", 2),))

    def test_24_missing_required_fields(self):
        _cache, manifest = self.frozen_cache()
        payload = json.loads(manifest.to_bytes())
        payload.pop("files")
        with self.assertRaisesRegex(ManifestError, "MANIFEST_REQUIRED_FIELDS_MISMATCH"):
            manifest_from_dict(payload)

    def test_25_malformed_json(self):
        path = self.make_directory() / "manifest.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(ManifestError, "MANIFEST_JSON_INVALID"):
            read_manifest(path)

    def test_26_unsupported_schema_version(self):
        _cache, manifest = self.frozen_cache()
        payload = json.loads(manifest.to_bytes())
        payload["schema_version"] = 999
        with self.assertRaisesRegex(ManifestError, "UNSUPPORTED_SCHEMA_VERSION"):
            manifest_from_dict(payload)

    def test_27_manifest_payload_changed_after_creation(self):
        _cache, manifest = self.frozen_cache()
        payload = json.loads(manifest.to_bytes())
        payload["generated_timestamp"] = "changed"
        with self.assertRaisesRegex(ManifestError, "MANIFEST_PAYLOAD_SHA256_MISMATCH"):
            manifest_from_dict(payload)

    def test_28_archive_file_mapping_incomplete(self):
        _cache, manifest = self.frozen_cache()
        changed = replace(manifest.files[0], source_archive_sha256="0" * 64)
        with self.assertRaisesRegex(ManifestError, "ARCHIVE_FILE_MAPPING_INCOMPLETE"):
            replace(manifest, files=(changed, *manifest.files[1:])).to_bytes()

    def test_29_duplicated_raw_file_record(self):
        _cache, manifest = self.frozen_cache()
        with self.assertRaisesRegex(ManifestError, "DUPLICATE_RAW_FILE_RECORD"):
            replace(manifest, files=(manifest.files[0], manifest.files[0])).to_bytes()

    def test_56_57_revision_independent_separator_normalization(self):
        forward = RawFileRecord(
            relative_path="subject/run.bin",
            byte_size=1,
            sha256="a" * 64,
            source_archive_sha256="b" * 64,
        )
        backward = replace(forward, relative_path=r"subject\run.bin")
        archive = ArchiveRecord(
            schema_version=1,
            dataset_name="Lee2019_MI",
            implementation_identifier=None,
            source_url=None,
            retrieval_timestamp=FIXED_TIME,
            http_status=None,
            content_length=None,
            etag=None,
            last_modified=None,
            redirect_chain=(),
            archive_filename="fixture.zip",
            downloaded_byte_count=1,
            sha256="b" * 64,
            transport_identifier="SYNTHETIC",
        )
        left = ExtractedManifest(1, "Lee2019_MI", archive, FIXED_TIME, (forward,))
        right = ExtractedManifest(1, "Lee2019_MI", archive, FIXED_TIME, (backward,))
        self.assertEqual(left.to_bytes(), right.to_bytes())
        self.assertNotIn(str(REPO_ROOT).encode(), left.to_bytes())

    def test_59_utf8_manifest_serialization_is_deterministic(self):
        payload = {"role": "S1-离线", "dataset": "Lee2019_MI"}
        first = canonical_json_bytes(payload)
        second = canonical_json_bytes(dict(reversed(tuple(payload.items()))))
        self.assertEqual(first, second)
        self.assertIn("离线".encode("utf-8"), first)


class SafeExtractionTests(PhaseIIBFixture):
    def test_07_safe_extraction_of_ordinary_files(self):
        archive = self.write_zip([
            ("folder/a.bin", b"alpha"),
            ("folder/b.bin", b"beta"),
        ])
        destination = self.make_directory() / "raw"
        extracted = safe_extract_archive(archive, destination)
        self.assertEqual(
            tuple(path.relative_to(destination).as_posix() for path in extracted),
            ("folder/a.bin", "folder/b.bin"),
        )
        self.assertEqual((destination / "folder" / "a.bin").read_bytes(), b"alpha")

    def test_31_32_33_34_unsafe_path_forms(self):
        attacks = ("../escape.bin", "/absolute.bin", r"C:\drive.bin", r"\\server\share.bin")
        for name in attacks:
            with self.subTest(name=name):
                archive = self.write_zip([(name, b"x")])
                destination = self.make_directory() / "raw"
                with self.assertRaisesRegex(AcquisitionError, "UNSAFE_ARCHIVE_PATH"):
                    safe_extract_archive(archive, destination)
                self.assertFalse(destination.exists())

    def test_35_zip_symlink_member(self):
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive = self.write_zip([(link, b"target")])
        with self.assertRaisesRegex(AcquisitionError, "ARCHIVE_LINK_REJECTED"):
            safe_extract_archive(archive, self.make_directory() / "raw")

    def test_36_duplicate_extraction_target(self):
        archive = self.write_zip([("same.bin", b"a"), ("same.bin", b"b")])
        with self.assertRaisesRegex(AcquisitionError, "DUPLICATE_ARCHIVE_TARGET"):
            safe_extract_archive(archive, self.make_directory() / "raw")

    def test_37_58_case_colliding_paths(self):
        archive = self.write_zip([("Subject/A.bin", b"a"), ("subject/a.BIN", b"b")])
        with self.assertRaisesRegex(AcquisitionError, "CASE_COLLISION"):
            safe_extract_archive(archive, self.make_directory() / "raw")

    def test_38_existing_file_overwrite_attempt(self):
        archive = self.write_zip([("a.bin", b"new")])
        destination = self.make_directory() / "raw"
        destination.mkdir()
        existing = destination / "a.bin"
        existing.write_bytes(b"preserve")
        with self.assertRaisesRegex(AcquisitionError, "EXTRACTION_TARGET_EXISTS"):
            safe_extract_archive(archive, destination)
        self.assertEqual(existing.read_bytes(), b"preserve")

    def test_39_total_extraction_size_limit(self):
        archive = self.write_zip([("large.bin", b"x" * 20)])
        with self.assertRaisesRegex(AcquisitionError, "EXTRACTION_SIZE_LIMIT_EXCEEDED"):
            safe_extract_archive(
                archive,
                self.make_directory() / "raw",
                max_total_size=10,
            )

    def test_40_suspicious_expansion_ratio(self):
        archive = self.write_zip(
            [("compressed.bin", b"x" * 10000)],
            compression=zipfile.ZIP_DEFLATED,
        )
        with self.assertRaisesRegex(AcquisitionError, "EXPANSION_RATIO_EXCEEDED"):
            safe_extract_archive(
                archive,
                self.make_directory() / "raw",
                max_expansion_ratio=2.0,
            )

    def test_41_unsupported_tar_member_type(self):
        path = self.make_directory() / "fixture.tar"
        with tarfile.open(path, "w") as archive:
            item = tarfile.TarInfo("fifo")
            item.type = tarfile.FIFOTYPE
            archive.addfile(item)
        with self.assertRaisesRegex(AcquisitionError, "UNSUPPORTED_ARCHIVE_MEMBER"):
            safe_extract_archive(path, self.make_directory() / "raw")

    def test_42_illegal_windows_filename(self):
        archive = self.write_zip([("CON.txt", b"x")])
        with self.assertRaisesRegex(AcquisitionError, "ILLEGAL_FILENAME"):
            safe_extract_archive(archive, self.make_directory() / "raw")


class CacheAndGateTests(PhaseIIBFixture):
    def test_10_11_synthetic_gate_pass_and_repeated_frozen_verification(self):
        cache, _manifest = self.frozen_cache()
        first = evaluate_raw_identity_gate(
            cache,
            repository_root=REPO_ROOT,
            expected_file_count=2,
            expected_subject_count=2,
            allow_temporary=True,
        )
        second = evaluate_raw_identity_gate(
            cache,
            repository_root=REPO_ROOT,
            expected_file_count=2,
            expected_subject_count=2,
            allow_temporary=True,
        )
        self.assertEqual(first, second)
        self.assertEqual(first.state, RawIdentityState.PASS)

    def test_12_offline_verification_has_no_transport_boundary(self):
        cache, _manifest = self.frozen_cache()
        with patch("urllib.request.urlopen") as network:
            result = evaluate_raw_identity_gate(
                cache,
                repository_root=REPO_ROOT,
                expected_subject_count=2,
                allow_temporary=True,
            )
        network.assert_not_called()
        self.assertEqual(result.state, RawIdentityState.PASS)

    def test_13_cli_help_and_plan_do_not_access_network_or_create_data(self):
        denied_cache = self.make_directory() / "denied-cache"
        with patch("urllib.request.urlopen") as network:
            from scripts.acquire_lee2019_mi import main

            self.assertEqual(main(["plan"]), 0)
            self.assertEqual(
                main([
                    "acquire",
                    "--cache-root",
                    str(denied_cache),
                    "--source-url",
                    "https://example.invalid/synthetic.zip",
                    "--archive-filename",
                    "synthetic.zip",
                    "--expected-sha256",
                    "0" * 64,
                ]),
                2,
            )
        network.assert_not_called()
        self.assertFalse(denied_cache.exists())
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("acquire", completed.stdout)

    def test_43_cache_root_omitted(self):
        with self.assertRaisesRegex(AcquisitionError, "CACHE_ROOT_REQUIRED"):
            validate_cache_root(None, repository_root=REPO_ROOT)
        self.assertEqual(
            evaluate_raw_identity_gate(None, repository_root=REPO_ROOT).state,
            RawIdentityState.NOT_ACQUIRED,
        )

    def test_44_cache_root_inside_repository(self):
        root = self.make_directory()
        cache = root / "repository" / "cache"
        with self.assertRaisesRegex(AcquisitionError, "CACHE_ROOT_INSIDE_REPOSITORY"):
            validate_cache_root(cache, repository_root=root / "repository")

    def test_45_unmanaged_unknown_file(self):
        cache = self.make_directory() / "cache"
        cache.mkdir()
        (cache / "unknown.bin").write_bytes(b"preserve")
        with self.assertRaisesRegex(
            AcquisitionError, "CACHE_ROOT_CONTAINS_UNEXPECTED_FILES"
        ):
            validate_cache_root(
                cache,
                repository_root=REPO_ROOT,
                allow_temporary=True,
            )
        result = evaluate_raw_identity_gate(
            cache,
            repository_root=REPO_ROOT,
            allow_temporary=True,
        )
        self.assertEqual(result.state, RawIdentityState.UNEXPECTED_FILE)
        self.assertEqual((cache / "unknown.bin").read_bytes(), b"preserve")

    def test_46_missing_expected_file(self):
        cache, manifest = self.frozen_cache()
        (cache / "raw" / manifest.files[0].relative_path).unlink()
        result = evaluate_raw_identity_gate(
            cache, repository_root=REPO_ROOT, allow_temporary=True
        )
        self.assertEqual(result.state, RawIdentityState.PARTIAL)

    def test_47_changed_extracted_file_hash(self):
        cache, manifest = self.frozen_cache()
        (cache / "raw" / manifest.files[0].relative_path).write_bytes(b"changed")
        result = evaluate_raw_identity_gate(
            cache, repository_root=REPO_ROOT, allow_temporary=True
        )
        self.assertEqual(result.state, RawIdentityState.HASH_MISMATCH)

    def test_48_extra_file(self):
        cache, _manifest = self.frozen_cache()
        targets = (
            cache / "raw" / "extra.bin",
            cache / "archives" / "extra.zip",
            cache / "manifests" / "extra.json",
        )
        for target in targets:
            with self.subTest(target=target.relative_to(cache)):
                target.write_bytes(b"extra")
                result = evaluate_raw_identity_gate(
                    cache, repository_root=REPO_ROOT, allow_temporary=True
                )
                self.assertEqual(result.state, RawIdentityState.UNEXPECTED_FILE)
                target.unlink()

    def test_49_incomplete_inventory(self):
        cache, _manifest = self.frozen_cache()
        result = evaluate_raw_identity_gate(
            cache,
            repository_root=REPO_ROOT,
            expected_subject_count=54,
            allow_temporary=True,
        )
        self.assertEqual(result.state, RawIdentityState.INVENTORY_MISMATCH)

    def test_50_ambiguous_source_identity(self):
        cache, manifest = self.frozen_cache()
        (cache / "archives" / manifest.source_archive.archive_filename).unlink()
        result = evaluate_raw_identity_gate(
            cache, repository_root=REPO_ROOT, allow_temporary=True
        )
        self.assertEqual(result.state, RawIdentityState.SOURCE_IDENTITY_AMBIGUOUS)

    def test_51_invalid_manifest_identity(self):
        cache, _manifest = self.frozen_cache()
        path = cache / "manifests" / "raw_manifest.json"
        payload = json.loads(path.read_bytes())
        payload["generated_timestamp"] = "tampered"
        path.write_bytes(canonical_json_bytes(payload))
        result = evaluate_raw_identity_gate(
            cache, repository_root=REPO_ROOT, allow_temporary=True
        )
        self.assertEqual(result.state, RawIdentityState.MANIFEST_INVALID)

    def test_52_53_no_automatic_redownload_or_repair(self):
        cache, manifest = self.frozen_cache()
        missing = cache / "raw" / manifest.files[0].relative_path
        missing.unlink()
        before = tuple(sorted(path.relative_to(cache) for path in cache.rglob("*")))
        with patch("urllib.request.urlopen") as network:
            result = evaluate_raw_identity_gate(
                cache, repository_root=REPO_ROOT, allow_temporary=True
            )
        after = tuple(sorted(path.relative_to(cache) for path in cache.rglob("*")))
        network.assert_not_called()
        self.assertEqual(result.state, RawIdentityState.PARTIAL)
        self.assertEqual(before, after)
        self.assertFalse(missing.exists())

    def test_global_cache_path_rejected_without_inspection(self):
        root = self.make_directory()
        home = root / "home"
        candidate = home / "mne_data"
        result = evaluate_raw_identity_gate(
            candidate,
            repository_root=REPO_ROOT,
            allow_temporary=True,
            home=home,
        )
        self.assertEqual(result.state, RawIdentityState.GLOBAL_CACHE_CONTAMINATION)
        self.assertFalse(candidate.exists())


if __name__ == "__main__":
    unittest.main()
