"""Synthetic preregistration tests for update-matched classification."""

import unittest

from src.update_matched_diagnostic import analyze_diagnostic, reference_update_budget


def primary_rows(full=.70, fixed=.40):
    return [{"subject": str(s), "budget": str(b), "training_seed": str(seed),
             "subset_seed": "20260719", "split_seed": "42",
             "train_sample_count": str({1.0: 230, .5: 114, .25: 55}[b]),
             "train_class_counts": ({1.0: '{"0":55,"1":55,"2":61,"3":59}',
                                      .5: '{"0":27,"1":27,"2":30,"3":30}',
                                      .25: '{"0":13,"1":13,"2":15,"3":14}'}[b]),
             "validation_sample_count": "58", "test_sample_count": "288",
             "primary_metric": "accuracy", "checkpoint": "best.pt",
             "test_accuracy": str(full if b == 1.0 else fixed), "run_status": "completed"}
            for s in range(1, 10) for seed in (42, 43, 44) for b in (1.0, .5, .25)]


def diagnostic_rows(matched=.50):
    return [{"subject": str(s), "condition": "update_matched_25", "budget": ".25",
             "split_seed": "42", "subset_seed": "20260719", "training_seed": str(seed),
             "target_optimizer_updates": "400", "actual_optimizer_updates": "400",
             "validation_event_count": "50", "subset_identity_status": "matched",
             "primary_metric": "accuracy", "test_accuracy": str(matched),
             "checkpoint": "best.pt", "run_status": "completed"}
            for s in range(1, 10) for seed in (42, 43, 44)]


class UpdateMatchedDiagnosticTests(unittest.TestCase):
    def test_reference_updates_use_ceil_without_drop_last(self):
        self.assertEqual(reference_update_budget(230, 32), (8, 400))

    def test_persistent_strong_failure(self):
        self.assertEqual(analyze_diagnostic(primary_rows(), diagnostic_rows(.50))["classification"],
                         "PERSISTENT_STRONG_FAILURE")

    def test_update_count_explains_most(self):
        self.assertEqual(analyze_diagnostic(primary_rows(), diagnostic_rows(.69))["classification"],
                         "UPDATE_COUNT_EXPLAINS_MOST")

    def test_partial_update_confound(self):
        self.assertEqual(analyze_diagnostic(primary_rows(), diagnostic_rows(.66))["classification"],
                         "PARTIAL_UPDATE_CONFOUND")

    def test_missing_run_is_invalid(self):
        self.assertEqual(analyze_diagnostic(primary_rows(), diagnostic_rows()[:-1])["classification"],
                         "INCOMPLETE_OR_INVALID")

    def test_wrong_update_count_is_invalid(self):
        rows = diagnostic_rows(); rows[0]["actual_optimizer_updates"] = "399"
        self.assertEqual(analyze_diagnostic(primary_rows(), rows)["classification"],
                         "INCOMPLETE_OR_INVALID")

    def test_wrong_validation_count_is_invalid(self):
        rows = diagnostic_rows(); rows[0]["validation_event_count"] = "51"
        self.assertEqual(analyze_diagnostic(primary_rows(), rows)["classification"],
                         "INCOMPLETE_OR_INVALID")

    def test_subset_mismatch_is_invalid(self):
        rows = diagnostic_rows(); rows[0]["subset_identity_status"] = "mismatch"
        self.assertEqual(analyze_diagnostic(primary_rows(), rows)["classification"],
                         "INCOMPLETE_OR_INVALID")

    def test_seed_aggregation_occurs_within_subject(self):
        rows = diagnostic_rows(.50)
        for row in rows:
            if row["subject"] == "1":
                row["test_accuracy"] = {"42": ".4", "43": ".5", "44": ".6"}[row["training_seed"]]
        result = analyze_diagnostic(primary_rows(), rows)
        self.assertAlmostEqual(result["subject_diagnostics"][0]["accuracy_25_matched_mean"], .5)

    def test_residual_gap_is_percentage_points(self):
        result = analyze_diagnostic(primary_rows(.70, .40), diagnostic_rows(.55))
        row = result["subject_diagnostics"][0]
        self.assertAlmostEqual(row["original_gap_pp"], 30.0)
        self.assertAlmostEqual(row["recovery_pp"], 15.0)
        self.assertAlmostEqual(row["residual_gap_pp"], 15.0)


if __name__ == "__main__": unittest.main()
