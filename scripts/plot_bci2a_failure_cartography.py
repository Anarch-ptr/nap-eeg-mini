"""Generate preregistered descriptive Failure Cartography figures."""
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

def save(fig,path):fig.tight_layout();fig.savefig(path,dpi=180);plt.close(fig)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--input-root",type=Path,default=Path("results/bci2a_failure_cartography"));a=p.parse_args();out=a.input_root/"figures";out.mkdir(parents=True,exist_ok=True)
 runs=pd.read_csv(a.input_root/"cartography_runs.csv");shifts=pd.read_csv(a.input_root/"layer_shifts.csv")
 fig,ax=plt.subplots();runs.groupby("budget")[["validation_accuracy","evaluation_accuracy"]].mean().plot(marker="o",ax=ax);save(fig,out/"validation_vs_evaluation_accuracy_by_budget.png")
 fig,ax=plt.subplots();runs.groupby("budget")["session_generalization_gap"].mean().plot(marker="o",ax=ax);save(fig,out/"session_generalization_gap_by_budget.png")
 heat=runs.pivot_table(index="subject",columns="budget",values="session_generalization_gap",aggfunc="mean");fig,ax=plt.subplots();im=ax.imshow(heat);fig.colorbar(im,ax=ax);ax.set_xticks(range(len(heat.columns)),heat.columns);ax.set_yticks(range(len(heat.index)),heat.index);save(fig,out/"subject_failure_heatmap.png")
 fig,ax=plt.subplots();runs.groupby("budget")["evaluation_accuracy"].std().plot(marker="o",ax=ax);save(fig,out/"seed_variance_by_budget.png")
 fig,ax=plt.subplots();runs.groupby("budget")[["evaluation_ece","evaluation_aurc"]].mean().plot(marker="o",ax=ax);save(fig,out/"calibration_metrics_by_budget.png")
 coral=shifts[shifts.shift_metric=="coral_distance"];fig,ax=plt.subplots();coral.groupby("layer_name")["shift_value"].mean().plot(kind="bar",ax=ax);save(fig,out/"layerwise_representation_shift.png")
 fig,ax=plt.subplots();
 for name,group in coral.groupby("layer_name"):ax.scatter(group.shift_value,group.session_generalization_gap,label=name,alpha=.6)
 ax.legend(fontsize=7);ax.set_xlabel("CORAL distance");ax.set_ylabel("session generalization gap");save(fig,out/"layerwise_shift_vs_gap.png")
if __name__=="__main__":main()
