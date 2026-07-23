from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.external_replication.environment as environment_module
import src.external_replication.startup as startup_module
from src.external_replication.environment import (
    EnvironmentFailureReason,
    EnvironmentStatus,
    FatalTrustedRepositoryRootMismatch,
    capture_current_environment,
)
from src.external_replication.protocol_identity import (
    ProtocolIdentityError,
    ProtocolIdentityStatus,
    verify_protocol_identity,
)
from src.external_replication.startup import (
    enforce_pre_scientific_startup_or_abort,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCIENTIFIC_MODULES = {"numpy", "torch", "scipy", "mne", "moabb", "sklearn", "pandas"}


class StartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity = verify_protocol_identity(REPO_ROOT)

    def failed_identity(self):
        return dataclasses.replace(
            self.identity,
            status=ProtocolIdentityStatus.FAIL,
            failure_reasons=("SYNTHETIC_PROTOCOL_FAILURE",),
        )

    def test_protocol_failure_stops_startup_before_environment(self):
        with (
            patch.object(startup_module, "verify_protocol_identity", return_value=self.failed_identity()),
            patch.object(startup_module, "_capture_current_environment_after_prerequisites") as environment_gate,
        ):
            with self.assertRaises(ProtocolIdentityError):
                enforce_pre_scientific_startup_or_abort(REPO_ROOT)
        environment_gate.assert_not_called()

    def test_direct_environment_call_reads_no_environment_files_after_protocol_failure(self):
        reads = []
        original = Path.read_bytes

        def tracked(path):
            reads.append(path)
            return original(path)

        with (
            patch.object(environment_module, "verify_protocol_identity", return_value=self.failed_identity()),
            patch.object(Path, "read_bytes", tracked),
            patch.object(environment_module.metadata, "version") as package_lookup,
        ):
            report = capture_current_environment(REPO_ROOT)
        self.assertEqual(report.status, EnvironmentStatus.NONCONFORMANT)
        self.assertEqual(
            report.failure_reasons,
            (EnvironmentFailureReason.PROTOCOL_IDENTITY_MISMATCH,),
        )
        self.assertEqual(reads, [])
        package_lookup.assert_not_called()

    def test_protocol_first_import_has_no_scientific_eager_imports(self):
        code = (
            "import sys; "
            "from src.external_replication.protocol_identity import verify_protocol_identity; "
            "r=verify_protocol_identity(); "
            f"blocked={sorted(SCIENTIFIC_MODULES)!r}; "
            "loaded=[n for n in blocked if n in sys.modules]; "
            "print(r.status.value); print(','.join(loaded))"
        )
        completed = subprocess.run(
            [sys.executable, "-S", "-B", "-c", code],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines(), ["PASS", ""])

    def test_forced_protocol_failure_in_fresh_process_imports_no_science(self):
        code = (
            "import dataclasses,sys; "
            "import src.external_replication.startup as s; "
            "from src.external_replication.protocol_identity import ProtocolIdentityStatus,verify_protocol_identity; "
            "i=dataclasses.replace(verify_protocol_identity(),status=ProtocolIdentityStatus.FAIL,failure_reasons=('forced',)); "
            "s.verify_protocol_identity=lambda root:i; "
            "\ntry:s.enforce_pre_scientific_startup_or_abort()\n"
            "except Exception:pass\n"
            f"print(','.join(n for n in {sorted(SCIENTIFIC_MODULES)!r} if n in sys.modules))"
        )
        completed = subprocess.run(
            [sys.executable, "-S", "-B", "-c", code],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "")

    def test_startup_passes_only_through_environment_stage(self):
        result = enforce_pre_scientific_startup_or_abort(REPO_ROOT)
        self.assertEqual(result.status, "PASS_THROUGH_ENVIRONMENT_STAGE")
        self.assertEqual(result.protocol_identity_gate, "PASS")
        self.assertEqual(result.implementation_constants_conformance_gate, "PASS")
        self.assertEqual(result.environment_enforcement_gate, "PASS")
        self.assertEqual(result.raw_data_identity_gate, "NOT_IMPLEMENTED_PHASE_II_B")
        self.assertEqual(result.scientific_execution_authorization, "DENY")

    def test_unrelated_cwd_cannot_change_authoritative_root(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            try:
                os.chdir(temporary)
                result = enforce_pre_scientific_startup_or_abort()
            finally:
                os.chdir(original)
        self.assertEqual(result.status, "PASS_THROUGH_ENVIRONMENT_STAGE")
        self.assertEqual(result.scientific_execution_authorization, "DENY")

    def test_startup_rejects_different_declared_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FatalTrustedRepositoryRootMismatch):
                enforce_pre_scientific_startup_or_abort(temporary)


if __name__ == "__main__":
    unittest.main()
