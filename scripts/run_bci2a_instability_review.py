"""Execute the frozen zero-training EEGNet instability/reliability review."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch

from src.failure_cartography import ActivationCapture
from src.instability_measurement import (
    centered_linear_cka,
    deterministic_domain_subsamples,
    representation_degeneracy_diagnostics,
)
from src.instability_review import (
    BN_MODULES,
    LEARNED_STAGES,
    SEED_PAIRS,
    TRAINING_SEEDS,
    batchnorm_vector_diagnostics,
    classwise_diagnostics,
    correctness_stability,
    descriptive_summary,
    efficient_representation_shift,
    prediction_pair_diagnostics,
    stable_identity_hash,
)
from src.train import build_dataloaders, build_model, load_config


BUDGET_DIRS = {1.0: "budget_100", 0.5: "budget_050", 0.25: "budget_025"}
SESSIONS = ("validation", "official_evaluation")
STAGES = ("model_input", *LEARNED_STAGES)
FRACTIONS = (0.50, 0.75, 1.00)
REPEAT_SEEDS = tuple(range(20260721, 20260741))
SHIFT_METRICS = (
    "coral_distance",
    "rbf_mmd2",
    "feature_mean_shift",
    "feature_variance_shift",
    "covariance_difference",
)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to create empty output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    if any(set(row) != set(fields) for row in rows):
        raise RuntimeError(f"inconsistent output schema: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def cell_dir(root: Path, subject: int, budget: float, seed: int) -> Path:
    return root / BUDGET_DIRS[budget] / f"seed_{seed}" / f"subject_{subject:02d}"


def extract(model, loader, device) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    model.eval(); capture = ActivationCapture(model); logits, targets = [], []
    try:
        with torch.no_grad():
            for x, y in loader:
                capture.record_input(x)
                logits.append(model(x.to(device)).cpu())
                targets.append(y.cpu())
        return torch.cat(logits).numpy(), torch.cat(targets).numpy(), capture.arrays()
    finally:
        capture.close()


def same_provenance(payloads: dict[int, dict], key_path: tuple[str, ...]) -> bool:
    values = []
    for payload in payloads.values():
        value = payload
        for key in key_path: value = value[key]
        values.append(value)
    return all(value == values[0] for value in values[1:])


def group_summaries(rows: list[dict], field: str, prefix: str) -> None:
    summary = descriptive_summary([row[field] for row in rows], prefix)
    for row in rows: row.update(summary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("results/bci2a_small_sample_audit"))
    parser.add_argument("--output-root", type=Path, default=Path("results/bci2a_instability_reliability_review"))
    parser.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 10)))
    parser.add_argument("--budgets", type=float, nargs="+", default=[1.0, 0.5, 0.25])
    parser.add_argument("--confirm-full-matrix", action="store_true")
    args = parser.parse_args()
    if any(subject not in range(1, 10) for subject in args.subjects):
        raise ValueError("subjects must be between 1 and 9")
    if any(budget not in BUDGET_DIRS for budget in args.budgets):
        raise ValueError("budgets must be 1.0, 0.5, or 0.25")
    if len(set(args.subjects)) * len(set(args.budgets)) == 27 and not args.confirm_full_matrix:
        raise RuntimeError("the frozen 81-checkpoint review requires --confirm-full-matrix")
    args.output_root.mkdir(parents=True, exist_ok=True)
    device = torch.device("cpu")

    prediction_rows=[]; correctness_rows=[]; error_rows=[]; class_rows=[]
    probability_rows=[]; history_rows=[]; bn_rows=[]; cka_rows=[]; degeneracy_rows=[]
    reliability_rows=[]; pipeline_issues=[]; checkpoint_count=0
    preprocessing_signatures=set(); matched_groups=0

    for subject in args.subjects:
      for budget in args.budgets:
        paths={seed:cell_dir(args.source_root,subject,budget,seed) for seed in TRAINING_SEEDS}
        configs={seed:load_config(str(paths[seed]/"resolved_config.yaml")) for seed in TRAINING_SEEDS}
        splits={seed:json.loads((paths[seed]/"split_indices.json").read_text(encoding="utf-8")) for seed in TRAINING_SEEDS}
        summaries={seed:json.loads((paths[seed]/"run_summary.json").read_text(encoding="utf-8")) for seed in TRAINING_SEEDS}
        for seed,config in configs.items():
            signature=(config["data"]["fmin"],config["data"]["fmax"],config["data"]["tmin"],config["data"]["tmax"],config["data"]["normalize"],config["data"]["split_seed"],config["small_sample"]["subset_seed"])
            preprocessing_signatures.add(signature)
            if config["data"]["subject_id"]!=subject or config["seed"]!=seed or float(config["small_sample"]["budget"])!=budget:
                pipeline_issues.append(f"config identity mismatch A{subject:02d} budget={budget} seed={seed}")
        for key_path in (("validation_indices",),("test_indices",),("small_sample","selected_training_indices")):
            if not same_provenance(splits,key_path): pipeline_issues.append(f"seed provenance mismatch A{subject:02d} budget={budget} {key_path}")
        normalizations=[summaries[s]["normalization"] for s in TRAINING_SEEDS]
        if any(n.get("source")!="train_subset" for n in normalizations):pipeline_issues.append(f"normalization source mismatch A{subject:02d} budget={budget}")
        if any(n!=normalizations[0] for n in normalizations[1:]):pipeline_issues.append(f"normalization differs across seeds A{subject:02d} budget={budget}")

        bundle=build_dataloaders(configs[42])
        expected_train=splits[42]["small_sample"]["selected_training_indices"]
        if bundle.train_indices!=expected_train or bundle.val_indices!=splits[42]["validation_indices"] or bundle.test_indices!=splits[42]["test_indices"]:
            pipeline_issues.append(f"reconstructed split mismatch A{subject:02d} budget={budget}")
        if bundle.normalization!=normalizations[0]:pipeline_issues.append(f"reconstructed normalization mismatch A{subject:02d} budget={budget}")
        identities={"validation":list(bundle.val_indices),"official_evaluation":list(bundle.test_indices)}
        identity_hashes={session:stable_identity_hash(session,values) for session,values in identities.items()}

        outputs={}
        for seed in TRAINING_SEEDS:
            checkpoint=torch.load(paths[seed]/"best_validation_checkpoint.pt",map_location=device,weights_only=True)
            model=build_model(configs[seed]).to(device);model.load_state_dict(checkpoint["model_state_dict"],strict=True);model.eval()
            val_logits,val_targets,val_rep=extract(model,bundle.val_loader,device)
            eval_logits,eval_targets,eval_rep=extract(model,bundle.test_loader,device)
            outputs[seed]={"checkpoint":checkpoint,"validation":(val_logits,val_targets,val_rep),"official_evaluation":(eval_logits,eval_targets,eval_rep)}
            checkpoint_count+=1
        for session in SESSIONS:
            targets=[outputs[s][session][1] for s in TRAINING_SEEDS]
            if not all(np.array_equal(targets[0],value) for value in targets[1:]):
                raise RuntimeError(f"target order mismatch A{subject:02d} budget={budget} {session}")
            target=targets[0]; matched_groups+=1
            pair_prediction=[];pair_error=[];pair_probability=[]
            for seed_a,seed_b in SEED_PAIRS:
                diagnostic=prediction_pair_diagnostics(outputs[seed_a][session][0],outputs[seed_b][session][0],target)
                common={"subject":subject,"budget":budget,"session":session,"seed_a":seed_a,"seed_b":seed_b,"sample_count":len(target),"trial_identity_hash":identity_hashes[session]}
                prow={**common,"agreement_rate":diagnostic["agreement_rate"],"disagreement_rate":diagnostic["disagreement_rate"],"prediction_cohen_kappa":diagnostic["prediction_cohen_kappa"]};pair_prediction.append(prow)
                erow={**common,"error_count_a":diagnostic["error_count_a"],"error_count_b":diagnostic["error_count_b"],"intersection_count":diagnostic["error_intersection_count"],"union_count":diagnostic["error_union_count"],"error_jaccard":diagnostic["error_jaccard"]};pair_error.append(erow)
                qrow={**common,**descriptive_summary(diagnostic["absolute_predicted_confidence_difference"],"confidence_abs_difference"),**descriptive_summary(diagnostic["absolute_logit_margin_difference"],"logit_margin_abs_difference"),**descriptive_summary(diagnostic["js_divergence"],"js_divergence")};pair_probability.append(qrow)
            for field in ("agreement_rate","disagreement_rate","prediction_cohen_kappa"):group_summaries(pair_prediction,field,f"pairwise_{field}")
            group_summaries(pair_error,"error_jaccard","pairwise_error_jaccard")
            for field in ("confidence_abs_difference_mean","logit_margin_abs_difference_mean","js_divergence_mean"):group_summaries(pair_probability,field,f"pairwise_{field}")
            prediction_rows.extend(pair_prediction);error_rows.extend(pair_error);probability_rows.extend(pair_probability)

            prediction_matrix=np.stack([outputs[s][session][0].argmax(1) for s in TRAINING_SEEDS])
            correctness_rows.append({"subject":subject,"budget":budget,"session":session,"trial_identity_hash":identity_hashes[session],**correctness_stability(prediction_matrix,target)})
            per_seed_classes={s:classwise_diagnostics(outputs[s][session][0],target) for s in TRAINING_SEEDS}
            for class_id in range(4):
                recalls=[per_seed_classes[s][class_id]["recall"] for s in TRAINING_SEEDS];precisions=[per_seed_classes[s][class_id]["precision"] for s in TRAINING_SEEDS]
                rs=descriptive_summary(recalls,"seed_recall");ps=descriptive_summary(precisions,"seed_precision")
                for seed in TRAINING_SEEDS:class_rows.append({"subject":subject,"budget":budget,"session":session,"training_seed":seed,"class_id":class_id,"trial_identity_hash":identity_hashes[session],**per_seed_classes[seed][class_id],**rs,**ps})

            for stage in STAGES:
                pair_stage=[]
                for seed_a,seed_b in SEED_PAIRS:
                    value=centered_linear_cka(outputs[seed_a][session][2][stage],outputs[seed_b][session][2][stage])
                    pair_stage.append({"subject":subject,"budget":budget,"session":session,"stage":stage,"evidence_role":"integrity_control_only" if stage=="model_input" else "learned_representation","seed_a":seed_a,"seed_b":seed_b,"sample_count":len(target),"trial_identity_hash":identity_hashes[session],"cka":value})
                group_summaries(pair_stage,"cka","within_layer_pairwise_cka");cka_rows.extend(pair_stage)
                for seed in TRAINING_SEEDS:
                    degeneracy_rows.append({"subject":subject,"budget":budget,"session":session,"stage":stage,"training_seed":seed,"trial_identity_hash":identity_hashes[session],**representation_degeneracy_diagnostics(outputs[seed][session][2][stage])})

        for seed_a,seed_b in SEED_PAIRS:
            state_a=outputs[seed_a]["checkpoint"]["model_state_dict"];state_b=outputs[seed_b]["checkpoint"]["model_state_dict"]
            for module in BN_MODULES:
                for state_name in ("running_mean","running_var"):
                    key=f"{module}.{state_name}"
                    bn_rows.append({"subject":subject,"budget":budget,"seed_a":seed_a,"seed_b":seed_b,"batchnorm_module":module,"state_name":state_name,**batchnorm_vector_diagnostics(state_a[key].cpu().numpy(),state_b[key].cpu().numpy())})

        history_by_seed={}
        for seed in TRAINING_SEEDS:
            with (paths[seed]/"metrics.csv").open(encoding="utf-8",newline="") as handle:history_by_seed[seed]=list(csv.DictReader(handle))
        if any(len(history_by_seed[s])!=50 for s in TRAINING_SEEDS):pipeline_issues.append(f"history length mismatch A{subject:02d} budget={budget}")
        for epoch in range(1,51):
            records={s:history_by_seed[s][epoch-1] for s in TRAINING_SEEDS}
            summaries_by_field={field:descriptive_summary([float(records[s][field]) for s in TRAINING_SEEDS],f"seed_{field}") for field in ("train_loss","train_accuracy","val_loss","val_accuracy")}
            for seed in TRAINING_SEEDS:
                checkpoint=outputs[seed]["checkpoint"]
                history_rows.append({"subject":subject,"budget":budget,"training_seed":seed,"epoch":epoch,"train_loss":float(records[seed]["train_loss"]),"train_accuracy":float(records[seed]["train_accuracy"]),"val_loss":float(records[seed]["val_loss"]),"val_accuracy":float(records[seed]["val_accuracy"]),"best_validation_epoch":int(checkpoint["epoch"]),"best_validation_accuracy":float(checkpoint["best_validation_metrics"]["accuracy"]),"best_validation_loss":float(checkpoint["best_validation_metrics"]["loss"]),**{k:v for summary in summaries_by_field.values() for k,v in summary.items()}})

        for seed in TRAINING_SEEDS:
            val_rep=outputs[seed]["validation"][2];eval_rep=outputs[seed]["official_evaluation"][2]
            for stage in STAGES:
                full=efficient_representation_shift(val_rep[stage],eval_rep[stage])
                for fraction in FRACTIONS:
                    values={metric:[] for metric in SHIFT_METRICS}
                    if fraction==1.0:
                        for metric in SHIFT_METRICS:values[metric]=[full[metric]]*len(REPEAT_SEEDS)
                    else:
                        for repeat_seed in REPEAT_SEEDS:
                            vi,ei=deterministic_domain_subsamples(len(val_rep[stage]),len(eval_rep[stage]),fraction,repeat_seed)
                            estimate=efficient_representation_shift(val_rep[stage][vi],eval_rep[stage][ei])
                            for metric in SHIFT_METRICS:values[metric].append(estimate[metric])
                    for metric in SHIFT_METRICS:
                        deviations=[abs(v-full[metric])/max(abs(full[metric]),1e-12) for v in values[metric]]
                        reliability_rows.append({"subject":subject,"budget":budget,"training_seed":seed,"stage":stage,"shift_metric":metric,"fraction":fraction,"repeat_count":len(values[metric]),"validation_sample_count":min(len(val_rep[stage]),max(2,int(np.floor(len(val_rep[stage])*fraction)))),"evaluation_sample_count":min(len(eval_rep[stage]),max(2,int(np.floor(len(eval_rep[stage])*fraction)))),"full_estimate":full[metric],**descriptive_summary(values[metric],"estimate"),**descriptive_summary(deviations,"absolute_relative_deviation_from_full")})
        print(f"Completed zero-training review A{subject:02d} budget={budget:g}",flush=True)

    outputs={
      "prediction_agreement.csv":prediction_rows,"correctness_stability.csv":correctness_rows,
      "error_set_overlap.csv":error_rows,"classwise_stability.csv":class_rows,
      "probability_logit_stability.csv":probability_rows,"training_history_stability.csv":history_rows,
      "batchnorm_stability.csv":bn_rows,"representation_cka.csv":cka_rows,
      "representation_diagnostics.csv":degeneracy_rows,"measurement_reliability.csv":reliability_rows,
    }
    for name,rows in outputs.items():write_csv(args.output_root/name,rows)
    pipeline={"classification":"NO_SYSTEMATIC_PIPELINE_ISSUE_FOUND" if not pipeline_issues else "POTENTIAL_SYSTEMATIC_CONFOUNDER","checkpoint_count":checkpoint_count,"matched_session_groups":matched_groups,"preprocessing_signatures":[list(v) for v in sorted(preprocessing_signatures)],"split_seed":42,"subset_seed":20260719,"normalization_source":"train_subset","official_evaluation_policy":"post_hoc_only_no_adaptation","issues":pipeline_issues}
    (args.output_root/"pipeline_integrity_review.json").write_text(json.dumps(pipeline,indent=2),encoding="utf-8")
    status={"experiment_status":"COMPLETED_DIAGNOSTICS_INTERPRETATION_PENDING","checkpoint_count":checkpoint_count,"scientific_classification":"PENDING_CONSERVATIVE_EVIDENCE_SYNTHESIS","architecture_stop_rule":"ACTIVE","no_training":True,"additional_training_seeds":False}
    (args.output_root/"analysis_status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
    print(json.dumps({"row_counts":{name:len(rows) for name,rows in outputs.items()},"pipeline":pipeline,"status":status},indent=2))


if __name__=="__main__":main()
