"""Run frozen EEGNet EOG-coupled component dependency audit."""

from __future__ import annotations
import argparse, csv, json
from pathlib import Path
import numpy as np
import torch, yaml
from torch.utils.data import DataLoader, TensorDataset
from src.data import load_bci2a_coupling_subject
from src.eog_dependency_audit import *
from src.evaluate import evaluate_classifier_detailed
from src.train import build_model

FIELDS = ["subject","seed","window","alpha","condition","accuracy","balanced_accuracy","macro_f1","per_class_recall","confusion_matrix","clean_accuracy","delta","dependency_contrast","eeg_rms","component_rms","component_eeg_rms_ratio","matching_relative_error","checkpoint"]

def evaluate(model, x, y, device, batch_size):
    return evaluate_classifier_detailed(model, DataLoader(TensorDataset(torch.from_numpy(x).float(), torch.from_numpy(y).long()), batch_size=batch_size), device, 4)

def main():
    p=argparse.ArgumentParser(); p.add_argument("--baseline-root",type=Path,default=Path("results/bci2a_eegnet_multiseed")); p.add_argument("--output-root",type=Path,default=Path("results/bci2a_eog_dependency_audit")); p.add_argument("--data-dir",type=Path,default=Path("data/moabb")); p.add_argument("--subjects",nargs="+",type=int,default=list(range(1,10))); p.add_argument("--seeds",nargs="+",type=int,default=[42,43,44]); p.add_argument("--device",default="cuda" if torch.cuda.is_available() else "cpu"); args=p.parse_args()
    rows=[]; integrity=[]; args.output_root.mkdir(parents=True,exist_ok=True); device=torch.device(args.device)
    for subject in args.subjects:
        data=load_bci2a_coupling_subject(subject,args.data_dir)
        for seed in args.seeds:
            run=args.baseline_root/f"seed_{seed}"/f"subject_{subject:02d}"
            config=yaml.safe_load((run/"resolved_config.yaml").read_text(encoding="utf-8")); split=json.loads((run/"split_indices.json").read_text(encoding="utf-8")); summary=json.loads((run/"run_summary.json").read_text(encoding="utf-8"))
            train_idx=validate_split(split,len(data.eeg_train),len(data.eeg_test)); eeg_mean,eeg_std=verify_normalization(data.eeg_train,train_idx,summary["normalization"])
            clean=((data.eeg_test-eeg_mean)/eeg_std).astype(np.float32); _,slopes,eog_mean,eog_std=fit_mapping(data.eeg_train,data.eog_train,train_idx,eeg_mean,eeg_std)
            model=build_model(config).to(device); checkpoint=run/"best_validation_checkpoint.pt"; state=torch.load(checkpoint,map_location=device,weights_only=True); model.load_state_dict(state["model_state_dict"])
            clean_metrics=evaluate(model,clean,data.y_test,device,config["training"]["batch_size"]); recorded=float(summary["final_test_metrics"]["accuracy"]); error=abs(clean_metrics["accuracy"]-recorded)
            integrity.append({"subject":subject,"seed":seed,"recorded_accuracy":recorded,"recomputed_accuracy":clean_metrics["accuracy"],"absolute_error":error,"passed":error<1e-12})
            if error>=1e-12: raise RuntimeError(f"Clean checkpoint reproduction failed for A{subject:02d} seed {seed}: {error}")
            true_component=predict_component(data.eog_test,slopes,eog_mean,eog_std)
            mapping=make_test_control_mapping(data.y_test,20260718+subject*100+seed); raw_control=predict_component(data.eog_test[mapping],slopes,eog_mean,eog_std)
            q=orthogonal_rotation(22,20260718+subject*100+seed); rotated=rotate_channels(true_component,q)
            for window in WINDOWS:
                selected=window_slice(window,data.sampling_rate,clean.shape[2]); control=energy_match(true_component,raw_control,selected)
                true_mag=component_magnitude(clean,true_component,selected); control_mag=component_magnitude(clean,control,selected); rotated_mag=component_magnitude(clean,rotated,selected)
                match_err=abs(true_mag["component_rms"]-control_mag["component_rms"])/max(true_mag["component_rms"],1e-12)
                if match_err>1e-10: raise RuntimeError("Matched control RMS check failed.")
                for alpha in ALPHAS:
                    conditions={"clean":(clean,clean_metrics,{"eeg_rms":true_mag["eeg_rms"],"component_rms":0.0,"component_eeg_rms_ratio":0.0}),"true_coupled_removal":(remove_component(clean,true_component,window,alpha,data.sampling_rate),None,true_mag),"matched_cross_trial_removal":(remove_component(clean,control,window,alpha,data.sampling_rate),None,control_mag),"rotated_component_removal":(remove_component(clean,rotated,window,alpha,data.sampling_rate),None,rotated_mag)}
                    measured={};
                    for name,(x,metric,mag) in conditions.items(): measured[name]=metric or evaluate(model,x,data.y_test,device,config["training"]["batch_size"])
                    contrast=paired_effect(clean_metrics["accuracy"],measured["true_coupled_removal"]["accuracy"],measured["matched_cross_trial_removal"]["accuracy"])
                    for name,(_,__,mag) in conditions.items():
                        metric=measured[name]; delta=metric["accuracy"]-clean_metrics["accuracy"]
                        rows.append({"subject":subject,"seed":seed,"window":window,"alpha":alpha,"condition":name,"accuracy":metric["accuracy"],"balanced_accuracy":metric["balanced_accuracy"],"macro_f1":metric["macro_f1"],"per_class_recall":json.dumps(metric["per_class_recall"]),"confusion_matrix":json.dumps(metric["confusion_matrix"]),"clean_accuracy":clean_metrics["accuracy"],"delta":delta,"dependency_contrast":contrast["dependency_contrast"] if name=="true_coupled_removal" else "","eeg_rms":mag["eeg_rms"],"component_rms":alpha*mag["component_rms"],"component_eeg_rms_ratio":alpha*mag["component_eeg_rms_ratio"],"matching_relative_error":match_err if name=="matched_cross_trial_removal" else "","checkpoint":str(checkpoint)})
            print(f"Completed A{subject:02d} seed {seed}")
    for filename,data_rows in [("dependency_results.csv",rows),("checkpoint_integrity.csv",integrity)]:
        with (args.output_root/filename).open("w",newline="",encoding="utf-8") as f: w=csv.DictWriter(f,fieldnames=list(data_rows[0])); w.writeheader(); w.writerows(data_rows)

if __name__=="__main__": main()
