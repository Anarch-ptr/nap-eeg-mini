"""Safe Phase II-B acquisition, planning, and offline verification CLI."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.external_replication.acquisition import (  # noqa: E402
    AcquisitionError,
    AcquisitionFailureReason,
)
from src.external_replication.acquisition_workflow import (  # noqa: E402
    AcquisitionDependencies,
    AcquisitionRequest,
    AcquisitionWorkflowError,
    ExpectedRawFile,
    InventoryExpectation,
    SourceIdentity,
    run_acquisition,
)
from src.external_replication.network_policy import (  # noqa: E402
    AcquisitionAuthorization,
    AuthorizationState,
    NetworkPolicy,
    NetworkPolicyError,
    TransportResponse,
)
from src.external_replication.multi_object_acquisition import (  # noqa: E402
    GIGADB_ORIGINAL_MAT_OBJECTS,
)
from src.external_replication.raw_identity import (  # noqa: E402
    evaluate_raw_identity_gate,
    not_acquired_result,
)
from src.external_replication.raw_manifest import ManifestError, read_manifest  # noqa: E402


class ExplicitUrllibTransport:
    """Minimal no-retry transport used only after explicit CLI authorization."""

    def open(self, source_url: str) -> TransportResponse:
        response = urllib.request.urlopen(source_url, timeout=60)
        if urlparse(response.geturl()).scheme != "https":
            response.close()
            raise AcquisitionError(AcquisitionFailureReason.SOURCE_IDENTITY_INVALID)

        def chunks():
            with response:
                while chunk := response.read(1024 * 1024):
                    yield chunk

        return TransportResponse(
            status=response.status,
            chunks=chunks(),
            headers=dict(response.headers.items()),
            redirect_chain=(
                (response.geturl(),) if response.geturl() != source_url else ()
            ),
            transport_identifier="PYTHON_STDLIB_URLLIB_NO_RETRY",
        )


def _authorization(args: argparse.Namespace) -> AcquisitionAuthorization:
    return AcquisitionAuthorization(
        acquisition=(
            AuthorizationState.ALLOW
            if getattr(args, "allow_acquisition", False)
            else AuthorizationState.DENY
        ),
        network=(
            AuthorizationState.ALLOW
            if getattr(args, "allow_network", False)
            else AuthorizationState.DENY
        ),
        scientific_execution=AuthorizationState.DENY,
    )


def _print_status(
    authorization: AcquisitionAuthorization,
    gate_state: str,
) -> None:
    print("LEE2019_MI_DATA_ACCESS=NONE")
    print(f"NETWORK_AUTHORIZATION={authorization.network.value}")
    print(f"ACQUISITION_AUTHORIZATION={authorization.acquisition.value}")
    print(f"RAW_DATA_IDENTITY_GATE={gate_state}")
    print(
        "SCIENTIFIC_EXECUTION_AUTHORIZATION="
        f"{authorization.scientific_execution.value}"
    )


def _print_collection_status(
    authorization: AcquisitionAuthorization,
    gate_state: str = "NOT_ACQUIRED",
) -> None:
    print("DATA_ACCESS=NONE")
    print(f"NETWORK_AUTHORIZATION={authorization.network.value}")
    print(f"ACQUISITION_AUTHORIZATION={authorization.acquisition.value}")
    print(f"SOURCE_REPRESENTATION={GIGADB_ORIGINAL_MAT_OBJECTS}")
    print("EXPECTED_OBJECT_COUNT=108")
    print(f"CANDIDATE_COLLECTION_GATE={gate_state}")
    print("HUMAN_APPROVAL_STATE=PENDING_HUMAN_APPROVAL")
    print("SCIENTIFIC_EXECUTION_AUTHORIZATION=DENY")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed Lee2019_MI Phase II-B acquisition foundation"
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("plan", help="describe the offline acquisition plan")
    subparsers.add_parser(
        "plan-collection",
        help="describe the offline, non-executable 108-object collection plan",
    )
    verify_collection = subparsers.add_parser(
        "verify-candidate-collection",
        help="offline collection verification skeleton; real plan remains unapproved",
    )
    verify_collection.add_argument("--cache-root", type=Path)
    collection_gate = subparsers.add_parser(
        "print-collection-gate-status",
        help="print the fail-closed collection gate without network access",
    )
    collection_gate.add_argument("--cache-root", type=Path)
    acquire_collection = subparsers.add_parser(
        "acquire-collection",
        help="refuse real collection acquisition while B3 approvals are unresolved",
    )
    acquire_collection.add_argument("--allow-acquisition", action="store_true")
    acquire_collection.add_argument("--allow-network", action="store_true")

    manifest = subparsers.add_parser(
        "verify-manifest", help="verify deterministic manifest self-identity"
    )
    manifest.add_argument("manifest", type=Path)

    cache = subparsers.add_parser(
        "verify-cache", help="verify a managed cache without network access"
    )
    cache.add_argument("--cache-root", type=Path, required=True)
    cache.add_argument("--allow-temporary-test-root", action="store_true")

    gate = subparsers.add_parser(
        "print-gate-status", help="print raw identity state without acquisition"
    )
    gate.add_argument("--cache-root", type=Path)
    gate.add_argument("--allow-temporary-test-root", action="store_true")

    acquire = subparsers.add_parser(
        "acquire", help="explicitly authorized archive acquisition only"
    )
    acquire.add_argument("--cache-root", type=Path, required=True)
    acquire.add_argument("--source-url", required=True)
    acquire.add_argument("--archive-filename", required=True)
    acquire.add_argument("--expected-length", type=int)
    acquire.add_argument("--expected-sha256", required=True)
    acquire.add_argument(
        "--inventory-plan",
        type=Path,
        help="JSON file containing expected_subject_count and exact raw files",
    )
    acquire.add_argument("--allow-acquisition", action="store_true")
    acquire.add_argument("--allow-network", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "plan"
    authorization = _authorization(args)
    try:
        if command == "plan":
            _print_status(authorization, not_acquired_result().state.value)
            print("PLAN=DOWNLOAD_VERIFY_EXTRACT_INVENTORY_MANIFEST_GATE")
            print("PLAN_WRITES_DATA=NO")
            return 0
        if command == "plan-collection":
            _print_collection_status(authorization)
            print("PLAN=VALIDATE_LOCK_STAGE_VERIFY_PUBLISH_MANIFEST_QUARANTINE")
            print("PLAN_WRITES_DATA=NO")
            print("CONCURRENCY_MODEL=SINGLE_COLLECTION_SINGLE_PROCESS")
            return 0
        if command in {
            "verify-candidate-collection",
            "print-collection-gate-status",
        }:
            _print_collection_status(authorization)
            print("REAL_COLLECTION_PLAN=UNAPPROVED")
            return 0 if command == "print-collection-gate-status" else 2
        if command == "acquire-collection":
            _print_collection_status(authorization)
            print("ERROR=REAL_COLLECTION_AUTHORIZATION_UNAVAILABLE", file=sys.stderr)
            return 2
        if command == "verify-manifest":
            manifest = read_manifest(args.manifest)
            _print_status(authorization, "NOT_ACQUIRED")
            print(f"MANIFEST_PAYLOAD_SHA256={manifest.manifest_payload_sha256}")
            return 0
        if command in {"verify-cache", "print-gate-status"}:
            result = evaluate_raw_identity_gate(
                args.cache_root,
                repository_root=REPO_ROOT,
                allow_temporary=args.allow_temporary_test_root,
            )
            _print_status(authorization, result.state.value)
            print(json.dumps({
                "affected_relative_paths": result.affected_relative_paths,
                "reason_codes": result.reason_codes,
            }, sort_keys=True))
            return 0 if command == "print-gate-status" or result.state.value == "PASS" else 2
        if command == "acquire":
            policy = NetworkPolicy(authorization=authorization)
            # Validate both switches before constructing the only real transport.
            policy.authorize_network()
            if args.inventory_plan is None:
                raise ManifestError("INVENTORY_PLAN_REQUIRED")
            inventory_payload = json.loads(args.inventory_plan.read_bytes())
            inventory = InventoryExpectation(
                files=tuple(
                    ExpectedRawFile(**record)
                    for record in inventory_payload["files"]
                ),
                expected_subject_count=inventory_payload[
                    "expected_subject_count"
                ],
            )
            request = AcquisitionRequest(
                cache_root=args.cache_root,
                repository_root=REPO_ROOT,
                source=SourceIdentity(
                    source_url=args.source_url,
                    archive_filename=args.archive_filename,
                    expected_size=args.expected_length or 0,
                    expected_sha256=args.expected_sha256,
                ),
                inventory=inventory,
                authorization=authorization,
            )
            result = run_acquisition(
                request,
                AcquisitionDependencies(
                    transport=ExplicitUrllibTransport(),
                    clock=lambda: datetime.now(timezone.utc),
                ),
            )
            _print_status(authorization, result.gate_result.state.value)
            print(json.dumps({
                "archive": request.source.archive_filename,
                "manifest_sha256": result.manifest_sha256,
                "sha256": result.archive_sha256,
                "state": result.state.value,
            }, sort_keys=True))
            return 0
    except (
        AcquisitionError,
        AcquisitionWorkflowError,
        ManifestError,
        NetworkPolicyError,
        OSError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        _print_status(authorization, "NOT_ACQUIRED")
        print(f"ERROR={exc}", file=sys.stderr)
        return 2
    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
