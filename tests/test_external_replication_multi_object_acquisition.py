from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import unicodedata
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.external_replication.acquisition import initialize_managed_cache
from src.external_replication.multi_object_acquisition import (
    CANDIDATE_MANIFEST_NAME,
    CANDIDATE_MARKER_NAME,
    COLLECTION_LOCK_NAME,
    GIGADB_ORIGINAL_MAT_OBJECTS,
    NEMAR_BIDS_DERIVATIVE,
    ApprovedCollectionIdentity,
    CandidateCollectionManifest,
    CollectionAcquisitionError,
    CollectionFailureReason,
    CollectionGateState,
    CollectionObjectPlan,
    CollectionState,
    MultiObjectAcquisitionRequest,
    MultiObjectDependencies,
    MultiObjectResourceLimits,
    collection_plan_sha256,
    classify_source_change,
    evaluate_candidate_collection_gate,
    run_multi_object_acquisition,
    validate_collection_plan,
)
from src.external_replication.network_policy import (
    AcquisitionAuthorization,
    AuthorizationState,
    TransportResponse,
)
from src.external_replication.raw_manifest import canonical_json_bytes


REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE = "424e8c6a958f169d2896321255c727700472bbe7"
FIXED_TIME = datetime(2026, 7, 24, 1, 2, 3, tzinfo=timezone.utc)


def opaque_bytes(index: int) -> bytes:
    return hashlib.sha256(f"synthetic-opaque-fixture-{index}".encode()).digest()


def make_objects() -> tuple[CollectionObjectPlan, ...]:
    objects = []
    index = 0
    for session in (1, 2):
        for subject in range(1, 55):
            payload = opaque_bytes(index)
            relative = (
                f"session{session}/s{subject}/"
                f"sess0{session}_subj{subject:02d}_EEG_MI.mat"
            )
            objects.append(CollectionObjectPlan(
                object_id=f"synthetic-object-{index:03d}",
                relative_path=relative,
                source_url=f"https://synthetic.invalid/fixtures/{relative}",
                expected_size=len(payload),
                expected_sha256=hashlib.sha256(payload).hexdigest(),
                subject_id=f"s{subject}",
                session_id=f"session{session}",
                source_role="MOTOR_IMAGERY_SESSION_OBJECT",
                content_kind="OPAQUE_SYNTHETIC_BYTES",
            ))
            index += 1
    return tuple(objects)


def make_request(root: Path, **changes) -> MultiObjectAcquisitionRequest:
    request = MultiObjectAcquisitionRequest(
        dataset_id="Lee2019_MI",
        source_representation=GIGADB_ORIGINAL_MAT_OBJECTS,
        cache_root=root,
        repository_root=REPO_ROOT,
        collection_objects=make_objects(),
        authorization=AcquisitionAuthorization.explicitly_authorized_for_acquisition(),
        scientific_execution_authorization=AuthorizationState.DENY,
        expected_object_count=108,
        expected_subject_count=54,
        expected_session_count=2,
        collection_schema_version=1,
        resource_limits=MultiObjectResourceLimits(
            maximum_total_object_count=108,
            maximum_bytes_per_object=64,
            maximum_total_downloaded_bytes=108 * 64,
            maximum_redirects_per_object=0,
            maximum_url_length=300,
            maximum_relative_path_length=120,
            maximum_concurrent_object_transfers=1,
            timeout_seconds=10,
            maximum_retry_count=0,
        ),
        approved_scheme="https",
        approved_host="synthetic.invalid",
        approved_path_prefixes=("/fixtures/session1/", "/fixtures/session2/"),
        authorization_id="SYNTHETIC_TEST_ONLY",
        baseline_commit=BASELINE,
        allow_temporary=True,
    )
    return replace(request, **changes)


