"""Synthetic tests frozen before weight-decay control outcomes."""

import unittest

from src.simple_control_analysis import analyze_simple_control


def primary_rows(full=.70):
    rows=[]
    for s in range(1,10):
        for seed in (42,43,44):
            for budget,count,acc,counts in [(1.,230,full,'{"0":55,"1":55,"2":61,"3":59}'),
                                             (.5,114,.55,'{"0":27,"1":27,"2":30,"3":30}'),
                                             (.25,55,.4,'{"0":13,"1":13,"2":15,"3":14}')]:
                rows.append({"subject":str(s),"budget":str(budget),"training_seed":str(seed),
                    "subset_seed":"20260719","split_seed":"42","train_sample_count":str(count),
                    "train_class_counts":counts,"validation_sample_count":"58","test_sample_count":"288",
                    "primary_metric":"accuracy","checkpoint":"p.pt","test_accuracy":str(acc),"run_status":"completed"})
    return rows


def matched_rows(value=.50):
    return [{"subject":str(s),"condition":"update_matched_25","budget":".25",
        "split_seed":"42","subset_seed":"20260719","training_seed":str(seed),
        "target_optimizer_updates":"400","actual_optimizer_updates":"400",
        "validation_event_count":"50","subset_identity_status":"matched",
        "primary_metric":"accuracy","checkpoint":"m.pt","test_accuracy":str(value),"run_status":"completed"}
        for s in range(1,10) for seed in (42,43,44)]


def control_rows(value=.55):
    return [{"subject":str(s),"condition":"update_matched_25_wd1e3","budget":".25",
        "weight_decay":"0.001","split_seed":"42","subset_seed":"20260719","training_seed":str(seed),
        "target_optimizer_updates":"400","actual_optimizer_updates":"400",
        "validation_event_count":"50","subset_identity_status":"matched",
        "primary_metric":"accuracy","checkpoint":"c.pt","test_accuracy":str(value),"run_status":"completed"}
        for s in range(1,10) for seed in (42,43,44)]


class SimpleControlAnalysisTests(unittest.TestCase):
    def classify(self, control, matched=.50):
        return analyze_simple_control(primary_rows(), matched_rows(matched), control_rows(control))

    def test_simple_control_solves_most(self):
        self.assertEqual(self.classify(.69)["classification"], "SIMPLE_CONTROL_SOLVES_MOST")

    def test_persistent_strong_failure_after_control(self):
        self.assertEqual(self.classify(.55)["classification"], "PERSISTENT_STRONG_FAILURE_AFTER_CONTROL")

    def test_partial_simple_control_effect(self):
        self.assertEqual(self.classify(.66)["classification"], "PARTIAL_SIMPLE_CONTROL_EFFECT")

    def test_no_meaningful_control_benefit(self):
        self.assertEqual(self.classify(.505)["classification"], "NO_MEANINGFUL_CONTROL_BENEFIT")

    def test_missing_run_is_invalid(self):
        self.assertEqual(analyze_simple_control(primary_rows(), matched_rows(), control_rows()[:-1])["classification"], "INCOMPLETE_OR_INVALID")

    def test_wrong_weight_decay_is_invalid(self):
        rows=control_rows(); rows[0]["weight_decay"]=".0001"
        self.assertEqual(analyze_simple_control(primary_rows(), matched_rows(), rows)["classification"], "INCOMPLETE_OR_INVALID")

    def test_wrong_update_count_is_invalid(self):
        rows=control_rows(); rows[0]["actual_optimizer_updates"]="399"
        self.assertEqual(analyze_simple_control(primary_rows(), matched_rows(), rows)["classification"], "INCOMPLETE_OR_INVALID")

    def test_wrong_validation_count_is_invalid(self):
        rows=control_rows(); rows[0]["validation_event_count"]="49"
        self.assertEqual(analyze_simple_control(primary_rows(), matched_rows(), rows)["classification"], "INCOMPLETE_OR_INVALID")

    def test_subset_mismatch_is_invalid(self):
        rows=control_rows(); rows[0]["subset_identity_status"]="mismatch"
        self.assertEqual(analyze_simple_control(primary_rows(), matched_rows(), rows)["classification"], "INCOMPLETE_OR_INVALID")

    def test_seed_aggregation_is_within_subject(self):
        rows=control_rows(.55)
        for row in rows:
            if row["subject"]=="1": row["test_accuracy"]={"42":".5","43":".6","44":".7"}[row["training_seed"]]
        result=analyze_simple_control(primary_rows(),matched_rows(),rows)
        self.assertAlmostEqual(result["subject_control_diagnostics"][0]["accuracy_25_matched_wd1e3_mean"],.6)

    def test_control_gain_percentage_points(self):
        row=self.classify(.55)["subject_control_diagnostics"][0]
        self.assertAlmostEqual(row["control_gain_pp"],5.)

    def test_control_residual_percentage_points(self):
        row=self.classify(.55)["subject_control_diagnostics"][0]
        self.assertAlmostEqual(row["control_residual_gap_pp"],15.)

    def test_no_benefit_precedes_persistent(self):
        result=self.classify(.505)
        self.assertGreaterEqual(result["median_control_residual_gap_pp"],5.)
        self.assertEqual(result["classification"],"NO_MEANINGFUL_CONTROL_BENEFIT")


if __name__=="__main__": unittest.main()
