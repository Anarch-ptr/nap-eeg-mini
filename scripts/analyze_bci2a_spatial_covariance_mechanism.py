"""Run the frozen zero-training spatial covariance mechanism audit."""

import argparse,csv,json
from pathlib import Path
import matplotlib.pyplot as plt
from src.data import load_bci2a_subject
from src.spatial_covariance_mechanism import FEATURES,SUBJECTS,analyze,covariance_geometry,frozen_subset,log_covariance_trials

def read(path):
    with path.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def write(path,rows,excluded=()):
    clean=[{k:v for k,v in r.items() if k not in excluded} for r in rows]
    with path.open("w",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(clean[0]));w.writeheader();w.writerows(clean)
def plot(path,feature,rows):
    fig,ax=plt.subplots(figsize=(6,4.5));x=[r[feature] for r in rows];y=[r["residual_gap_pp"] for r in rows];ax.scatter(x,y)
    for r in rows:ax.annotate(f"A{r['subject']:02d}",(r[feature],r["residual_gap_pp"]),xytext=(4,4),textcoords="offset points")
    ax.set_xlabel(feature);ax.set_ylabel("Residual gap (percentage points)");ax.grid(alpha=.25);fig.tight_layout();fig.savefig(path,dpi=160);plt.close(fig)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--primary-root",type=Path,default=Path("results/bci2a_small_sample_audit"));p.add_argument("--mechanism-table",type=Path,default=Path("results/bci2a_small_sample_mechanism_audit/mechanism_subject_table.csv"));p.add_argument("--output-dir",type=Path,default=Path("results/bci2a_spatial_covariance_mechanism_audit"));a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    prior={int(r["subject"]):r for r in read(a.mechanism_table)};rows=[]
    for subject in SUBJECTS:
        indices=frozen_subset(a.primary_root,subject);data=load_bci2a_subject(subject,"data/moabb",8.,32.,0.,4.)
        values=covariance_geometry(log_covariance_trials(data.x_train[indices]),data.y_train[indices])
        row={"subject":subject,"residual_gap_pp":float(prior[subject]["residual_gap_pp"]),"post_weight_decay_residual_gap_pp":float(prior[subject]["post_control_residual_gap_pp"]),"subset_trial_count":len(indices),"subset_class_counts":json.dumps([int((data.y_train[indices]==c).sum()) for c in range(4)])}
        for feature in FEATURES:row[feature]=values[feature]
        row["cov_within_per_class"]=json.dumps(values["cov_within_per_class"]);rows.append(row)
    result=analyze(rows);write(a.output_dir/"spatial_covariance_subjects.csv",rows);write(a.output_dir/"spatial_covariance_associations.csv",result["associations"],("loso_values",))
    loso=[{"feature_name":r["feature_name"],"excluded_subject":s,"spearman_rho":r["loso_values"][s-1]} for r in result["associations"] for s in SUBJECTS];write(a.output_dir/"spatial_covariance_loso.csv",loso)
    (a.output_dir/"spatial_covariance_audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    for f in FEATURES:plot(a.output_dir/f"residual_vs_{f}.png",f,rows)
    lines=["# Spatial Covariance Mechanism Audit","",f"Integrity pass: `{result['integrity_pass']}`","","| Feature | Spearman | Kendall | LOSO min | LOSO median | LOSO max | Stable | Classification |","|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in result["associations"]:lines.append(f"| {r['feature_name']} | {r['spearman_rho']:.3f} | {r['kendall_tau']:.3f} | {r['loso_min_spearman_rho']:.3f} | {r['loso_median_spearman_rho']:.3f} | {r['loso_max_spearman_rho']:.3f} | {r['direction_stability_count']}/9 | {r['classification']} |")
    robust=[r for r in result["associations"] if r["classification"]=="ROBUST_CANDIDATE_SIGNAL"]
    conclusion="At least one covariance property is a robust candidate requiring targeted intervention, not NAP." if robust else "No robust covariance-property signal was identified; stop the current mechanism-driven architecture search."
    lines += ["","## Interpretation","",conclusion,"","Spatial covariance is incomplete: phase coupling, fine temporal dynamics, transients, and nonlinear interactions remain unrepresented. Correlation cannot establish causality."]
    (a.output_dir/"spatial_covariance_audit.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"Integrity pass: {result['integrity_pass']}")
    for r in result["associations"]:print(f"{r['feature_name']}: {r['classification']} (rho={r['spearman_rho']:.3f})")
if __name__=="__main__":main()
