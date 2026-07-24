from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.external_replication.acquisition import COMPLETE_CACHE_MARKER
from src.external_replication.acquisition_workflow import (
    AcquisitionDependencies,
    AcquisitionRequest,
    AcquisitionState,
    AcquisitionWorkflowError,
    ExpectedRawFile,
    ExtractionPolicy,
    InventoryExpectation,
    SourceIdentity,
    WorkflowFailureReason,
    run_acquisition,
)
from src.external_replication.network_policy import (
    AcquisitionAuthorization,
    AuthorizationState,
    TransportResponse,
)
from src.external_replication.acquisition import initialize_managed_cache
from src.external_replication.raw_identity import RawIdentityState, not_acquired_result
from src.external_replication.raw_manifest import read_manifest
from src.external_replication.raw_manifest import ManifestError, canonical_json_bytes


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_CLOCK = lambda: datetime(2026, 7, 24, tzinfo=timezone.utc)


def synthetic_zip(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100600 << 16
            archive.writestr(info, payload)
    return stream.getvalue()


class RecordingTransport:
    def __init__(
        self,
        payload: bytes,
        *,
        chunks=None,
        headers: dict[str, str] | None = None,
        status: int = 200,
    ):
        self.payload = payload
        self.chunks = chunks
        self.headers = headers
        self.status = status
        self.calls = 0

    def open(self, _source_url: str) -> TransportResponse:
        self.calls += 1
        return TransportResponse(
            status=self.status,
            chunks=self.chunks if self.chunks is not None else (self.payload,),
            headers=(
                self.headers
                if self.headers is not None
                else {
                    "Content-Length": str(len(self.payload)),
                    "Content-Type": "application/zip",
                }
            ),
            transport_identifier="SYNTHETIC_RECORDING_TRANSPORT",
        )


class ExplodingTransport:
    calls = 0

    def open(self, _source_url: str) -> TransportResponse:
        self.calls += 1
        raise AssertionError("transport must not be called")


class AcquisitionWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = {
            "subject-01/session-S1/run-R1.bin": b"subject-one",
            "subject-02/session-S1/run-R1.bin": b"subject-two",
        }
        self.archive = synthetic_zip(self.files)

    def request(self, cache_root: Path) -> AcquisitionRequest:
        expected = tuple(
            ExpectedRawFile(
                relative_path=path,
                byte_size=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
                subject_id=path.split("/", 1)[0],
                session_id="S1",
                run_id="R1",
                role="SYNTHETIC_TEST",
                label_status="LABELED",
                acquisition_status="ACQUIRED",
            )
            for path, payload in sorted(self.files.items())
        )
        return AcquisitionRequest(
            cache_root=cache_root,
            repository_root=REPO_ROOT,
            source=SourceIdentity(
                source_url="https://example.invalid/lee2019-mi-synthetic.zip",
                archive_filename="lee2019-mi-synthetic.zip",
                expected_size=len(self.archive),
                expected_sha256=hashlib.sha256(self.archive).hexdigest(),
                implementation_identifier="production-path-synthetic-test",
            ),
            inventory=InventoryExpectation(
                files=expected,
                expected_subject_count=2,
            ),
            authorization=(
                AcquisitionAuthorization.explicitly_authorized_for_acquisition()
            ),
            allow_temporary=True,
        )

    def dependencies(self, transport) -> AcquisitionDependencies:
        return AcquisitionDependencies(transport=transport, clock=FIXED_CLOCK)

    @staticmethod
    def with_archive(request: AcquisitionRequest, archive: bytes) -> AcquisitionRequest:
        return replace(
            request,
            source=replace(
                request.source,
                expected_size=len(archive),
                expected_sha256=hashlib.sha256(archive).hexdigest(),
            ),
        )

    def test_production_path_completes_then_reruns_verification_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            partial = (
                request.cache_root
                / "archives"
                / (request.source.archive_filename + ".partial")
            )
            observed_partial: list[bool] = []

            def chunks():
                observed_partial.append(partial.is_file())
                yield self.archive[:17]
                observed_partial.append(partial.is_file())
                yield self.archive[17:]

            transport = RecordingTransport(self.archive, chunks=chunks())
            result = run_acquisition(request, self.dependencies(transport))
            self.assertEqual(result.state, AcquisitionState.COMPLETE)
            self.assertEqual(result.gate_result.state, RawIdentityState.PASS)
            self.assertTrue(result.transport_used)
            self.assertEqual(transport.calls, 1)
            self.assertEqual(observed_partial, [True, True])
            self.assertFalse(partial.exists())
            self.assertFalse((request.cache_root / "raw.extracting").exists())
            self.assertTrue((request.cache_root / COMPLETE_CACHE_MARKER).is_file())
            manifest = read_manifest(
                request.cache_root / "manifests" / "raw_manifest.json"
            )
            self.assertEqual(result.manifest_sha256, manifest.payload_sha256())

            no_network = ExplodingTransport()
            verified = run_acquisition(request, self.dependencies(no_network))
            self.assertEqual(verified.state, AcquisitionState.VERIFIED_COMPLETE)
            self.assertFalse(verified.transport_used)
            self.assertEqual(no_network.calls, 0)

    def test_denied_authorization_precedes_transport_and_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = replace(
                self.request(Path(temporary) / "controlled-cache"),
                authorization=AcquisitionAuthorization(),
            )
            transport = ExplodingTransport()
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(transport))
            self.assertEqual(
                caught.exception.reason, WorkflowFailureReason.NETWORK_POLICY_FAILED
            )
            self.assertEqual(transport.calls, 0)
            self.assertFalse(request.cache_root.exists())

    def test_network_denial_precedes_transport_and_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = replace(
                self.request(Path(temporary) / "controlled-cache"),
                authorization=AcquisitionAuthorization(
                    acquisition=AuthorizationState.ALLOW,
                    network=AuthorizationState.DENY,
                ),
            )
            transport = ExplodingTransport()
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(transport))
            self.assertEqual(
                caught.exception.reason, WorkflowFailureReason.NETWORK_POLICY_FAILED
            )
            self.assertEqual(caught.exception.detail, "NETWORK_NOT_AUTHORIZED")
            self.assertEqual(transport.calls, 0)
            self.assertFalse(request.cache_root.exists())

    def test_invalid_source_precedes_transport_and_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            request = replace(
                request,
                source=replace(
                    request.source,
                    source_url=(
                        "https://synthetic:redacted@example.invalid/"
                        "data.zip?opaque=redacted"
                    ),
                ),
            )
            transport = ExplodingTransport()
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(transport))
            self.assertEqual(
                caught.exception.reason, WorkflowFailureReason.SOURCE_IDENTITY_INVALID
            )
            self.assertEqual(transport.calls, 0)
            self.assertFalse(request.cache_root.exists())

    def test_stale_lock_refuses_without_transport_or_lock_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            lock = request.cache_root.with_name(
                request.cache_root.name + ".phase_ii_b.lock"
            )
            lock.write_text("stale\n", encoding="utf-8")
            transport = ExplodingTransport()
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(transport))
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.CONCURRENT_ACQUISITION_REFUSED,
            )
            self.assertTrue(lock.is_file())
            self.assertEqual(transport.calls, 0)

    def test_interrupted_stream_leaves_no_partial_and_no_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")

            def chunks():
                yield self.archive[:10]
                raise OSError("synthetic interruption")

            transport = RecordingTransport(self.archive, chunks=chunks())
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(transport))
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.ACQUISITION_PRIMITIVE_FAILED,
            )
            self.assertEqual(caught.exception.detail, "STREAM_FAILURE")
            self.assertFalse(
                (
                    request.cache_root
                    / "archives"
                    / (request.source.archive_filename + ".partial")
                ).exists()
            )
            self.assertFalse((request.cache_root / COMPLETE_CACHE_MARKER).exists())

    def test_download_identity_failures_never_publish_archive_or_complete(self) -> None:
        cases = (
            (
                "zero",
                b"",
                None,
                "ZERO_BYTE_PAYLOAD",
                None,
            ),
            (
                "byte-count",
                self.archive[:-1],
                None,
                "BYTE_COUNT_MISMATCH",
                None,
            ),
            (
                "hash",
                self.archive,
                "0" * 64,
                "HASH_MISMATCH",
                None,
            ),
            (
                "html",
                b"<html>error</html>",
                None,
                "HTML_OR_ERROR_PAYLOAD",
                {"Content-Type": "text/html"},
            ),
        )
        for name, payload, digest, reason, headers in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                request = self.request(Path(temporary) / "controlled-cache")
                if name == "html":
                    request = self.with_archive(request, payload)
                elif digest is not None:
                    request = replace(
                        request,
                        source=replace(request.source, expected_sha256=digest),
                    )
                transport = RecordingTransport(payload, headers=headers)
                with self.assertRaises(AcquisitionWorkflowError) as caught:
                    run_acquisition(request, self.dependencies(transport))
                self.assertEqual(
                    caught.exception.reason,
                    WorkflowFailureReason.ACQUISITION_PRIMITIVE_FAILED,
                )
                self.assertEqual(caught.exception.detail, reason)
                self.assertFalse(
                    (
                        request.cache_root
                        / "archives"
                        / request.source.archive_filename
                    ).exists()
                )
                self.assertFalse((request.cache_root / COMPLETE_CACHE_MARKER).exists())

    def test_unsafe_archive_rejection_leaves_no_raw_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            unsafe = synthetic_zip({"../escape.bin": b"escape"})
            request = self.with_archive(
                self.request(Path(temporary) / "controlled-cache"), unsafe
            )
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(RecordingTransport(unsafe)))
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.ACQUISITION_PRIMITIVE_FAILED,
            )
            self.assertEqual(caught.exception.detail, "UNSAFE_ARCHIVE_PATH")
            self.assertFalse((request.cache_root / "raw").exists())
            self.assertFalse((request.cache_root / "raw.extracting").exists())
            self.assertFalse((request.cache_root / COMPLETE_CACHE_MARKER).exists())

    def test_inventory_mismatch_is_incomplete_and_never_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            wrong = replace(
                request.inventory.files[0],
                sha256="0" * 64,
            )
            request = replace(
                request,
                inventory=replace(
                    request.inventory,
                    files=(wrong, *request.inventory.files[1:]),
                ),
            )
            transport = RecordingTransport(self.archive)
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(transport))
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.RAW_FILE_IDENTITY_MISMATCH,
            )
            self.assertFalse((request.cache_root / "raw").exists())
            self.assertFalse((request.cache_root / "raw.extracting").exists())
            self.assertFalse((request.cache_root / COMPLETE_CACHE_MARKER).exists())
            no_network = ExplodingTransport()
            with self.assertRaises(AcquisitionWorkflowError) as rerun:
                run_acquisition(request, self.dependencies(no_network))
            self.assertEqual(
                rerun.exception.reason,
                WorkflowFailureReason.INCOMPLETE_CACHE_REQUIRES_OPERATOR,
            )
            self.assertEqual(no_network.calls, 0)

    def test_extraction_limits_fail_before_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = replace(
                self.request(Path(temporary) / "controlled-cache"),
                extraction=ExtractionPolicy(max_file_count=1),
            )
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(
                    request, self.dependencies(RecordingTransport(self.archive))
                )
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.ACQUISITION_PRIMITIVE_FAILED,
            )
            self.assertEqual(
                caught.exception.detail, "ARCHIVE_FILE_COUNT_LIMIT_EXCEEDED"
            )
            self.assertFalse((request.cache_root / COMPLETE_CACHE_MARKER).exists())

    def test_preexisting_incomplete_states_refuse_without_transport(self) -> None:
        artifacts = (
            ("final archive", Path("archives/lee2019-mi-synthetic.zip"), b"x"),
            (
                "partial archive",
                Path("archives/lee2019-mi-synthetic.zip.partial"),
                b"x",
            ),
            ("extraction stage", Path("raw.extracting/sentinel.bin"), b"x"),
            ("raw without manifest", Path("raw/sentinel.bin"), b"x"),
            ("invalid manifest", Path("manifests/raw_manifest.json"), b"{}"),
            ("unknown file", Path("unknown.bin"), b"x"),
        )
        for name, relative, content in artifacts:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                request = self.request(Path(temporary) / "controlled-cache")
                initialize_managed_cache(
                    request.cache_root,
                    repository_root=REPO_ROOT,
                    allow_temporary=True,
                )
                artifact = request.cache_root / relative
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_bytes(content)
                transport = ExplodingTransport()
                with self.assertRaises(AcquisitionWorkflowError) as caught:
                    run_acquisition(request, self.dependencies(transport))
                expected_reason = (
                    WorkflowFailureReason.INCOMPLETE_CACHE_REQUIRES_OPERATOR
                    if relative.parts[0] in {"archives", "raw", "manifests"}
                    else WorkflowFailureReason.ACQUISITION_PRIMITIVE_FAILED
                )
                self.assertIn(
                    caught.exception.reason,
                    {
                        expected_reason,
                        WorkflowFailureReason.ACQUISITION_PRIMITIVE_FAILED,
                    },
                )
                self.assertEqual(transport.calls, 0)
                self.assertEqual(artifact.read_bytes(), content)

    def test_changed_raw_file_in_complete_cache_is_detected_without_network(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            run_acquisition(
                request, self.dependencies(RecordingTransport(self.archive))
            )
            raw = request.cache_root / "raw" / request.inventory.files[0].relative_path
            raw.write_bytes(b"tampered")
            no_network = ExplodingTransport()
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(no_network))
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.COMPLETE_MARKER_INVALID,
            )
            self.assertEqual(no_network.calls, 0)

    def test_recomputed_manifest_and_marker_cannot_replace_expected_inventory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            run_acquisition(
                request, self.dependencies(RecordingTransport(self.archive))
            )
            raw = request.cache_root / "raw" / request.inventory.files[0].relative_path
            replacement = b"synthetic-replacement"
            raw.write_bytes(replacement)
            manifest_path = request.cache_root / "manifests" / "raw_manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            record = next(
                item
                for item in manifest["files"]
                if item["relative_path"] == request.inventory.files[0].relative_path
            )
            record["byte_size"] = len(replacement)
            record["sha256"] = hashlib.sha256(replacement).hexdigest()
            payload = dict(manifest)
            payload.pop("manifest_payload_sha256")
            manifest_identity = hashlib.sha256(
                canonical_json_bytes(payload)
            ).hexdigest()
            manifest["manifest_payload_sha256"] = manifest_identity
            manifest_path.write_bytes(canonical_json_bytes(manifest))
            marker_path = request.cache_root / COMPLETE_CACHE_MARKER
            marker = json.loads(marker_path.read_bytes())
            marker["manifest_payload_sha256"] = manifest_identity
            marker_path.write_bytes(canonical_json_bytes(marker))

            no_network = ExplodingTransport()
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(no_network))
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.COMPLETE_MARKER_INVALID,
            )
            self.assertEqual(no_network.calls, 0)

    def test_tampered_completion_marker_fails_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            run_acquisition(
                request, self.dependencies(RecordingTransport(self.archive))
            )
            marker = request.cache_root / COMPLETE_CACHE_MARKER
            payload = json.loads(marker.read_text(encoding="utf-8"))
            payload["archive_sha256"] = "0" * 64
            marker.write_text(json.dumps(payload), encoding="utf-8")
            no_network = ExplodingTransport()
            with self.assertRaises(AcquisitionWorkflowError) as caught:
                run_acquisition(request, self.dependencies(no_network))
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.COMPLETE_MARKER_INVALID,
            )
            self.assertEqual(no_network.calls, 0)

    def test_manifest_publication_failure_never_emits_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            with patch(
                "src.external_replication.acquisition_workflow.write_manifest_atomic",
                side_effect=ManifestError("SYNTHETIC_MANIFEST_FAILURE"),
            ):
                with self.assertRaises(AcquisitionWorkflowError) as caught:
                    run_acquisition(
                        request,
                        self.dependencies(RecordingTransport(self.archive)),
                    )
            self.assertEqual(
                caught.exception.reason, WorkflowFailureReason.MANIFEST_FAILED
            )
            self.assertFalse((request.cache_root / COMPLETE_CACHE_MARKER).exists())

    def test_manifest_self_verification_failure_never_emits_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            with patch(
                "src.external_replication.raw_manifest.read_manifest",
                side_effect=ManifestError("SYNTHETIC_SELF_VERIFICATION_FAILURE"),
            ):
                with self.assertRaises(AcquisitionWorkflowError) as caught:
                    run_acquisition(
                        request,
                        self.dependencies(RecordingTransport(self.archive)),
                    )
            self.assertEqual(
                caught.exception.reason, WorkflowFailureReason.MANIFEST_FAILED
            )
            self.assertEqual(
                caught.exception.detail, "SYNTHETIC_SELF_VERIFICATION_FAILURE"
            )
            self.assertFalse((request.cache_root / COMPLETE_CACHE_MARKER).exists())

    def test_completion_publication_failure_is_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            with patch(
                "src.external_replication.acquisition_workflow._publish_json_atomic",
                side_effect=OSError("synthetic publication failure"),
            ):
                with self.assertRaises(AcquisitionWorkflowError) as caught:
                    run_acquisition(
                        request,
                        self.dependencies(RecordingTransport(self.archive)),
                    )
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.COMPLETION_PUBLICATION_FAILED,
            )
            self.assertFalse((request.cache_root / COMPLETE_CACHE_MARKER).exists())

    def test_gate_failure_never_emits_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary) / "controlled-cache")
            with patch(
                "src.external_replication.acquisition_workflow._gate",
                return_value=not_acquired_result(),
            ):
                with self.assertRaises(AcquisitionWorkflowError) as caught:
                    run_acquisition(
                        request,
                        self.dependencies(RecordingTransport(self.archive)),
                    )
            self.assertEqual(
                caught.exception.reason,
                WorkflowFailureReason.RAW_IDENTITY_GATE_FAILED,
            )
            self.assertEqual(caught.exception.detail, "NOT_ACQUIRED")
            self.assertFalse((request.cache_root / COMPLETE_CACHE_MARKER).exists())


if __name__ == "__main__":
    unittest.main()
