from __future__ import annotations

import tempfile
import unittest
from importlib import metadata
from pathlib import Path

from src.external_replication.environment import (
    EnvironmentFailureReason,
    EnvironmentNotConformantError,
    EnvironmentStatus,
    capture_environment,
    enforce_environment_or_abort,
)


class EnvironmentTests(unittest.TestCase):
    def make_repo(self, requirements: str):
        temporary = tempfile.TemporaryDirectory()
        Path(temporary.name, "requirements.txt").write_text(requirements, encoding="utf-8")
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    @staticmethod
    def lookup(versions):
        def get(name):
            if name not in versions:
                raise metadata.PackageNotFoundError(name)
            return versions[name]

        return get

    def all_versions(self, moabb="1.5.0"):
        return {
            "moabb": moabb,
            "mne": "1",
            "numpy": "1",
            "scipy": "1",
            "torch": "1",
            "scikit-learn": "1",
        }

    def test_exact_requirement_match_but_unlocked_dependencies_remain_unresolved(self):
        repo = self.make_repo("moabb==1.5.0\n")
        report = capture_environment(repo, version_lookup=self.lookup(self.all_versions()), implementation_commit="abc")
        self.assertEqual(report.status, EnvironmentStatus.UNRESOLVED)
        moabb = next(item for item in report.dependencies if item.distribution == "moabb")
        self.assertIsNone(moabb.failure_reason)

    def test_exact_version_mismatch(self):
        repo = self.make_repo("moabb==1.5.0\n")
        report = capture_environment(repo, version_lookup=self.lookup(self.all_versions("1.4.3")), implementation_commit="abc")
        self.assertEqual(report.status, EnvironmentStatus.NONCONFORMANT)
        moabb = next(item for item in report.dependencies if item.distribution == "moabb")
        self.assertEqual(moabb.failure_reason, EnvironmentFailureReason.DEPENDENCY_VERSION_MISMATCH)

    def test_missing_dependency(self):
        repo = self.make_repo("moabb==1.5.0\n")
        versions = self.all_versions()
        del versions["moabb"]
        report = capture_environment(repo, version_lookup=self.lookup(versions), implementation_commit="abc")
        moabb = next(item for item in report.dependencies if item.distribution == "moabb")
        self.assertEqual(moabb.failure_reason, EnvironmentFailureReason.DEPENDENCY_MISSING)

    def test_unresolved_requirement(self):
        repo = self.make_repo("")
        report = capture_environment(repo, version_lookup=self.lookup(self.all_versions()), implementation_commit="abc")
        self.assertEqual(report.status, EnvironmentStatus.UNRESOLVED)
        self.assertTrue(all(item.lock_status == "LOCK_REQUIRED_PHASE_II" for item in report.dependencies))

    def test_enforcement_is_fail_closed(self):
        repo = self.make_repo("moabb==1.5.0\n")
        report = capture_environment(repo, version_lookup=self.lookup(self.all_versions()), implementation_commit="abc")
        with self.assertRaisesRegex(EnvironmentNotConformantError, "ENVIRONMENT_NOT_CONFORMANT"):
            enforce_environment_or_abort(report)

    def test_current_environment_is_reportable_without_importing_scientific_packages(self):
        report = capture_environment()
        self.assertIn(report.status, set(EnvironmentStatus))
        self.assertIsNotNone(report.python_version)
        self.assertIsNotNone(report.platform)


if __name__ == "__main__":
    unittest.main()
