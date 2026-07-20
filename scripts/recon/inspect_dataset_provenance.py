"""Inspect native/framework provenance without scientific preprocessing.

This script is intentionally isolated from the training and reliability
pipelines. It reads structural metadata and event markers only; it never builds
scientific epochs, normalizes signals, loads a model, or calculates performance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.io import loadmat


DATASET_ALIASES = {
    "lee2019_mi": "Lee2019_MI",
    "bnci2015_001": "BNCI2015-001",
}

TRIAL_LOSS_REASONS = {
    "NATIVE_DATA_MISSING",
    "NATIVE_EVENT_MISSING",
    "FRAMEWORK_EVENT_MAPPING_LOSS",
    "FRAMEWORK_BOUNDARY_EXCLUSION",
    "FRAMEWORK_RECORDING_EXCLUSION",
    "DUPLICATE_EVENT_REMOVAL",
    "AMBIGUOUS_EVENT_MAPPING",
    "UNKNOWN_TRIAL_LOSS",
    "OTHER_DOCUMENTED_REASON",
    "NO_OBSERVED_LOSS",
}

PROVENANCE_CLASSES = {
    "PROVENANCE_CONSISTENT",
    "ABSTRACTION_RENAMING_ONLY",
    "ABSTRACTION_SEMANTIC_MISMATCH",
    "PROVENANCE_INCOMPLETE",
    "REPLICATION_BLOCKING_MISMATCH",
}


def natural_key(value: Any) -> tuple:
    """Return a deterministic ordering key without assuming integer IDs."""
    text = str(value)
    pieces: list[tuple[int, Any]] = []
    current = ""
    digit = None
    for character in text:
        is_digit = character.isdigit()
        if digit is None or is_digit == digit:
            current += character
        else:
            pieces.append((0, int(current)) if digit else (1, current.lower()))
            current = character
        digit = is_digit
    if current:
        pieces.append((0, int(current)) if digit else (1, current.lower()))
    return tuple(pieces)


def structural_trial_id(
    dataset_id: str,
    subject_id: Any,
    physical_session_id: Any,
    run_or_block_id: Any,
    event_sample: int,
    event_ordinal: int,
) -> str:
    """Create a stable opaque ID from explicit structural provenance."""
    fields = {
        "dataset_id": str(dataset_id),
        "subject_id": str(subject_id),
        "physical_session_id": str(physical_session_id),
        "run_or_block_id": str(run_or_block_id),
        "event_sample": int(event_sample),
        "event_ordinal": int(event_ordinal),
    }
    textual = (
        fields["dataset_id"],
        fields["subject_id"],
        fields["physical_session_id"],
        fields["run_or_block_id"],
    )
    if any(not value for value in textual):
        raise ValueError("trial identity fields must be non-empty")
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require_unique(values: Iterable[str], label: str = "identities") -> None:
    """Reject duplicated structural identities."""
    items = list(values)
    duplicates = sorted(key for key, count in Counter(items).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate {label}: {duplicates[:5]}")


def classify_trial_loss(
    native_observed: int | None,
    framework_observed: int | None,
) -> str:
    """Classify only what counts establish; never guess the loss mechanism."""
    if native_observed is None or framework_observed is None:
        return "UNKNOWN_TRIAL_LOSS"
    if native_observed == framework_observed:
        return "NO_OBSERVED_LOSS"
    if native_observed > framework_observed:
        return "UNKNOWN_TRIAL_LOSS"
    return "UNKNOWN_TRIAL_LOSS"


def classify_dataset_provenance(
    dataset_key: str,
    raw_metadata_verified: bool,
    declared_sessions_per_subject: int,
    observed_session_counts: Iterable[int],
) -> tuple[str, list[str]]:
    """Classify observed structure without turning it into feasibility."""
    if not raw_metadata_verified:
        return "PROVENANCE_INCOMPLETE", []
    counts = list(observed_session_counts)
    if dataset_key == "bnci2015_001" and any(
        count != declared_sessions_per_subject for count in counts
    ):
        return (
            "ABSTRACTION_SEMANTIC_MISMATCH",
            ["FRAMEWORK_DECLARED_SESSION_COUNT_CONFLICTS_WITH_OBSERVED_HETEROGENEITY"],
        )
    if dataset_key == "lee2019_mi":
        return "ABSTRACTION_RENAMING_ONLY", []
    return "PROVENANCE_CONSISTENT", []


def moabb_relative_cache_argument(data_root: Path, cwd: Path | None = None) -> str:
    """Avoid MOABB 1.5 sanitizing the colon in an absolute Windows path."""
    base = (cwd or Path.cwd()).resolve()
    resolved = data_root.resolve()
    try:
        relative = resolved.relative_to(base)
    except ValueError as error:
        raise ValueError(
            "reconnaissance cache root must be inside the working tree so MOABB "
            "can receive a Windows-safe relative path"
        ) from error
    return str(relative)


def legacy_sanitized_cache_root(
    data_root: Path, cwd: Path | None = None
) -> Path:
    """Reconstruct the earlier MOABB-sanitized location without mutating it."""
    base = (cwd or Path.cwd()).resolve()
    sanitized = str(data_root.resolve()).translate({ord(c): "-" for c in ':*?"<>|'})
    return base / sanitized


def _lee_expected_paths(root: Path, subject: Any) -> list[Path]:
    prefix = root / "MNE-lee2019-mi-data" / "gigadb-datasets" / "live" / "pub"
    prefix = prefix / "10.5524" / "100001_101000" / "100542"
    return [
        prefix
        / f"session{session}"
        / f"s{subject}"
        / f"sess{session:02d}_subj{int(subject):02d}_EEG_MI.mat"
        for session in (1, 2)
    ]


def _existing_lee_subject_paths(subject: Any, roots: Iterable[Path]) -> list[str] | None:
    """Reuse a complete existing subject pair; never mix or duplicate it."""
    for root in roots:
        paths = _lee_expected_paths(root, subject)
        if all(path.is_file() for path in paths):
            return [str(path.resolve()) for path in paths]
    return None


def session_availability_matrix(
    subject_sessions: dict[str, Iterable[str]],
    native_to_physical: dict[str, str] | None = None,
) -> dict:
    """Build a heterogeneous subject-by-physical-session availability matrix."""
    mapping = native_to_physical or {}
    rows = []
    physical_levels: set[str] = set()
    for subject in sorted(subject_sessions, key=natural_key):
        native = sorted({str(value) for value in subject_sessions[subject]}, key=natural_key)
        physical = [mapping.get(value, value) for value in native]
        if len(set(physical)) != len(physical):
            raise ValueError(f"ambiguous session mapping for subject {subject}")
        physical_levels.update(physical)
        rows.append(
            {
                "subject_id": str(subject),
                "native_session_ids": native,
                "physical_session_ids": physical,
            }
        )
    levels = sorted(physical_levels, key=natural_key)
    for row in rows:
        available = set(row["physical_session_ids"])
        row["availability"] = {level: level in available for level in levels}
    coverage = {
        level: sum(bool(row["availability"][level]) for row in rows)
        for level in levels
    }
    common_s1_s2 = sum(
        bool(row["availability"].get("S1") and row["availability"].get("S2"))
        for row in rows
    )
    common_s1_s2_s3 = sum(
        bool(
            row["availability"].get("S1")
            and row["availability"].get("S2")
            and row["availability"].get("S3")
        )
        for row in rows
    )
    return {
        "physical_session_levels": levels,
        "rows": rows,
        "coverage": coverage,
        "verified_common_s1_s2": common_s1_s2,
        "verified_common_s1_s2_s3": common_s1_s2_s3,
    }


def validate_recon_record(record: dict) -> None:
    """Validate the machine-readable provenance envelope."""
    required = {
        "dataset_id",
        "dataset_class",
        "documentation_status",
        "raw_metadata_status",
        "provenance_classification",
        "framework_dataset_metadata",
        "inspected_subjects",
        "subject_records",
        "trial_retention_summary",
        "scientific_metrics_calculated",
    }
    missing = sorted(required - set(record))
    if missing:
        raise ValueError(f"missing reconnaissance fields: {missing}")
    if record["raw_metadata_status"] not in {
        "RAW_METADATA_VERIFIED",
        "RAW_METADATA_VERIFICATION_PARTIAL",
        "RAW_METADATA_VERIFICATION_FAILED",
    }:
        raise ValueError("invalid raw metadata status")
    if record["provenance_classification"] not in PROVENANCE_CLASSES:
        raise ValueError("invalid provenance classification")
    if record["scientific_metrics_calculated"] is not False:
        raise ValueError("reconnaissance must not contain scientific metrics")


def _mat_field(value: Any, name: str, default: Any = None) -> Any:
    if hasattr(value, name):
        return getattr(value, name)
    names = getattr(getattr(value, "dtype", None), "names", None)
    if names and name in names:
        return value[name]
    return default


def _as_runs(value: Any) -> list[Any]:
    if isinstance(value, np.ndarray):
        return list(value.reshape(-1))
    return [value]


def _label_counts(values: Any) -> dict[str, int]:
    array = np.asarray(values).reshape(-1)
    return {str(key): int(count) for key, count in sorted(Counter(array.tolist()).items())}


def _inspect_lee_native(
    paths: list[str], payloads: list[dict] | None = None
) -> list[dict]:
    rows = []
    for physical_index, path in enumerate(paths, start=1):
        payload = (
            loadmat(path, squeeze_me=True, struct_as_record=False)
            if payloads is None
            else payloads[physical_index - 1]
        )
        for phase, key, ground_truth in (
            ("offline_train", "EEG_MI_train", True),
            ("online_test", "EEG_MI_test", False),
        ):
            value = payload.get(key)
            if (
                isinstance(value, np.ndarray)
                and value.dtype.names
                and value.size == 1
            ):
                value = value.reshape(-1)[0]
            if value is None:
                rows.append(
                    {
                        "physical_session_id": f"S{physical_index}",
                        "native_run_id": phase,
                        "source_path": str(Path(path).resolve()),
                        "native_observed_event_count": None,
                        "event_samples_unique": None,
                        "label_availability": "MISSING_NATIVE_STRUCTURE",
                    }
                )
                continue
            samples = np.asarray(_mat_field(value, "t", [])).reshape(-1)
            labels = np.asarray(_mat_field(value, "y_dec", [])).reshape(-1)
            rows.append(
                {
                    "physical_session_id": f"S{physical_index}",
                    "native_run_id": phase,
                    "source_path": str(Path(path).resolve()),
                    "native_observed_event_count": int(samples.size),
                    "event_samples_unique": bool(len(np.unique(samples)) == len(samples)),
                    "native_label_vector_count": int(labels.size),
                    "native_label_value_counts": _label_counts(labels) if labels.size else {},
                    "label_availability": (
                        "GROUND_TRUTH_LABELS_PRESENT"
                        if ground_truth
                        else "ONLINE_LABEL_SEMANTICS_UNRESOLVED"
                    ),
                    "sampling_rate": float(np.asarray(_mat_field(value, "fs")).item()),
                }
            )
    return rows


def _inspect_bnci_native(paths: list[str]) -> list[dict]:
    rows = []
    for path in paths:
        session_suffix = Path(path).stem[-1].upper()
        physical = {"A": "S1", "B": "S2", "C": "S3"}.get(
            session_suffix, f"UNKNOWN_{session_suffix}"
        )
        payload = loadmat(path, squeeze_me=True, struct_as_record=False)
        for run_index, run in enumerate(_as_runs(payload["data"])):
            samples = np.asarray(_mat_field(run, "trial", [])).reshape(-1)
            labels = np.asarray(_mat_field(run, "y", [])).reshape(-1)
            rows.append(
                {
                    "physical_session_id": physical,
                    "native_session_suffix": session_suffix,
                    "native_run_id": str(run_index),
                    "source_path": str(Path(path).resolve()),
                    "native_observed_event_count": int(samples.size),
                    "event_samples_unique": bool(len(np.unique(samples)) == len(samples)),
                    "native_label_vector_count": int(labels.size),
                    "native_label_value_counts": _label_counts(labels) if labels.size else {},
                    "label_availability": "GROUND_TRUTH_LABELS_PRESENT" if labels.size else "MISSING",
                    "sampling_rate": float(np.asarray(_mat_field(run, "fs")).item()),
                }
            )
    return rows


def _raw_events(raw: Any) -> tuple[np.ndarray, np.ndarray]:
    stim_indices = [
        index for index, channel_type in enumerate(raw.get_channel_types())
        if channel_type == "stim"
    ]
    if not stim_indices:
        return np.asarray([], dtype=np.int64), np.asarray([], dtype=np.int64)
    stim = raw.get_data(picks=stim_indices)
    combined = np.max(np.abs(stim), axis=0)
    samples = np.flatnonzero(combined != 0)
    codes = np.rint(stim[:, samples].sum(axis=0)).astype(np.int64)
    return samples.astype(np.int64), codes


def _inspect_framework_subject(
    dataset_id: str,
    subject: Any,
    sessions: dict,
    physical_mapping: dict[str, str],
) -> tuple[list[dict], list[str]]:
    rows = []
    identities = []
    for session_id in sorted(sessions, key=natural_key):
        physical = physical_mapping.get(str(session_id), f"UNRESOLVED_{session_id}")
        for run_id in sorted(sessions[session_id], key=natural_key):
            raw = sessions[session_id][run_id]
            samples, codes = _raw_events(raw)
            run_ids = [
                structural_trial_id(
                    dataset_id, subject, physical, run_id, int(sample), ordinal
                )
                for ordinal, sample in enumerate(samples)
            ]
            require_unique(run_ids, "trial IDs within run")
            identities.extend(run_ids)
            rows.append(
                {
                    "framework_session_id": str(session_id),
                    "physical_session_id": physical,
                    "framework_run_id": str(run_id),
                    "framework_observed_event_count": int(samples.size),
                    "framework_event_code_counts": _label_counts(codes),
                    "event_samples_unique": bool(len(np.unique(samples)) == len(samples)),
                    "sampling_rate": float(raw.info["sfreq"]),
                    "channel_count": int(len(raw.ch_names)),
                    "channel_names": list(raw.ch_names),
                    "channel_types": list(raw.get_channel_types()),
                    "recording_duration_seconds": float(raw.times[-1]) if len(raw.times) else 0.0,
                    "trial_identity_status": "DETERMINISTIC_UNIQUE_WITHIN_INSPECTED_STRUCTURE",
                }
            )
    require_unique(identities, "trial IDs across subject")
    return rows, identities


def _retention_rows(
    dataset_id: str,
    subject: Any,
    native_rows: list[dict],
    framework_rows: list[dict],
) -> list[dict]:
    framework_lookup = {
        (row["physical_session_id"], row["framework_run_id"]): row
        for row in framework_rows
    }
    rows = []
    for native in native_rows:
        run = native["native_run_id"]
        framework_run = run
        if dataset_id == "Lee2019_MI":
            framework_run = "1train" if run == "offline_train" else "4test"
        framework = framework_lookup.get((native["physical_session_id"], framework_run))
        native_count = native.get("native_observed_event_count")
        framework_count = None if framework is None else framework["framework_observed_event_count"]
        reason = classify_trial_loss(native_count, framework_count)
        rows.append(
            {
                "dataset_id": dataset_id,
                "subject_id": str(subject),
                "physical_session_id": native["physical_session_id"],
                "run_or_block_id": run,
                "documented_trial_count": 100 if dataset_id == "Lee2019_MI" else 200,
                "native_observed_event_count": native_count,
                "framework_observed_event_count": framework_count,
                "structurally_eligible_trial_count": (
                    native_count if reason == "NO_OBSERVED_LOSS" else "NOT_YET_DETERMINED"
                ),
                "scientifically_usable_trial_count": "NOT_YET_DETERMINED",
                "trial_loss_classification": reason,
                "trial_retention_status": (
                    "NO_OBSERVED_TRIAL_RETENTION_LOSS"
                    if reason == "NO_OBSERVED_LOSS"
                    else "TRIAL_RETENTION_DISCREPANCY"
                ),
                "label_availability": native.get("label_availability"),
            }
        )
    return rows


def lee_subject_session_matrix(subject_records: Iterable[dict]) -> list[dict]:
    """Summarize Lee physical-session/run availability without scientific roles."""
    rows = []
    for subject in sorted(subject_records, key=lambda item: natural_key(item["subject_id"])):
        native = {
            (item["physical_session_id"], item["native_run_id"]): item
            for item in subject["native_or_local_structure"]
        }
        framework = {
            (item["physical_session_id"], item["framework_run_id"]): item
            for item in subject["framework_structure"]
        }
        s1_offline = native.get(("S1", "offline_train"))
        s2_offline = native.get(("S2", "offline_train"))
        offline_pair = bool(
            s1_offline
            and s2_offline
            and s1_offline.get("label_availability") == "GROUND_TRUTH_LABELS_PRESENT"
            and s2_offline.get("label_availability") == "GROUND_TRUTH_LABELS_PRESENT"
        )
        session_ids = set(subject.get("framework_session_ids", []))
        rows.append(
            {
                "subject_id": subject["subject_id"],
                "session_1_available": "0" in session_ids,
                "session_2_available": "1" in session_ids,
                "session_1_offline_train_available": ("S1", "1train") in framework,
                "session_2_offline_train_available": ("S2", "1train") in framework,
                "session_1_online_test_available": ("S1", "4test") in framework,
                "session_2_online_test_available": ("S2", "4test") in framework,
                "offline_common_session_pair_available": offline_pair,
                "session_1_offline_event_count": (
                    None if s1_offline is None else s1_offline["native_observed_event_count"]
                ),
                "session_2_offline_event_count": (
                    None if s2_offline is None else s2_offline["native_observed_event_count"]
                ),
                "session_1_offline_class_counts": (
                    {} if s1_offline is None else s1_offline["native_label_value_counts"]
                ),
                "session_2_offline_class_counts": (
                    {} if s2_offline is None else s2_offline["native_label_value_counts"]
                ),
                "session_1_online_label_status": (
                    "MISSING" if native.get(("S1", "online_test")) is None
                    else native[("S1", "online_test")]["label_availability"]
                ),
                "session_2_online_label_status": (
                    "MISSING" if native.get(("S2", "online_test")) is None
                    else native[("S2", "online_test")]["label_availability"]
                ),
                "trial_identity_unique": subject.get("trial_identity_status")
                == "DETERMINISTIC_UNIQUE_WITHIN_INSPECTED_STRUCTURE",
                "session_mapping_status": (
                    "ABSTRACTION_RENAMING_ONLY"
                    if session_ids == {"0", "1"}
                    else "UNRESOLVED_SESSION_MAPPING"
                ),
                "run_mapping_status": (
                    "ABSTRACTION_RENAMING_ONLY"
                    if all(
                        key in framework
                        for key in (
                            ("S1", "1train"),
                            ("S1", "4test"),
                            ("S2", "1train"),
                            ("S2", "4test"),
                        )
                    )
                    else "UNRESOLVED_RUN_MAPPING"
                ),
            }
        )
    return rows


def lee_cohort_consistency_summary(record: dict, matrix: list[dict]) -> dict:
    """List every anomaly category explicitly rather than hiding aggregates."""
    retention_by_subject: dict[str, list[dict]] = {}
    for item in record["trial_retention_summary"]:
        retention_by_subject.setdefault(item["subject_id"], []).append(item)
    expected_channels = None
    channel_anomalies = []
    sampling_anomalies = []
    for subject in record["subject_records"]:
        structures = subject["framework_structure"]
        for item in structures:
            channels = item["channel_names"]
            if expected_channels is None:
                expected_channels = channels
            if channels != expected_channels:
                channel_anomalies.append(subject["subject_id"])
            if item["sampling_rate"] != 1000.0:
                sampling_anomalies.append(subject["subject_id"])
    missing_sessions = [
        row["subject_id"]
        for row in matrix
        if not (row["session_1_available"] and row["session_2_available"])
    ]
    missing_runs = [
        row["subject_id"]
        for row in matrix
        if not all(
            row[key]
            for key in (
                "session_1_offline_train_available",
                "session_2_offline_train_available",
                "session_1_online_test_available",
                "session_2_online_test_available",
            )
        )
    ]
    count_discrepancies = [
        subject
        for subject, rows in retention_by_subject.items()
        if any(item["trial_loss_classification"] != "NO_OBSERVED_LOSS" for item in rows)
    ]
    ambiguous_ids = [
        row["subject_id"] for row in matrix if not row["trial_identity_unique"]
    ]
    unresolved_sessions = [
        row["subject_id"]
        for row in matrix
        if row["session_mapping_status"] != "ABSTRACTION_RENAMING_ONLY"
    ]
    structural_anomalies = sorted(
        set(
            missing_sessions
            + missing_runs
            + count_discrepancies
            + ambiguous_ids
            + unresolved_sessions
            + channel_anomalies
            + sampling_anomalies
        ),
        key=natural_key,
    )
    return {
        "total_subjects_exposed": record["framework_dataset_metadata"][
            "framework_subject_count"
        ],
        "total_subjects_inspected": len(record["inspected_subjects"]),
        "subjects_with_verified_s1": sum(row["session_1_available"] for row in matrix),
        "subjects_with_verified_s2": sum(row["session_2_available"] for row in matrix),
        "subjects_with_verified_s1_s2": sum(
            row["session_1_available"] and row["session_2_available"] for row in matrix
        ),
        "subjects_with_verified_labeled_offline_s1_s2": sum(
            row["offline_common_session_pair_available"] for row in matrix
        ),
        "subjects_with_expected_100_offline_events_s1": sum(
            row["session_1_offline_event_count"] == 100 for row in matrix
        ),
        "subjects_with_expected_100_offline_events_s2": sum(
            row["session_2_offline_event_count"] == 100 for row in matrix
        ),
        "subjects_with_structural_anomalies": structural_anomalies,
        "subjects_with_trial_count_discrepancies": sorted(
            count_discrepancies, key=natural_key
        ),
        "subjects_with_ambiguous_trial_identities": sorted(ambiguous_ids, key=natural_key),
        "subjects_with_unresolved_session_mappings": sorted(
            unresolved_sessions, key=natural_key
        ),
        "subjects_with_missing_sessions": sorted(missing_sessions, key=natural_key),
        "subjects_with_missing_runs": sorted(missing_runs, key=natural_key),
        "subjects_with_channel_count_or_order_anomalies": sorted(
            set(channel_anomalies), key=natural_key
        ),
        "subjects_with_sampling_rate_anomalies": sorted(
            set(sampling_anomalies), key=natural_key
        ),
        "total_structural_trial_identities_checked": sum(
            item["trial_identity_count"] for item in record["subject_records"]
        ),
    }


def write_lee_matrix_csv(path: Path, matrix: list[dict]) -> None:
    """Write the provenance matrix with JSON-encoded class-count cells."""
    if not matrix:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(matrix[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in matrix:
            serialized = dict(row)
            for key in ("session_1_offline_class_counts", "session_2_offline_class_counts"):
                serialized[key] = json.dumps(serialized[key], sort_keys=True)
            writer.writerow(serialized)


def _dataset_instance(dataset_key: str):
    if dataset_key == "lee2019_mi":
        from moabb.datasets import Lee2019_MI

        return Lee2019_MI(train_run=True, test_run=True)
    if dataset_key == "bnci2015_001":
        from moabb.datasets import BNCI2015_001

        return BNCI2015_001()
    raise ValueError(f"unsupported dataset: {dataset_key}")


def _framework_metadata(dataset: Any) -> dict:
    return {
        "moabb_version": importlib.metadata.version("moabb"),
        "mne_version": importlib.metadata.version("mne"),
        "dataset_class": f"{dataset.__class__.__module__}.{dataset.__class__.__name__}",
        "dataset_code": str(dataset.code),
        "framework_subject_list": [str(value) for value in dataset.subject_list],
        "framework_subject_count": int(len(dataset.subject_list)),
        "class_event_mapping": {str(k): int(v) for k, v in dataset.event_id.items()},
        "declared_sessions_per_subject": int(dataset.n_sessions),
        "declared_interval_seconds": [float(value) for value in dataset.interval],
    }


def inspect_dataset(
    dataset_key: str,
    subjects: list[Any],
    data_root: Path,
    output_path: Path,
    resume: bool = False,
) -> dict:
    """Inspect selected subjects and persist after every subject."""
    dataset = _dataset_instance(dataset_key)
    dataset_id = DATASET_ALIASES[dataset_key]
    invalid = sorted(set(subjects) - set(dataset.subject_list), key=natural_key)
    if invalid:
        raise ValueError(f"invalid subjects for {dataset_id}: {invalid}")

    data_root.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_argument = moabb_relative_cache_argument(data_root)
    legacy_root = legacy_sanitized_cache_root(data_root)
    record = {
        "dataset_id": dataset_id,
        "dataset_class": f"{dataset.__class__.__module__}.{dataset.__class__.__name__}",
        "documentation_status": "DOCUMENTATION_ELIGIBLE",
        "raw_metadata_status": "RAW_METADATA_VERIFICATION_PARTIAL",
        "provenance_classification": "PROVENANCE_INCOMPLETE",
        "framework_dataset_metadata": _framework_metadata(dataset),
        "requested_subjects": [str(value) for value in subjects],
        "inspected_subjects": [],
        "subject_records": [],
        "trial_retention_summary": [],
        "subject_session_availability": None,
        "common_session_pair_coverage": None,
        "download_or_cache_root": str(data_root.resolve()),
        "cache_path_audit": {
            "requested_absolute_root": str(data_root.resolve()),
            "moabb_path_argument": cache_argument,
            "effective_new_download_root": str(data_root.resolve()),
            "effective_mne_data_environment": os.environ.get("MNE_DATA"),
            "effective_lee_dataset_environment": os.environ.get(
                "MNE_DATASETS_LEE2019-MI_PATH"
            ),
            "effective_bnci_dataset_environment": os.environ.get(
                "MNE_DATASETS_BNCI_PATH"
            ),
            "legacy_sanitized_root": str(legacy_root.resolve()),
            "legacy_root_policy": "READ_ONLY_REUSE_NO_MOVE_NO_DELETE_NO_REDOWNLOAD",
            "root_cause": (
                "MOABB_1_5_DATA_DL_SANITIZED_WINDOWS_DRIVE_COLON_IN_FULL_"
                "DESTINATION_AND_PRODUCED_A_RELATIVE_PATH"
            ),
        },
        "scientific_metrics_calculated": False,
        "scientific_preprocessing_applied": False,
        "replication_feasibility_status": "PENDING_HUMAN_DECISION",
        "issues": [],
    }

    if resume and output_path.exists():
        previous = json.loads(output_path.read_text(encoding="utf-8"))
        if previous.get("dataset_id") != dataset_id:
            raise ValueError("resume artifact belongs to a different dataset")
        record.update(previous)
        record["requested_subjects"] = [str(value) for value in subjects]
        record["framework_dataset_metadata"] = _framework_metadata(dataset)
        record["cache_path_audit"] = {
            "requested_absolute_root": str(data_root.resolve()),
            "moabb_path_argument": cache_argument,
            "effective_new_download_root": str(data_root.resolve()),
            "effective_mne_data_environment": os.environ.get("MNE_DATA"),
            "effective_lee_dataset_environment": os.environ.get(
                "MNE_DATASETS_LEE2019-MI_PATH"
            ),
            "effective_bnci_dataset_environment": os.environ.get(
                "MNE_DATASETS_BNCI_PATH"
            ),
            "legacy_sanitized_root": str(legacy_root.resolve()),
            "legacy_root_policy": "READ_ONLY_REUSE_NO_MOVE_NO_DELETE_NO_REDOWNLOAD",
            "root_cause": (
                "MOABB_1_5_DATA_DL_SANITIZED_WINDOWS_DRIVE_COLON_IN_FULL_"
                "DESTINATION_AND_PRODUCED_A_RELATIVE_PATH"
            ),
        }

    subject_sessions: dict[str, list[str]] = {
        item["subject_id"]: item["framework_session_ids"]
        for item in record["subject_records"]
    }
    inspected = set(record["inspected_subjects"])
    for subject in subjects:
        if str(subject) in inspected:
            continue
        if dataset_key == "lee2019_mi":
            paths = _existing_lee_subject_paths(
                subject, (data_root.resolve(), legacy_root.resolve())
            )
            cache_source = "REUSED_EXISTING_COMPLETE_SUBJECT_PAIR"
            if paths is None:
                paths = dataset.data_path(subject, path=cache_argument, verbose=False)
                cache_source = "INTENTIONAL_RECON_CACHE_ROOT"
            payloads = [loadmat(path) for path in paths]
            native = _inspect_lee_native(paths, payloads)
            mapping = {"0": "S1", "1": "S2"}
            sessions = {}
            for index, payload in enumerate(payloads):
                session = str(index)
                sessions[session] = {
                    "1train": dataset._get_single_run(payload["EEG_MI_train"][0, 0]),
                    "4test": dataset._get_single_run(payload["EEG_MI_test"][0, 0]),
                }
        else:
            paths = dataset.data_path(subject, path=cache_argument, verbose=False)
            cache_source = "INTENTIONAL_RECON_CACHE_ROOT"
            from moabb.datasets.bnci.bnci_2015 import _load_data_001_2015

            sessions = _load_data_001_2015(
                subject,
                path=str(data_root.resolve()),
                force_update=False,
                update_path=False,
                verbose=False,
            )
            native = _inspect_bnci_native(paths)
            mapping = {"0A": "S1", "1B": "S2", "2C": "S3"}
        framework, identities = _inspect_framework_subject(
            dataset_id, subject, sessions, mapping
        )
        retention = _retention_rows(dataset_id, subject, native, framework)
        session_ids = sorted(sessions, key=natural_key)
        subject_sessions[str(subject)] = session_ids
        record["subject_records"].append(
            {
                "subject_id": str(subject),
                "source_paths": [str(Path(path).resolve()) for path in paths],
                "cache_source": cache_source,
                "native_or_local_structure": native,
                "framework_structure": framework,
                "framework_session_ids": session_ids,
                "trial_identity_count": len(identities),
                "trial_identity_status": "DETERMINISTIC_UNIQUE_WITHIN_INSPECTED_STRUCTURE",
            }
        )
        record["trial_retention_summary"].extend(retention)
        record["inspected_subjects"].append(str(subject))
        output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    if dataset_key == "lee2019_mi":
        matrix = lee_subject_session_matrix(record["subject_records"])
        record["subject_session_availability"] = matrix
        record["cohort_consistency_summary"] = lee_cohort_consistency_summary(
            record, matrix
        )
        write_lee_matrix_csv(
            output_path.parent / "lee2019_mi_subject_session_matrix.csv", matrix
        )

    if dataset_key == "bnci2015_001":
        availability = session_availability_matrix(
            subject_sessions, {"0A": "S1", "1B": "S2", "2C": "S3"}
        )
        for row in availability["rows"]:
            row["framework_session_ids"] = row.pop("native_session_ids")
            subject_record = next(
                item
                for item in record["subject_records"]
                if item["subject_id"] == row["subject_id"]
            )
            row["native_session_ids"] = sorted(
                {
                    item["native_session_suffix"]
                    for item in subject_record["native_or_local_structure"]
                },
                key=natural_key,
            )
            row["session_mapping_status"] = "PROVISIONALLY_CONSISTENT_WITH_NATIVE_SUFFIX"
        record["subject_session_availability"] = availability["rows"]
        record["common_session_pair_coverage"] = {
            "subjects_with_physical_s1": availability["coverage"].get("S1", 0),
            "subjects_with_physical_s2": availability["coverage"].get("S2", 0),
            "subjects_with_physical_s3": availability["coverage"].get("S3", 0),
            "subjects_with_verified_common_s1_s2": availability["verified_common_s1_s2"],
            "subjects_with_verified_s1_s2_s3": availability["verified_common_s1_s2_s3"],
            "structural_status": "PRIMARY_COMMON_SESSION_PAIR_STRUCTURALLY_POSSIBLE",
            "extra_session_condition_status": "TO_BE_VERIFIED",
            "scientific_session_role_decision": "PENDING_HUMAN_DECISION",
        }

    all_requested = len(record["inspected_subjects"]) == len(dataset.subject_list)
    no_loss = all(
        row["trial_loss_classification"] == "NO_OBSERVED_LOSS"
        for row in record["trial_retention_summary"]
    )
    if all_requested and no_loss:
        record["raw_metadata_status"] = "RAW_METADATA_VERIFIED"
        classification, issues = classify_dataset_provenance(
            dataset_key,
            True,
            record["framework_dataset_metadata"]["declared_sessions_per_subject"],
            (len(value) for value in subject_sessions.values()),
        )
        record["provenance_classification"] = classification
        record["issues"].extend(issues)
        if dataset_key == "lee2019_mi":
            anomalies = record["cohort_consistency_summary"][
                "subjects_with_structural_anomalies"
            ]
            if anomalies:
                record["provenance_classification"] = "REPLICATION_BLOCKING_MISMATCH"
                record["issues"].append(
                    "STRUCTURAL_ANOMALIES_REQUIRE_HUMAN_REVIEW:" + ",".join(anomalies)
                )
            else:
                issue = (
                    "NO_COHORT_WIDE_STRUCTURAL_BLOCKER_OBSERVED_UNDER_INSPECTED_METADATA"
                )
                if issue not in record["issues"]:
                    record["issues"].append(issue)
    else:
        record["raw_metadata_status"] = "RAW_METADATA_VERIFICATION_PARTIAL"
        record["provenance_classification"] = "PROVENANCE_INCOMPLETE"
    validate_recon_record(record)
    output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def write_recon_summary(output_dir: Path) -> Path | None:
    """Write a compact structural-only index when both candidate outputs exist."""
    paths = {
        "Lee2019_MI": (
            output_dir / "lee2019_mi_cohort_provenance.json"
            if (output_dir / "lee2019_mi_cohort_provenance.json").exists()
            else output_dir / "lee2019_mi_provenance.json"
        ),
        "BNCI2015-001": output_dir / "bnci2015_001_provenance.json",
    }
    if not all(path.exists() for path in paths.values()):
        return None
    datasets = []
    for dataset_id, path in paths.items():
        record = json.loads(path.read_text(encoding="utf-8"))
        datasets.append(
            {
                "dataset_id": dataset_id,
                "raw_metadata_status": record["raw_metadata_status"],
                "provenance_classification": record["provenance_classification"],
                "inspected_subject_count": len(record["inspected_subjects"]),
                "framework_subject_count": record["framework_dataset_metadata"][
                    "framework_subject_count"
                ],
                "replication_feasibility_status": "PENDING_HUMAN_DECISION",
                "active_phase_a_candidate": True,
                "final_dataset_selection": "PENDING_HUMAN_DECISION",
                **(
                    {
                        "common_s1_s2_human_review_status": (
                            "STRUCTURALLY_ACCEPTABLE_FOR_CONTINUED_CONSIDERATION"
                        ),
                        "s3_assignment_condition": "S3_ASSIGNMENT_CONDITION_UNKNOWN",
                        "s3_primary_analysis_status": "NOT_AUTOMATICALLY_INCLUDED",
                    }
                    if dataset_id == "BNCI2015-001"
                    else {
                        "cohort_reconnaissance_status": (
                            "COMPLETE"
                            if len(record["inspected_subjects"])
                            == record["framework_dataset_metadata"][
                                "framework_subject_count"
                            ]
                            else "PARTIAL"
                        )
                    }
                ),
            }
        )
    summary = {
        "artifact_type": "STRUCTURAL_PROVENANCE_ONLY",
        "datasets": datasets,
        "scientific_metrics_calculated": False,
        "scientific_preprocessing_applied": False,
        "final_dataset_selection": "PENDING_HUMAN_DECISION",
    }
    path = output_dir / "recon_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return path


def parse_subjects(values: list[str] | None, available: list[Any]) -> list[Any]:
    if not values or values == ["all"]:
        return list(available)
    lookup = {str(value): value for value in available}
    missing = sorted(set(values) - set(lookup), key=natural_key)
    if missing:
        raise ValueError(f"unknown subject identifiers: {missing}")
    return [lookup[value] for value in values]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=sorted(DATASET_ALIASES),
        required=True,
    )
    parser.add_argument("--subjects", nargs="+", default=["all"])
    parser.add_argument("--data-root", type=Path, default=Path("data/external_recon"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/external_boundary_recon")
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted cohort artifact and skip inspected subjects.",
    )
    args = parser.parse_args()

    os.environ.setdefault("MNE_DONTWRITE_HOME", "true")
    os.environ.setdefault("MNE_LOGGING_LEVEL", "WARNING")
    # On Windows MNE resolves USERPROFILE before MNE_DONTWRITE_HOME. Keep its
    # config lock and dataset keys inside the isolated reconnaissance root.
    config_root = (args.data_root / ".mne_config").resolve()
    config_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(config_root))
    intentional_root = str(args.data_root.resolve())
    os.environ["MNE_DATA"] = intentional_root
    os.environ["MNE_DATASETS_LEE2019-MI_PATH"] = intentional_root
    os.environ["MNE_DATASETS_BNCI_PATH"] = intentional_root
    dataset = _dataset_instance(args.dataset)
    subjects = parse_subjects(args.subjects, dataset.subject_list)
    output_name = (
        "lee2019_mi_cohort_provenance.json"
        if args.dataset == "lee2019_mi" and len(subjects) == len(dataset.subject_list)
        else "lee2019_mi_provenance.json"
        if args.dataset == "lee2019_mi"
        else "bnci2015_001_provenance.json"
    )
    record = inspect_dataset(
        args.dataset,
        subjects,
        args.data_root,
        args.output_dir / output_name,
        resume=args.resume,
    )
    write_recon_summary(args.output_dir)
    print(
        json.dumps(
            {
                "dataset_id": record["dataset_id"],
                "raw_metadata_status": record["raw_metadata_status"],
                "provenance_classification": record["provenance_classification"],
                "inspected_subject_count": len(record["inspected_subjects"]),
                "output": str((args.output_dir / output_name).resolve()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
