"""Engineering-only tests for external dataset provenance reconnaissance."""

import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import scripts.recon.inspect_dataset_provenance as recon_module
from scripts.recon.inspect_dataset_provenance import (
    classify_dataset_provenance,
    classify_trial_loss,
    enforce_phase_ii_b_acquisition_or_abort,
    lee_subject_session_matrix,
    legacy_sanitized_cache_root,
    moabb_relative_cache_argument,
    natural_key,
    require_unique,
    session_availability_matrix,
    structural_trial_id,
    validate_recon_record,
)


class DatasetReconTests(unittest.TestCase):
    def test_reconnaissance_acquisition_is_retired_until_phase_ii_b(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "RAW_DATA_IDENTITY_GATE_NOT_IMPLEMENTED_PHASE_II_B",
        ):
            enforce_phase_ii_b_acquisition_or_abort()

    def test_former_authorization_symbol_cannot_enable_acquisition(self):
        setattr(recon_module, "PHASE_II_B_DATA_ACQUISITION_AUTHORIZATION", "ALLOW")
        self.addCleanup(
            lambda: delattr(
                recon_module, "PHASE_II_B_DATA_ACQUISITION_AUTHORIZATION"
            )
            if hasattr(recon_module, "PHASE_II_B_DATA_ACQUISITION_AUTHORIZATION")
            else None
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "LEE_DATA_ACQUISITION_NOT_AUTHORIZED",
        ):
            enforce_phase_ii_b_acquisition_or_abort()

    def test_direct_dataset_instance_cannot_construct_lee(self):
        calls = []
        fake_datasets = types.ModuleType("moabb.datasets")

        class FakeLee2019MI:
            def __init__(self, *args, **kwargs):
                calls.append((args, kwargs))

        fake_datasets.Lee2019_MI = FakeLee2019MI
        with patch.dict(
            sys.modules,
            {
                "moabb": types.ModuleType("moabb"),
                "moabb.datasets": fake_datasets,
            },
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "LEE_DATA_ACQUISITION_NOT_AUTHORIZED",
            ):
                recon_module._dataset_instance("lee2019_mi")
        self.assertEqual(calls, [])

    def test_direct_main_aborts_before_cache_or_dataset_construction(self):
        calls = {"constructor": 0, "mkdir": 0}
        fake_datasets = types.ModuleType("moabb.datasets")

        class FakeLee2019MI:
            def __init__(self, *args, **kwargs):
                calls["constructor"] += 1

        def tracked_mkdir(self, *args, **kwargs):
            calls["mkdir"] += 1

        fake_datasets.Lee2019_MI = FakeLee2019MI
        with (
            patch.dict(
                sys.modules,
                {
                    "moabb": types.ModuleType("moabb"),
                    "moabb.datasets": fake_datasets,
                },
            ),
            patch.object(
                sys,
                "argv",
                [
                    "inspect_dataset_provenance.py",
                    "--dataset",
                    "lee2019_mi",
                    "--subjects",
                    "all",
                    "--resume",
                ],
            ),
            patch.object(Path, "mkdir", tracked_mkdir),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "LEE_DATA_ACQUISITION_NOT_AUTHORIZED",
            ):
                recon_module.main()
        self.assertEqual(calls, {"constructor": 0, "mkdir": 0})

    def test_inspect_dataset_helper_aborts_before_data_path(self):
        calls = {"data_path": 0}

        class FakeDataset:
            subject_list = [1]

            def data_path(self, *args, **kwargs):
                calls["data_path"] += 1
                return []

        with patch.object(
            recon_module,
            "_dataset_instance",
            side_effect=RuntimeError("LEE_DATA_ACQUISITION_NOT_AUTHORIZED"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "LEE_DATA_ACQUISITION_NOT_AUTHORIZED",
            ):
                recon_module.inspect_dataset(
                    "lee2019_mi",
                    Path("data/external_recon"),
                    Path("results/external_boundary_recon"),
                    [1],
                )
        self.assertEqual(calls["data_path"], 0)

    def test_structural_trial_id_is_stable_and_opaque_subject_safe(self):
        first = structural_trial_id("dataset", "subject-A", "S1", "run-x", 42, 0)
        second = structural_trial_id("dataset", "subject-A", "S1", "run-x", 42, 0)
        self.assertEqual(first, second)
        self.assertNotEqual(
            first,
            structural_trial_id("dataset", "subject-B", "S1", "run-x", 42, 0),
        )

    def test_duplicate_identity_detection(self):
        require_unique(["a", "b"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            require_unique(["a", "a"])

    def test_natural_order_is_deterministic(self):
        values = ["session_10", "session_2", "session_1"]
        self.assertEqual(
            sorted(values, key=natural_key),
            ["session_1", "session_2", "session_10"],
        )

    def test_trial_loss_does_not_invent_a_cause(self):
        self.assertEqual(classify_trial_loss(100, 100), "NO_OBSERVED_LOSS")
        self.assertEqual(classify_trial_loss(100, 88), "UNKNOWN_TRIAL_LOSS")
        self.assertEqual(
            classify_trial_loss(None, 88),
            "UNKNOWN_TRIAL_LOSS",
        )
        self.assertEqual(classify_trial_loss(88, 100), "UNKNOWN_TRIAL_LOSS")

    def test_declared_session_count_conflict_is_not_called_consistent(self):
        classification, issues = classify_dataset_provenance(
            "bnci2015_001", True, 2, [2, 3]
        )
        self.assertEqual(classification, "ABSTRACTION_SEMANTIC_MISMATCH")
        self.assertEqual(
            issues,
            ["FRAMEWORK_DECLARED_SESSION_COUNT_CONFLICTS_WITH_OBSERVED_HETEROGENEITY"],
        )

    def test_recon_cache_argument_stays_relative_inside_worktree(self):
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory) / "data" / "external_recon"
            root.mkdir(parents=True)
            argument = moabb_relative_cache_argument(root, Path.cwd())
            self.assertFalse(Path(argument).is_absolute())
            self.assertNotIn(":", argument)
            legacy = legacy_sanitized_cache_root(root, Path.cwd())
            self.assertTrue(str(legacy).startswith(str(Path.cwd())))

    def test_lee_matrix_requires_two_ground_truth_offline_sessions(self):
        native = []
        framework = []
        for session in ("S1", "S2"):
            native.extend(
                [
                    {
                        "physical_session_id": session,
                        "native_run_id": "offline_train",
                        "native_observed_event_count": 100,
                        "native_label_value_counts": {"1": 50, "2": 50},
                        "label_availability": "GROUND_TRUTH_LABELS_PRESENT",
                    },
                    {
                        "physical_session_id": session,
                        "native_run_id": "online_test",
                        "label_availability": "ONLINE_LABEL_SEMANTICS_UNRESOLVED",
                    },
                ]
            )
            framework.extend(
                {
                    "physical_session_id": session,
                    "framework_run_id": run,
                }
                for run in ("1train", "4test")
            )
        rows = lee_subject_session_matrix(
            [
                {
                    "subject_id": "opaque-subject",
                    "framework_session_ids": ["0", "1"],
                    "native_or_local_structure": native,
                    "framework_structure": framework,
                    "trial_identity_status": (
                        "DETERMINISTIC_UNIQUE_WITHIN_INSPECTED_STRUCTURE"
                    ),
                }
            ]
        )
        self.assertTrue(rows[0]["offline_common_session_pair_available"])
        self.assertEqual(
            rows[0]["session_1_online_label_status"],
            "ONLINE_LABEL_SEMANTICS_UNRESOLVED",
        )

    def test_heterogeneous_session_availability_is_preserved(self):
        result = session_availability_matrix(
            {"opaque-A": ["0A", "1B"], "opaque-B": ["0A", "1B", "2C"]},
            {"0A": "S1", "1B": "S2", "2C": "S3"},
        )
        self.assertEqual(result["coverage"], {"S1": 2, "S2": 2, "S3": 1})
        self.assertEqual(result["verified_common_s1_s2"], 2)
        self.assertEqual(result["verified_common_s1_s2_s3"], 1)

    def test_ambiguous_session_mapping_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ambiguous session mapping"):
            session_availability_matrix(
                {"subject": ["run-a", "run-b"]},
                {"run-a": "S1", "run-b": "S1"},
            )

    def test_recon_schema_rejects_scientific_metrics(self):
        record = {
            "dataset_id": "candidate",
            "dataset_class": "module.Class",
            "documentation_status": "DOCUMENTATION_ELIGIBLE",
            "raw_metadata_status": "RAW_METADATA_VERIFICATION_PARTIAL",
            "provenance_classification": "PROVENANCE_INCOMPLETE",
            "framework_dataset_metadata": {},
            "inspected_subjects": [],
            "subject_records": [],
            "trial_retention_summary": [],
            "scientific_metrics_calculated": True,
        }
        with self.assertRaisesRegex(ValueError, "scientific metrics"):
            validate_recon_record(record)


if __name__ == "__main__":
    unittest.main()
