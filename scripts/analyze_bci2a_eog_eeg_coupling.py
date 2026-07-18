"""Aggregate deterministic EOG-to-EEG coupling contrasts."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    args = parser.parse_args()
    with (args.results_root / "coupling_results.csv").open(
        encoding="utf-8", newline=""
    ) as file:
        rows = list(csv.DictReader(file))
    expected = 9 * 4 * 22 * 2
    if len(rows) != expected:
        raise RuntimeError(f"Expected {expected} rows, got {len(rows)}")

    pivot = defaultdict(dict)
    metadata = {}
    for row in rows:
        key = (int(row["subject"]), row["window"], row["eeg_channel"])
        pivot[key][row["condition"]] = row
        metadata[key] = row
    contrasts = []
    for key in sorted(pivot):
        subject, window, channel = key
        same = pivot[key]["same_trial"]
        control = pivot[key]["same_class_cross_trial"]
        contrasts.append({
            "subject": subject,
            "window": window,
            "eeg_channel": channel,
            "eeg_channel_index": int(same["eeg_channel_index"]),
            "region": same["region"],
            "same_trial_r2": float(same["r2"]),
            "control_r2": float(control["r2"]),
            "delta_r2": float(same["r2"]) - float(control["r2"]),
            "same_trial_correlation": float(same["correlation"]),
            "control_correlation": float(control["correlation"]),
        })
    write_csv(args.results_root / "coupling_channel_contrasts.csv", contrasts)

    grouped = defaultdict(list)
    for row in contrasts:
        grouped[(row["subject"], row["window"])].append(row)
    subject_rows = []
    for key in sorted(grouped):
        subject, window = key
        values = grouped[key]
        subject_rows.append({
            "subject": subject,
            "window": window,
            "mean_same_trial_r2": statistics.mean(x["same_trial_r2"] for x in values),
            "median_same_trial_r2": statistics.median(x["same_trial_r2"] for x in values),
            "mean_control_r2": statistics.mean(x["control_r2"] for x in values),
            "median_control_r2": statistics.median(x["control_r2"] for x in values),
            "mean_delta_r2": statistics.mean(x["delta_r2"] for x in values),
            "median_delta_r2": statistics.median(x["delta_r2"] for x in values),
            "channels_positive_delta": sum(x["delta_r2"] > 0 for x in values),
        })
    write_csv(args.results_root / "coupling_subjects.csv", subject_rows)

    channel_groups = defaultdict(list)
    region_groups = defaultdict(list)
    for row in contrasts:
        channel_groups[(row["window"], row["eeg_channel"])].append(row)
        region_groups[(row["window"], row["region"])].append(row)
    channel_rows = []
    for key in sorted(channel_groups):
        window, channel = key
        values = channel_groups[key]
        channel_rows.append({
            "window": window,
            "eeg_channel": channel,
            "region": values[0]["region"],
            "mean_same_trial_r2": statistics.mean(x["same_trial_r2"] for x in values),
            "mean_control_r2": statistics.mean(x["control_r2"] for x in values),
            "mean_delta_r2": statistics.mean(x["delta_r2"] for x in values),
            "subjects_positive_delta": sum(x["delta_r2"] > 0 for x in values),
        })
    write_csv(args.results_root / "coupling_channels.csv", channel_rows)

    region_rows = []
    for key in sorted(region_groups):
        window, region = key
        values = region_groups[key]
        by_subject = defaultdict(list)
        for value in values:
            by_subject[value["subject"]].append(value["delta_r2"])
        subject_means = [statistics.mean(v) for v in by_subject.values()]
        region_rows.append({
            "window": window,
            "region": region,
            "mean_delta_r2_across_subjects": statistics.mean(subject_means),
            "median_delta_r2_across_subjects": statistics.median(subject_means),
        })
    write_csv(args.results_root / "coupling_regions.csv", region_rows)


if __name__ == "__main__":
    main()
