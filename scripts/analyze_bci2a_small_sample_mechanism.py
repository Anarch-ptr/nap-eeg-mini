"""Run the frozen zero-new-training small-sample mechanism audit."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

from src.data import load_bci2a_subject
from src.mechanism_audit import (FEATURE_SOURCES, SUBJECTS, analyze,
                                 frozen_subset_indices, geometry_features,
                                 log_bandpower_features)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as file: return list(csv.DictReader(file))


def write_csv(path, rows, excluded=()):
    clean = [{k: v for k, v in row.items() if k not in excluded} for row in rows]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(clean[0])); writer.writeheader(); writer.writerows(clean)


def plot_relationship(output, feature, rows):
    x = [r[feature] for r in rows]; y = [r["residual_gap_pp"] for r in rows]
    fig, ax = plt.subplots(figsize=(6, 4.5)); ax.scatter(x, y)
    for row in rows: ax.annotate(f"A{row['subject']:02d}", (row[feature], row["residual_gap_pp"]), xytext=(4,4), textcoords="offset points")
    ax.set_xlabel(feature); ax.set_ylabel("Residual gap (percentage points)")
    ax.grid(alpha=.25); fig.tight_layout(); fig.savefig(output, dpi=160); plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary-root", type=Path, default=Path("results/bci2a_small_sample_audit"))
    p.add_argument("--matched-root", type=Path, default=Path("results/bci2a_update_matched_diagnostic"))
    p.add_argument("--control-root", type=Path, default=Path("results/bci2a_simple_control_weight_decay"))
    p.add_argument("--output-dir", type=Path, default=Path("results/bci2a_small_sample_mechanism_audit"))
    a = p.parse_args(); a.output_dir.mkdir(parents=True, exist_ok=True)
    primary = read_csv(a.primary_root / "small_sample_runs.csv")
    matched = read_csv(a.matched_root / "update_matched_runs.csv")
    control = read_csv(a.control_root / "simple_control_runs.csv")
    geometry = {}; provenance_ok = True
    for subject in SUBJECTS:
        try:
            indices = frozen_subset_indices(a.primary_root, subject)
            data = load_bci2a_subject(subject_id=subject, data_dir="data/moabb", fmin=8., fmax=32., tmin=0., tmax=4.)
            x, y = data.x_train[indices], data.y_train[indices]
            geometry[subject] = geometry_features(log_bandpower_features(x, data.sampling_rate), y)
        except (KeyError, OSError, RuntimeError, ValueError) as exc:
            provenance_ok = False; raise RuntimeError(f"A{subject:02d} geometry/provenance failure") from exc
    from src.mechanism_audit import build_subject_table
    subjects = build_subject_table(primary, matched, control, geometry)
    result = analyze(subjects, primary, matched, control, provenance_ok)
    write_csv(a.output_dir / "mechanism_subject_table.csv", subjects)
    write_csv(a.output_dir / "mechanism_feature_associations.csv", result["associations"], excluded=("loso_values",))
    loso = [{"feature_name": row["feature_name"], "excluded_subject": subject,
             "spearman_rho": row["loso_values"][subject-1]}
            for row in result["associations"] for subject in SUBJECTS]
    write_csv(a.output_dir / "mechanism_loso_stability.csv", loso)
    serializable = dict(result); serializable["associations"] = [dict(r) for r in result["associations"]]
    (a.output_dir / "mechanism_audit.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    for feature in ("separability_ratio", "within_class_dispersion", "seed_std_25_matched", "full_data_accuracy"):
        plot_relationship(a.output_dir / f"residual_vs_{feature}.png", feature, subjects)
    lines = ["# Small-Sample Mechanism Audit", "", f"Integrity pass: `{result['integrity_pass']}`",
             "", "The outcome is the frozen subject-level 100%-fixed minus 25%-update-matched accuracy gap. Seeds are aggregated within subject.",
             "", "## Associations", "", "| Feature | Source | Spearman | Kendall | LOSO median | Stable | Classification |",
             "|---|---|---:|---:|---:|---:|---|"]
    for r in result["associations"]:
        lines.append(f"| {r['feature_name']} | {r['feature_source']} | {r['spearman_rho']:.3f} | {r['kendall_tau']:.3f} | {r['loso_median_spearman_rho']:.3f} | {r['direction_stability_count']}/9 | {r['classification']} |")
    lines += ["", "Correlation does not establish mechanism. A robust training-data-only association authorizes a targeted follow-up hypothesis, not an architecture."]
    (a.output_dir / "mechanism_audit.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(f"Integrity pass: {result['integrity_pass']}")
    for r in result["associations"]: print(f"{r['feature_name']}: {r['classification']} (rho={r['spearman_rho']:.3f})")


if __name__ == "__main__": main()
