from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.external_replication.reconstruction as reconstruction_module
from src.external_replication.reconstruction import (
    BOOTSTRAP_METHOD,
    EXPECTED_ARTIFACT_COUNT,
    HASH_ENFORCEMENT_AT_INSTALL,
    ApprovedArtifact,
    ReconstructionIntegrityError,
    build_install_argv,
    enforce_reference_platform_compatibility,
    install_preverified_artifacts,
    load_approved_artifacts,
    normalized_install_argv,
    verify_wheelhouse,
    _isolated_startup_argv,
    _load_committed_platform_contract,
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

    def test_reference_platform_and_all_frozen_wheel_tags_are_compatible(self):
        _root, artifacts = load_approved_artifacts()
        result = enforce_reference_platform_compatibility(artifacts)
        self.assertEqual(
            result["compatibility_status"],
            "PASS_FROZEN_WINDOWS_AMD64_CP312",
        )
        self.assertEqual(result["compatible_wheel_count"], EXPECTED_ARTIFACT_COUNT)
        self.assertEqual(
            result["manifest_sha256"],
            reconstruction_module.EXPECTED_ENVIRONMENT_MANIFEST_SHA256,
        )

    def test_platform_contract_is_loaded_from_hash_validated_manifest(self):
        contract = _load_committed_platform_contract()
        self.assertEqual(contract["os"], "Windows")
        self.assertEqual(contract["machine_architecture"], "AMD64")
        self.assertEqual(contract["python_version"], "3.12.10")
        self.assertEqual(contract["python_tag"], "cp312")
        self.assertEqual(tuple(inspect.signature(_load_committed_platform_contract).parameters), ())

    def test_reconstruction_uses_absolute_isolated_startup_entrypoint(self):
        argv = _isolated_startup_argv(
            REPO_ROOT,
            REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        )
        self.assertEqual(argv[1:5], ("-I", "-E", "-B", "-S"))
        self.assertEqual(
            Path(argv[5]),
            (REPO_ROOT / "scripts" / "verify_external_replication_startup.py").resolve(),
        )

    def test_platform_mismatch_aborts_before_pip(self):
        wheelhouse, artifact = self.wheelhouse()
        calls = []

        def runner(*args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args[0], 0, "", "")

        def observed(**changes):
            values = {
                "os_name": "nt",
                "sys_platform": "win32",
                "platform_system": "Windows",
                "machine": "AMD64",
                "python_implementation": "CPython",
                "python_version": "3.12.10",
                "python_cache_tag": "cpython-312",
                "pointer_bits": 64,
            }
            values.update(changes)
            return values

        attacks = (
            observed(sys_platform="linux"),
            observed(platform_system="Linux"),
            observed(platform_system="Darwin"),
            observed(machine="ARM64"),
            observed(machine="x86"),
            observed(pointer_bits=32),
            observed(python_version="3.12.11"),
            observed(python_cache_tag="cpython-311"),
            observed(python_implementation="PyPy"),
        )
        for attack in attacks:
            with self.subTest(attack=attack):
                with patch.object(
                    reconstruction_module,
                    "_platform_observations",
                    return_value=attack,
                ):
                    with self.assertRaises(ReconstructionIntegrityError):
                        install_preverified_artifacts(
                            Path("python.exe"),
                            wheelhouse,
                            (artifact,),
                            runner=runner,
                        )
        self.assertEqual(calls, [])

    def test_amd64_aliases_are_accepted_on_windows(self):
        _root, artifacts = load_approved_artifacts()
        for machine in ("AMD64", "amd64", "x86_64"):
            with self.subTest(machine=machine):
                with patch.object(
                    reconstruction_module,
                    "_platform_observations",
                    return_value={
                        "os_name": "nt",
                        "sys_platform": "win32",
                        "platform_system": "Windows",
                        "machine": machine,
                        "python_implementation": "CPython",
                        "python_version": "3.12.10",
                        "python_cache_tag": "cpython-312",
                        "pointer_bits": 64,
                    },
                ):
                    result = enforce_reference_platform_compatibility(artifacts)
                self.assertEqual(result["machine"], "AMD64")

    def test_tampered_manifest_bytes_fail_closed(self):
        original = Path.read_bytes

        def tampered(path):
            if path.name == "external_boundary_replication_environment_v1.json":
                return original(path) + b" "
            return original(path)

        with patch.object(Path, "read_bytes", tampered):
            with self.assertRaisesRegex(
                ReconstructionIntegrityError,
                "ENVIRONMENT_MANIFEST_SHA256_MISMATCH",
            ):
                enforce_reference_platform_compatibility(())

    def test_alternative_torch_wheel_fails_closed_for_full_set(self):
        _root, artifacts = load_approved_artifacts()
        altered = tuple(
            dataclasses.replace(
                artifact,
                filename="torch-2.12.1-cp312-cp312-win_amd64.whl",
                version="2.12.1",
            )
            if artifact.normalized_name == "torch"
            else artifact
            for artifact in artifacts
        )
        with self.assertRaisesRegex(
            ReconstructionIntegrityError,
            "TORCH_WHEEL_IDENTITY_MISMATCH",
        ):
            enforce_reference_platform_compatibility(altered)

    def test_incompatible_wheel_tag_aborts_before_pip(self):
        wheelhouse, artifact = self.wheelhouse()
        incompatible = self.artifact(
            filename="example-1.0-cp311-cp311-win_amd64.whl"
        )
        (wheelhouse / artifact.filename).rename(wheelhouse / incompatible.filename)
        calls = []

        def runner(*args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args[0], 0, "", "")

        with self.assertRaisesRegex(
            ReconstructionIntegrityError,
            "APPROVED_WHEEL_TAG_INCOMPATIBLE",
        ):
            install_preverified_artifacts(
                Path("python.exe"),
                wheelhouse,
                (incompatible,),
                runner=runner,
            )
        self.assertEqual(calls, [])

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
