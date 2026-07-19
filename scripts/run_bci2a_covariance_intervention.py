"""Run the frozen 54-cell Pair-Set-1 covariance intervention."""
import argparse,copy,csv,json
from pathlib import Path
import torch
from scripts.run_bci2a_multiseed import validate_seeds
from scripts.run_bci2a_multisubject import validate_subjects
from src.covariance_separation_intervention import (CONDITIONS,FEASIBILITY_COMMIT,
    TARGET_UPDATES,VALIDATION_EVENTS,assert_pair_identity,load_frozen_pairs,
    run_intervention_training,selected_identity)
from src.train import load_config

FIELDS=("subject","condition","candidate_id","separation_value","separation_percentile",
"training_seed","split_seed","sample_count","per_class_counts","trial_indices",
"target_optimizer_updates","actual_optimizer_updates","validation_event_count",
"best_validation_event","checkpoint","test_accuracy","balanced_accuracy","macro_f1",
"run_status","intervention_freeze_commit","frozen_feasibility_commit",
"trial_identity_integrity","normalization_provenance","official_test_evaluations",
"best_checkpoint_restored_before_test")

def read_rows(path):
    if not path.is_file(): return []
    with path.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
def write_history(path,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def build_config(base,subject,condition,seed,root):
    c=copy.deepcopy(base);c["seed"]=seed;c["data"]["subject_id"]=subject
    c["small_sample"]["enabled"]=False
    run=root/condition.lower()/f"seed_{seed}"/f"subject_{subject:02d}"
    c["output"]["table_dir"]=str(run);return c,run

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path,default=Path("configs/bci2a_small_sample_audit.yaml"))
    p.add_argument("--feasibility",type=Path,default=Path("results/bci2a_covariance_intervention_feasibility/feasibility_audit.json"))
    p.add_argument("--output-root",type=Path,default=Path("results/bci2a_covariance_intervention"))
    p.add_argument("--subjects",type=int,nargs="+",default=list(range(1,10)))
    p.add_argument("--training-seeds",type=int,nargs="+",default=[42,43,44])
    p.add_argument("--intervention-freeze-commit",required=True);a=p.parse_args()
    subjects,seeds=validate_subjects(a.subjects),validate_seeds(a.training_seeds)
    base=load_config(str(a.config));pairs=load_frozen_pairs(a.feasibility)
    if int(base["data"]["split_seed"])!=42 or int(base["training"]["batch_size"])!=32:raise RuntimeError("frozen config changed")
    if float(base["training"]["weight_decay"])!=1e-4 or float(base["model"]["dropout"])!=.25:raise RuntimeError("frozen training recipe changed")
    # Verify every requested identity and official split before the first update.
    for subject in subjects:
      for condition in CONDITIONS:
        c,_=build_config(base,subject,condition,seeds[0],a.output_root)
        from src.covariance_separation_intervention import build_intervention_dataloaders
        assert_pair_identity(build_intervention_dataloaders(c,pairs[subject],condition),pairs[subject],condition)
    print("Preflight frozen Pair-Set-1 identity verification passed.")
    rows=read_rows(a.output_root/"intervention_runs.csv");device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    for subject in subjects:
      for condition in CONDITIONS:
       candidate,identities,separation,percentile=selected_identity(pairs[subject],condition)
       for seed in seeds:
        c,run=build_config(base,subject,condition,seed,a.output_root);result=run_intervention_training(c,pairs[subject],condition,device)
        summary,metrics=result["summary"],result["metrics"]
        row={"subject":subject,"condition":condition,"candidate_id":candidate,"separation_value":separation,
        "separation_percentile":percentile,"training_seed":seed,"split_seed":42,"sample_count":len(identities),
        "per_class_counts":json.dumps(pairs[subject]["per_class_counts"]),"trial_indices":json.dumps(identities),
        "target_optimizer_updates":TARGET_UPDATES,"actual_optimizer_updates":summary["actual_optimizer_updates"],
        "validation_event_count":summary["validation_event_count"],"best_validation_event":summary["best_validation_event"],
        "checkpoint":summary["best_checkpoint"],"test_accuracy":metrics["accuracy"],"balanced_accuracy":metrics["balanced_accuracy"],
        "macro_f1":metrics["macro_f1"],"run_status":"completed","intervention_freeze_commit":a.intervention_freeze_commit,
        "frozen_feasibility_commit":FEASIBILITY_COMMIT,"trial_identity_integrity":"matched",
        "normalization_provenance":json.dumps(summary["normalization"]),"official_test_evaluations":1,
        "best_checkpoint_restored_before_test":True}
        rows=[r for r in rows if (int(r["subject"]),r["condition"],int(r["training_seed"]))!=(subject,condition,seed)]+[row]
        write_rows(a.output_root/"intervention_runs.csv",rows);write_history(run/"metrics.csv",result["history"])
        (run/"intervention_result.json").write_text(json.dumps(row,indent=2),encoding="utf-8")
        print(f"Completed A{subject:02d} {condition} seed={seed}")
    print(f"Completed runs: {len(rows)}")
if __name__=="__main__":main()
