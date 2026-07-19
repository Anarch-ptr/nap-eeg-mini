"""Pre-registered analysis for BCI2a Small-Sample Robustness Audit v1."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict


REQUIRED_SUBJECTS = tuple(range(1, 10))
REQUIRED_BUDGETS = (1.0, 0.5, 0.25)
REQUIRED_SEEDS = (42, 43, 44)
EXPECTED_SPLIT_SEED = 42
EXPECTED_SUBSET_SEED = 20260719
PRIMARY_METRIC_FIELD = "test_accuracy"


def _number(row, field, cast=float):
    try:
        return cast(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid {field!r}: {row.get(field)!r}") from error


def validate_matrix(rows: list[dict]) -> list[str]:
    """Return all protocol-integrity errors without interpreting outcomes."""

    errors: list[str] = []
    parsed = []
    required_fields = {
        "subject", "budget", "subset_seed", "split_seed", "training_seed",
        "train_sample_count", "train_class_counts", "validation_sample_count",
        "test_sample_count", "primary_metric", PRIMARY_METRIC_FIELD,
        "run_status", "checkpoint",
    }
    for position, row in enumerate(rows, start=2):
        missing = sorted(required_fields - set(row))
        if missing:
            errors.append(f"row {position}: missing fields {missing}")
            continue
        try:
            parsed.append((
                _number(row, "subject", int), _number(row, "budget"),
                _number(row, "subset_seed", int),
                _number(row, "split_seed", int),
                _number(row, "training_seed", int), row,
            ))
        except ValueError as error:
            errors.append(f"row {position}: {error}")

    keys = [(s, b, ss, sp, ts) for s, b, ss, sp, ts, _ in parsed]
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate primary run keys: {duplicates}")

    cells = Counter((s, b, ts) for s, b, _, _, ts, _ in parsed)
    expected_cells = {
        (subject, budget, seed)
        for subject in REQUIRED_SUBJECTS
        for budget in REQUIRED_BUDGETS
        for seed in REQUIRED_SEEDS
    }
    missing_cells = sorted(expected_cells - set(cells))
    unexpected_cells = sorted(set(cells) - expected_cells)
    repeated_cells = sorted(key for key, count in cells.items() if count != 1)
    if missing_cells:
        errors.append(f"missing subject-budget-seed cells: {missing_cells}")
    if unexpected_cells:
        errors.append(f"unexpected subject-budget-seed cells: {unexpected_cells}")
    if repeated_cells:
        errors.append(f"non-unique subject-budget-seed cells: {repeated_cells}")

    for subject, budget, subset_seed, split_seed, training_seed, row in parsed:
        label = f"A{subject:02d}/budget={budget}/seed={training_seed}"
        if split_seed != EXPECTED_SPLIT_SEED:
            errors.append(f"{label}: split_seed={split_seed}, expected 42")
        if subset_seed != EXPECTED_SUBSET_SEED:
            errors.append(
                f"{label}: subset_seed={subset_seed}, "
                f"expected {EXPECTED_SUBSET_SEED}"
            )
        if row["run_status"] != "completed":
            errors.append(f"{label}: run_status={row['run_status']!r}")
        if row["primary_metric"] != "accuracy":
            errors.append(f"{label}: primary_metric={row['primary_metric']!r}")
        if not str(row["checkpoint"]).strip():
            errors.append(f"{label}: checkpoint identity is empty")
        try:
            train_count = _number(row, "train_sample_count", int)
            validation_count = _number(row, "validation_sample_count", int)
            test_count = _number(row, "test_sample_count", int)
            metric = _number(row, PRIMARY_METRIC_FIELD)
            counts = json.loads(row["train_class_counts"])
            if train_count <= 0 or validation_count <= 0 or test_count <= 0:
                errors.append(f"{label}: non-positive sample count")
            if not 0.0 <= metric <= 1.0:
                errors.append(f"{label}: test_accuracy outside [0, 1]")
            if set(counts) != {"0", "1", "2", "3"}:
                errors.append(f"{label}: expected four represented classes")
            elif sum(int(value) for value in counts.values()) != train_count:
                errors.append(f"{label}: class counts do not sum to train count")
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            errors.append(f"{label}: invalid counts or metric: {error}")

    grouped = defaultdict(list)
    for subject, budget, _, _, _, row in parsed:
        grouped[subject].append((budget, row))
    for subject in REQUIRED_SUBJECTS:
        subject_rows = grouped.get(subject, [])
        validation_counts = {
            int(row["validation_sample_count"]) for _, row in subject_rows
        }
        test_counts = {int(row["test_sample_count"]) for _, row in subject_rows}
        if len(validation_counts) > 1:
            errors.append(f"A{subject:02d}: validation counts vary across runs")
        if len(test_counts) > 1:
            errors.append(f"A{subject:02d}: test counts vary across runs")
        by_budget = defaultdict(set)
        for budget, row in subject_rows:
            by_budget[budget].add(int(row["train_sample_count"]))
        varying_budgets = [
            budget for budget, values in by_budget.items() if len(values) > 1
        ]
        if varying_budgets:
            errors.append(
                f"A{subject:02d}: training counts vary within budgets "
                f"{sorted(varying_budgets)}"
            )
        if all(budget in by_budget and len(by_budget[budget]) == 1 for budget in REQUIRED_BUDGETS):
            counts = {budget: next(iter(by_budget[budget])) for budget in REQUIRED_BUDGETS}
            if not counts[1.0] >= counts[0.5] >= counts[0.25] > 0:
                errors.append(f"A{subject:02d}: unexpected training-count ordering {counts}")
    return list(dict.fromkeys(errors))


def aggregate_subjects(rows: list[dict]) -> list[dict]:
    """Aggregate optimization seeds within each subject and budget."""

    grouped = defaultdict(list)
    for row in rows:
        if row.get("run_status") != "completed":
            continue
        grouped[(int(row["subject"]), float(row["budget"]))].append(
            float(row[PRIMARY_METRIC_FIELD])
        )
    output = []
    for (subject, budget), values in sorted(grouped.items()):
        output.append({
            "subject": subject,
            "budget": budget,
            "metric_mean": statistics.mean(values),
            "metric_std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "n_seeds": len(values),
        })
    return output


def build_subject_comparisons(subject_budget_rows: list[dict]) -> list[dict]:
    """Pivot budget means and expose fraction deltas and pp degradations."""

    grouped = defaultdict(dict)
    for row in subject_budget_rows:
        grouped[int(row["subject"])][float(row["budget"])] = row
    output = []
    for subject in sorted(grouped):
        values = grouped[subject]
        if not all(budget in values for budget in REQUIRED_BUDGETS):
            continue
        full, half, quarter = (values[b] for b in REQUIRED_BUDGETS)
        delta50 = half["metric_mean"] - full["metric_mean"]
        delta25 = quarter["metric_mean"] - full["metric_mean"]
        output.append({
            "subject": subject,
            "metric_100_mean": full["metric_mean"],
            "metric_100_std": full["metric_std"],
            "metric_50_mean": half["metric_mean"],
            "metric_50_std": half["metric_std"],
            "metric_25_mean": quarter["metric_mean"],
            "metric_25_std": quarter["metric_std"],
            "n_seeds_100": full["n_seeds"],
            "n_seeds_50": half["n_seeds"],
            "n_seeds_25": quarter["n_seeds"],
            "delta50_fraction": delta50,
            "delta25_fraction": delta25,
            "degradation50_pp": -delta50 * 100.0,
            "degradation25_pp": -delta25 * 100.0,
            "dose_response_monotonic": (
                full["metric_mean"] >= half["metric_mean"]
                >= quarter["metric_mean"]
            ),
        })
    return output


def seed_diagnostics(rows: list[dict]) -> list[dict]:
    """Compute seed-wise median degradation as a reproducibility diagnostic."""

    lookup = {
        (int(row["subject"]), float(row["budget"]), int(row["training_seed"])):
        float(row[PRIMARY_METRIC_FIELD])
        for row in rows if row.get("run_status") == "completed"
    }
    output = []
    for seed in REQUIRED_SEEDS:
        degradations = []
        for subject in REQUIRED_SUBJECTS:
            full = lookup.get((subject, 1.0, seed))
            quarter = lookup.get((subject, 0.25, seed))
            if full is not None and quarter is not None:
                degradations.append((full - quarter) * 100.0)
        median = statistics.median(degradations) if degradations else None
        output.append({
            "training_seed": seed,
            "n_subjects": len(degradations),
            "median_degradation25_pp": median,
            "positive_group_direction": median is not None and median > 0.0,
        })
    return output


def classify(rows: list[dict]) -> dict:
    """Apply the frozen integrity and scientific decision rules."""

    integrity_errors = validate_matrix(rows)
    subject_budget = aggregate_subjects(rows)
    subjects = build_subject_comparisons(subject_budget)
    seeds = seed_diagnostics(rows)
    if integrity_errors:
        classification = "INCOMPLETE_OR_INVALID"
    else:
        degradations = [row["degradation25_pp"] for row in subjects]
        median_degradation = statistics.median(degradations)
        subjects_ge_3 = sum(value >= 3.0 for value in degradations)
        seed_consistent = all(
            row["positive_group_direction"] and row["n_subjects"] == 9
            for row in seeds
        )
        medians = {
            budget: statistics.median(
                row["metric_mean"] for row in subject_budget
                if row["budget"] == budget
            ) for budget in REQUIRED_BUDGETS
        }
        dose_pass = medians[1.0] >= medians[0.5] >= medians[0.25]
        strong = (
            median_degradation >= 5.0 and subjects_ge_3 >= 7
            and seed_consistent and dose_pass
        )
        meaningful_signal = (
            median_degradation >= 3.0
            or subjects_ge_3 >= 3
            or median_degradation >= 5.0
            or subjects_ge_3 >= 7
        )
        if strong:
            classification = "STRONG_FAILURE"
        elif meaningful_signal:
            classification = "MIXED_FAILURE"
        else:
            classification = "NO_MEANINGFUL_FAILURE"

    complete = not integrity_errors
    degradations = [row["degradation25_pp"] for row in subjects]
    median_degradation = statistics.median(degradations) if degradations else None
    subjects_ge_3 = sum(value >= 3.0 for value in degradations)
    seed_consistent = complete and all(
        row["positive_group_direction"] and row["n_subjects"] == 9
        for row in seeds
    )
    budget_medians = {}
    for budget in REQUIRED_BUDGETS:
        values = [
            row["metric_mean"] for row in subject_budget
            if row["budget"] == budget
        ]
        budget_medians[str(budget)] = statistics.median(values) if values else None
    dose_pass = (
        complete and budget_medians["1.0"] >= budget_medians["0.5"]
        >= budget_medians["0.25"]
    )
    return {
        "classification": classification,
        "primary_metric": "accuracy",
        "metric_storage_unit": "fraction_0_to_1",
        "degradation_unit": "percentage_points",
        "median_degradation25_pp": median_degradation,
        "subjects_degraded_ge_3pp": subjects_ge_3,
        "seed_direction_consistent": seed_consistent,
        "dose_response_pass": dose_pass,
        "subject_monotonic_count": sum(
            row["dose_response_monotonic"] for row in subjects
        ),
        "budget_median_metrics": budget_medians,
        "integrity_pass": complete,
        "integrity_errors": integrity_errors,
        "subject_budget_rows": subject_budget,
        "subject_comparisons": subjects,
        "seed_diagnostics": seeds,
    }
