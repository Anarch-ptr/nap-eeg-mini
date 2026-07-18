"""Run Phase 2B frozen spatial masking and noise audit."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import numpy as np,torch,yaml
from torch.utils.data import DataLoader,TensorDataset
from src.data import load_bci2a_subject
from src.eog_dependency_audit import validate_split,verify_normalization
from src.evaluate import evaluate_classifier_detailed
from src.spatial_artifact_audit import *
from src.train import build_model

def evaluate(model,x,y,device,batch): return evaluate_classifier_detailed(model,DataLoader(TensorDataset(torch.from_numpy(x).float(),torch.from_numpy(y).long()),batch_size=batch),device,4)
def main():
 p=argparse.ArgumentParser();p.add_argument("--baseline-root",type=Path,default=Path("results/bci2a_eegnet_multiseed"));p.add_argument("--output-root",type=Path,default=Path("results/bci2a_spatial_artifact_audit"));p.add_argument("--data-dir",type=Path,default=Path("data/moabb"));p.add_argument("--subjects",nargs="+",type=int,default=list(range(1,10)));p.add_argument("--seeds",nargs="+",type=int,default=[42,43,44]);p.add_argument("--device",default="cuda" if torch.cuda.is_available() else "cpu");a=p.parse_args();device=torch.device(a.device);rows=[];integrity=[];a.output_root.mkdir(parents=True,exist_ok=True)
 for subject in a.subjects:
  data=load_bci2a_subject(subject,a.data_dir);validate_channel_names(data.channel_names)
  for seed in a.seeds:
   run=a.baseline_root/f"seed_{seed}"/f"subject_{subject:02d}";config=yaml.safe_load((run/"resolved_config.yaml").read_text());split=json.loads((run/"split_indices.json").read_text());summary=json.loads((run/"run_summary.json").read_text());idx=validate_split(split,len(data.x_train),len(data.x_test));mean,std=verify_normalization(data.x_train,idx,summary["normalization"]);clean=((data.x_test-mean)/std).astype(np.float32);model=build_model(config).to(device);state=torch.load(run/"best_validation_checkpoint.pt",map_location=device,weights_only=True);model.load_state_dict(state["model_state_dict"]);cm=evaluate(model,clean,data.y_test,device,config["training"]["batch_size"]);recorded=float(summary["final_test_metrics"]["accuracy"]);error=abs(cm["accuracy"]-recorded);integrity.append({"subject":subject,"seed":seed,"recorded_accuracy":recorded,"recomputed_accuracy":cm["accuracy"],"absolute_error":error,"passed":error<1e-12});
   if error>=1e-12: raise RuntimeError(f"Clean reproduction failed A{subject:02d} seed {seed}")
   def add(family,condition,group,window,sigma,iseed,x):
    m=cm if condition=="clean" else evaluate(model,x,data.y_test,device,config["training"]["batch_size"]);pr,ratio=perturbation_stats(clean,x);rows.append({"subject":subject,"seed":seed,"intervention_family":family,"condition":condition,"channel_group":group,"channel_names":"|".join(group_names(group)) if group in CHANNEL_GROUPS else "|".join(CHANNEL_NAMES),"channel_indices":"|".join(map(str,CHANNEL_GROUPS[group])) if group in CHANNEL_GROUPS else "|".join(map(str,range(22))),"window":window,"sigma":"" if sigma is None else sigma,"intervention_seed":"" if iseed is None else iseed,"test_accuracy":m["accuracy"],"balanced_accuracy":m["balanced_accuracy"],"macro_f1":m["macro_f1"],"delta_accuracy":m["accuracy"]-cm["accuracy"],"delta_balanced_accuracy":m["balanced_accuracy"]-cm["balanced_accuracy"],"delta_macro_f1":m["macro_f1"]-cm["macro_f1"],"per_class_recall":json.dumps(m["per_class_recall"]),"confusion_matrix":json.dumps(m["confusion_matrix"]),"perturbation_rms":pr,"perturbation_eeg_rms_ratio":ratio})
   add("mask","clean","all","full",None,None,clean)
   for window in WINDOWS:
    for group,indices in CHANNEL_GROUPS.items():add("mask",f"{group}_mask",group,window,None,None,mask_channels(clean,indices,window,data.sampling_rate))
   for sigma in SIGMAS:
    iseed=GROUP_SEED+subject*10000+seed*10+int(sigma*100);noise=base_group_noise(clean.shape,sigma,iseed)
    for group,indices in CHANNEL_GROUPS.items():add("noise",f"{group}_noise",group,"full",sigma,iseed,inject_group_noise(clean,indices,noise))
    gx,_=inject_global_noise(clean,sigma,iseed+1);add("noise","global_noise","global","full",sigma,iseed+1,gx)
   print(f"Completed A{subject:02d} seed {seed}")
 for name,values in (("spatial_results.csv",rows),("checkpoint_integrity.csv",integrity)):
  with (a.output_root/name).open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(values[0]));w.writeheader();w.writerows(values)
 (a.output_root/"frozen_groups.json").write_text(json.dumps({"channel_names":CHANNEL_NAMES,"groups":{k:{"indices":v,"names":group_names(k)} for k,v in CHANNEL_GROUPS.items()},"random_seed":GROUP_SEED,"sigmas":SIGMAS,"windows":WINDOWS},indent=2),encoding="utf-8")
if __name__=="__main__":main()