class FakeTransport:
    def __init__(self, objects=None, failure_at=None, response_changes=None):
        self.objects = objects or make_objects()
        self.payload_by_url = {
            item.source_url: opaque_bytes(index)
            for index, item in enumerate(self.objects)
        }
        self.failure_at = failure_at
        self.response_changes = response_changes or {}
        self.calls = []
        self.lock_seen = []

    def open(self, source_url: str) -> TransportResponse:
        self.lock_seen.append(self.current_root.joinpath(COLLECTION_LOCK_NAME).exists())
        self.calls.append(source_url)
        if self.failure_at == len(self.calls):
            raise OSError("synthetic interruption")
        payload = self.payload_by_url[source_url]
        changes = self.response_changes
        return TransportResponse(
            status=changes.get("status", 200),
            chunks=changes.get("chunks", (payload,)),
            headers=changes.get("headers", {"Content-Length": str(len(payload))}),
            redirect_chain=changes.get("redirect_chain", ()),
            transport_identifier="IN_MEMORY_SYNTHETIC_TRANSPORT",
        )


def dependencies(transport: FakeTransport, root: Path, events=None):
    transport.current_root = root
    return MultiObjectDependencies(
        transport=transport,
        clock=lambda: FIXED_TIME,
        event_sink=None if events is None else events.append,
    )


