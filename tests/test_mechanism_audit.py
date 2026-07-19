"""Synthetic tests frozen before real mechanism associations."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.mechanism_audit import (association, build_subject_table,
    frozen_subset_indices, geometry_features, log_bandpower_features)


def primary():
    rows=[]
    for s in range(1,10):
        for seed in (42,43,44):
            for b,n,a,c in [(1.,230,.7,'{"0":55,"1":55,"2":61,"3":59}'),(.5,114,.55,'{"0":27,"1":27,"2":30,"3":30}'),(.25,55,.4,'{"0":13,"1":13,"2":15,"3":14}')]:
                rows.append({"subject":str(s),"budget":str(b),"training_seed":str(seed),"subset_seed":"20260719","split_seed":"42","train_sample_count":str(n),"train_class_counts":c,"validation_sample_count":"58","test_sample_count":"288","primary_metric":"accuracy","checkpoint":"x","test_accuracy":str(a),"run_status":"completed"})
    return rows


def matched(value=.5):
    return [{"subject":str(s),"condition":"update_matched_25","budget":".25","split_seed":"42","subset_seed":"20260719","training_seed":str(seed),"target_optimizer_updates":"400","actual_optimizer_updates":"400","validation_event_count":"50","subset_identity_status":"matched","primary_metric":"accuracy","checkpoint":"x","test_accuracy":str(value),"run_status":"completed"} for s in range(1,10) for seed in (42,43,44)]


def control(value=.5):
    return [{"subject":str(s),"condition":"update_matched_25_wd1e3","budget":".25","weight_decay":".001","split_seed":"42","subset_seed":"20260719","training_seed":str(seed),"target_optimizer_updates":"400","actual_optimizer_updates":"400","validation_event_count":"50","subset_identity_status":"matched","primary_metric":"accuracy","checkpoint":"x","test_accuracy":str(value),"run_status":"completed"} for s in range(1,10) for seed in (42,43,44)]


class MechanismAuditTests(unittest.TestCase):
    def test_subject_alignment_across_results(self):
        geometry={s:{"within_class_dispersion":1.,"between_class_separation":2.,"separability_ratio":2.,"trial_feature_variability":3.} for s in range(1,10)}
        rows=build_subject_table(primary(),matched(),control(),geometry)
        self.assertEqual([r["subject"] for r in rows],list(range(1,10)))

    def test_exact_subset_provenance_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); payload={"validation_indices":[2],"test_indices":[0],"small_sample":{"split_seed":42,"subset_seed":20260719,"selected_training_indices":[1,3],"validation_indices":[2],"test_indices":[0]}}
            for seed in (42,43,44):
                p=root/"budget_025"/f"seed_{seed}"/"subject_01"/"split_indices.json";p.parent.mkdir(parents=True);p.write_text(json.dumps(payload))
            self.assertEqual(frozen_subset_indices(root,1),[1,3])

    def test_residual_gap_calculation(self):
        geometry={s:{"within_class_dispersion":1.,"between_class_separation":2.,"separability_ratio":2.,"trial_feature_variability":3.} for s in range(1,10)}
        self.assertAlmostEqual(build_subject_table(primary(),matched(.5),control(),geometry)[0]["residual_gap_pp"],20.)

    def test_seed_std_calculation(self):
        rows=matched(); vals={42:.4,43:.5,44:.6}
        for r in rows:
            if r["subject"]=="1":r["test_accuracy"]=str(vals[int(r["training_seed"])])
        geometry={s:{"within_class_dispersion":1.,"between_class_separation":2.,"separability_ratio":2.,"trial_feature_variability":3.} for s in range(1,10)}
        self.assertAlmostEqual(build_subject_table(primary(),rows,control(),geometry)[0]["seed_std_25_matched"],.1)

    def test_feature_extraction_is_deterministic(self):
        x=np.random.default_rng(1).normal(size=(8,2,500))
        np.testing.assert_array_equal(log_bandpower_features(x,250),log_bandpower_features(x,250))

    def test_within_class_dispersion(self):
        f=np.array([[0.],[2.],[10.],[12.]]);g=geometry_features(f,np.array([0,0,1,1]))
        self.assertGreater(g["within_class_dispersion"],0)

    def test_between_class_separation(self):
        g=geometry_features(np.array([[0.],[0.],[10.],[10.]]),np.array([0,0,1,1]))
        self.assertGreater(g["between_class_separation"],0)

    def test_separability_ratio(self):
        g=geometry_features(np.array([[0.],[1.],[10.],[11.]]),np.array([0,0,1,1]))
        self.assertAlmostEqual(g["separability_ratio"],g["between_class_separation"]/g["within_class_dispersion"])

    def test_spearman(self):
        self.assertAlmostEqual(association(range(9),range(9),"training_data_only")["spearman_rho"],1.)

    def test_kendall(self):
        self.assertAlmostEqual(association(range(9),range(9),"training_data_only")["kendall_tau"],1.)

    def test_loso_influence(self):
        r=association(range(9),range(9),"training_data_only")
        self.assertEqual(len(r["loso_values"]),9);self.assertEqual(r["direction_stability_count"],9)
        json.dumps(r)

    def test_robust_candidate_signal(self):
        self.assertEqual(association(range(9),range(9),"training_data_only")["classification"],"ROBUST_CANDIDATE_SIGNAL")

    def test_robust_descriptive_association(self):
        self.assertEqual(association(range(9),range(9),"result_descriptive")["classification"],"ROBUST_DESCRIPTIVE_ASSOCIATION")

    def test_weak_or_unstable(self):
        result=association(range(9),[0,4,1,7,3,8,2,6,5],"training_data_only")
        self.assertEqual(result["classification"],"WEAK_OR_UNSTABLE_ASSOCIATION")

    def test_no_clear_association(self):
        result=association(range(9),[4,0,8,2,6,1,7,3,5],"training_data_only")
        self.assertEqual(result["classification"],"NO_CLEAR_ASSOCIATION")

    def test_subject_mismatch_is_invalid(self):
        from src.mechanism_audit import analyze
        result=analyze([],primary(),matched(),control())
        self.assertFalse(result["integrity_pass"])


if __name__=="__main__":unittest.main()
