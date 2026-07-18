"""Aggregate Phase 2B with subjects as biological units."""
import argparse,csv,statistics
from collections import defaultdict
from pathlib import Path
from src.spatial_artifact_audit import random_summary
def write(p,r):
 with p.open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(r[0]));w.writeheader();w.writerows(r)
def main():
 p=argparse.ArgumentParser();p.add_argument("--results-root",type=Path,required=True);a=p.parse_args()
 with (a.results_root/"spatial_results.csv").open(encoding="utf-8") as f:rows=list(csv.DictReader(f))
 effects=[]
 for r in rows:
  if r["condition"]=="clean":continue
  effects.append({"subject":int(r["subject"]),"seed":int(r["seed"]),"family":r["intervention_family"],"group":r["channel_group"],"window":r["window"],"sigma":r["sigma"],"delta_accuracy":float(r["delta_accuracy"]),"delta_balanced_accuracy":float(r["delta_balanced_accuracy"]),"delta_macro_f1":float(r["delta_macro_f1"])})
 write(a.results_root/"spatial_seed_effects.csv",effects)
 groups=defaultdict(list)
 for r in effects:groups[(r["subject"],r["family"],r["group"],r["window"],r["sigma"])].append(r)
 subjects=[]
 for key,v in sorted(groups.items()):
  subjects.append(dict(zip(("subject","family","group","window","sigma"),key))|{f"mean_{m}":statistics.mean(x[m] for x in v) for m in ("delta_accuracy","delta_balanced_accuracy","delta_macro_f1")}|{"seed_sd_accuracy":statistics.stdev(x["delta_accuracy"] for x in v)})
 write(a.results_root/"spatial_subject_effects.csv",subjects)
 groups=defaultdict(list)
 for r in subjects:groups[(r["family"],r["group"],r["window"],r["sigma"])].append(r)
 cross=[]
 for key,v in sorted(groups.items()):
  vals=[x["mean_delta_accuracy"] for x in v];cross.append(dict(zip(("family","group","window","sigma"),key))|{"mean_delta_accuracy":statistics.mean(vals),"median_delta_accuracy":statistics.median(vals),"sd_delta_accuracy":statistics.stdev(vals),"subjects_negative":sum(x<0 for x in vals),"mean_delta_balanced_accuracy":statistics.mean(x["mean_delta_balanced_accuracy"] for x in v),"mean_delta_macro_f1":statistics.mean(x["mean_delta_macro_f1"] for x in v)})
 write(a.results_root/"spatial_cross_subject.csv",cross)
 by=defaultdict(dict)
 for r in subjects:
  if r["family"]=="mask" and r["window"]=="full":by[r["subject"]][r["group"]]=r["mean_delta_accuracy"]
 contrasts=[]
 for s,v in sorted(by.items()):
  rs=[v[f"random_0{i}"] for i in range(1,6)];contrasts.append({"subject":s,"delta_frontal":v["frontal"],"delta_matched":v["matched_nonfrontal"],"frontal_minus_matched":v["frontal"]-v["matched_nonfrontal"],**random_summary(v["frontal"],rs)})
 write(a.results_root/"masking_subject_contrasts.csv",contrasts)
if __name__=="__main__":main()
