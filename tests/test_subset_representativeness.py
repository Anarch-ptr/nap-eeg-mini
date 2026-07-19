"""Synthetic preregistration tests for subset representativeness."""

import inspect
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.mechanism_audit import association, log_bandpower_features
from src.subset_representativeness import (analyze, reconstruct_partition,
    nonstationarity_diagnostics, representativeness_features, shared_normalize)


def make_root(mismatch=False):
    tmp=tempfile.TemporaryDirectory();root=Path(tmp.name)
    for seed in (42,43,44):
        subset=[0,2] if not mismatch or seed!=44 else [0,3]
        payload={"training_pool_indices":[0,1,2,3],"validation_indices":[4],"test_indices":list(range(288)),
                 "small_sample":{"training_pool_indices":[0,1,2,3],"selected_training_indices":subset,
                 "validation_indices":[4],"test_indices":list(range(288)),"split_seed":42,"subset_seed":20260719}}
        p=root/"budget_025"/f"seed_{seed}"/"subject_01"/"split_indices.json";p.parent.mkdir(parents=True);p.write_text(json.dumps(payload))
    return tmp,root


def feature_data():
    sub=np.array([[0.,0.],[1.,0.],[10.,0.],[11.,0.],[20.,0.],[21.,0.],[30.,0.],[31.,0.]])
    rem=sub+np.array([2.,0.]); labels=np.repeat(range(4),2)
    return sub,labels,rem,labels.copy()


class RepresentativenessTests(unittest.TestCase):
    def test_fixed_pool_reconstruction(self):
        t,r=make_root();self.addCleanup(t.cleanup);self.assertEqual(reconstruct_partition(r,1)["training_pool_indices"],[0,1,2,3])
    def test_subset_identity(self):
        t,r=make_root();self.addCleanup(t.cleanup);self.assertEqual(reconstruct_partition(r,1)["subset_indices"],[0,2])
    def test_partition_disjoint(self):
        t,r=make_root();self.addCleanup(t.cleanup);p=reconstruct_partition(r,1);self.assertFalse(set(p["subset_indices"])&set(p["remainder_indices"]))
    def test_partition_union(self):
        t,r=make_root();self.addCleanup(t.cleanup);p=reconstruct_partition(r,1);self.assertEqual(set(p["subset_indices"])|set(p["remainder_indices"]),set(p["training_pool_indices"]))
    def test_validation_exclusion(self):
        t,r=make_root();self.addCleanup(t.cleanup);p=reconstruct_partition(r,1);self.assertFalse(set(p["validation_indices"])&set(p["training_pool_indices"]))
    def test_official_test_exclusion(self):
        self.assertNotIn("test",inspect.signature(representativeness_features).parameters)
    def test_shared_normalization(self):
        pool=np.array([[0.],[2.],[4.],[6.]]);a,b=shared_normalize(pool,pool[:2],pool[2:]);self.assertAlmostEqual(np.concatenate([a,b]).mean(),0.)
    def test_centroid_shift(self):
        a,y,b,z=feature_data();self.assertAlmostEqual(representativeness_features(a,y,b,z)["class_centroid_shift"],2.)
    def test_covariance_shift(self):
        a,y,b,z=feature_data();self.assertAlmostEqual(representativeness_features(a,y,b,z)["class_covariance_shift"],0.)
    def test_coverage_distance(self):
        a,y,b,z=feature_data();self.assertAlmostEqual(representativeness_features(a,y,b,z)["class_coverage_distance"],1.5)
    def test_worst_coverage(self):
        a,y,b,z=feature_data();v=representativeness_features(a,y,b,z);self.assertAlmostEqual(v["worst_class_coverage_distance"],max(v["coverage_distance_per_class"]))
    def test_deterministic_extraction(self):
        x=np.random.default_rng(2).normal(size=(4,2,500));np.testing.assert_array_equal(log_bandpower_features(x,250),log_bandpower_features(x,250))
    def test_spearman(self):self.assertAlmostEqual(association(range(9),range(9),"training_data_only")["spearman_rho"],1.)
    def test_kendall(self):self.assertAlmostEqual(association(range(9),range(9),"training_data_only")["kendall_tau"],1.)
    def test_loso(self):self.assertEqual(len(association(range(9),range(9),"training_data_only")["loso_values"]),9)
    def test_robust_signal(self):self.assertEqual(association(range(9),range(9),"training_data_only")["classification"],"ROBUST_CANDIDATE_SIGNAL")
    def test_weak_signal(self):self.assertEqual(association(range(9),[0,4,1,7,3,8,2,6,5],"training_data_only")["classification"],"WEAK_OR_UNSTABLE_ASSOCIATION")
    def test_no_clear(self):self.assertEqual(association(range(9),[4,0,8,2,6,1,7,3,5],"training_data_only")["classification"],"NO_CLEAR_ASSOCIATION")
    def test_provenance_mismatch_invalid(self):
        t,r=make_root(True);self.addCleanup(t.cleanup)
        with self.assertRaises(RuntimeError):reconstruct_partition(r,1)
    def test_nonstationarity_checks_are_descriptive(self):
        import pandas as pd
        partition={"training_pool_indices":list(range(8)),"subset_indices":[0,2,4,6],"remainder_indices":[1,3,5,7]}
        metadata=pd.DataFrame({"run":["0","0","1","1","2","2","3","3"]})
        result=nonstationarity_diagnostics(partition,np.array([0,0,1,1,2,2,3,3]),metadata)
        self.assertIn("run_balance_tvd",result);self.assertNotIn("classification",result)


if __name__=="__main__":unittest.main()
