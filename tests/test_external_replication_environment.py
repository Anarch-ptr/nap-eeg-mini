from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.external_replication.environment import (
    CORE_SCIENTIFIC_DISTRIBUTIONS,
    ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH,
    ENVIRONMENT_ENFORCEMENT_GATE_STATUS,
    ENVIRONMENT_LOCK_RELATIVE_PATH,
    ENVIRONMENT_MANIFEST_RELATIVE_PATH,
    EXPECTED_ENVIRONMENT_ARTIFACT_MANIFEST_SHA256,
    EXPECTED_ENVIRONMENT_LOCK_SHA256,
    EXPECTED_ENVIRONMENT_MANIFEST_SHA256,
    CALLER_REPOSITORY_ROOT_ROLE,
    PRODUCTION_AUTHORIZATION_ROLE,
    PRODUCTION_REPOSITORY_ROOT_ROLE,
    SYNTHETIC_EVALUATOR_ROLE,
    EnvironmentFailureReason,
    EnvironmentLockIntegrityError,
    EnvironmentNotConformantError,
    FatalTrustedRepositoryRootMismatch,
    EnvironmentSnapshot,
    EnvironmentStatus,
    _active_dependency_names,
    _evaluate_environment_snapshot,
    _read_environment_lock_after_prerequisites,
    capture_current_environment,
    enforce_environment_or_abort,
    read_exact_requirements,
    resolve_production_repository_root,
    trusted_repository_root,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_LOCK = REPO_ROOT / ENVIRONMENT_LOCK_RELATIVE_PATH
PRODUCTION_MANIFEST = REPO_ROOT / ENVIRONMENT_MANIFEST_RELATIVE_PATH
PRODUCTION_ARTIFACTS = REPO_ROOT / ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH
RECONSTRUCTION_RECORD = (
    REPO_ROOT
    / "manifests"
    / "external_boundary_replication_environment_reconstruction_v1.json"
)

LOCK_SHA = "f079f7a40243ad365dfa984980da1e825932b0d317adc94c36da78b3cd5ac121"
MANIFEST_SHA = "dd0ca1c0a1229a79c35a040741e351efd4fe134a91b203c750292c552d921b0a"
ARTIFACT_SHA = "49bea1b78a6f290a09e39049bc4116f044837dd85d0d98449d50e00eb3a6fd65"
DEPENDENCY_COUNT = 62
CORE_VERSIONS = {
    "moabb": "1.5.0",
    "mne": "1.12.1",
    "numpy": "2.5.0",
    "scipy": "1.18.0",
    "torch": "2.12.1+cu130",
    "scikit-learn": "1.9.0",
}


class EnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.locked_versions = read_exact_requirements(PRODUCTION_LOCK)
        cls.lock = _read_environment_lock_after_prerequisites(REPO_ROOT)

    def make_repo(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for relative in (
            ENVIRONMENT_LOCK_RELATIVE_PATH,
            ENVIRONMENT_MANIFEST_RELATIVE_PATH,
            ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH,
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / relative, target)
        return root

    def snapshot(self, **changes) -> EnvironmentSnapshot:
        canonical = EnvironmentSnapshot(
            executable=str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"),
            python_version="3.12.10",
            python_version_info=(3, 12, 10),
            python_implementation="CPython",
            prefix=str(REPO_ROOT / ".venv"),
            base_prefix=r"E:\Study_Software\Python",
            system="Windows",
            machine="AMD64",
            platform_description="Windows-test",
            installed_versions=tuple(self.locked_versions.items()),
            active_dependency_names=tuple(sorted(self.locked_versions)),
            implementation_commit="future-head-is-allowed",
        )
        return dataclasses.replace(canonical, **changes)

    def evaluate(self, **changes):
        return _evaluate_environment_snapshot(
            REPO_ROOT, self.lock, self.snapshot(**changes)
        )

    def test_fixed_hashes_and_dependency_count_are_independent_literals(self):
        self.assertEqual(EXPECTED_ENVIRONMENT_LOCK_SHA256, LOCK_SHA)
        self.assertEqual(EXPECTED_ENVIRONMENT_MANIFEST_SHA256, MANIFEST_SHA)
        self.assertEqual(EXPECTED_ENVIRONMENT_ARTIFACT_MANIFEST_SHA256, ARTIFACT_SHA)
        self.assertEqual(hashlib.sha256(PRODUCTION_LOCK.read_bytes()).hexdigest(), LOCK_SHA)
        self.assertEqual(hashlib.sha256(PRODUCTION_MANIFEST.read_bytes()).hexdigest(), MANIFEST_SHA)
        self.assertEqual(hashlib.sha256(PRODUCTION_ARTIFACTS.read_bytes()).hexdigest(), ARTIFACT_SHA)
        self.assertEqual(len(self.locked_versions), DEPENDENCY_COUNT)
        self.assertEqual(self.lock.artifact_record_count, DEPENDENCY_COUNT)

    def test_clean_reconstruction_record_is_machine_readable_and_fail_closed(self):
        record = json.loads(RECONSTRUCTION_RECORD.read_bytes())
        self.assertEqual(record["record_trust_role"], "EVIDENCE_ONLY")
        self.assertEqual(
            record["wheelhouse"]["approved_present_artifacts"],
            DEPENDENCY_COUNT,
        )
        self.assertEqual(record["lock"]["sha256"], LOCK_SHA)
        self.assertEqual(record["artifact_manifest"]["sha256"], ARTIFACT_SHA)
        self.assertEqual(record["environment_manifest"]["sha256"], MANIFEST_SHA)
        self.assertTrue(record["installation"]["no_index"])
        self.assertTrue(record["installation"]["no_cache_dir"])
        self.assertTrue(record["installation"]["no_deps"])
        self.assertEqual(
            record["installation"]["network_fallback"],
            "IMPOSSIBLE_BY_INSTALL_COMMAND",
        )
        self.assertEqual(
            record["post_install"]["startup_result"][
                "scientific_execution_authorization"
            ],
            "DENY",
        )

    def test_independent_core_version_literals(self):
        self.assertEqual(set(CORE_SCIENTIFIC_DISTRIBUTIONS), set(CORE_VERSIONS))
        for name, version in CORE_VERSIONS.items():
            self.assertEqual(self.locked_versions[name], version)

    def test_synthetic_evaluator_is_private_and_current_process_is_production(self):
        self.assertEqual(SYNTHETIC_EVALUATOR_ROLE, "TEST_AND_PURE_LOGIC_ONLY")
        self.assertEqual(PRODUCTION_AUTHORIZATION_ROLE, "CURRENT_PROCESS_ONLY")
        self.assertEqual(
            tuple(inspect.signature(capture_current_environment).parameters),
            ("repo_root",),
        )
        self.assertEqual(
            tuple(inspect.signature(enforce_environment_or_abort).parameters),
            ("repo_root",),
        )
        self.assertEqual(
            PRODUCTION_REPOSITORY_ROOT_ROLE,
            "EXECUTING_MODULE_PHYSICAL_ROOT",
        )
        self.assertEqual(
            CALLER_REPOSITORY_ROOT_ROLE,
            "OPTIONAL_TRUSTED_ROOT_CONSISTENCY_ASSERTION",
        )

    def test_caller_cannot_inject_observations_or_report(self):
        forbidden = (
            {"version_lookup": lambda _name: "forged"},
            {"python_version": "3.12.10"},
            {"protocol_result": object()},
            {"report": self.evaluate()},
        )
        for kwargs in forbidden:
            with self.subTest(kwargs=tuple(kwargs)):
                with self.assertRaises(TypeError):
                    enforce_environment_or_abort(**kwargs)

    def test_exact_synthetic_environment_is_conformant(self):
        report = self.evaluate()
        self.assertEqual(report.status, EnvironmentStatus.CONFORMANT)
        self.assertEqual(report.failure_reasons, ())

    def test_missing_required_dependency_is_explicitly_nonconformant(self):
        versions = dict(self.locked_versions)
        versions.pop("numpy")
        report = self.evaluate(installed_versions=tuple(versions.items()))
        self.assertEqual(report.status, EnvironmentStatus.NONCONFORMANT)
        numpy = next(
            item for item in report.dependencies if item.distribution == "numpy"
        )
        self.assertEqual(
            numpy.failure_reason,
            EnvironmentFailureReason.DEPENDENCY_MISSING,
        )
        with self.assertRaises(TypeError):
            enforce_environment_or_abort(report=report)

    def test_python_implementation_and_patch_are_exact(self):
        attacks = (
            ({"python_implementation": "PyPy"}, EnvironmentFailureReason.PYTHON_IMPLEMENTATION_MISMATCH),
            ({"python_version": "3.12.9", "python_version_info": (3, 12, 9)}, EnvironmentFailureReason.PYTHON_VERSION_MISMATCH),
            ({"python_version": "3.12.11", "python_version_info": (3, 12, 11)}, EnvironmentFailureReason.PYTHON_VERSION_MISMATCH),
        )
        for changes, reason in attacks:
            with self.subTest(changes=changes):
                self.assertIn(reason, self.evaluate(**changes).failure_reasons)

    def test_executable_and_prefix_must_be_repository_venv(self):
        report = self.evaluate(
            executable=r"E:\Study_Software\Python\python.exe",
            prefix=r"E:\Study_Software\Python",
        )
        self.assertIn(EnvironmentFailureReason.PYTHON_EXECUTABLE_MISMATCH, report.failure_reasons)
        self.assertIn(EnvironmentFailureReason.VENV_PREFIX_MISMATCH, report.failure_reasons)

    def test_platform_and_machine_are_exact(self):
        self.assertIn(
            EnvironmentFailureReason.PLATFORM_SYSTEM_MISMATCH,
            self.evaluate(system="Linux").failure_reasons,
        )
        self.assertIn(
            EnvironmentFailureReason.PLATFORM_MACHINE_MISMATCH,
            self.evaluate(machine="ARM64").failure_reasons,
        )

    def test_dependency_and_torch_build_mismatches_fail(self):
        for distribution in CORE_VERSIONS:
            versions = dict(self.locked_versions)
            versions[distribution] = "0.invalid"
            report = self.evaluate(installed_versions=tuple(versions.items()))
            with self.subTest(distribution=distribution):
                self.assertIn(
                    EnvironmentFailureReason.DEPENDENCY_VERSION_MISMATCH,
                    report.failure_reasons,
                )

    def test_complete_active_dependency_closure(self):
        closure = set(_active_dependency_names(tuple(self.locked_versions)))
        self.assertEqual(closure - set(self.locked_versions), set())
        self.assertEqual(closure, set(self.locked_versions))
        report = self.evaluate(
            active_dependency_names=tuple(sorted(closure | {"unlocked-active"}))
        )
        self.assertIn(
            EnvironmentFailureReason.ACTIVE_DEPENDENCY_CLOSURE_INCOMPLETE,
            report.failure_reasons,
        )

    def test_strict_lock_grammar_rejects_ambiguous_syntax(self):
        attacks = (
            "numpy==2.*\n",
            'numpy==2.5.0; python_version >= "3.12"\n',
            "numpy[foo]==2.5.0\n",
            "numpy==2.5.0 # comment\n",
            "numpy>=2.5.0\n",
            "numpy~=2.5.0\n",
            "numpy>=2,<3\n",
            "numpy\n",
            "numpy @ https://example.invalid/numpy.whl\n",
            "-e package\n",
            ".\\local-package\n",
            "git+https://example.invalid/project.git\n",
            "--index-url https://example.invalid/simple\n",
        )
        for content in attacks:
            with self.subTest(content=content.strip()):
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "lock.txt"
                    path.write_text(content, encoding="utf-8", newline="\n")
                    with self.assertRaises(EnvironmentLockIntegrityError):
                        read_exact_requirements(path)

    def test_empty_lock_is_fatal_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "empty.lock"
            path.write_bytes(b"")
            with self.assertRaises(EnvironmentLockIntegrityError) as caught:
                read_exact_requirements(path)
        self.assertEqual(
            caught.exception.reason,
            EnvironmentFailureReason.ENVIRONMENT_LOCK_CORRUPT,
        )

    def test_malformed_unresolved_lock_is_fatal(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "malformed.lock"
            path.write_text("numpy???2.5.0\n", encoding="utf-8", newline="\n")
            with self.assertRaises(EnvironmentLockIntegrityError) as caught:
                read_exact_requirements(path)
        self.assertEqual(
            caught.exception.reason,
            EnvironmentFailureReason.ENVIRONMENT_LOCK_CORRUPT,
        )

    def test_normalized_duplicates_and_conflicts_fail(self):
        attacks = (
            "numpy==2.5.0\nNumPy==2.5.0\n",
            "numpy==2.5.0\nNumPy==2.4.0\n",
            "scikit-learn==1.9.0\nscikit_learn==1.9.0\n",
            "scikit-learn==1.9.0\nscikit.learn==1.8.0\n",
        )
        for content in attacks:
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / "lock.txt"
                    path.write_text(content, encoding="utf-8", newline="\n")
                    with self.assertRaises(EnvironmentLockIntegrityError):
                        read_exact_requirements(path)

    def test_lock_manifest_and_artifact_mutations_fail_closed(self):
        targets = (
            (ENVIRONMENT_LOCK_RELATIVE_PATH, EnvironmentFailureReason.ENVIRONMENT_LOCK_SHA256_MISMATCH),
            (ENVIRONMENT_MANIFEST_RELATIVE_PATH, EnvironmentFailureReason.ENVIRONMENT_MANIFEST_SHA256_MISMATCH),
            (ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH, EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_MANIFEST_SHA256_MISMATCH),
        )
        for relative, reason in targets:
            with self.subTest(relative=str(relative)):
                root = self.make_repo()
                path = root / relative
                path.write_bytes(path.read_bytes() + b" ")
                with self.assertRaises(EnvironmentLockIntegrityError) as caught:
                    _read_environment_lock_after_prerequisites(root)
                self.assertEqual(caught.exception.reason, reason)

    def test_artifact_record_and_torch_hash_mutations_fail_closed(self):
        for target in ("numpy", "torch"):
            root = self.make_repo()
            artifact_path = root / ENVIRONMENT_ARTIFACT_MANIFEST_RELATIVE_PATH
            artifact = json.loads(artifact_path.read_bytes())
            record = next(r for r in artifact["records"] if r["normalized_name"] == target)
            record["artifact_sha256"] = "0" * 64
            mutated = (json.dumps(artifact, sort_keys=True, indent=2) + "\n").encode()
            artifact_path.write_bytes(mutated)
            with self.assertRaises(EnvironmentLockIntegrityError) as caught:
                _read_environment_lock_after_prerequisites(root)
            self.assertEqual(
                caught.exception.reason,
                EnvironmentFailureReason.ENVIRONMENT_ARTIFACT_MANIFEST_SHA256_MISMATCH,
            )

    def test_current_canonical_process_is_conformant(self):
        report = capture_current_environment(REPO_ROOT)
        self.assertEqual(report.status, EnvironmentStatus.CONFORMANT)
        self.assertEqual(Path(report.executable).resolve(), Path(sys.executable).resolve())

    def test_noncanonical_process_is_rejected(self):
        interpreter = Path(r"E:\Study_Software\Python\python.exe")
        completed = subprocess.run(
            [
                str(interpreter),
                "-c",
                "from src.external_replication.environment import enforce_environment_or_abort; enforce_environment_or_abort()",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("ENVIRONMENT_NOT_CONFORMANT", completed.stderr)

    def test_noncanonical_process_cannot_use_original_forgery_inputs(self):
        interpreter = Path(r"E:\Study_Software\Python\python.exe")
        code = (
            "from src.external_replication.environment import enforce_environment_or_abort; "
            "attacks=({'version_lookup':lambda n:'forged'},"
            "{'python_version':'3.12.10'},{'protocol_result':object()},"
            "{'report':object()}); blocked=0; "
            "\nfor kwargs in attacks:\n"
            " try: enforce_environment_or_abort(**kwargs)\n"
            " except TypeError: blocked+=1\n"
            "print(blocked)"
        )
        completed = subprocess.run(
            [str(interpreter), "-c", code],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "4")

    def test_production_enforcement_passes_canonical_process(self):
        self.assertEqual(
            enforce_environment_or_abort(REPO_ROOT).status,
            EnvironmentStatus.CONFORMANT,
        )

    def test_repo_root_is_only_a_same_physical_root_assertion(self):
        alias = REPO_ROOT / "src" / ".."
        self.assertEqual(
            resolve_production_repository_root(alias),
            trusted_repository_root(),
        )
        self.assertEqual(
            enforce_environment_or_abort(alias).status,
            EnvironmentStatus.CONFORMANT,
        )

    def test_fake_root_and_junction_attack_fail_before_artifact_reads(self):
        root = self.make_repo()
        junction = root / ".venv"
        junction_created = False
        if os.name == "nt":
            completed = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(REPO_ROOT / ".venv")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            junction_created = completed.returncode == 0
        else:
            junction.symlink_to(REPO_ROOT / ".venv", target_is_directory=True)
            junction_created = True
        if junction_created:
            self.addCleanup(lambda: junction.exists() and os.rmdir(junction))

        fake_reads = []
        original = Path.read_bytes

        def tracked(path):
            resolved = path.resolve()
            if resolved == root or root in resolved.parents:
                fake_reads.append(resolved)
            return original(path)

        with patch.object(Path, "read_bytes", tracked):
            with self.assertRaises(FatalTrustedRepositoryRootMismatch):
                enforce_environment_or_abort(root)
        self.assertEqual(fake_reads, [])

    def test_gate_status_is_current_process_only(self):
        self.assertEqual(
            ENVIRONMENT_ENFORCEMENT_GATE_STATUS,
            "IMPLEMENTED_CURRENT_PROCESS_ONLY",
        )


if __name__ == "__main__":
    unittest.main()
