"""Run the BCI2a EEGNet baseline across multiple random seeds."""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

import torch

from scripts.run_bci2a_multisubject import build_subject_config
from scripts.run_bci2a_multisubject import get_summary_path
from scripts.run_bci2a_multisubject import load_existing_summary
from scripts.run_bci2a_multisubject import run_subject
from scripts.run_bci2a_multisubject import save_aggregate_summary
from scripts.run_bci2a_multisubject import summary_to_row
from scripts.run_bci2a_multisubject import validate_subjects
from src.train import load_config


MULTISEED_FIELDS = [
    "seed",
    "subject_id",
    "best_epoch",
    "best_validation_loss",
    "best_validation_accuracy",
    "final_test_loss",
    "final_test_accuracy",
]


SEED_SUMMARY_FIELDS = [
    "seed",
    "num_subjects",
    "mean_test_accuracy",
    "std_test_accuracy",
]


def validate_seeds(seeds: list[int]) -> list[int]:
    """Validate and de-duplicate random seeds."""

    validated: list[int] = []

    for seed in seeds:
        if seed < 0:
            raise ValueError(
                f"Random seeds must be non-negative, got {seed}"
            )

        if seed not in validated:
            validated.append(seed)

    if not validated:
        raise ValueError(
            "At least one random seed is required."
        )

    return validated


def save_csv(
    rows: list[dict],
    fieldnames: list[str],
    output_path: Path,
) -> None:
    """Save rows to a CSV file."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def build_seed_summary(
    seed: int,
    subject_rows: list[dict],
) -> dict:
    """Build aggregate statistics for one seed."""

    accuracies = [
        float(row["final_test_accuracy"])
        for row in subject_rows
    ]

    std_accuracy = 0.0

    if len(accuracies) > 1:
        std_accuracy = statistics.stdev(
            accuracies
        )

    return {
        "seed": seed,
        "num_subjects": len(accuracies),
        "mean_test_accuracy": statistics.mean(
            accuracies
        ),
        "std_test_accuracy": std_accuracy,
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Run the BCI2a EEGNet baseline across "
            "multiple random seeds."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/bci2a_eegnet_baseline.yaml"
        ),
        help="Base YAML configuration.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[42, 43, 44],
        help="Random seeds to evaluate.",
    )
    parser.add_argument(
        "--subjects",
        type=int,
        nargs="+",
        default=list(range(1, 10)),
        help="BCI2a subject identifiers.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            "results/bci2a_eegnet_multiseed"
        ),
        help="Parent directory for multi-seed outputs.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse completed subject runs.",
    )

    return parser.parse_args()


def main() -> None:
    """Run the requested seeds and subjects."""

    args = parse_args()

    seeds = validate_seeds(args.seeds)
    subjects = validate_subjects(
        args.subjects
    )
    base_config = load_config(
        str(args.config)
    )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    all_rows: list[dict] = []
    seed_rows: list[dict] = []

    multiseed_path = (
        args.output_root
        / "multiseed_subjects_summary.csv"
    )
    seeds_summary_path = (
        args.output_root
        / "seeds_summary.csv"
    )

    print(f"Using device: {device}")
    print(f"Seeds: {seeds}")
    print(f"Subjects: {subjects}")
    print(f"Output root: {args.output_root}")

    for seed_position, seed in enumerate(
        seeds,
        start=1,
    ):
        print("")
        print("#" * 72)
        print(
            f"Seed {seed} "
            f"({seed_position}/{len(seeds)})"
        )
        print("#" * 72)

        seed_config = dict(base_config)
        seed_config["seed"] = seed

        seed_root = (
            args.output_root
            / f"seed_{seed}"
        )
        seed_summary_path = (
            seed_root
            / "subjects_summary.csv"
        )

        subject_rows: list[dict] = []

        for subject_position, subject_id in enumerate(
            subjects,
            start=1,
        ):
            print("")
            print("=" * 72)
            print(
                f"Seed {seed} | "
                f"Subject A{subject_id:02d} "
                f"({subject_position}/{len(subjects)})"
            )
            print("=" * 72)

            config = build_subject_config(
                base_config=seed_config,
                subject_id=subject_id,
                output_root=seed_root,
            )

            run_summary_path = get_summary_path(
                config
            )

            if (
                args.skip_existing
                and run_summary_path.is_file()
            ):
                print(
                    "Reusing existing summary: "
                    f"{run_summary_path}"
                )
                summary = load_existing_summary(
                    run_summary_path
                )
            else:
                summary = run_subject(
                    config=config,
                    device=device,
                )

            row = summary_to_row(
                subject_id=subject_id,
                summary=summary,
            )

            subject_rows.append(row)

            multiseed_row = {
                "seed": seed,
                **row,
            }
            all_rows.append(
                multiseed_row
            )

            save_aggregate_summary(
                rows=subject_rows,
                output_path=seed_summary_path,
            )

            save_csv(
                rows=all_rows,
                fieldnames=MULTISEED_FIELDS,
                output_path=multiseed_path,
            )

        seed_rows.append(
            build_seed_summary(
                seed=seed,
                subject_rows=subject_rows,
            )
        )

        save_csv(
            rows=seed_rows,
            fieldnames=SEED_SUMMARY_FIELDS,
            output_path=seeds_summary_path,
        )

    run_accuracies = [
        float(
            row["final_test_accuracy"]
        )
        for row in all_rows
    ]

    print("")
    print("Multi-seed baseline finished.")
    print(
        f"Completed runs: {len(all_rows)}"
    )
    print(
        "Overall mean official test accuracy: "
        f"{statistics.mean(run_accuracies):.4f}"
    )
    print(
        "Saved run-level summary: "
        f"{multiseed_path}"
    )
    print(
        "Saved seed-level summary: "
        f"{seeds_summary_path}"
    )


if __name__ == "__main__":
    main()

