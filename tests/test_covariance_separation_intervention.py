"""Synthetic tests frozen before Pair-Set-1 performance is observed."""
import json,unittest
from src.covariance_separation_intervention import (CONDITIONS,FEASIBILITY_COMMIT,
    SEEDS,SUBJECTS,analyze_intervention,validate_intervention_matrix)

def pairs():
 return {s:{"subject":s,"subset_size":4,"per_class_counts":[1,1,1,1],
  "low_candidate_id":s*10,"high_candidate_id":s*10+1,
  "low_trial_indices":[0,1,2,3],"high_trial_indices":[4,5,6,7],
  "low_separation":1.,"high_separation":2.,
  "low_separation_percentile":10.,"high_separation_percentile":90.} for s in SUBJECTS}
def rows(low=.5,high=.5):
 out=[]
 for s in SUBJECTS:
  for c in CONDITIONS:
   for seed in SEEDS:
    p=pairs()[s];side="low" if c=="LOW_SEP" else "high"
    out.append({"subject":str(s),"condition":c,"training_seed":str(seed),
    "candidate_id":str(p[f"{side}_candidate_id"]),"trial_indices":json.dumps(p[f"{side}_trial_indices"]),
    "sample_count":"4","per_class_counts":json.dumps([1,1,1,1]),
    "separation_value":str(p[f"{side}_separation"]),"separation_percentile":str(p[f"{side}_separation_percentile"]),
    "target_optimizer_updates":"400","actual_optimizer_updates":"400","validation_event_count":"50",
    "frozen_feasibility_commit":FEASIBILITY_COMMIT,"trial_identity_integrity":"matched","run_status":"completed",
    "official_test_evaluations":"1","best_checkpoint_restored_before_test":"True",
    "test_accuracy":str(low if c=="LOW_SEP" else high)})
 return out
def primary():
 counts={1.:{"0":55,"1":55,"2":61,"3":59},.5:{"0":27,"1":27,"2":30,"3":30},.25:{"0":13,"1":13,"2":15,"3":14}}
 return [{"subject":str(s),"budget":str(b),"training_seed":str(seed),"subset_seed":"20260719","split_seed":"42",
 "train_sample_count":str({1.:230,.5:114,.25:55}[b]),"train_class_counts":json.dumps(counts[b]),
 "validation_sample_count":"58","test_sample_count":"288","primary_metric":"accuracy","checkpoint":"x","test_accuracy":".7","run_status":"completed"}
 for s in SUBJECTS for seed in SEEDS for b in (1.,.5,.25)]
def analyze(low,high):return analyze_intervention(rows(low,high),pairs(),primary())

class InterventionTests(unittest.TestCase):
 def test_high_worse(self):self.assertEqual(analyze(.60,.55)["classification"],"HIGH_SEPARATION_WORSE")
 def test_high_better(self):self.assertEqual(analyze(.55,.60)["classification"],"HIGH_SEPARATION_BETTER")
 def test_no_effect(self):self.assertEqual(analyze(.55,.555)["classification"],"NO_MEANINGFUL_INTERVENTION_EFFECT")
 def test_heterogeneous(self):
  r=rows(.5,.5)
  for row in r:
   if row["condition"]=="HIGH_SEP":row["test_accuracy"]=str(.55 if int(row["subject"])%2 else .45)
  self.assertEqual(analyze_intervention(r,pairs(),primary())["classification"],"HETEROGENEOUS_OR_WEAK_INTERVENTION_EFFECT")
 def test_missing_run_invalid(self):self.assertEqual(analyze_intervention(rows()[:-1],pairs(),primary())["classification"],"INCOMPLETE_OR_INVALID")
 def test_duplicate_invalid(self):
  r=rows();r.append(r[0].copy());self.assertTrue(validate_intervention_matrix(r,pairs()))
 def test_wrong_identity_invalid(self):
  r=rows();r[0]["candidate_id"]="999";self.assertTrue(validate_intervention_matrix(r,pairs()))
 def test_wrong_update_invalid(self):
  r=rows();r[0]["actual_optimizer_updates"]="399";self.assertTrue(validate_intervention_matrix(r,pairs()))
 def test_wrong_validation_invalid(self):
  r=rows();r[0]["validation_event_count"]="49";self.assertTrue(validate_intervention_matrix(r,pairs()))
 def test_wrong_feasibility_commit_invalid(self):
  r=rows();r[0]["frozen_feasibility_commit"]="bad";self.assertTrue(validate_intervention_matrix(r,pairs()))
 def test_seed_aggregation_within_subject(self):
  r=rows(.5,.5)
  for row in r:
   if row["subject"]=="1" and row["condition"]=="HIGH_SEP":row["test_accuracy"]={"42":".4","43":".5","44":".6"}[row["training_seed"]]
  result=analyze_intervention(r,pairs(),primary());self.assertAlmostEqual(result["subject_results"][0]["accuracy_high"],.5)
 def test_effect_percentage_points(self):self.assertAlmostEqual(analyze(.5,.55)["subject_results"][0]["intervention_effect_pp"],5.)
 def test_secondary_residual_gaps(self):
  row=analyze(.5,.55)["subject_results"][0];self.assertAlmostEqual(row["low_residual_gap_pp"],20.);self.assertAlmostEqual(row["high_residual_gap_pp"],15.)
 def test_classification_precedence_invalid_first(self):
  r=rows(.6,.5)[:-1];self.assertEqual(analyze_intervention(r,pairs(),primary())["classification"],"INCOMPLETE_OR_INVALID")
 def test_exact_54_cells(self):self.assertEqual(len(rows()),54);self.assertEqual(validate_intervention_matrix(rows(),pairs()),[])
if __name__=="__main__":unittest.main()
