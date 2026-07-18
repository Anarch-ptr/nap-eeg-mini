"""Aggregate Phase 2A paired effects with subject as biological unit."""
import argparse,csv,statistics
from collections import defaultdict
from pathlib import Path

def write(path,rows):
    with path.open("w",newline="",encoding="utf-8") as f: w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    p=argparse.ArgumentParser();p.add_argument("--results-root",type=Path,required=True);a=p.parse_args()
    with (a.results_root/"dependency_results.csv").open(encoding="utf-8") as f: rows=list(csv.DictReader(f))
    pivot=defaultdict(dict)
    for r in rows:pivot[(int(r["subject"]),int(r["seed"]),r["window"],float(r["alpha"]))][r["condition"]]=r
    seed_rows=[]
    for (s,seed,w,alpha),v in sorted(pivot.items()):
        c,t,k=[float(v[x]["accuracy"]) for x in ("clean","true_coupled_removal","matched_cross_trial_removal")]; dt=t-c;dc=k-c
        seed_rows.append({"subject":s,"seed":seed,"window":w,"alpha":alpha,"clean_accuracy":c,"true_removed_accuracy":t,"control_removed_accuracy":k,"delta_true":dt,"delta_control":dc,"dependency_contrast":dt-dc,"clean_balanced_accuracy":float(v["clean"]["balanced_accuracy"]),"true_balanced_accuracy":float(v["true_coupled_removal"]["balanced_accuracy"]),"control_balanced_accuracy":float(v["matched_cross_trial_removal"]["balanced_accuracy"]),"clean_macro_f1":float(v["clean"]["macro_f1"]),"true_macro_f1":float(v["true_coupled_removal"]["macro_f1"]),"control_macro_f1":float(v["matched_cross_trial_removal"]["macro_f1"])})
    write(a.results_root/"dependency_seed_effects.csv",seed_rows)
    groups=defaultdict(list)
    for r in seed_rows:groups[(r["subject"],r["window"],r["alpha"])].append(r)
    subjects=[]
    for (s,w,alpha),v in sorted(groups.items()):
        subjects.append({"subject":s,"window":w,"alpha":alpha,"mean_delta_true":statistics.mean(x["delta_true"] for x in v),"mean_delta_control":statistics.mean(x["delta_control"] for x in v),"mean_dependency_contrast":statistics.mean(x["dependency_contrast"] for x in v),"dependency_contrast_seed_sd":statistics.stdev(x["dependency_contrast"] for x in v)})
    write(a.results_root/"dependency_subject_effects.csv",subjects)
    groups=defaultdict(list)
    for r in subjects:groups[(r["window"],r["alpha"])].append(r["mean_dependency_contrast"])
    cross=[]
    for (w,alpha),v in sorted(groups.items()):cross.append({"window":w,"alpha":alpha,"mean":statistics.mean(v),"median":statistics.median(v),"sd":statistics.stdev(v),"min":min(v),"max":max(v),"subjects_negative":sum(x<0 for x in v),"subjects_positive":sum(x>0 for x in v)})
    write(a.results_root/"dependency_cross_subject.csv",cross)
if __name__=="__main__":main()