class MultiObjectSuccessTests(unittest.TestCase):
    def test_synthetic_108_object_end_to_end_and_idempotency(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "collection-cache"
            request = make_request(root)
            transport = FakeTransport()
            events = []
            result = run_multi_object_acquisition(
                request, dependencies(transport, root, events)
            )
            self.assertEqual(len(validate_collection_plan(request)), 108)
            self.assertEqual(
                {item.subject_id for item in request.collection_objects},
                {f"s{index}" for index in range(1, 55)},
            )
            self.assertEqual(
                {item.session_id for item in request.collection_objects},
                {"session1", "session2"},
            )
            self.assertEqual(len(transport.calls), 108)
            self.assertTrue(all(transport.lock_seen))
            self.assertEqual(result.gate_result.state, CollectionGateState.UNAPPROVED_CANDIDATE)
            self.assertEqual(result.approval_state, "UNAPPROVED_CANDIDATE")
            self.assertEqual(result.source_representation, GIGADB_ORIGINAL_MAT_OBJECTS)
            self.assertEqual(result.baseline_commit, BASELINE)
            self.assertEqual(events[-1], CollectionState.AWAITING_HUMAN_APPROVAL)
            self.assertFalse(any(root.rglob("*.partial")))
            self.assertFalse((root / COLLECTION_LOCK_NAME).exists())
            manifest_path = root / "manifests" / CANDIDATE_MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["objects"]), 108)
            self.assertEqual(
                [item["relative_path"] for item in manifest["objects"]],
                sorted(
                    (item.relative_path for item in request.collection_objects),
                    key=lambda value: (value.casefold(), value),
                ),
            )
            payload = dict(manifest)
            identity = payload.pop("manifest_payload_sha256")
            self.assertEqual(
                identity, hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
            )
            marker = json.loads(
                (root / CANDIDATE_MARKER_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(marker["candidate_manifest_sha256"], identity)
            repeated = run_multi_object_acquisition(
                request,
                MultiObjectDependencies(
                    transport=None,
                    clock=lambda: FIXED_TIME,
                ),
            )
            self.assertEqual(repeated.transport_call_count, 0)
            self.assertEqual(
                repeated.gate_result.state, CollectionGateState.UNAPPROVED_CANDIDATE
            )

    def test_plan_identity_is_order_independent_but_exactly_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            request = make_request(Path(temporary) / "cache")
            reversed_request = replace(
                request, collection_objects=tuple(reversed(request.collection_objects))
            )
            self.assertEqual(
                collection_plan_sha256(request),
                collection_plan_sha256(reversed_request),
            )
            changed = list(request.collection_objects)
            changed[0] = replace(changed[0], source_role="CHANGED")
            self.assertNotEqual(
                collection_plan_sha256(request),
                collection_plan_sha256(
                    replace(request, collection_objects=tuple(changed))
                ),
            )

    def test_explicit_complete_approval_is_separate_and_fully_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "cache"
            request = make_request(root)
            result = run_multi_object_acquisition(
                request, dependencies(FakeTransport(), root)
            )
            payload = json.loads(
                (root / "manifests" / CANDIDATE_MANIFEST_NAME).read_text()
            )
            identities = tuple(
                (item["object_id"], item["downloaded_bytes"], item["sha256"])
                for item in payload["objects"]
            )
            approval = ApprovedCollectionIdentity(
                dataset_id=request.dataset_id,
                source_representation=request.source_representation,
                plan_sha256=result.plan_sha256,
                candidate_manifest_sha256=result.candidate_manifest_sha256,
                object_identities=identities,
                approval_id="synthetic-approval",
                approver="Synthetic Test Approver",
                approval_timestamp=FIXED_TIME.isoformat(),
                baseline_commit=BASELINE,
                destination="synthetic-test-destination",
                source_authenticity_evidence_reference="synthetic-evidence",
                license_review_reference="synthetic-license-review",
            )
            self.assertEqual(
                evaluate_candidate_collection_gate(request, approval).state,
                CollectionGateState.APPROVED_COLLECTION_PASS,
            )
            invalid_approvals = (
                replace(approval, approver=""),
                replace(approval, approval_timestamp=""),
                replace(approval, object_identities=approval.object_identities[:-1]),
                replace(approval, baseline_commit="0" * 40),
            )
            for invalid in invalid_approvals:
                with self.subTest(invalid=invalid):
                    self.assertNotEqual(
                        evaluate_candidate_collection_gate(request, invalid).state,
                        CollectionGateState.APPROVED_COLLECTION_PASS,
                    )


class MultiObjectFailureTests(unittest.TestCase):
    def assert_plan_invalid(self, request):
        with self.assertRaises((ValueError, CollectionAcquisitionError)):
            validate_collection_plan(request)

    def test_authorization_and_representation_fail_closed_before_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = make_request(Path(temporary) / "cache")
            cases = (
                replace(base, authorization=replace(base.authorization, acquisition=AuthorizationState.DENY)),
                replace(base, authorization=replace(base.authorization, network=AuthorizationState.DENY)),
                replace(base, authorization=replace(base.authorization, scientific_execution=AuthorizationState.ALLOW)),
                replace(base, scientific_execution_authorization=AuthorizationState.ALLOW),
                replace(base, dataset_id="wrong"),
                replace(base, source_representation=NEMAR_BIDS_DERIVATIVE),
            )
            for request in cases:
                with self.subTest(change=request):
                    transport = FakeTransport()
                    with self.assertRaises(CollectionAcquisitionError):
                        run_multi_object_acquisition(
                            request, dependencies(transport, request.cache_root)
                        )
                    self.assertEqual(transport.calls, [])

    def test_source_url_policy_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = make_request(Path(temporary) / "cache")
            objects = list(base.collection_objects)
            variants = []
            for url in (
                objects[0].source_url.replace("https:", "http:"),
                "https://other.invalid/fixtures/session1/a.mat",
                "https://synthetic.invalid/unexpected/a.mat",
                objects[0].source_url + "?token=secret",
                "https://user:password@synthetic.invalid/fixtures/session1/a.mat",
            ):
                changed = list(objects)
                changed[0] = replace(changed[0], source_url=url)
                variants.append(replace(base, collection_objects=tuple(changed)))
            changed = list(objects)
            changed[1] = replace(changed[1], source_url=changed[0].source_url)
            variants.append(replace(base, collection_objects=tuple(changed)))
            changed = list(objects)
            changed[1] = replace(changed[1], object_id=changed[0].object_id)
            variants.append(replace(base, collection_objects=tuple(changed)))
            changed = list(objects)
            changed[1] = replace(changed[1], relative_path=changed[0].relative_path)
            variants.append(replace(base, collection_objects=tuple(changed)))
            for request in variants:
                with self.subTest(url=request.collection_objects[0].source_url):
                    self.assert_plan_invalid(request)
            self.assert_plan_invalid(replace(base, approved_host="*.invalid"))

    def test_count_subject_session_and_pair_integrity(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = make_request(Path(temporary) / "cache")
            variants = (
                replace(base, collection_objects=base.collection_objects[:-1]),
                replace(base, collection_objects=base.collection_objects + (replace(
                    base.collection_objects[-1],
                    object_id="extra",
                    relative_path="session2/s55/sess02_subj55_EEG_MI.mat",
                    source_url="https://synthetic.invalid/fixtures/session2/s55/sess02_subj55_EEG_MI.mat",
                    subject_id="s55",
                ),)),
                replace(base, expected_subject_count=55),
                replace(base, expected_session_count=3),
            )
            for request in variants:
                with self.subTest(count=len(request.collection_objects)):
                    self.assert_plan_invalid(request)
            changed = list(base.collection_objects)
            changed[1] = replace(
                changed[1],
                subject_id=changed[0].subject_id,
                session_id=changed[0].session_id,
            )
            self.assert_plan_invalid(replace(base, collection_objects=tuple(changed)))

    def test_hostile_paths_and_collisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = make_request(Path(temporary) / "cache")
            hostile = (
                "../escape.mat", "/absolute.mat", "C:/drive.mat", "//server/share.mat",
                "session1\\mixed.mat", "session1/CON/file.mat", "session1/file.",
                "session1/file ", "session1/file:stream", "x" * 121,
            )
            for value in hostile:
                changed = list(base.collection_objects)
                changed[0] = replace(changed[0], relative_path=value)
                with self.subTest(path=value):
                    self.assert_plan_invalid(
                        replace(base, collection_objects=tuple(changed))
                    )
            changed = list(base.collection_objects)
            changed[1] = replace(
                changed[1],
                relative_path=changed[0].relative_path.upper(),
            )
            self.assert_plan_invalid(replace(base, collection_objects=tuple(changed)))
            composed = "session1/café/file.mat"
            decomposed = unicodedata.normalize("NFD", composed)
            changed = list(base.collection_objects)
            changed[0] = replace(changed[0], relative_path=composed)
            changed[1] = replace(changed[1], relative_path=decomposed)
            self.assert_plan_invalid(replace(base, collection_objects=tuple(changed)))

    def test_interruptions_leave_no_owned_partial_and_restart_is_resumable(self):
        for failure_at in (1, 54, 108):
            with self.subTest(failure_at=failure_at), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "cache"
                request = make_request(root)
                with self.assertRaises(CollectionAcquisitionError):
                    run_multi_object_acquisition(
                        request,
                        dependencies(FakeTransport(failure_at=failure_at), root),
                    )
                self.assertFalse(any(root.rglob("*.partial")))
                self.assertFalse((root / COLLECTION_LOCK_NAME).exists())
                resumed_transport = FakeTransport()
                result = run_multi_object_acquisition(
                    request, dependencies(resumed_transport, root)
                )
                self.assertEqual(
                    len(resumed_transport.calls), 109 - failure_at
                )
                self.assertEqual(
                    result.gate_result.state, CollectionGateState.UNAPPROVED_CANDIDATE
                )

    def test_payload_transport_and_limit_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            base_root = Path(temporary)
            cases = (
                {"chunks": ()},
                {"chunks": (b"wrong",)},
                {"chunks": (b"<html>synthetic error</html>",), "headers": {"Content-Type": "text/html"}},
                {"status": 500},
                {"redirect_chain": ("https://other.invalid/fixtures/session1/a.mat",)},
                {"redirect_chain": (
                    "https://synthetic.invalid/fixtures/session1/a.mat",
                    "https://synthetic.invalid/fixtures/session1/b.mat",
                )},
            )
            for index, changes in enumerate(cases):
                root = base_root / f"case-{index}"
                request = make_request(root)
                with self.subTest(index=index), self.assertRaises(CollectionAcquisitionError):
                    run_multi_object_acquisition(
                        request,
                        dependencies(FakeTransport(response_changes=changes), root),
                    )
                self.assertFalse(any(root.rglob("*.partial")))
            root = base_root / "per-object-limit"
            request = make_request(root)
            request = replace(
                request,
                resource_limits=replace(
                    request.resource_limits, maximum_bytes_per_object=16
                ),
            )
            self.assert_plan_invalid(request)
            root = base_root / "total-limit"
            request = make_request(root)
            request = replace(
                request,
                resource_limits=replace(
                    request.resource_limits, maximum_total_downloaded_bytes=100
                ),
            )
            self.assert_plan_invalid(request)

    def test_existing_objects_unknown_files_partials_and_locks_refuse(self):
        scenarios = ("invalid-object", "unknown-object", "foreign-partial", "lock")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "cache"
                request = make_request(root)
                initialize_managed_cache(
                    root, repository_root=REPO_ROOT, allow_temporary=True
                )
                if scenario == "invalid-object":
                    target = root / "objects" / request.collection_objects[0].relative_path
                elif scenario == "unknown-object":
                    target = root / "objects" / "unknown.bin"
                elif scenario == "foreign-partial":
                    target = root / "objects" / "foreign.partial"
                else:
                    target = root / COLLECTION_LOCK_NAME
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"foreign")
                transport = FakeTransport()
                with self.assertRaises(CollectionAcquisitionError):
                    run_multi_object_acquisition(
                        request, dependencies(transport, root)
                    )
                self.assertEqual(transport.calls, [])
                self.assertEqual(target.read_bytes(), b"foreign")

    def test_gate_detects_tampering_missing_extra_and_plan_substitution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "cache"
            request = make_request(root)
            run_multi_object_acquisition(
                request, dependencies(FakeTransport(), root)
            )
            first = request.collection_objects[0]
            target = root / "objects" / first.relative_path
            original = target.read_bytes()
            target.write_bytes(b"tampered")
            self.assertEqual(
                evaluate_candidate_collection_gate(request).state,
                CollectionGateState.OBJECT_SIZE_MISMATCH,
            )
            target.write_bytes(original)
            target.unlink()
            self.assertEqual(
                evaluate_candidate_collection_gate(request).state,
                CollectionGateState.OBJECT_MISSING,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original)
            extra = root / "objects" / "unknown.bin"
            extra.write_bytes(b"x")
            self.assertEqual(
                evaluate_candidate_collection_gate(request).state,
                CollectionGateState.OBJECT_UNEXPECTED,
            )
            extra.unlink()
            altered = list(request.collection_objects)
            altered[0] = replace(altered[0], source_role="ALTERED")
            altered_request = replace(request, collection_objects=tuple(altered))
            self.assertEqual(
                evaluate_candidate_collection_gate(altered_request).state,
                CollectionGateState.PLAN_IDENTITY_MISMATCH,
            )

    def test_manifest_marker_and_self_consistent_substitution_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "cache"
            request = make_request(root)
            run_multi_object_acquisition(
                request, dependencies(FakeTransport(), root)
            )
            manifest_path = root / "manifests" / CANDIDATE_MANIFEST_NAME
            payload = json.loads(manifest_path.read_text())
            payload["objects"][0]["sha256"] = "0" * 64
            manifest_payload = dict(payload)
            manifest_payload.pop("manifest_payload_sha256")
            payload["manifest_payload_sha256"] = hashlib.sha256(
                canonical_json_bytes(manifest_payload)
            ).hexdigest()
            manifest_path.write_bytes(canonical_json_bytes(payload))
            self.assertIn(
                evaluate_candidate_collection_gate(request).state,
                {
                    CollectionGateState.OBJECT_HASH_MISMATCH,
                    CollectionGateState.MANIFEST_IDENTITY_MISMATCH,
                },
            )

    def test_publication_failures_never_approve(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "cache"
            request = make_request(root)
            with patch(
                "src.external_replication.multi_object_acquisition._publish_json_atomic",
                side_effect=OSError("synthetic publication failure"),
            ):
                with self.assertRaises(CollectionAcquisitionError) as caught:
                    run_multi_object_acquisition(
                        request, dependencies(FakeTransport(), root)
                    )
            self.assertEqual(
                caught.exception.reason,
                CollectionFailureReason.MANIFEST_PUBLICATION_FAILED,
            )
            self.assertFalse((root / CANDIDATE_MARKER_NAME).exists())

    def test_marker_publication_and_lock_cleanup_fail_closed(self):
        from src.external_replication import multi_object_acquisition as module

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "marker-cache"
            request = make_request(root)
            real_publish = module._publish_json_atomic

            def fail_marker(path, payload):
                if path.name == CANDIDATE_MARKER_NAME:
                    raise OSError("synthetic marker failure")
                return real_publish(path, payload)

            with patch.object(module, "_publish_json_atomic", side_effect=fail_marker):
                with self.assertRaises(CollectionAcquisitionError) as caught:
                    run_multi_object_acquisition(
                        request, dependencies(FakeTransport(), root)
                    )
            self.assertEqual(
                caught.exception.reason, CollectionFailureReason.MARKER_PUBLICATION_FAILED
            )
            self.assertFalse((root / CANDIDATE_MARKER_NAME).exists())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "lock-cache"
            request = make_request(root)
            real_unlink = Path.unlink

            def fail_lock_unlink(path, *args, **kwargs):
                if path.name == COLLECTION_LOCK_NAME:
                    raise OSError("synthetic lock cleanup failure")
                return real_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", new=fail_lock_unlink):
                with self.assertRaises(CollectionAcquisitionError) as caught:
                    run_multi_object_acquisition(
                        request, dependencies(FakeTransport(), root)
                    )
            self.assertEqual(
                caught.exception.reason, CollectionFailureReason.LOCK_CLEANUP_FAILED
            )
            self.assertTrue((root / COLLECTION_LOCK_NAME).exists())

    def test_incomplete_artifact_combinations_are_not_complete(self):
        scenarios = ("manifest-only", "objects-only", "marker-only")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "cache"
                request = make_request(root)
                initialize_managed_cache(
                    root, repository_root=REPO_ROOT, allow_temporary=True
                )
                if scenario == "manifest-only":
                    target = root / "manifests" / CANDIDATE_MANIFEST_NAME
                elif scenario == "objects-only":
                    target = root / "objects" / request.collection_objects[0].relative_path
                else:
                    target = root / CANDIDATE_MARKER_NAME
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("{}", encoding="utf-8")
                self.assertNotIn(
                    evaluate_candidate_collection_gate(request).state,
                    {
                        CollectionGateState.UNAPPROVED_CANDIDATE,
                        CollectionGateState.APPROVED_COLLECTION_PASS,
                    },
                )

    def test_application_module_has_no_scientific_or_real_transport_imports(self):
        source = (
            REPO_ROOT
            / "src"
            / "external_replication"
            / "multi_object_acquisition.py"
        ).read_text(encoding="utf-8").casefold()
        for forbidden in (
            "import moabb", "import mne", "import scipy", "loadmat",
            "mat73", "h5py", "urllib.request", "requests", "httpx",
            "aiohttp", "socket", "pickle", "subprocess",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_source_change_classification_never_adopts_identity(self):
        digest = "a" * 64
        self.assertEqual(
            classify_source_change(
                approved_url="https://synthetic.invalid/fixtures/session1/a.mat",
                approved_size=32,
                approved_sha256=digest,
                candidate_url="https://synthetic.invalid/fixtures/session1/a.mat",
                candidate_size=32,
                candidate_sha256="b" * 64,
            ),
            CollectionGateState.SOURCE_IDENTITY_CHANGED,
        )
        self.assertEqual(
            classify_source_change(
                approved_url="https://synthetic.invalid/fixtures/session1/a.mat",
                approved_size=32,
                approved_sha256=digest,
                candidate_url="https://synthetic.invalid/fixtures/session1/b.mat",
                candidate_size=32,
                candidate_sha256=digest,
            ),
            CollectionGateState.SOURCE_MIGRATION_CANDIDATE,
        )


if __name__ == "__main__":
    unittest.main()
