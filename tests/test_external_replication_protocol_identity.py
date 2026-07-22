from __future__ import annotations

import dataclasses
import subprocess
import unittest
from dataclasses import fields
from pathlib import Path

from src.external_replication.protocol_identity import (
    DuplicateKeyError,
    FROZEN_PROTOCOL_V1,
    ProtocolIdentityStatus,
    enforce_protocol_identity_or_abort,
    parse_strict_json,
    verify_protocol_identity,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProtocolIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = verify_protocol_identity(REPO_ROOT)

    def test_frozen_git_object_identity_passes(self):
        self.assertEqual(self.result.status, ProtocolIdentityStatus.PASS)
        self.assertEqual(self.result.failure_reasons, ())

    def test_tag_is_annotated_and_peels_to_freeze_commit(self):
        self.assertIsNotNone(self.result.tag_object_oid)
        self.assertEqual(self.result.freeze_commit, FROZEN_PROTOCOL_V1.freeze_commit)

    def test_raw_protocol_blob_fields_match(self):
        self.assertEqual(self.result.protocol_blob_oid, FROZEN_PROTOCOL_V1.protocol_blob_oid)
        self.assertEqual(self.result.protocol_blob_sha256, FROZEN_PROTOCOL_V1.protocol_blob_sha256)
        self.assertEqual(self.result.protocol_byte_length, FROZEN_PROTOCOL_V1.protocol_byte_length)

    def test_freeze_record_blob_fields_match(self):
        self.assertEqual(self.result.freeze_record_blob_oid, FROZEN_PROTOCOL_V1.freeze_record_blob_oid)
        self.assertEqual(self.result.freeze_record_sha256, FROZEN_PROTOCOL_V1.freeze_record_sha256)
        self.assertEqual(self.result.freeze_record_byte_length, FROZEN_PROTOCOL_V1.freeze_record_byte_length)

    def test_repository_object_format_matches(self):
        self.assertEqual(self.result.repository_object_format, "sha1")

    def test_altered_expected_identity_fails(self):
        altered = dataclasses.replace(FROZEN_PROTOCOL_V1, protocol_blob_sha256="0" * 64)
        result = verify_protocol_identity(REPO_ROOT, altered)
        self.assertEqual(result.status, ProtocolIdentityStatus.FAIL)
        self.assertTrue(any("PROTOCOL_SHA256" in reason for reason in result.failure_reasons))

    def test_current_implementation_identity_is_separate_field(self):
        current_head = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        self.assertEqual(self.result.implementation_commit, current_head)
        self.assertEqual(self.result.freeze_commit, FROZEN_PROTOCOL_V1.freeze_commit)
        if current_head != FROZEN_PROTOCOL_V1.freeze_commit:
            self.assertNotEqual(
                self.result.implementation_commit,
                self.result.freeze_commit,
            )
        names = {field.name for field in fields(type(self.result))}
        self.assertIn("implementation_commit", names)
        self.assertIn("freeze_commit", names)

    def test_enforcement_returns_only_passing_result(self):
        self.assertEqual(
            enforce_protocol_identity_or_abort(REPO_ROOT).status,
            ProtocolIdentityStatus.PASS,
        )

    def test_top_level_duplicate_json_key_is_rejected(self):
        with self.assertRaisesRegex(DuplicateKeyError, "DUPLICATE_JSON_KEY: key"):
            parse_strict_json(b'{"key":1,"key":2}')

    def test_nested_duplicate_json_key_is_rejected(self):
        with self.assertRaisesRegex(DuplicateKeyError, "DUPLICATE_JSON_KEY: nested"):
            parse_strict_json(b'{"outer":{"nested":1,"nested":2}}')


if __name__ == "__main__":
    unittest.main()
