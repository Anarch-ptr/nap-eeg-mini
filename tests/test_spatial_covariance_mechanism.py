"""Synthetic tests frozen before real spatial-covariance associations."""
import inspect,unittest
from pathlib import Path
import numpy as np
from src.mechanism_audit import association
from src.spatial_covariance_mechanism import (ALPHA,analyze,covariance_geometry,
    frozen_subset,log_covariance_trials,log_euclidean_distance,matrix_log_spd,trial_covariance)

class CovarianceAuditTests(unittest.TestCase):
    def test_exact_subset_uses_frozen_partition(self):
        self.assertIn("reconstruct_partition",inspect.getsource(frozen_subset))
    def test_validation_test_excluded(self):
        self.assertEqual(list(inspect.signature(log_covariance_trials).parameters),["x"])
    def test_trial_centering(self):
        x=np.array([[1.,2.,3.],[4.,6.,8.]])
        np.testing.assert_allclose(trial_covariance(x),trial_covariance(x+10))
    def test_covariance_calculation(self):
        x=np.array([[0.,1.,2.],[0.,2.,4.]])
        raw=(x-x.mean(1,keepdims=True))@(x-x.mean(1,keepdims=True)).T/2
        expected=raw/np.trace(raw);expected=(1-ALPHA)*expected+ALPHA*np.eye(2)/2
        np.testing.assert_allclose(trial_covariance(x),expected)
    def test_trace_normalization(self):
        self.assertAlmostEqual(np.trace(trial_covariance(np.array([[0.,1.,2.],[2.,0.,1.]]))),1.)
    def test_fixed_alpha(self):self.assertEqual(ALPHA,1e-3)
    def test_positive_eigenvalues(self):
        self.assertGreater(np.linalg.eigvalsh(trial_covariance(np.array([[0.,1.,2.],[0.,2.,4.]]))).min(),0)
    def test_matrix_log(self):
        m=np.diag([1.,np.e]);np.testing.assert_allclose(matrix_log_spd(m),np.diag([0.,1.]))
    def test_log_euclidean_distance(self):
        self.assertAlmostEqual(log_euclidean_distance(np.zeros((2,2)),np.eye(2)),np.sqrt(2))
    def sample_geometry(self):
        values=[];labels=[]
        for c in range(4):
            values.extend([np.eye(2)*c,np.eye(2)*c+np.eye(2)]);labels.extend([c,c])
        return covariance_geometry(np.array(values),np.array(labels))
    def test_within_dispersion(self):self.assertGreater(self.sample_geometry()["cov_within_class_dispersion"],0)
    def test_between_separation(self):self.assertGreater(self.sample_geometry()["cov_between_class_separation"],0)
    def test_ratio(self):
        g=self.sample_geometry();self.assertAlmostEqual(g["cov_separability_ratio"],g["cov_between_class_separation"]/(g["cov_within_class_dispersion"]+1e-12))
    def test_deterministic(self):
        x=np.random.default_rng(3).normal(size=(4,3,100));np.testing.assert_array_equal(log_covariance_trials(x),log_covariance_trials(x))
    def test_spearman(self):self.assertAlmostEqual(association(range(9),range(9),"training_data_only")["spearman_rho"],1)
    def test_kendall(self):self.assertAlmostEqual(association(range(9),range(9),"training_data_only")["kendall_tau"],1)
    def test_loso(self):self.assertEqual(len(association(range(9),range(9),"training_data_only")["loso_values"]),9)
    def test_robust(self):self.assertEqual(association(range(9),range(9),"training_data_only")["classification"],"ROBUST_CANDIDATE_SIGNAL")
    def test_weak(self):self.assertEqual(association(range(9),[0,4,1,7,3,8,2,6,5],"training_data_only")["classification"],"WEAK_OR_UNSTABLE_ASSOCIATION")
    def test_no_clear(self):self.assertEqual(association(range(9),[4,0,8,2,6,1,7,3,5],"training_data_only")["classification"],"NO_CLEAR_ASSOCIATION")
    def test_provenance_mismatch_invalid(self):self.assertFalse(analyze([])["integrity_pass"])

if __name__=="__main__":unittest.main()
