"""Run the frozen zero-training covariance intervention feasibility audit."""
import argparse,csv,json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from src.covariance_intervention_feasibility import classify,generate_candidate_bank,select_matched_pair
from src.data import load_bci2a_subject
from src.spatial_covariance_mechanism import covariance_geometry,log_covariance_trials
from src.subset_representativeness import reconstruct_partition

def serial(row):return {k:(json.dumps(v) if isinstance(v,(list,dict)) else v) for k,v in row.items()}
def write(path,rows,excluded=()):
    clean=[serial({k:v for k,v in r.items() if k not in excluded}) for r in rows]
    with path.open("w",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(clean[0]));w.writeheader();w.writerows(clean)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--primary-root",type=Path,default=Path("results/bci2a_small_sample_audit"));p.add_argument("--output-dir",type=Path,default=Path("results/bci2a_covariance_intervention_feasibility"));a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    subjects=[];all_candidates=[];errors=[]
    for subject in range(1,10):
        partition=reconstruct_partition(a.primary_root,subject);pool=partition["training_pool_indices"];original=partition["subset_indices"]
        if len(pool)!=230 or set(pool)&set(partition["validation_indices"]):raise RuntimeError(f"A{subject:02d}: pool integrity failure")
        data=load_bci2a_subject(subject,"data/moabb",8.,32.,0.,4.);logs=log_covariance_trials(data.x_train[pool]);counts=[int((data.y_train[original]==c).sum()) for c in range(4)]
        bank=generate_candidate_bank(pool,data.y_train,logs,counts,data.train_metadata["run"].astype(str).to_numpy(),subject)
        for row in bank:all_candidates.append({"subject":subject,**row})
        pair=select_matched_pair(bank);formal=covariance_geometry(log_covariance_trials(data.x_train[original]),data.y_train[original])["cov_between_class_separation"]
        pair.update({"subject":subject,"formal_original_separation":formal})
        subjects.append(pair)
        values=[r["cov_between_class_separation"] for r in bank];fig,ax=plt.subplots(figsize=(6,4.5));ax.hist(values,bins=30,alpha=.75);ax.axvline(formal,color="black",label="formal frozen 25%")
        if pair["feasible_pair"]:ax.axvline(pair["low_separation"],color="blue",label="LOW");ax.axvline(pair["high_separation"],color="red",label="HIGH")
        ax.set_xlabel("Covariance between-class separation");ax.set_ylabel("Candidate count");ax.set_title(f"A{subject:02d}");ax.legend();fig.tight_layout();fig.savefig(a.output_dir/f"subject_{subject:02d}_candidate_distribution.png",dpi=160);plt.close(fig)
    result=classify(subjects,errors);write(a.output_dir/"feasibility_subjects.csv",subjects,("low_trial_indices","high_trial_indices"));write(a.output_dir/"candidate_bank.csv",all_candidates)
    (a.output_dir/"feasibility_audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    lines=["# Covariance Intervention Feasibility Audit","",f"Classification: **{result['classification']}**",f"Integrity pass: `{result['integrity_pass']}`",f"Feasible subjects: {result['feasible_subjects']}/9",f"Meaningful contrasts: {result['meaningful_contrast_subjects']}/9","","Feasibility demonstrates only that a controlled intervention can be constructed; it does not establish causality.","","## Causal Interpretation Boundary and Ultimate Exit Protocol","","Covariance separation uses frozen log-Euclidean spatial covariance, not log-bandpower. A future intervention must use validation only for checkpoint selection and official test only once after restoring the checkpoint. HIGH-vs-LOW is primary; gaps to 100% are secondary. HIGH worse, HIGH better, no effect, and heterogeneous effects are symmetric frozen outcomes.","","One selected pair per subject is a first intervention-style test, not definitive causality; trial identities necessarily differ and unmeasured properties may remain. Additional-pair training requires separate preregistration. Micro-mechanism hunting remains blocked until directional intervention evidence. Feasibility, no-effect, and heterogeneity STOP rules cannot be relaxed after results."]
    (a.output_dir/"feasibility_audit.md").write_text("\n".join(lines)+"\n",encoding="utf-8");print(f"Classification: {result['classification']}");print(f"Feasible: {result['feasible_subjects']}/9; meaningful: {result['meaningful_contrast_subjects']}/9")
if __name__=="__main__":main()
