"""Synthetic tests frozen before real covariance feasibility output."""
import inspect,unittest
import numpy as np
from src.covariance_intervention_feasibility import (N_CANDIDATES,classify,
    chronological_descriptors,generate_candidate_bank,pair_is_matched,run_tvd,select_matched_pair)
from src.spatial_covariance_mechanism import ALPHA,covariance_geometry

def candidate(cid,sep,within=1.,runs=None,mean=.5,spread=.2):
    return {"candidate_id":cid,"trial_indices":[cid,cid+10],"per_class_counts":[1,1,1,1],
            "cov_between_class_separation":sep,"cov_within_class_dispersion":within,
            "cov_separability_ratio":sep/within,"run_distribution":runs or [.5,.5],
            "run_tvd_from_pool":0.,"chronological_mean_position":mean,"chronological_spread":spread}

class FeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pool=np.arange(160);labels=np.repeat(range(4),40);logs=np.asarray([np.eye(2)*(1+i/1000) for i in pool]);runs=np.asarray([str(i%6) for i in pool])
        cls.bank=generate_candidate_bank(pool,labels,logs,[2,2,2,2],runs,1)
        cls.bank2=generate_candidate_bank(pool,labels,logs,[2,2,2,2],runs,1)
    def test_exact_pool_provenance_dependency(self):self.assertIn("pool_indices",inspect.signature(generate_candidate_bank).parameters)
    def test_exact_class_counts(self):self.assertTrue(all(r["per_class_counts"]==[2,2,2,2] for r in self.bank))
    def test_deterministic_bank(self):self.assertEqual([r["trial_indices"] for r in self.bank],[r["trial_indices"] for r in self.bank2])
    def test_exactly_512(self):self.assertEqual(len(self.bank),N_CANDIDATES)
    def test_representation_unchanged(self):self.assertEqual(ALPHA,1e-3)
    def test_separation_calculation(self):self.assertIn("cov_between_class_separation",covariance_geometry(np.asarray([np.eye(2)*i for i in range(8)]),np.repeat(range(4),2)))
    def test_within_calculation(self):self.assertIn("cov_within_class_dispersion",covariance_geometry(np.asarray([np.eye(2)*i for i in range(8)]),np.repeat(range(4),2)))
    def test_run_tvd(self):self.assertAlmostEqual(run_tvd([.5,.5],[1.,0.]),.5)
    def test_chronological_mean(self):self.assertAlmostEqual(chronological_descriptors([0,9],10)[0],.5)
    def test_chronological_spread(self):self.assertAlmostEqual(chronological_descriptors([0,9],10)[1],.5)
    def test_matching_constraints(self):self.assertTrue(pair_is_matched({"within_dispersion_relative_difference":.1,"run_distribution_TVD_between_subsets":.1,"chronological_mean_position_difference":.1,"chronological_spread_difference":.1}))
    def test_tie_breaking(self):
        result=select_matched_pair([candidate(0,1),candidate(1,3),candidate(2,1),candidate(3,3)])
        self.assertEqual((result["low_candidate_id"],result["high_candidate_id"]),(0,1))
    def test_meaningful_percentile_gate(self):
        result=select_matched_pair([candidate(i,float(i)) for i in range(8)])
        self.assertTrue(result["meaningful_property_contrast"])
    def test_intervention_feasible(self):
        rows=[{"subject":i,"feasible_pair":True,"meaningful_property_contrast":True} for i in range(1,10)]
        self.assertEqual(classify(rows)["classification"],"INTERVENTION_FEASIBLE")
    def test_intervention_not_feasible(self):
        rows=[{"subject":i,"feasible_pair":i<7,"meaningful_property_contrast":i<7} for i in range(1,10)]
        self.assertEqual(classify(rows)["classification"],"INTERVENTION_NOT_FEASIBLE")
    def test_invalid(self):self.assertEqual(classify([],['bad'])["classification"],"INCOMPLETE_OR_INVALID")
    def test_no_validation_test_inputs(self):
        params=inspect.signature(generate_candidate_bank).parameters;self.assertNotIn("validation",params);self.assertNotIn("test",params)
    def test_trial_indices_reproducible(self):self.assertEqual(self.bank[100]["trial_indices"],self.bank2[100]["trial_indices"])

if __name__=="__main__":unittest.main()
