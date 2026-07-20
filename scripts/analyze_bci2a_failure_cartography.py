"""Descriptive aggregation for completed Failure Cartography outputs."""
import argparse,csv,json,statistics
from collections import defaultdict
from pathlib import Path
from scipy.stats import spearmanr

def read(path):
 with path.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def write(path,rows):
 if not rows:return
 with path.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def summarize(rows,group_fields,value_fields):
 groups=defaultdict(list)
 for row in rows:groups[tuple(row[f] for f in group_fields)].append(row)
 out=[]
 for key,cells in sorted(groups.items()):
  item=dict(zip(group_fields,key));item["n_cells"]=len(cells)
  for field in value_fields:
   values=[float(c[field]) for c in cells]
   mean=statistics.mean(values)
   item.update({f"{field}_mean":mean,f"{field}_std":statistics.stdev(values) if len(values)>1 else 0.,f"{field}_min":min(values),f"{field}_max":max(values),f"{field}_range":max(values)-min(values),f"{field}_max_abs_deviation_from_mean":max(abs(v-mean) for v in values)})
  out.append(item)
 return out
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--input-root",type=Path,default=Path("results/bci2a_failure_cartography"));a=p.parse_args();runs=read(a.input_root/"cartography_runs.csv");shifts=read(a.input_root/"layer_shifts.csv");validity=read(a.input_root/"representation_validity.csv")
 metrics=["validation_accuracy","evaluation_accuracy","session_generalization_gap","evaluation_ece","evaluation_aurc"]
 budget=summarize(runs,["budget"],metrics);subject=summarize(runs,["subject","budget"],metrics);write(a.input_root/"budget_summary.csv",budget);write(a.input_root/"subject_budget_summary.csv",subject)
 grouped=defaultdict(list)
 for r in shifts:grouped[(r["subject"],r["budget"],r["layer_name"],r["shift_metric"])].append(r)
 aggregate=[]
 for key,cells in grouped.items():aggregate.append({"subject":key[0],"budget":key[1],"layer_name":key[2],"shift_metric":key[3],"mean_shift_value":statistics.mean(float(c["shift_value"]) for c in cells),"mean_session_generalization_gap":statistics.mean(float(c["session_generalization_gap"]) for c in cells)})
 correlations=[]
 for layer in sorted({r["layer_name"] for r in aggregate}):
  for metric in sorted({r["shift_metric"] for r in aggregate}):
   cells=[r for r in aggregate if r["layer_name"]==layer and r["shift_metric"]==metric]
   rho,p=spearmanr([r["mean_shift_value"] for r in cells],[r["mean_session_generalization_gap"] for r in cells]) if len(cells)>2 else (float("nan"),float("nan"))
   correlations.append({"layer_name":layer,"shift_metric":metric,"n_subject_budget_units":len(cells),"spearman_rho":rho,"p_value_descriptive":p})
 write(a.input_root/"layer_shift_aggregates.csv",aggregate);write(a.input_root/"shift_gap_associations.csv",correlations)
 metric_validity=[]
 for layer in sorted({r["layer_name"] for r in shifts}):
  for metric in sorted({r["shift_metric"] for r in shifts}):
   values=[float(r["shift_value"]) for r in shifts if r["layer_name"]==layer and r["shift_metric"]==metric]
   metric_validity.append({"layer_name":layer,"shift_metric":metric,"n_cells":len(values),"all_finite":all(__import__('math').isfinite(v) for v in values),"minimum":min(values),"maximum":max(values),"sample_std":statistics.stdev(values) if len(values)>1 else 0.,"exactly_constant":max(values)==min(values)})
 write(a.input_root/"metric_validity.csv",metric_validity)
 embedding_valid=all(r["all_finite"]=="True" and float(r["feature_value_std"])>0 for r in validity)
 enough_cells=all(r["n_cells"]>1 for r in metric_validity)
 metric_valid=enough_cells and all(r["all_finite"] and not r["exactly_constant"] for r in metric_validity)
 validity_state="PASS" if embedding_valid and metric_valid else ("INSUFFICIENT_CELLS" if embedding_valid and not enough_cells else "FAIL")
 note={"outcome_classification":"NOT_RUN_OR_NOT_PREREGISTERED","measurement_validity_state":validity_state,"reason":"Scientific outcome classification remains separate; any measurement invalidity requires STOP and controlled protocol amendment."}
 (a.input_root/"analysis_status.json").write_text(json.dumps(note,indent=2),encoding="utf-8")
if __name__=="__main__":main()
