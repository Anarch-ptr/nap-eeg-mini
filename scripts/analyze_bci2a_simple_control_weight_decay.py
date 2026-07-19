"""Analyze the frozen weight-decay simple-control experiment."""

import argparse
import csv
import json
from pathlib import Path

from src.simple_control_analysis import analyze_simple_control


def read(path):
    with path.open(encoding="utf-8", newline="") as f: return list(csv.DictReader(f))


def write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary", type=Path, default=Path("results/bci2a_small_sample_audit/small_sample_runs.csv"))
    p.add_argument("--matched", type=Path, default=Path("results/bci2a_update_matched_diagnostic/update_matched_runs.csv"))
    p.add_argument("--control", type=Path, default=Path("results/bci2a_simple_control_weight_decay/simple_control_runs.csv"))
    p.add_argument("--output-dir", type=Path, default=Path("results/bci2a_simple_control_weight_decay/analysis"))
    a = p.parse_args(); a.output_dir.mkdir(parents=True, exist_ok=True)
    result = analyze_simple_control(read(a.primary), read(a.matched), read(a.control))
    write(a.output_dir / "simple_control_subject_summary.csv", result["subject_control_diagnostics"])
    write(a.output_dir / "simple_control_seed_diagnostics.csv", result["seed_control_residual_diagnostics"])
    (a.output_dir / "simple_control_analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Weight-Decay Simple-Control Analysis", "",
             f"Integrity pass: `{result['integrity_pass']}`",
             f"Classification: **{result['classification']}**", "",
             f"- Median matched residual gap: {result['median_matched_residual_gap_pp']:.2f} pp",
             f"- Median control gain: {result['median_control_gain_pp']:.2f} pp",
             f"- Median control residual gap: {result['median_control_residual_gap_pp']:.2f} pp",
             f"- Subjects with control residual >=3 pp: {result['subjects_control_residual_ge_3pp']}/9",
             f"- Subjects with control gain >=3 pp: {result['subjects_control_gain_ge_3pp']}/9", "",
             "Failure of this one control does not prove all simple controls fail. Success argues against a complex NAP architecture. Persistent failure permits mechanism investigation but does not prove NAP is correct."]
    (a.output_dir / "simple_control_analysis.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(f"Classification: {result['classification']}"); print(f"Integrity pass: {result['integrity_pass']}")


if __name__ == "__main__": main()
