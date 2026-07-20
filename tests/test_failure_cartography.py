"""Synthetic safeguards for post-hoc EEGNet Failure Cartography."""
import json,tempfile,unittest
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader,TensorDataset
from src.failure_cartography import (LAYER_MODULES,ActivationCapture,
    assert_frozen_split,diagnostic_metrics,embedding_validity,infer_diagnostics,
    representation_shift,risk_coverage)
from src.models.eegnet import EEGNet
from src.train import DataBundle

class CartographyTests(unittest.TestCase):
 def setUp(self):
  torch.manual_seed(3);self.model=EEGNet(4,128,4);self.x=torch.randn(12,4,128);self.y=torch.arange(12)%4
  self.loader=DataLoader(TensorDataset(self.x,self.y),batch_size=4)
 def test_actual_module_names_exist(self):self.assertTrue(set(LAYER_MODULES.values())<=set(dict(self.model.named_modules())))
 def test_hooks_do_not_change_predictions(self):
  self.model.eval()
  with torch.no_grad():before=self.model(self.x).clone()
  capture=ActivationCapture(self.model);capture.record_input(self.x)
  with torch.no_grad():after=self.model(self.x)
  capture.close();self.assertTrue(torch.equal(before,after))
 def test_all_stages_are_captured(self):
  _,arrays=infer_diagnostics(self.model,self.loader,torch.device("cpu"));self.assertEqual(set(arrays),{"model_input",*LAYER_MODULES});self.assertTrue(all(len(v)==12 for v in arrays.values()))
 def test_logits_metrics(self):
  logits=np.asarray([[4,0],[0,4],[3,0],[0,3]],float);m=diagnostic_metrics(logits,np.asarray([0,1,0,1]));self.assertEqual(m["accuracy"],1.);self.assertIn("cohen_kappa",m);self.assertIn("nll",m);self.assertIn("brier_score",m);self.assertIn("ece",m);self.assertIn("aurc",m)
 def test_error_auroc_is_diagnostic(self):
  logits=np.asarray([[3,0],[3,0],[.1,0],[.1,0]]);m=diagnostic_metrics(logits,np.asarray([0,1,0,1]));self.assertIsNotNone(m["error_detection_auroc"])
 def test_risk_coverage_lengths(self):
  c=risk_coverage(np.asarray([.9,.8,.7]),np.asarray([1,0,1]));self.assertEqual(len(c["risk"]),3);self.assertEqual(c["coverage"][-1],1.)
 def test_shift_zero_for_identical_samples(self):
  x=np.arange(24,dtype=float).reshape(6,4);m=representation_shift(x,x.copy());self.assertAlmostEqual(m["feature_mean_shift"],0.);self.assertAlmostEqual(m["coral_distance"],0.)
 def test_shift_metrics_are_finite(self):
  rng=np.random.default_rng(4);m=representation_shift(rng.normal(size=(8,5)),rng.normal(size=(9,5)));self.assertEqual(set(m),{"feature_mean_shift","feature_variance_shift","covariance_difference","coral_distance","rbf_mmd2"});self.assertTrue(all(np.isfinite(v) for v in m.values()))
 def test_mismatched_width_rejected(self):
  with self.assertRaises(ValueError):representation_shift(np.ones((3,2)),np.ones((4,3)))
 def test_frozen_split_guard(self):
  bundle=DataBundle(None,None,None,[1,2],[3],[0,1],None)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"split.json";p.write_text(json.dumps({"small_sample":{"selected_training_indices":[1,2]},"validation_indices":[3],"test_indices":[0,1]}))
   assert_frozen_split(bundle,p);bundle.val_indices=[4]
   with self.assertRaises(RuntimeError):assert_frozen_split(bundle,p)
 def test_input_embedding_is_bounded(self):
  _,arrays=infer_diagnostics(self.model,self.loader,torch.device("cpu"));self.assertEqual(arrays["model_input"].shape[1],8)
 def test_embedding_validity_reports_rank_and_finiteness(self):
  result=embedding_validity(np.arange(30,dtype=float).reshape(6,5));self.assertTrue(result["all_finite"]);self.assertEqual(result["feature_dimension"],5);self.assertLessEqual(result["covariance_rank"],result["maximum_possible_sample_rank"])
 def test_embedding_validity_rejects_too_few_samples(self):
  with self.assertRaises(ValueError):embedding_validity(np.ones((1,3)))
if __name__=="__main__":unittest.main()
