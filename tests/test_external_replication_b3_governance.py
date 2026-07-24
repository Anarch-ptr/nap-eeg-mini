from __future__ import annotations

import json
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
B3_TEMPLATE_PATH = (
    REPOSITORY_ROOT
    / "configs"
    / "external_replication"
    / "lee2019_mi_b3_authorization_template.json"
)


class Lee2019MIB3GovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = json.loads(B3_TEMPLATE_PATH.read_text(encoding="utf-8"))

    def test_draft_template_remains_fail_closed(self):
        template = self.template
        self.assertEqual(template["authorization_mode"], "OPAQUE_BYTE_ACQUISITION_ONLY")
        self.assertEqual(template["default"], "DENY")
        self.assertEqual(template["template_status"], "DRAFT_ONLY")
        self.assertEqual(template["authorization_identity"]["status"], "DRAFT_DENY")
        self.assertEqual(
            template["review_status"]["real_data_acquisition_authorization"], "DENY"
        )
        self.assertEqual(
            template["review_status"]["scientific_execution_authorization"], "DENY"
        )

    def test_unresolved_release_and_identity_prevent_authorization(self):
        template = self.template
        self.assertIsNone(template["dataset"]["release_or_version"])
        self.assertEqual(template["dataset"]["release_or_version_status"], "UNKNOWN")
        self.assertIsNone(template["source"]["sha256"])
        self.assertIsNone(template["source"]["size_bytes"])
        self.assertIsNone(template["source"]["hash_approval_source"])
        self.assertEqual(
            template["source"]["first_acquisition_identity_policy"],
            "QUARANTINE_THEN_HUMAN_APPROVAL",
        )
        self.assertEqual(
            template["review_status"]["b3_preauthorization"],
            "BLOCKED_UNRESOLVED",
        )

    def test_source_scope_is_exact_and_downgrade_is_forbidden(self):
        source = self.template["source"]
        self.assertEqual(source["approved_scheme"], "https")
        self.assertEqual(
            source["approved_host"], "s3.ap-northeast-1.wasabisys.com"
        )
        self.assertFalse(source["wildcard_host_allowed"])
        self.assertTrue(source["no_http_downgrade"])
        self.assertIn("/100542/session1/", source["approved_path_or_pattern"])
        self.assertIn("/100542/session2/", source["approved_path_or_pattern"])
        self.assertEqual(source["expected_file_count"], 108)
        self.assertEqual(source["source_selection_status"], "CANDIDATE_NOT_AUTHORIZED")

    def test_license_does_not_imply_automated_download_authorization(self):
        terms = self.template["license_and_terms"]
        self.assertEqual(terms["license_identifier"], "CC0-1.0")
        self.assertEqual(terms["research_use_permission"], "PERMITTED")
        self.assertEqual(terms["redistribution_permission"], "PERMITTED")
        self.assertEqual(terms["automated_download_permission"], "UNVERIFIED")
        self.assertTrue(terms["approval_status"].endswith("_DENY"))

    def test_resource_and_human_approval_gates_remain_unresolved(self):
        self.assertTrue(
            all(value is None for value in self.template["resource_limits"].values())
        )
        self.assertEqual(
            self.template["destination"]["safe_extraction_toctou_approval"],
            "PENDING_HUMAN_APPROVAL",
        )
        identity = self.template["authorization_identity"]
        self.assertIsNone(identity["approver"])
        self.assertIsNone(identity["approval_reference"])
        self.assertIsNone(identity["authorization_id"])

    def test_every_scientific_capability_remains_denied(self):
        capabilities = self.template["scientific_capabilities"]
        self.assertTrue(capabilities)
        self.assertEqual(set(capabilities.values()), {"DENY"})
        self.assertEqual(
            self.template["post_acquisition_scientific_execution_authorization"],
            "DENY",
        )
        self.assertIn(
            "scientific_file_format_parsing",
            self.template["prohibited_operations"],
        )

    def test_one_boolean_cannot_turn_draft_into_authorization(self):
        template = self.template
        unresolved = {
            "release": template["dataset"]["release_or_version"],
            "automated_download": template["license_and_terms"][
                "automated_download_permission"
            ],
            "sha256": template["source"]["sha256"],
            "limits": tuple(template["resource_limits"].values()),
            "approver": template["authorization_identity"]["approver"],
            "toctou": template["destination"]["safe_extraction_toctou_approval"],
        }
        self.assertEqual(unresolved["release"], None)
        self.assertEqual(unresolved["automated_download"], "UNVERIFIED")
        self.assertEqual(unresolved["sha256"], None)
        self.assertTrue(all(value is None for value in unresolved["limits"]))
        self.assertEqual(unresolved["approver"], None)
        self.assertEqual(unresolved["toctou"], "PENDING_HUMAN_APPROVAL")

    def test_b3a_collection_shape_is_declared_but_not_executable(self):
        collection = self.template["multi_object_collection"]
        self.assertEqual(
            collection["source_representation"], "GIGADB_ORIGINAL_MAT_OBJECTS"
        )
        self.assertEqual(collection["expected_object_count"], 108)
        self.assertEqual(collection["expected_subject_count"], 54)
        self.assertEqual(collection["expected_session_count"], 2)
        self.assertFalse(collection["extraction_required"])
        self.assertIsNone(collection["collection_plan"])
        self.assertEqual(collection["approval_state"], "DRAFT_UNAPPROVED")
        self.assertIn(
            "NEMAR_BIDS_DERIVATIVE",
            collection["substitution_representations_denied"],
        )

    def test_b3a_real_resource_limits_remain_unresolved(self):
        limits = self.template["multi_object_resource_limits"]
        self.assertTrue(limits)
        self.assertTrue(all(value is None for value in limits.values()))


if __name__ == "__main__":
    unittest.main()
