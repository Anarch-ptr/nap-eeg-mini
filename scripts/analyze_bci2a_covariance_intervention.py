"""Apply the frozen Pair-Set-1 intervention analysis."""
import argparse,csv,json
from pathlib import Path
from src.covariance_separation_intervention import analyze_intervention,load_frozen_pairs
def read(path):
 with path.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def write(path,rows):
 if not rows:return
 with path.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--runs",type=Path,default=Path("results/bci2a_covariance_intervention/intervention_runs.csv"));p.add_argument("--feasibility",type=Path,default=Path("results/bci2a_covariance_intervention_feasibility/feasibility_audit.json"));p.add_argument("--primary",type=Path,default=Path("results/bci2a_small_sample_audit/small_sample_runs.csv"));p.add_argument("--output-dir",type=Path,default=Path("results/bci2a_covariance_intervention"));a=p.parse_args()
 result=analyze_intervention(read(a.runs),load_frozen_pairs(a.feasibility),read(a.primary));a.output_dir.mkdir(parents=True,exist_ok=True)
 write(a.output_dir/"intervention_subjects.csv",result["subject_results"]);write(a.output_dir/"intervention_seeds.csv",result["seed_diagnostics"])
 (a.output_dir/"intervention_analysis.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
 lines=["# Covariance-Separation Intervention","",f"Classification: **{result['classification']}**",f"Evidence label: **{result['evidence_label']}**",f"Integrity pass: `{result['integrity_pass']}`",f"Median HIGH-LOW effect: {result['median_intervention_effect_pp']:.3f} pp" if result['median_intervention_effect_pp'] is not None else "Median effect: unavailable","", "One frozen matched pair per subject was tested. This is not definitive causal proof; a stable directional result requires independently preregistered Pair Set 2 replication."]
 (a.output_dir/"intervention_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8");print(result["classification"])
if __name__=="__main__":main()
