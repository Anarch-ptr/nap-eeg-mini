"""Run deterministic linear EOG-to-EEG coupling audit for BCI2a."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.data import load_bci2a_coupling_subject
from src.eog_eeg_coupling import TEMPORAL_WINDOWS
from src.eog_eeg_coupling import apply_standardization
from src.eog_eeg_coupling import channel_metrics
from src.eog_eeg_coupling import crop_trials
from src.eog_eeg_coupling import eeg_region
from src.eog_eeg_coupling import fit_ols
from src.eog_eeg_coupling import fit_train_standardization
from src.eog_eeg_coupling import predict_ols
from src.eog_eeg_coupling import same_class_derangement


FIELDS = [
    "subject", "window", "tmin", "tmax", "num_samples", "eeg_channel",
    "eeg_channel_index", "region", "condition", "r2", "correlation",
    "permutation_seed",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 10)))
    parser.add_argument("--data-dir", type=Path, default=Path("data/moabb"))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results/bci2a_eog_eeg_coupling"),
    )
    parser.add_argument("--permutation-seed", type=int, default=20260718)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if sorted(set(args.subjects)) != sorted(args.subjects):
        raise ValueError("Subjects must be unique and sorted.")
    all_rows = []
    for subject in args.subjects:
        print(f"Loading aligned coupling data for A{subject:02d}")
        data = load_bci2a_coupling_subject(subject, data_dir=args.data_dir)
        subject_rows = []
        normalization = {}
        train_mapping = same_class_derangement(
            data.y_train, args.permutation_seed
        )
        test_mapping = same_class_derangement(
            data.y_test, args.permutation_seed + 1
        )
        for window, (tmin, tmax) in TEMPORAL_WINDOWS.items():
            eeg_train = crop_trials(data.eeg_train, tmin, tmax, data.sampling_rate)
            eog_train = crop_trials(data.eog_train, tmin, tmax, data.sampling_rate)
            eeg_test = crop_trials(data.eeg_test, tmin, tmax, data.sampling_rate)
            eog_test = crop_trials(data.eog_test, tmin, tmax, data.sampling_rate)
            eeg_mean, eeg_std = fit_train_standardization(eeg_train)
            eog_mean, eog_std = fit_train_standardization(eog_train)
            eeg_train = apply_standardization(eeg_train, eeg_mean, eeg_std)
            eog_train = apply_standardization(eog_train, eog_mean, eog_std)
            eeg_test = apply_standardization(eeg_test, eeg_mean, eeg_std)
            eog_test = apply_standardization(eog_test, eog_mean, eog_std)
            normalization[window] = {
                "source": "official_0train",
                "eeg_mean": eeg_mean.squeeze().tolist(),
                "eeg_std": eeg_std.squeeze().tolist(),
                "eog_mean": eog_mean.squeeze().tolist(),
                "eog_std": eog_std.squeeze().tolist(),
            }
            conditions = {
                "same_trial": (eog_train, eog_test, None),
                "same_class_cross_trial": (
                    eog_train[train_mapping],
                    eog_test[test_mapping],
                    args.permutation_seed,
                ),
            }
            for condition, (fit_eog, test_eog, permutation_seed) in conditions.items():
                coefficients = fit_ols(fit_eog, eeg_train)
                predictions = predict_ols(test_eog, coefficients)
                metrics = channel_metrics(eeg_test, predictions)
                for channel_index, (channel_name, metric) in enumerate(
                    zip(data.eeg_channel_names, metrics)
                ):
                    subject_rows.append({
                        "subject": subject,
                        "window": window,
                        "tmin": tmin,
                        "tmax": tmax,
                        "num_samples": eeg_test.shape[2],
                        "eeg_channel": channel_name,
                        "eeg_channel_index": channel_index,
                        "region": eeg_region(channel_name),
                        "condition": condition,
                        "r2": metric["r2"],
                        "correlation": metric["correlation"],
                        "permutation_seed": permutation_seed,
                    })
        subject_dir = args.output_root / f"subject_{subject:02d}"
        subject_dir.mkdir(parents=True, exist_ok=True)
        with (subject_dir / "coupling_results.csv").open(
            "w", encoding="utf-8", newline=""
        ) as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(subject_rows)
        with (subject_dir / "normalization.json").open("w", encoding="utf-8") as file:
            json.dump(normalization, file, indent=2, sort_keys=True)
        with (subject_dir / "run_config.json").open("w", encoding="utf-8") as file:
            json.dump(
                {
                    "subject": subject,
                    "permutation_seed": args.permutation_seed,
                    "test_permutation_seed": args.permutation_seed + 1,
                    "filter": [8.0, 32.0],
                    "sampling_rate": data.sampling_rate,
                    "eeg_channels": data.eeg_channel_names,
                    "eog_channels": data.eog_channel_names,
                    "fit_session": "0train",
                    "evaluation_session": "1test",
                    "windows": TEMPORAL_WINDOWS,
                },
                file,
                indent=2,
                sort_keys=True,
            )
        all_rows.extend(subject_rows)
        print(f"Completed A{subject:02d}: {len(subject_rows)} channel-condition rows")
    args.output_root.mkdir(parents=True, exist_ok=True)
    with (args.output_root / "coupling_results.csv").open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)


if __name__ == "__main__":
    main()
