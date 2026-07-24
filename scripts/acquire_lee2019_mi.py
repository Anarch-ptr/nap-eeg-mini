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
    atomic_download,
    initialize_managed_cache,
    safe_extract_archive,
)
from src.external_replication.network_policy import (  # noqa: E402
    AcquisitionAuthorization,
    AuthorizationState,
    NetworkPolicy,
    NetworkPolicyError,
    TransportResponse,
)
from src.external_replication.raw_identity import (  # noqa: E402
    evaluate_raw_identity_gate,
    not_acquired_result,
)
from src.external_replication.raw_manifest import (  # noqa: E402
    ManifestError,
    ArchiveRecord,
    ExtractedManifest,
    raw_file_record,
    read_manifest,
    write_manifest,
)


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed Lee2019_MI Phase II-B acquisition foundation"
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("plan", help="describe the offline acquisition plan")

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
            parsed_source = urlparse(args.source_url)
            if parsed_source.scheme != "https" or not parsed_source.netloc:
                raise AcquisitionError(
                    AcquisitionFailureReason.SOURCE_IDENTITY_INVALID
                )
            if (
                len(args.expected_sha256) != 64
                or any(character not in "0123456789abcdefABCDEF" for character in args.expected_sha256)
            ):
                raise AcquisitionError(
                    AcquisitionFailureReason.SOURCE_IDENTITY_INVALID
                )
            if Path(args.archive_filename).name != args.archive_filename:
                raise AcquisitionError(
                    AcquisitionFailureReason.SOURCE_IDENTITY_INVALID
                )
            policy = NetworkPolicy(authorization=authorization)
            policy.authorize_acquisition()
            cache_root = initialize_managed_cache(
                args.cache_root,
                repository_root=REPO_ROOT,
            )
            policy.authorize_transport(ExplicitUrllibTransport())
            receipt = atomic_download(
                source_url=args.source_url,
                target=cache_root / "archives" / args.archive_filename,
                policy=policy,
                transport=ExplicitUrllibTransport(),
                expected_length=args.expected_length,
                expected_sha256=args.expected_sha256,
            )
            extracted = safe_extract_archive(
                receipt.target,
                cache_root / "raw",
            )
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            archive_record = ArchiveRecord(
                schema_version=1,
                dataset_name="Lee2019_MI",
                implementation_identifier=None,
                source_url=receipt.source_url,
                retrieval_timestamp=timestamp,
                http_status=receipt.http_status,
                content_length=receipt.content_length,
                etag=receipt.etag,
                last_modified=receipt.last_modified,
                redirect_chain=receipt.redirect_chain,
                archive_filename=receipt.target.name,
                downloaded_byte_count=receipt.downloaded_byte_count,
                sha256=receipt.sha256,
                transport_identifier=receipt.transport_identifier,
            )
            manifest = ExtractedManifest(
                schema_version=1,
                dataset_name="Lee2019_MI",
                source_archive=archive_record,
                generated_timestamp=timestamp,
                files=tuple(
                    raw_file_record(
                        path,
                        relative_to=cache_root / "raw",
                        source_archive_sha256=receipt.sha256,
                    )
                    for path in extracted
                ),
            )
            manifest_path = cache_root / "manifests" / "raw_manifest.json"
            write_manifest(manifest_path, manifest)
            read_manifest(manifest_path)
            gate_result = evaluate_raw_identity_gate(
                cache_root,
                repository_root=REPO_ROOT,
                expected_subject_count=54,
            )
            _print_status(authorization, gate_result.state.value)
            print(json.dumps({
                "archive": receipt.target.name,
                "byte_count": receipt.downloaded_byte_count,
                "manifest": manifest_path.name,
                "sha256": receipt.sha256,
            }, sort_keys=True))
            return 0 if gate_result.state.value == "PASS" else 2
    except (AcquisitionError, ManifestError, NetworkPolicyError, OSError) as exc:
        _print_status(authorization, "NOT_ACQUIRED")
        print(f"ERROR={exc}", file=sys.stderr)
        return 2
    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
