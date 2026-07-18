import unittest
import numpy as np
from src.spatial_artifact_audit import *
class SpatialAuditTests(unittest.TestCase):
 def setUp(self):self.x=np.ones((3,22,1001),dtype=np.float32)
 def test_names_and_frozen_groups(self):
  validate_channel_names(CHANNEL_NAMES);self.assertEqual(group_names("frontal"),("Fz","FC3","FC1","FCz","FC2","FC4"));self.assertEqual(len(CHANNEL_GROUPS["matched_nonfrontal"]),6)
 def test_random_groups_frozen_and_equal_count(self):
  self.assertEqual(GROUP_SEED,20260718);self.assertEqual([len(CHANNEL_GROUPS[f"random_0{i}"]) for i in range(1,6)],[6]*5);self.assertEqual(CHANNEL_GROUPS["random_01"],(1,10,11,13,14,18))
 def test_mask_full(self):
  y=mask_channels(self.x,CHANNEL_GROUPS["frontal"]);self.assertEqual(y.shape,self.x.shape);np.testing.assert_array_equal(y[:,CHANNEL_GROUPS["frontal"],:],0);np.testing.assert_array_equal(y[:,6:,:],1)
 def test_temporal_mask(self):
  y=mask_channels(self.x,CHANNEL_GROUPS["frontal"],"early",250);np.testing.assert_array_equal(y[:,:,:251][:,CHANNEL_GROUPS["frontal"],:],0);np.testing.assert_array_equal(y[:,:,251:],1)
 def test_noise_deterministic_sigma(self):
  a=base_group_noise(self.x.shape,.5,7);b=base_group_noise(self.x.shape,.5,7);np.testing.assert_array_equal(a,b);self.assertAlmostEqual(float(a.std()),.5,places=2)
 def test_group_noise_selected_only_and_matched(self):
  n=base_group_noise(self.x.shape,.5,8);a=inject_group_noise(self.x,CHANNEL_GROUPS["frontal"],n);b=inject_group_noise(self.x,CHANNEL_GROUPS["matched_nonfrontal"],n);np.testing.assert_array_equal(a[:,6:,:],self.x[:,6:,:]);self.assertAlmostEqual(perturbation_stats(self.x,a)[0],perturbation_stats(self.x,b)[0])
 def test_global_noise(self):
  y,n=inject_global_noise(self.x,.25,9);self.assertTrue(np.all(np.any(y!=self.x,axis=(0,2))));np.testing.assert_allclose(y-self.x,n,atol=1e-7)
 def test_metrics_and_random_summary(self):
  self.assertAlmostEqual(paired_delta(.7,.6),-.1);self.assertAlmostEqual(frontal_matched_contrast(-.2,-.1),-.1);s=random_summary(-.2,[-.1,-.3,-.15,-.05,-.25]);self.assertEqual(s["frontal_rank_most_negative_first"],3)
if __name__=="__main__":unittest.main()
