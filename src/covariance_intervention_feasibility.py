"""Frozen zero-training covariance intervention feasibility audit."""

from __future__ import annotations

import itertools
import json

import numpy as np

from src.spatial_covariance_mechanism import covariance_geometry


N_CANDIDATES = 512
CANDIDATE_BANK_SEED = 20260720
RUN_TVD_LIMIT = .10
CHRONO_MEAN_LIMIT = .10
CHRONO_SPREAD_LIMIT = .10
WITHIN_RELATIVE_LIMIT = .10


def run_distribution(indices, runs, run_levels):
    values=np.asarray(runs)[np.asarray(indices,int)]
    counts=np.asarray([(values==level).sum() for level in run_levels],float)
    return counts/counts.sum()


def run_tvd(first,second):return float(.5*np.abs(np.asarray(first)-np.asarray(second)).sum())


def chronological_descriptors(indices,total_trials):
    positions=np.asarray(indices,float)/max(total_trials-1,1)
    return float(positions.mean()),float(positions.std(ddof=0))


def generate_candidate_bank(pool_indices, labels, pool_log_covariances,
                            class_counts, runs, subject):
    """Generate exactly 512 unique class-stratified candidates deterministically."""
    pool=np.asarray(pool_indices,int);labels=np.asarray(labels);logs=np.asarray(pool_log_covariances)
    if len(pool)!=len(logs):raise ValueError("pool/log-covariance alignment mismatch")
    rng=np.random.default_rng(np.random.SeedSequence([CANDIDATE_BANK_SEED,int(subject)]))
    members={c:pool[labels[pool]==c] for c in range(4)};position={v:i for i,v in enumerate(pool)}
    run_levels=sorted(set(np.asarray(runs)[pool].astype(str)));pool_runs=run_distribution(pool,runs,run_levels)
    seen=set();rows=[];attempts=0
    while len(rows)<N_CANDIDATES:
        attempts+=1
        if attempts>100000:raise RuntimeError("unable to generate unique candidate bank")
        selected=np.sort(np.concatenate([rng.choice(members[c],int(class_counts[c]),replace=False) for c in range(4)]))
        key=tuple(int(v) for v in selected)
        if key in seen:continue
        seen.add(key);candidate_logs=logs[[position[v] for v in selected]]
        geometry=covariance_geometry(candidate_logs,labels[selected])
        dist=run_distribution(selected,runs,run_levels);mean,spread=chronological_descriptors(selected,len(labels))
        rows.append({"candidate_id":len(rows),"trial_indices":list(key),"per_class_counts":[int((labels[selected]==c).sum()) for c in range(4)],
            "cov_between_class_separation":geometry["cov_between_class_separation"],
            "cov_within_class_dispersion":geometry["cov_within_class_dispersion"],
            "cov_separability_ratio":geometry["cov_separability_ratio"],"run_distribution":dist.tolist(),
            "run_tvd_from_pool":run_tvd(dist,pool_runs),"chronological_mean_position":mean,
            "chronological_spread":spread})
    return rows


def pair_differences(first,second):
    low,high=sorted((first,second),key=lambda r:(r["cov_between_class_separation"],r["candidate_id"]))
    within=abs(low["cov_within_class_dispersion"]-high["cov_within_class_dispersion"])/max(abs(low["cov_within_class_dispersion"]),abs(high["cov_within_class_dispersion"]),1e-12)
    return low,high,{"within_dispersion_relative_difference":float(within),
        "run_distribution_TVD_between_subsets":run_tvd(low["run_distribution"],high["run_distribution"]),
        "chronological_mean_position_difference":abs(low["chronological_mean_position"]-high["chronological_mean_position"]),
        "chronological_spread_difference":abs(low["chronological_spread"]-high["chronological_spread"])}


def pair_is_matched(differences):
    return (differences["within_dispersion_relative_difference"]<=WITHIN_RELATIVE_LIMIT
            and differences["run_distribution_TVD_between_subsets"]<=RUN_TVD_LIMIT
            and differences["chronological_mean_position_difference"]<=CHRONO_MEAN_LIMIT
            and differences["chronological_spread_difference"]<=CHRONO_SPREAD_LIMIT)


def select_matched_pair(bank):
    feasible=[]
    separations=np.asarray([r["cov_between_class_separation"] for r in bank])
    for first,second in itertools.combinations(bank,2):
        low,high,diff=pair_differences(first,second)
        if pair_is_matched(diff):
            contrast=high["cov_between_class_separation"]-low["cov_between_class_separation"]
            feasible.append((-contrast,low["candidate_id"],high["candidate_id"],low,high,diff))
    if not feasible:return {"feasible_pair":False,"meaningful_property_contrast":False,"feasible_pair_count":0,"meaningful_pair_count":0}
    feasible.sort(key=lambda item:item[:3]);_,_,_,low,high,diff=feasible[0]
    percentile=lambda value:float(100*np.count_nonzero(separations<=value)/len(separations))
    low_p,high_p=percentile(low["cov_between_class_separation"]),percentile(high["cov_between_class_separation"])
    meaningful_count=0
    for _,_,_,lo,hi,_ in feasible:
        if percentile(lo["cov_between_class_separation"])<=25 and percentile(hi["cov_between_class_separation"])>=75:meaningful_count+=1
    overlap=len(set(low["trial_indices"])&set(high["trial_indices"]))
    return {"feasible_pair":True,"meaningful_property_contrast":low_p<=25 and high_p>=75,
        "low_candidate_id":low["candidate_id"],"high_candidate_id":high["candidate_id"],
        "low_separation":low["cov_between_class_separation"],"high_separation":high["cov_between_class_separation"],
        "absolute_separation_difference":high["cov_between_class_separation"]-low["cov_between_class_separation"],
        "relative_separation_difference":(high["cov_between_class_separation"]-low["cov_between_class_separation"])/max(abs(low["cov_between_class_separation"]),1e-12),
        "low_separation_percentile":low_p,"high_separation_percentile":high_p,
        "low_within_dispersion":low["cov_within_class_dispersion"],"high_within_dispersion":high["cov_within_class_dispersion"],
        **diff,"trial_overlap_count":overlap,"trial_overlap_fraction":overlap/len(low["trial_indices"]),
        "subset_size":len(low["trial_indices"]),"per_class_counts":low["per_class_counts"],
        "low_trial_indices":low["trial_indices"],"high_trial_indices":high["trial_indices"],
        "feasible_pair_count":len(feasible),"meaningful_pair_count":meaningful_count}


def classify(subject_rows,integrity_errors=None):
    errors=list(integrity_errors or [])
    if len(subject_rows)!=9 or [r.get("subject") for r in subject_rows]!=list(range(1,10)):errors.append("subject matrix incomplete")
    feasible=sum(bool(r.get("feasible_pair")) for r in subject_rows)
    meaningful=sum(bool(r.get("meaningful_property_contrast")) for r in subject_rows)
    if errors:classification="INCOMPLETE_OR_INVALID"
    elif feasible>=7 and meaningful>=7:classification="INTERVENTION_FEASIBLE"
    else:classification="INTERVENTION_NOT_FEASIBLE"
    return {"classification":classification,"integrity_pass":not errors,"integrity_errors":errors,
            "feasible_subjects":feasible,"meaningful_contrast_subjects":meaningful,"subject_rows":subject_rows}
