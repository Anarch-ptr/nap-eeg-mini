"""Freeze conservative evidence synthesis for the completed zero-training review."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


EXPECTED_ROWS = {
    "prediction_agreement.csv": 162,
    "correctness_stability.csv": 54,
    "error_set_overlap.csv": 162,
    "classwise_stability.csv": 648,
    "probability_logit_stability.csv": 162,
    "training_history_stability.csv": 4050,
    "batchnorm_stability.csv": 486,
    "representation_cka.csv": 972,
    "representation_diagnostics.csv": 972,
    "measurement_reliability.csv": 7290,
}


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summary(values) -> dict:
    array = np.asarray(list(values), dtype=np.float64)
    return {
        "n_units": int(len(array)),
        "mean": float(array.mean()),
        "sample_sd": float(array.std(ddof=1)) if len(array) > 1 else 0.0,
        "minimum": float(array.min()),
        "maximum": float(array.max()),
        "range": float(array.max() - array.min()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("results/bci2a_instability_reliability_review"))
    args = parser.parse_args()
    tables = {name: read(args.root / name) for name in EXPECTED_ROWS}
    observed_rows = {name: len(rows) for name, rows in tables.items()}
    if observed_rows != EXPECTED_ROWS:
        raise RuntimeError(f"incomplete review tables: {observed_rows}")
    pipeline = json.loads((args.root / "pipeline_integrity_review.json").read_text(encoding="utf-8"))
    if pipeline["classification"] != "NO_SYSTEMATIC_PIPELINE_ISSUE_FOUND":
        raise RuntimeError("pipeline integrity must pass before evidence synthesis")

    prediction = tables["prediction_agreement.csv"]
    correctness = tables["correctness_stability.csv"]
    errors = tables["error_set_overlap.csv"]
    probability = tables["probability_logit_stability.csv"]
    representation = tables["representation_cka.csv"]
    diagnostics = tables["representation_diagnostics.csv"]
    reliability = tables["measurement_reliability.csv"]

    prediction_summary = {}
    for session in ("validation", "official_evaluation"):
        prediction_summary[session] = {}
        for budget in ("1.0", "0.5", "0.25"):
            pair_rows = [r for r in prediction if r["session"] == session and r["budget"] == budget]
            subject_rows = {r["subject"]: r for r in pair_rows}.values()
            correctness_rows = [r for r in correctness if r["session"] == session and r["budget"] == budget]
            error_rows = {r["subject"]: r for r in errors if r["session"] == session and r["budget"] == budget}.values()
            probability_rows = {r["subject"]: r for r in probability if r["session"] == session and r["budget"] == budget}.values()
            prediction_summary[session][budget] = {
                "subject_pairmean_disagreement": summary(float(r["pairwise_disagreement_rate_mean"]) for r in subject_rows),
                "mixed_correctness_fraction": summary(float(r["mixed_correctness_fraction"]) for r in correctness_rows),
                "subject_pairmean_error_jaccard": summary(float(r["pairwise_error_jaccard_mean"]) for r in error_rows),
                "subject_pairmean_confidence_difference": summary(float(r["pairwise_confidence_abs_difference_mean_mean"]) for r in probability_rows),
                "subject_pairmean_margin_difference": summary(float(r["pairwise_logit_margin_abs_difference_mean_mean"]) for r in probability_rows),
                "subject_pairmean_js_divergence": summary(float(r["pairwise_js_divergence_mean_mean"]) for r in probability_rows),
            }

    reliability_summary = {}
    for metric in ("coral_distance", "rbf_mmd2", "feature_mean_shift", "feature_variance_shift", "covariance_difference"):
        reliability_summary[metric] = {}
        for fraction in ("0.5", "0.75", "1.0"):
            rows = [r for r in reliability if r["shift_metric"] == metric and r["fraction"] == fraction]
            reliability_summary[metric][fraction] = summary(
                float(r["absolute_relative_deviation_from_full_mean"]) for r in rows
            )

    block2_summary = {}
    for session in ("validation", "official_evaluation"):
        rows = [r for r in diagnostics if r["stage"] == "final_latent" and r["session"] == session]
        block2_summary[session] = {
            "rank": summary(float(r["matrix_rank"]) for r in rows),
            "effective_dimension_participation_ratio": summary(
                float(r["effective_dimension_participation_ratio"]) for r in rows
            ),
            "zero_variance_feature_fraction": summary(
                float(r["zero_variance_feature_fraction"]) for r in rows
            ),
        }

    input_rows = [r for r in representation if r["stage"] == "model_input"]
    input_integrity = all(abs(float(r["cka"]) - 1.0) <= 1e-12 for r in input_rows)
    evidence = {
        "review_scope": "81 frozen checkpoints; zero training",
        "row_counts": observed_rows,
        "matched_input_integrity_pass": input_integrity,
        "prediction_summary": prediction_summary,
        "measurement_reliability_summary": reliability_summary,
        "block2_effective_dimension": block2_summary,
        "cka_interpretation_policy": "GROUPED_WITHIN_LAYER; absolute cross-layer magnitude comparison prohibited",
        "pipeline_integrity": pipeline,
    }
    (args.root / "evidence_summary.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    status = {
        "experiment_status": "COMPLETED_ZERO_TRAINING_REVIEW",
        "checkpoint_count": 81,
        "primary_review_classification": "MIXED_MODEL_AND_MEASUREMENT_INSTABILITY",
        "optimization_dependent_predictive_variation": "SUPPORTED_UNDER_THREE_TESTED_SEEDS",
        "measurement_dominant_as_sole_explanation": "NOT_SUPPORTED",
        "ordinary_high_variance_small_data_learning": "PLAUSIBLE_CONSISTENCY_NOT_CAUSAL_PROOF",
        "no_mechanistic_explanation_established": True,
        "seed_sample_conclusion": "UNRESOLVED_DUE_TO_SEED_SAMPLE_LIMITATION",
        "seed_sufficiency_classification": "SUFFICIENCY_C",
        "multi_seed_replication_trigger": "NOT_SATISFIED",
        "replication_trigger_reason": "Prediction variation is clear, but error overlap is not uniformly low, probability/logit patterns are not coherently stronger at lower budget, and shift-metric subsampling reliability is limited.",
        "representation_measurement_limitation": "block2 finite-sample baseline elevation, effective-dimension concentration, and summary information loss constrain interpretation",
        "pipeline_integrity": "NO_SYSTEMATIC_PIPELINE_ISSUE_FOUND",
        "architecture_stop_rule": "ACTIVE",
        "no_training": True,
        "additional_training_seeds": False,
        "allowed_next_step": "HUMAN_REVIEW_AND_STOP_MECHANISTIC_OR_ARCHITECTURAL_ESCALATION",
    }
    (args.root / "analysis_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({"evidence_summary": evidence, "analysis_status": status}, indent=2))


if __name__ == "__main__":
    main()
