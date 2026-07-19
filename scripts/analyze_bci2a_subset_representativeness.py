"""Run the frozen zero-training subset representativeness audit."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

from src.data import load_bci2a_subject
from src.mechanism_audit import log_bandpower_features
from src.subset_representativeness import (FEATURES, SUBJECTS, analyze,
    nonstationarity_diagnostics, reconstruct_partition,
    representativeness_features, shared_normalize)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f: return list(csv.DictReader(f))


def write_csv(path, rows, excluded=()):
    clean=[{k:v for k,v in r.items() if k not in excluded} for r in rows]
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(clean[0]));w.writeheader();w.writerows(clean)


def plot(path, feature, rows):
    fig,ax=plt.subplots(figsize=(6,4.5));x=[r[feature] for r in rows];y=[r["residual_gap_pp"] for r in rows]
    ax.scatter(x,y)
    for r in rows:ax.annotate(f"A{r['subject']:02d}",(r[feature],r["residual_gap_pp"]),xytext=(4,4),textcoords="offset points")
    ax.set_xlabel(feature);ax.set_ylabel("Residual gap (percentage points)");ax.grid(alpha=.25)
    fig.tight_layout();fig.savefig(path,dpi=160);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary-root",type=Path,default=Path("results/bci2a_small_sample_audit"))
    p.add_argument("--mechanism-table",type=Path,default=Path("results/bci2a_small_sample_mechanism_audit/mechanism_subject_table.csv"))
    p.add_argument("--output-dir",type=Path,default=Path("results/bci2a_subset_representativeness_audit"))
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    prior={int(r["subject"]):r for r in read_csv(a.mechanism_table)};rows=[]
    for subject in SUBJECTS:
        partition=reconstruct_partition(a.primary_root,subject)
        data=load_bci2a_subject(subject_id=subject,data_dir="data/moabb",fmin=8.,fmax=32.,tmin=0.,tmax=4.)
        pool,subset,remainder=map(partition.get,("training_pool_indices","subset_indices","remainder_indices"))
        raw=log_bandpower_features(data.x_train[pool],data.sampling_rate)
        position={index:i for i,index in enumerate(pool)}
        sub_raw=raw[[position[i] for i in subset]];rem_raw=raw[[position[i] for i in remainder]]
        sub,rem=shared_normalize(raw,sub_raw,rem_raw)
        sub_labels=data.y_train[subset];rem_labels=data.y_train[remainder]
        values=representativeness_features(sub,sub_labels,rem,rem_labels)
        confounds=nonstationarity_diagnostics(partition,data.y_train,data.train_metadata)
        row={"subject":subject,"residual_gap_pp":float(prior[subject]["residual_gap_pp"]),
             "post_weight_decay_residual_gap_pp":float(prior[subject]["post_control_residual_gap_pp"]),
             "subset_trial_count":len(subset),"remainder_trial_count":len(remainder),
             "subset_class_counts":json.dumps([int((sub_labels==c).sum()) for c in range(4)]),
             "remainder_class_counts":json.dumps([int((rem_labels==c).sum()) for c in range(4)])}
        for name in FEATURES:row[name]=values[name]
        for key in ("centroid_shift_per_class","covariance_shift_per_class","coverage_distance_per_class"):
            row[key]=json.dumps(values[key])
        for key,value in confounds.items():
            row[key]=json.dumps(value) if isinstance(value,list) else value
        rows.append(row)
    result=analyze(rows)
    write_csv(a.output_dir/"subset_representativeness_subjects.csv",rows)
    write_csv(a.output_dir/"subset_representativeness_associations.csv",result["associations"],("loso_values",))
    loso=[{"feature_name":r["feature_name"],"excluded_subject":s,"spearman_rho":r["loso_values"][s-1]}
          for r in result["associations"] for s in SUBJECTS]
    write_csv(a.output_dir/"subset_representativeness_loso.csv",loso)
    (a.output_dir/"subset_representativeness.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    for feature in FEATURES:plot(a.output_dir/f"residual_vs_{feature}.png",feature,rows)
    lines=["# Subset Representativeness Audit","",f"Integrity pass: `{result['integrity_pass']}`","",
           "| Feature | Spearman | Kendall | LOSO min | LOSO median | LOSO max | Stable | Classification |",
           "|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in result["associations"]:lines.append(f"| {r['feature_name']} | {r['spearman_rho']:.3f} | {r['kendall_tau']:.3f} | {r['loso_min_spearman_rho']:.3f} | {r['loso_median_spearman_rho']:.3f} | {r['loso_max_spearman_rho']:.3f} | {r['direction_stability_count']}/9 | {r['classification']} |")
    robust=[r["feature_name"] for r in result["associations"] if r["classification"]=="ROBUST_CANDIDATE_SIGNAL"]
    imbalance=any(r["obvious_nonstationarity_imbalance"] for r in rows)
    if robust and imbalance:
        conclusion="REPRESENTATIVENESS_SIGNAL_WITH_NONSTATIONARITY_CONFOUND: a robust association exists, but available run/order diagnostics show substantial imbalance."
    elif robust:
        conclusion="A stable training-data-only association exists and is not obviously explained by available run/order provenance; causality remains unestablished."
    else:
        conclusion="The preregistered subset-representativeness audit did not identify a robust training-data-only signal capable of explaining the persistent small-sample residual failure."
    lines += ["","## Skeptical Interpretation","",
              "1. **Representation assumption.** The strongest unverified assumption is that fixed log-bandpower geometry adequately captures relevant representativeness. EEGNet may use spatial, phase, temporal, transient, or nonlinear structure absent here.",
              "2. **Falsification rule.** The hypothesis is unsupported here when none of the four frozen features passes the unchanged robust-signal and LOSO gate; no pairwise subject rescue is permitted.",
              "3. **Simpler explanation.** Run imbalance or recording nonstationarity may explain measurable subset/remainder differences. Run, chronological-position, and class-by-run diagnostics are reported descriptively and are not candidate features.",
              f"4. **Strongest permitted conclusion.** {conclusion}","",
              "The audit distinguishes measurable subset difference, association with residual failure, and causation. It can support only the second; only intervention can approach the third."]
    (a.output_dir/"subset_representativeness.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"Integrity pass: {result['integrity_pass']}")
    for r in result["associations"]:print(f"{r['feature_name']}: {r['classification']} (rho={r['spearman_rho']:.3f})")


if __name__=="__main__":main()
