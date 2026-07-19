"""Synthetic preregistration tests for small-sample analysis decisions."""

import copy
import json
import unittest

from src.small_sample_analysis import aggregate_subjects
from src.small_sample_analysis import classify


def synthetic_matrix(mode):
    rows = []
    counts = {1.0: (230, [56, 56, 59, 59]), .5: (114, [28, 28, 29, 29]), .25: (55, [13, 13, 14, 15])}
    for subject in range(1, 10):
        for budget in (1.0, .5, .25):
            for seed in (42, 43, 44):
                full = .72 + subject * .001 + (seed - 43) * .002
                if mode == "strong":
                    metric = {1.0: full, .5: full - .04, .25: full - .08}[budget]
                elif mode == "mixed":
                    drop = .09 if subject <= 3 else 0.0
                    metric = {1.0: full, .5: full - drop / 2, .25: full - drop}[budget]
                elif mode == "seed_inconsistent":
                    direction = -.08 if seed != 44 else .02
                    metric = {1.0: full, .5: full + direction / 2, .25: full + direction}[budget]
                else:
                    metric = {1.0: full, .5: full - .005, .25: full - .01}[budget]
                count, per_class = counts[budget]
                rows.append({
                    "subject": str(subject), "budget": str(budget),
                    "subset_seed": "20260719", "split_seed": "42",
                    "training_seed": str(seed), "train_sample_count": str(count),
                    "train_class_counts": json.dumps({str(i): value for i, value in enumerate(per_class)}),
                    "validation_sample_count": "58", "test_sample_count": "288",
                    "primary_metric": "accuracy", "test_accuracy": str(metric),
                    "balanced_accuracy": str(metric), "macro_f1": str(metric),
                    "run_status": "completed", "checkpoint": f"checkpoint-{subject}-{budget}-{seed}.pt",
                })
    return rows


class SmallSampleAnalysisTests(unittest.TestCase):
    def test_strong_failure(self):
        result = classify(synthetic_matrix("strong"))
        self.assertEqual(result["classification"], "STRONG_FAILURE")
        self.assertTrue(result["seed_direction_consistent"])
        self.assertTrue(result["dose_response_pass"])
        self.assertEqual(result["subjects_degraded_ge_3pp"], 9)

    def test_mixed_failure_for_subject_heterogeneity(self):
        result = classify(synthetic_matrix("mixed"))
        self.assertEqual(result["classification"], "MIXED_FAILURE")
        self.assertEqual(result["subjects_degraded_ge_3pp"], 3)

    def test_mixed_failure_for_seed_inconsistency(self):
        result = classify(synthetic_matrix("seed_inconsistent"))
        self.assertEqual(result["classification"], "MIXED_FAILURE")
        self.assertFalse(result["seed_direction_consistent"])

    def test_no_meaningful_failure(self):
        result = classify(synthetic_matrix("stable"))
        self.assertEqual(result["classification"], "NO_MEANINGFUL_FAILURE")

    def test_incomplete_matrix(self):
        rows = synthetic_matrix("strong")[:-1]
        result = classify(rows)
        self.assertEqual(result["classification"], "INCOMPLETE_OR_INVALID")
        self.assertTrue(any("missing subject-budget-seed" in x for x in result["integrity_errors"]))

    def test_duplicate_run(self):
        rows = synthetic_matrix("strong")
        rows.append(copy.deepcopy(rows[0]))
        result = classify(rows)
        self.assertEqual(result["classification"], "INCOMPLETE_OR_INVALID")
        self.assertTrue(any("duplicate primary run" in x for x in result["integrity_errors"]))

    def test_wrong_split_seed(self):
        rows = synthetic_matrix("strong")
        rows[0]["split_seed"] = "43"
        result = classify(rows)
        self.assertEqual(result["classification"], "INCOMPLETE_OR_INVALID")
        self.assertTrue(any("split_seed=43" in x for x in result["integrity_errors"]))

    def test_seeds_are_aggregated_within_nine_subjects(self):
        rows = aggregate_subjects(synthetic_matrix("strong"))
        self.assertEqual(len(rows), 27)  # nine subjects by three budgets
        self.assertTrue(all(row["n_seeds"] == 3 for row in rows))
        result = classify(synthetic_matrix("strong"))
        self.assertEqual(len(result["subject_comparisons"]), 9)


if __name__ == "__main__":
    unittest.main()
