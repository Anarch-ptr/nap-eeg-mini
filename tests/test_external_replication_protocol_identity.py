from __future__ import annotations

import dataclasses
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
import zlib
from dataclasses import fields
from pathlib import Path

from src.external_replication.protocol_identity import (
    DuplicateKeyError,
    FROZEN_PROTOCOL_V1,
    ProtocolIdentityError,
    ProtocolIdentityStatus,
    _blob_oid_at_path,
    _commit_tree_oid,
    _parse_tag_target,
    _peel_tag_to_commit,
    _read_loose_object,
    _resolve_ref,
    _tree_entries,
    enforce_protocol_identity_or_abort,
    parse_strict_json,
    verify_protocol_identity,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def object_bytes(object_type: str, payload: bytes) -> bytes:
    return f"{object_type} {len(payload)}".encode("ascii") + b"\x00" + payload


def write_loose_object(git_dir: Path, object_type: str, payload: bytes) -> str:
    raw = object_bytes(object_type, payload)
    oid = hashlib.sha1(raw).hexdigest()
    path = git_dir / "objects" / oid[:2] / oid[2:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zlib.compress(raw))
    return oid


def tree_entry(mode: str, name: str, oid: str) -> bytes:
    return mode.encode("ascii") + b" " + name.encode("utf-8") + b"\x00" + bytes.fromhex(oid)


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
        current_head = (REPO_ROOT / ".git" / "HEAD").read_text(encoding="ascii").strip()
        if current_head.startswith("ref: "):
            current_head = (
                REPO_ROOT / ".git" / current_head[5:]
            ).read_text(encoding="ascii").strip()
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

    def test_hostile_path_git_is_not_invoked(self):
        with tempfile.TemporaryDirectory() as temporary:
            hostile = Path(temporary)
            log = hostile / "fake_git_invoked.txt"
            for name in ("git.exe", "git.cmd", "git.bat"):
                (hostile / name).write_text(
                    f"@echo off\r\necho invoked > \"{log}\"\r\nexit /b 7\r\n",
                    encoding="ascii",
                )
            code = (
                "from pathlib import Path; "
                "from src.external_replication.protocol_identity import "
                "ProtocolIdentityStatus,verify_protocol_identity; "
                f"r=verify_protocol_identity(Path({str(REPO_ROOT)!r})); "
                "print(r.status.value); "
                "print('|'.join(r.failure_reasons))"
            )
            environment = os.environ.copy()
            environment["PATH"] = str(hostile) + os.pathsep + environment.get("PATH", "")
            completed = subprocess.run(
                [sys.executable, "-B", "-c", code],
                cwd=REPO_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.splitlines(), ["PASS", ""])
            self.assertFalse(log.exists())

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

    def test_loose_object_hash_identity_is_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            git_dir = Path(temporary) / ".git"
            wrong_oid = "0" * 40
            path = git_dir / "objects" / wrong_oid[:2] / wrong_oid[2:]
            path.parent.mkdir(parents=True)
            path.write_bytes(zlib.compress(object_bytes("blob", b"test")))
            with self.assertRaisesRegex(
                ProtocolIdentityError,
                "GIT_OBJECT_IDENTITY_MISMATCH",
            ):
                _read_loose_object(git_dir, wrong_oid)

    def test_loose_object_rejects_malformed_oid_and_zlib(self):
        with tempfile.TemporaryDirectory() as temporary:
            git_dir = Path(temporary) / ".git"
            with self.assertRaisesRegex(ProtocolIdentityError, "MALFORMED_SHA1_OID"):
                _read_loose_object(git_dir, "abc")
            oid = "1" * 40
            path = git_dir / "objects" / oid[:2] / oid[2:]
            path.parent.mkdir(parents=True)
            path.write_bytes(b"not-zlib")
            with self.assertRaisesRegex(ProtocolIdentityError, "GIT_OBJECT_MALFORMED"):
                _read_loose_object(git_dir, oid)

    def test_loose_object_rejects_declared_length_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            git_dir = Path(temporary) / ".git"
            raw = b"blob 99\x00test"
            oid = hashlib.sha1(raw).hexdigest()
            path = git_dir / "objects" / oid[:2] / oid[2:]
            path.parent.mkdir(parents=True)
            path.write_bytes(zlib.compress(raw))
            with self.assertRaisesRegex(ProtocolIdentityError, "GIT_OBJECT_SIZE_MISMATCH"):
                _read_loose_object(git_dir, oid)

    def test_loose_object_rejects_unsupported_object_format(self):
        with tempfile.TemporaryDirectory() as temporary:
            git_dir = Path(temporary) / ".git"
            (git_dir / "objects").mkdir(parents=True)
            (git_dir / "config").write_text(
                "[extensions]\nobjectFormat = sha256\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                ProtocolIdentityError,
                "UNSUPPORTED_REPOSITORY_OBJECT_FORMAT",
            ):
                _read_loose_object(git_dir, "0" * 40)

    def test_tree_grammar_rejects_duplicate_and_unsafe_names(self):
        oid1 = "1" * 40
        oid2 = "2" * 40
        bad_payloads = {
            "duplicate": tree_entry("100644", "dup", oid1)
            + tree_entry("100644", "dup", oid2),
            "case_collision": tree_entry("100644", "Readme", oid1)
            + tree_entry("100644", "README", oid2),
            "dot": tree_entry("100644", ".", oid1),
            "dotdot": tree_entry("100644", "..", oid1),
            "slash": tree_entry("100644", "a/b", oid1),
            "backslash": tree_entry("100644", "a\\b", oid1),
            "invalid_mode": tree_entry("120000", "link", oid1),
            "submodule": tree_entry("160000", "submodule", oid1),
            "truncated_oid": b"100644 short\x00" + bytes.fromhex("1" * 38),
        }
        for label, payload in bad_payloads.items():
            with self.subTest(label=label):
                with self.assertRaises(ProtocolIdentityError):
                    _tree_entries(payload)

    def test_tree_traversal_enforces_child_types(self):
        with tempfile.TemporaryDirectory() as temporary:
            git_dir = Path(temporary) / ".git"
            blob_oid = write_loose_object(git_dir, "blob", b"content")
            tree_oid = write_loose_object(
                git_dir,
                "tree",
                tree_entry("100644", "file", blob_oid),
            )
            commit_oid = write_loose_object(
                git_dir,
                "commit",
                f"tree {tree_oid}\nauthor A <a@b> 0 +0000\ncommitter A <a@b> 0 +0000\n\nmsg\n".encode("ascii"),
            )
            self.assertEqual(_blob_oid_at_path(git_dir, commit_oid, "file"), blob_oid)
            with self.assertRaisesRegex(
                ProtocolIdentityError,
                "GIT_PATH_INTERMEDIATE_NOT_TREE",
            ):
                _blob_oid_at_path(git_dir, commit_oid, "file/child")
            root_tree_oid = write_loose_object(
                git_dir,
                "tree",
                tree_entry("40000", "dir", tree_oid),
            )
            root_commit_oid = write_loose_object(
                git_dir,
                "commit",
                f"tree {root_tree_oid}\nauthor A <a@b> 0 +0000\ncommitter A <a@b> 0 +0000\n\nmsg\n".encode("ascii"),
            )
            with self.assertRaisesRegex(ProtocolIdentityError, "GIT_PATH_NOT_FILE_MODE"):
                _blob_oid_at_path(git_dir, root_commit_oid, "dir")

    def test_ref_resolution_is_bounded_and_sanitized(self):
        with tempfile.TemporaryDirectory() as temporary:
            git_dir = Path(temporary) / ".git"
            ref_dir = git_dir / "refs" / "tags"
            ref_dir.mkdir(parents=True)
            oid = "1" * 40
            (ref_dir / "valid").write_text(oid + "\n", encoding="ascii", newline="\n")
            self.assertEqual(_resolve_ref(git_dir, "valid"), oid)
            (ref_dir / "self").write_text("ref: refs/tags/self\n", encoding="ascii", newline="\n")
            with self.assertRaisesRegex(ProtocolIdentityError, "SYMBOLIC_REF_CYCLE"):
                _resolve_ref(git_dir, "self")
            with self.assertRaisesRegex(ProtocolIdentityError, "MALFORMED_REF_NAME"):
                _resolve_ref(git_dir, "refs/tags/../bad")
            (ref_dir / "multi").write_text(
                oid + "\n" + ("2" * 40) + "\n",
                encoding="ascii",
                newline="\n",
            )
            with self.assertRaisesRegex(ProtocolIdentityError, "MALFORMED_REF_CONTENT"):
                _resolve_ref(git_dir, "multi")

    def test_loose_ref_content_parsing_is_exact_and_non_normalizing(self):
        with tempfile.TemporaryDirectory() as temporary:
            git_dir = Path(temporary) / ".git"
            ref_dir = git_dir / "refs" / "tags"
            ref_dir.mkdir(parents=True)
            oid = "1" * 40
            (ref_dir / "valid-no-newline").write_bytes(oid.encode("ascii"))
            self.assertEqual(_resolve_ref(git_dir, "valid-no-newline"), oid)
            (ref_dir / "valid-one-lf").write_bytes((oid + "\n").encode("ascii"))
            self.assertEqual(_resolve_ref(git_dir, "valid-one-lf"), oid)
            (ref_dir / "target").write_bytes((oid + "\n").encode("ascii"))
            (ref_dir / "valid-symbolic-no-newline").write_bytes(b"ref: refs/tags/target")
            self.assertEqual(_resolve_ref(git_dir, "valid-symbolic-no-newline"), oid)
            (ref_dir / "valid-symbolic-one-lf").write_bytes(b"ref: refs/tags/target\n")
            self.assertEqual(_resolve_ref(git_dir, "valid-symbolic-one-lf"), oid)

            malformed = {
                "leading-space": b" " + oid.encode("ascii"),
                "trailing-space": oid.encode("ascii") + b" ",
                "leading-tab": b"\t" + oid.encode("ascii"),
                "trailing-tab": oid.encode("ascii") + b"\t",
                "cr": oid.encode("ascii") + b"\r",
                "crlf": oid.encode("ascii") + b"\r\n",
                "two-lfs": oid.encode("ascii") + b"\n\n",
                "extra-blank-line": oid.encode("ascii") + b"\n\n",
                "multiple-lines": oid.encode("ascii") + b"\n" + ("2" * 40).encode("ascii"),
                "uppercase-oid": ("A" * 40).encode("ascii"),
                "abbreviated-oid": b"1" * 39,
                "oid-extra-token": oid.encode("ascii") + b" extra",
                "padded-symbolic-leading": b" ref: refs/tags/target",
                "padded-symbolic-trailing": b"ref: refs/tags/target ",
                "malformed-ref-spacing": b"ref:refs/tags/target",
                "embedded-nul": oid[:20].encode("ascii") + b"\x00" + oid[20:].encode("ascii"),
                "control-character": oid[:20].encode("ascii") + b"\x1f" + oid[20:].encode("ascii"),
            }
            for name, content in malformed.items():
                with self.subTest(name=name):
                    (ref_dir / name).write_bytes(content)
                    with self.assertRaises(ProtocolIdentityError):
                        _resolve_ref(git_dir, name)

    def test_tag_and_commit_parsing_is_strict(self):
        with tempfile.TemporaryDirectory() as temporary:
            git_dir = Path(temporary) / ".git"
            tree_oid = write_loose_object(git_dir, "tree", b"")
            commit_oid = write_loose_object(
                git_dir,
                "commit",
                f"tree {tree_oid}\nauthor A <a@b> 0 +0000\ncommitter A <a@b> 0 +0000\n\nobject fake in message\n".encode("ascii"),
            )
            tag_oid = write_loose_object(
                git_dir,
                "tag",
                f"object {commit_oid}\ntype commit\ntag v\n\nmessage\n".encode("ascii"),
            )
            self.assertEqual(_peel_tag_to_commit(git_dir, tag_oid), commit_oid)
            with self.assertRaisesRegex(ProtocolIdentityError, "COMMIT_TREE_HEADER_MISSING"):
                _commit_tree_oid(
                    f"author A <a@b> 0 +0000\n\n"
                    f"tree {tree_oid}\n".encode("ascii")
                )
            with self.assertRaisesRegex(ProtocolIdentityError, "COMMIT_TREE_HEADER_MISSING"):
                _commit_tree_oid(
                    f"tree {tree_oid}\ntree {tree_oid}\n\nmsg\n".encode("ascii")
                )
            with self.assertRaisesRegex(ProtocolIdentityError, "TAG_OBJECT_HEADER_INVALID"):
                _parse_tag_target(
                    f"object {commit_oid}\nobject {commit_oid}\ntype commit\n\nmsg\n".encode("ascii")
                )
            with self.assertRaisesRegex(ProtocolIdentityError, "TAG_TYPE_HEADER_INVALID"):
                _parse_tag_target(f"object {commit_oid}\n\nmsg\n".encode("ascii"))
            blob_oid = write_loose_object(git_dir, "blob", b"payload")
            blob_tag = write_loose_object(
                git_dir,
                "tag",
                f"object {blob_oid}\ntype blob\ntag bad\n\nmsg\n".encode("ascii"),
            )
            with self.assertRaisesRegex(ProtocolIdentityError, "TAG_TARGET_NOT_COMMIT"):
                _peel_tag_to_commit(git_dir, blob_tag)


if __name__ == "__main__":
    unittest.main()
