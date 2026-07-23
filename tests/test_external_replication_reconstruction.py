from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.external_replication.reconstruction import (
    BOOTSTRAP_METHOD,
    EXPECTED_ARTIFACT_COUNT,
    HASH_ENFORCEMENT_AT_INSTALL,
    ApprovedArtifact,
    ReconstructionIntegrityError,
    build_install_argv,
    install_preverified_artifacts,
    load_approved_artifacts,
    normalized_install_argv,
    verify_wheelhouse,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RECONSTRUCTION_RECORD = (
    REPO_ROOT
    / "manifests"
    / "external_boundary_replication_environment_reconstruction_v1.json"
)


class ReconstructionTests(unittest.TestCase):
    def artifact(self, data: bytes = b"approved", **changes) -> ApprovedArtifact:
        values = {
            "normalized_name": "example",
            "version": "1.0",
            "filename": "example-1.0-py3-none-any.whl",
            "byte_length": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_url": "https://example.invalid/example.whl",
        }
        values.update(changes)
        return ApprovedArtifact(**values)

    def wheelhouse(self, data: bytes = b"approved"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        artifact = self.artifact(data)
        (root / artifact.filename).write_bytes(data)
        return root, artifact

    def test_reconstruction_authority_accepts_no_manifest_override(self):
        self.assertEqual(tuple(inspect.signature(load_approved_artifacts).parameters), ())
        _root, artifacts = load_approved_artifacts()
        self.assertEqual(len(artifacts), EXPECTED_ARTIFACT_COUNT)

    def test_install_command_has_required_flags_and_62_exact_paths(self):
        root, artifacts = load_approved_artifacts()
        argv = build_install_argv(
            root / ".venv" / "Scripts" / "python.exe",
            root / "approved-wheelhouse",
            artifacts,
        )
        self.assertEqual(argv[1:4], ("-m", "pip", "install"))
        self.assertIn("--no-index", argv)
        self.assertIn("--no-cache-dir", argv)
        self.assertIn("--no-deps", argv)
        self.assertNotIn("--index-url", argv)
        self.assertNotIn("--extra-index-url", argv)
        self.assertNotIn("--find-links", argv)
        self.assertEqual(len(argv[7:]), EXPECTED_ARTIFACT_COUNT)
        for argument, artifact in zip(argv[7:], artifacts):
            self.assertEqual(Path(argument).name, artifact.filename)
        portable = normalized_install_argv(artifacts)
        self.assertEqual(len(portable[7:]), EXPECTED_ARTIFACT_COUNT)
        self.assertEqual(
            HASH_ENFORCEMENT_AT_INSTALL,
            "PREVERIFIED_EXACT_ARTIFACT_PATHS",
        )

    def test_sha_failure_aborts_before_pip(self):
        wheelhouse, artifact = self.wheelhouse()
        bad = self.artifact(sha256="0" * 64)
        calls = []

        def runner(*args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args[0], 0, "", "")

        with self.assertRaises(ReconstructionIntegrityError):
            install_preverified_artifacts(
                Path("python.exe"), wheelhouse, (bad,), runner=runner
            )
        self.assertEqual(calls, [])

    def test_length_failure_aborts_before_pip(self):
        wheelhouse, artifact = self.wheelhouse()
        bad = self.artifact(byte_length=artifact.byte_length + 1)
        calls = []

        def runner(*args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args[0], 0, "", "")

        with self.assertRaises(ReconstructionIntegrityError):
            install_preverified_artifacts(
                Path("python.exe"), wheelhouse, (bad,), runner=runner
            )
        self.assertEqual(calls, [])

    def test_unapproved_candidate_is_rejected_before_pip(self):
        wheelhouse, artifact = self.wheelhouse()
        (wheelhouse / "alternate-9.9-py3-none-any.whl").write_bytes(b"alternate")
        calls = []

        def runner(*args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args[0], 0, "", "")

        with self.assertRaisesRegex(
            ReconstructionIntegrityError, "UNAPPROVED_WHEELHOUSE_CANDIDATE"
        ):
            install_preverified_artifacts(
                Path("python.exe"), wheelhouse, (artifact,), runner=runner
            )
        self.assertEqual(calls, [])

    def test_missing_approved_wheel_prevents_install(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        calls = []

        def runner(*args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args[0], 0, "", "")

        with self.assertRaisesRegex(
            ReconstructionIntegrityError, "APPROVED_WHEEL_MISSING"
        ):
            install_preverified_artifacts(
                Path("python.exe"),
                Path(temporary.name),
                (self.artifact(),),
                runner=runner,
            )
        self.assertEqual(calls, [])

    def test_verified_exact_path_install_invokes_pip_once(self):
        wheelhouse, artifact = self.wheelhouse()
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "", "")

        inventory, results, command = install_preverified_artifacts(
            Path("python.exe"), wheelhouse, (artifact,), runner=runner
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(inventory), 1)
        self.assertEqual(results[0].verification_status, "PASS")
        self.assertEqual(command["return_code"], 0)
        self.assertIn("--no-index", calls[0][0])
        self.assertEqual(Path(calls[0][0][-1]).name, artifact.filename)

    def test_bootstrap_identity_is_explicitly_nonruntime(self):
        self.assertEqual(BOOTSTRAP_METHOD, "PYTHON_VENV_ENSUREPIP")
        record = json.loads(RECONSTRUCTION_RECORD.read_bytes())
        self.assertEqual(record["record_trust_role"], "EVIDENCE_ONLY")
        self.assertEqual(record["bootstrap"]["method"], BOOTSTRAP_METHOD)
        self.assertEqual(
            record["bootstrap"]["bootstrap_python"]["implementation"],
            "CPython",
        )
        self.assertEqual(
            record["bootstrap"]["bootstrap_python"]["version"],
            "3.12.10",
        )
        self.assertEqual(record["bootstrap"]["initial_pip"]["pip_version"], "25.0.1")
        self.assertEqual(
            record["preinstall_artifact_verification"]["verified_count"],
            EXPECTED_ARTIFACT_COUNT,
        )
        self.assertEqual(
            record["preinstall_artifact_verification"]["failure_count"],
            0,
        )
        self.assertEqual(
            len(record["installation"]["command"]["argv"][7:]),
            EXPECTED_ARTIFACT_COUNT,
        )


if __name__ == "__main__":
    unittest.main()
