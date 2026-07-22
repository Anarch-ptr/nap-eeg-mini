"""Synthetic tests for the cross-platform protocol byte/hash verifier."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.verify_protocol_hash import (
    ByteValidationError,
    ExpectedHashMismatch,
    GitAccessError,
    RepositoryPathError,
    inspect_index,
    inspect_revision,
    inspect_worktree,
    normalize_repository_path,
    read_git_blob,
    resolve_blob_oid,
    validate_canonical_bytes,
)


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "verify_protocol_hash.py"
)


class CanonicalByteValidationTests(unittest.TestCase):
    def test_valid_lf_only_bytes_pass(self):
        record = validate_canonical_bytes(b"alpha\nbeta\n")
        self.assertEqual(record["validation_status"], "PASS")
        self.assertEqual(record["terminal_newline"], "EXACTLY_ONE_LF")

    def test_utf8_bom_fails(self):
        with self.assertRaisesRegex(ByteValidationError, "UTF8_BOM_PRESENT"):
            validate_canonical_bytes(b"\xef\xbb\xbfalpha\n")

    def test_invalid_utf8_fails(self):
        with self.assertRaisesRegex(ByteValidationError, "STRICT_UTF8"):
            validate_canonical_bytes(b"\xff\n")

    def test_crlf_fails(self):
        with self.assertRaisesRegex(ByteValidationError, "CR_COUNT|BARE_CR"):
            validate_canonical_bytes(b"alpha\r\n")

    def test_bare_cr_fails(self):
        with self.assertRaisesRegex(ByteValidationError, "CR_COUNT|BARE_CR"):
            validate_canonical_bytes(b"alpha\rbeta\n")

    def test_missing_terminal_lf_fails(self):
        with self.assertRaisesRegex(ByteValidationError, "NEWLINE_MISSING"):
            validate_canonical_bytes(b"alpha")

    def test_two_terminal_lf_bytes_fail(self):
        with self.assertRaisesRegex(ByteValidationError, "NEWLINE_EXTRA"):
            validate_canonical_bytes(b"alpha\n\n")

    def test_more_than_two_terminal_lf_bytes_fail(self):
        with self.assertRaisesRegex(ByteValidationError, "NEWLINE_EXTRA"):
            validate_canonical_bytes(b"alpha\n\n\n")

    def test_trailing_space_fails(self):
        with self.assertRaisesRegex(ByteValidationError, "TRAILING"):
            validate_canonical_bytes(b"alpha \n")

    def test_trailing_tab_fails(self):
        with self.assertRaisesRegex(ByteValidationError, "TRAILING"):
            validate_canonical_bytes(b"alpha\t\n")

    def test_non_ascii_utf8_without_bom_passes(self):
        record = validate_canonical_bytes("脑电协议\n".encode("utf-8"))
        self.assertEqual(record["encoding"], "UTF-8")
        self.assertEqual(record["bom"], "ABSENT")

    def test_empty_file_fails(self):
        with self.assertRaisesRegex(ByteValidationError, "NEWLINE_MISSING"):
            validate_canonical_bytes(b"")


class SyntheticGitModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary_directory.name).resolve()
        self._git("init", "--quiet")
        self._git("config", "user.name", "Protocol Test")
        self._git("config", "user.email", "protocol-test@example.invalid")
        self._git("config", "core.autocrlf", "false")
        self.protocol = self.repo / "protocol.md"
        self.initial_bytes = "initial π\n".encode("utf-8")
        self.protocol.write_bytes(self.initial_bytes)
        self._git("add", "protocol.md")
        self._git("commit", "--quiet", "-m", "initial")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def test_revision_mode_reads_exact_blob_bytes(self):
        record = inspect_revision("HEAD", "protocol.md", repo_root=self.repo)
        self.assertEqual(record["byte_length"], len(self.initial_bytes))
        self.assertEqual(record["sha256"], hashlib.sha256(self.initial_bytes).hexdigest())
        oid = resolve_blob_oid(self.repo, "HEAD:protocol.md")
        self.assertEqual(read_git_blob(self.repo, oid), self.initial_bytes)

    def test_index_mode_reads_exact_staged_blob_bytes(self):
        staged = b"staged bytes\n"
        self.protocol.write_bytes(staged)
        self._git("add", "protocol.md")
        record = inspect_index("protocol.md", repo_root=self.repo)
        self.assertEqual(record["byte_length"], len(staged))
        self.assertEqual(record["sha256"], hashlib.sha256(staged).hexdigest())

    def test_worktree_mode_reads_exact_unstaged_bytes(self):
        worktree = b"unstaged bytes\n"
        self.protocol.write_bytes(worktree)
        record = inspect_worktree("protocol.md", repo_root=self.repo)
        self.assertEqual(record["byte_length"], len(worktree))
        self.assertEqual(record["sha256"], hashlib.sha256(worktree).hexdigest())

    def test_validate_only_without_expected_hash_does_not_calculate_digest(self):
        with patch(
            "scripts.verify_protocol_hash.sha256_bytes",
            side_effect=AssertionError("digest must not be calculated"),
        ):
            record = inspect_worktree(
                "protocol.md", repo_root=self.repo, validate_only=True
            )
        self.assertIsNone(record["sha256"])

    def test_blob_oid_and_sha256_are_distinct_fields(self):
        record = inspect_revision("HEAD", "protocol.md", repo_root=self.repo)
        self.assertIn("blob_oid", record)
        self.assertIn("sha256", record)
        self.assertNotEqual(record["blob_oid"], record["sha256"])

    def test_binary_blob_access_does_not_append_newline(self):
        oid = resolve_blob_oid(self.repo, "HEAD:protocol.md")
        data = read_git_blob(self.repo, oid)
        self.assertEqual(data, self.initial_bytes)
        self.assertEqual(len(data), len(self.initial_bytes))

    def test_invalid_crlf_blob_is_not_normalized(self):
        invalid = self.repo / "invalid.md"
        invalid.write_bytes(b"invalid\r\n")
        self._git("add", "invalid.md")
        self._git("commit", "--quiet", "-m", "invalid blob")
        oid = resolve_blob_oid(self.repo, "HEAD:invalid.md")
        self.assertEqual(read_git_blob(self.repo, oid), b"invalid\r\n")
        with self.assertRaises(ByteValidationError):
            inspect_revision("HEAD", "invalid.md", repo_root=self.repo)

    def test_repository_relative_path_handling(self):
        self.assertEqual(
            normalize_repository_path(self.repo, "protocol.md"), "protocol.md"
        )

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(RepositoryPathError):
            normalize_repository_path(self.repo, "../outside.md")

    def test_absolute_path_is_rejected(self):
        with self.assertRaises(RepositoryPathError):
            normalize_repository_path(self.repo, str(self.protocol.resolve()))

    def test_missing_git_path_fails(self):
        with self.assertRaises(GitAccessError):
            inspect_index("missing.md", repo_root=self.repo)

    def test_invalid_revision_fails(self):
        with self.assertRaises(GitAccessError):
            inspect_revision("missing-revision", "protocol.md", repo_root=self.repo)

    def test_expected_hash_mismatch_fails(self):
        with self.assertRaises(ExpectedHashMismatch):
            inspect_revision(
                "HEAD",
                "protocol.md",
                repo_root=self.repo,
                expected_sha256="0" * 64,
            )

    def test_cli_validate_only_omits_digest(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "worktree",
                "protocol.md",
                "--validate-only",
                "--json",
            ],
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        record = json.loads(completed.stdout)
        self.assertEqual(record["validation_status"], "PASS")
        self.assertIsNone(record["sha256"])


if __name__ == "__main__":
    unittest.main()
