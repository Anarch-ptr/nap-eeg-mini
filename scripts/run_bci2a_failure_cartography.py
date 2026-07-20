"""Post-hoc Failure Cartography over frozen BCI2a small-sample checkpoints."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import torch
from scripts.run_bci2a_multiseed import validate_seeds
from scripts.run_bci2a_multisubject import validate_subjects
from src.failure_cartography import (assert_frozen_split,embedding_validity,infer_diagnostics,
                                     representation_shift)
from src.small_sample_audit import validate_budget
from src.train import build_dataloaders,build_model,load_config

BUDGET_DIR={1.0:"budget_100",.5:"budget_050",.25:"budget_025"}
RUN_FIELDS=("subject","budget","training_seed","split_seed","subset_seed",
"validation_accuracy","validation_balanced_accuracy","validation_macro_f1",
"validation_cohen_kappa","validation_nll","validation_brier_score","validation_ece",
"validation_mean_confidence_correct","validation_mean_confidence_incorrect",
"validation_error_detection_auroc","validation_aurc","evaluation_accuracy",
"evaluation_balanced_accuracy","evaluation_macro_f1","evaluation_cohen_kappa",
"evaluation_nll","evaluation_brier_score","evaluation_ece",
"evaluation_mean_confidence_correct","evaluation_mean_confidence_incorrect",
"evaluation_error_detection_auroc","evaluation_aurc","session_generalization_gap",
"checkpoint","split_integrity","official_evaluation_policy","run_status")

def run_dir(root,subject,budget,seed):return root/BUDGET_DIR[budget]/f"seed_{seed}"/f"subject_{subject:02d}"
def write_csv(path,rows,fields):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def prefixed(prefix,metrics):return {f"{prefix}_{k}":v for k,v in metrics.items() if k!="risk_coverage"}

def evaluate_cell(source_root,output_root,subject,budget,seed,device):
 source=run_dir(source_root,subject,budget,seed);config=load_config(str(source/"resolved_config.yaml"))
 if int(config["data"]["split_seed"])!=42 or int(config["small_sample"]["subset_seed"])!=20260719:
  raise RuntimeError("split_seed/subset_seed boundary changed")
 bundle=build_dataloaders(config);assert_frozen_split(bundle,source/"split_indices.json")
 model=build_model(config).to(device);checkpoint=torch.load(source/"best_validation_checkpoint.pt",map_location=device)
 model.load_state_dict(checkpoint["model_state_dict"])
 validation,val_rep=infer_diagnostics(model,bundle.val_loader,device)
 evaluation,eval_rep=infer_diagnostics(model,bundle.test_loader,device)
 if abs(validation["accuracy"]-float(checkpoint["best_validation_metrics"]["accuracy"]))>1e-12:
  raise RuntimeError("restored checkpoint does not reproduce frozen validation accuracy")
 row={"subject":subject,"budget":budget,"training_seed":seed,"split_seed":42,"subset_seed":20260719,
      **prefixed("validation",validation),**prefixed("evaluation",evaluation),
      "session_generalization_gap":validation["accuracy"]-evaluation["accuracy"],
      "checkpoint":str(source/"best_validation_checkpoint.pt"),"split_integrity":"matched",
      "official_evaluation_policy":"post_hoc_diagnostic_only_no_adaptation","run_status":"completed"}
 shifts=[]
 for layer in val_rep:
  for metric,value in representation_shift(val_rep[layer],eval_rep[layer]).items():
   shifts.append({"subject":subject,"budget":budget,"training_seed":seed,"layer_name":layer,
    "shift_metric":metric,"shift_value":value,"validation_accuracy":validation["accuracy"],
    "evaluation_accuracy":evaluation["accuracy"],"session_generalization_gap":row["session_generalization_gap"]})
 cell=output_root/BUDGET_DIR[budget]/f"seed_{seed}"/f"subject_{subject:02d}";cell.mkdir(parents=True,exist_ok=True)
 (cell/"risk_coverage.json").write_text(json.dumps({"validation":validation["risk_coverage"],"evaluation":evaluation["risk_coverage"]},indent=2),encoding="utf-8")
 validity=[]
 for layer in val_rep:
  for session,arrays in (("validation",val_rep[layer]),("official_evaluation",eval_rep[layer])):
   validity.append({"subject":subject,"budget":budget,"training_seed":seed,
                    "layer_name":layer,"session":session,**embedding_validity(arrays)})
 return row,shifts,validity

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--source-root",type=Path,default=Path("results/bci2a_small_sample_audit"));p.add_argument("--output-root",type=Path,default=Path("results/bci2a_failure_cartography"));p.add_argument("--subjects",type=int,nargs="+",default=list(range(1,10)));p.add_argument("--budgets",type=float,nargs="+",default=[1.,.5,.25]);p.add_argument("--training-seeds",type=int,nargs="+",default=[42,43,44]);p.add_argument("--confirm-full-matrix",action="store_true");a=p.parse_args()
 subjects=validate_subjects(a.subjects);budgets=[validate_budget(v) for v in a.budgets];seeds=validate_seeds(a.training_seeds)
 cells=len(subjects)*len(budgets)*len(seeds)
 if cells==81 and not a.confirm_full_matrix:raise RuntimeError("full 81-cell cartography requires --confirm-full-matrix")
 device=torch.device("cuda" if torch.cuda.is_available() else "cpu");rows=[];shifts=[];validity=[]
 for subject in subjects:
  for budget in budgets:
   for seed in seeds:
    row,layer_rows,validity_rows=evaluate_cell(a.source_root,a.output_root,subject,budget,seed,device);rows.append(row);shifts.extend(layer_rows);validity.extend(validity_rows);print(f"Completed A{subject:02d} budget={budget} seed={seed}")
 write_csv(a.output_root/"cartography_runs.csv",rows,RUN_FIELDS)
 shift_fields=("subject","budget","training_seed","layer_name","shift_metric","shift_value","validation_accuracy","evaluation_accuracy","session_generalization_gap")
 write_csv(a.output_root/"layer_shifts.csv",shifts,shift_fields)
 validity_fields=("subject","budget","training_seed","layer_name","session","sample_count","feature_dimension","all_finite","feature_value_std","covariance_rank","maximum_possible_sample_rank","covariance_rank_fraction")
 write_csv(a.output_root/"representation_validity.csv",validity,validity_fields)
 print(f"Completed diagnostic cells: {len(rows)}")
if __name__=="__main__":main()
