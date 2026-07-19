"""Analyze the frozen optimizer-update-matched diagnostic."""

import argparse
import csv
import json
from pathlib import Path

from src.update_matched_diagnostic import analyze_diagnostic


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as file: return list(csv.DictReader(file))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary", type=Path, default=Path("results/bci2a_small_sample_audit/small_sample_runs.csv"))
    p.add_argument("--diagnostic", type=Path, default=Path("results/bci2a_update_matched_diagnostic/update_matched_runs.csv"))
    p.add_argument("--output-dir", type=Path, default=Path("results/bci2a_update_matched_diagnostic/analysis"))
    a = p.parse_args(); a.output_dir.mkdir(parents=True, exist_ok=True)
    result = analyze_diagnostic(read_csv(a.primary), read_csv(a.diagnostic))
    write_csv(a.output_dir / "update_matched_subject_summary.csv", result["subject_diagnostics"])
    write_csv(a.output_dir / "update_matched_seed_diagnostics.csv", result["seed_residual_diagnostics"])
    (a.output_dir / "update_matched_analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Optimizer-Update-Matched Diagnostic", "", f"Integrity pass: `{result['integrity_pass']}`",
             f"Classification: **{result['classification']}**", "", "## Aggregate results", "",
             f"- Original median gap: {result['original_median_gap_pp']:.2f} pp",
             f"- Median recovery: {result['median_recovery_pp']:.2f} pp",
             f"- Median residual gap: {result['median_residual_gap_pp']:.2f} pp",
             f"- Subjects with residual gap >=3 pp: {result['subjects_residual_ge_3pp']}/9",
             f"- Median descriptive gap closure: {result['median_gap_closure_fraction']:.4f}", "",
             "This diagnostic does not justify NAP. Positive recovery does not prove sample diversity is irrelevant; persistent residual failure does not prove NAP is required."]
    (a.output_dir / "update_matched_analysis.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(f"Classification: {result['classification']}"); print(f"Integrity pass: {result['integrity_pass']}")


if __name__ == "__main__": main()
