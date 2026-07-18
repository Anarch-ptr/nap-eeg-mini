import unittest
import numpy as np
from src.eog_dependency_audit import *

class DependencyAuditTests(unittest.TestCase):
    def setUp(self):
        self.clean=np.ones((8,22,1001));self.component=np.full_like(self.clean,.25)
    def test_alpha_zero_is_clean_and_shape_preserved(self):
        result=remove_component(self.clean,self.component,"early",0,250);np.testing.assert_array_equal(result,self.clean);self.assertEqual(result.shape,(8,22,1001))
    def test_alpha_one_and_only_window_changes(self):
        result=remove_component(self.clean,self.component,"middle",1,250);sl=window_slice("middle",250,1001);np.testing.assert_allclose(result[:,:,sl],.75);np.testing.assert_array_equal(result[:,:,:sl.start],self.clean[:,:,:sl.start]);np.testing.assert_array_equal(result[:,:,sl.stop:],self.clean[:,:,sl.stop:])
    def test_split_rejects_wrong_test(self):
        with self.assertRaises(RuntimeError):validate_split({"train_indices":[0],"validation_indices":[1],"test_indices":[1,0]},2,2)
    def test_normalization_provenance_and_values(self):
        x=np.arange(2*2*3,dtype=float).reshape(2,2,3);idx=np.array([0]);mean=x[idx].mean((0,2));std=x[idx].std((0,2),ddof=1)
        verify_normalization(x,idx,{"source":"train_subset","mean":mean.tolist(),"std":std.tolist()})
        with self.assertRaises(RuntimeError):verify_normalization(x,idx,{"source":"official_train","mean":mean.tolist(),"std":std.tolist()})
    def test_fit_mapping_uses_indices(self):
        rng=np.random.default_rng(1);eog=rng.normal(size=(4,3,20));eeg=np.einsum("nct,cd->ndt",eog,np.ones((3,22)));idx=np.array([0,1]);mean=eeg[idx].mean((0,2),keepdims=True);std=eeg[idx].std((0,2),ddof=1,keepdims=True);_,b,em,es=fit_mapping(eeg,eog,idx,mean,std);self.assertEqual(b.shape,(3,22));self.assertEqual(em.shape,(1,3,1));self.assertEqual(es.shape,(1,3,1))
    def test_control_properties(self):
        labels=np.repeat(np.arange(4),2);a=make_test_control_mapping(labels,7);b=make_test_control_mapping(labels,7);np.testing.assert_array_equal(a,b);self.assertTrue(np.all(a!=np.arange(8)));np.testing.assert_array_equal(labels[a],labels)
    def test_energy_matching_and_zero(self):
        true=np.ones((2,22,10));control=np.full_like(true,2);sl=slice(0,10);matched=energy_match(true,control,sl);np.testing.assert_allclose(np.linalg.norm(matched.reshape(2,-1),axis=1),np.linalg.norm(true.reshape(2,-1),axis=1));np.testing.assert_array_equal(energy_match(np.zeros_like(true),np.zeros_like(true),sl),np.zeros_like(true))
        with self.assertRaises(RuntimeError):energy_match(true,np.zeros_like(true),sl)
    def test_rotation_preserves_singular_values(self):
        rng=np.random.default_rng(2);x=rng.normal(size=(2,22,30));q=orthogonal_rotation(22,3);y=rotate_channels(x,q);np.testing.assert_allclose(np.linalg.norm(x),np.linalg.norm(y));np.testing.assert_allclose(np.linalg.svd(x[0],compute_uv=False),np.linalg.svd(y[0],compute_uv=False),rtol=1e-10,atol=1e-10)
    def test_paired_negative_effect(self):
        effect=paired_effect(.7,.5,.65);self.assertAlmostEqual(effect["delta_true"],-.2);self.assertAlmostEqual(effect["dependency_contrast"],-.15)
    def test_component_excludes_intercept(self):
        eog=np.zeros((2,3,4));p=predict_component(eog,np.ones((3,22)),np.zeros((1,3,1)),np.ones((1,3,1)));np.testing.assert_array_equal(p,0)

if __name__=="__main__":unittest.main()
