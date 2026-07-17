"""
Configurable training pipeline for NAP-EEG-Mini.

This script trains EEGNet on a synthetic EEG dataset and optionally runs
a simple artifact channel masking audit.

This is still a pipeline smoke test, not a real EEG experiment.
"""

import argparse
import copy
import csv
import json
import os
import random
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader, TensorDataset, random_split

from src.audit import evaluate_channel_masking
from src.audit import summarize_channel_masking_audit
from src.datasets import SyntheticEEGDataset
from src.data import load_bci2a_subject
from src.evaluate import evaluate_classifier
from src.models.eegnet import EEGNet


@dataclass
class DataBundle:
    """Dataloaders and reproducibility metadata for one training run."""

    train_loader: DataLoader
    val_loader: DataLoader
    test_loader: DataLoader | None
    train_indices: list[int]
    val_indices: list[int]
    test_indices: list[int]
    normalization: dict | None


def set_seed(seed: int) -> torch.Generator:
    """Seed Python, NumPy, PyTorch, CUDA, and cuDNN determinism knobs."""

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    return torch.Generator().manual_seed(seed)


def load_config(config_path):
    """
    Load a YAML configuration file.

    Parameters
    ----------
    config_path : str
        Path to the YAML config file.

    Returns
    -------
    dict
        Loaded configuration dictionary.
    """

    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    return config


def train_one_epoch(model, dataloader, criterion, optimizer, device):
    """
    Train the model for one epoch.

    Parameters
    ----------
    model : torch.nn.Module
        EEG classification model.
    dataloader : torch.utils.data.DataLoader
        Training dataloader.
    criterion : torch.nn.Module
        Loss function.
    optimizer : torch.optim.Optimizer
        Optimizer.
    device : torch.device
        Training device.

    Returns
    -------
    tuple
        A tuple containing average loss and accuracy.
    """

    model.train()

    total_loss = 0.0
    correct = 0
    total = 0

    for x, y in dataloader:
        x = x.to(device)
        y = y.to(device)

        optimizer.zero_grad()

        logits = model(x)
        loss = criterion(logits, y)

        loss.backward()
        optimizer.step()

        total_loss += loss.item() * x.size(0)

        predictions = torch.argmax(logits, dim=1)
        correct += (predictions == y).sum().item()
        total += y.size(0)

    average_loss = total_loss / total
    accuracy = correct / total

    return average_loss, accuracy


def build_dataloaders(config):
    """
    Build training and validation dataloaders.

    Synthetic data and BCI Competition IV 2a are supported.
    For BCI2a, only the official training session is split into
    training and validation subsets. The official test session
    remains untouched.
    """

    data_config = config["data"]
    training_config = config["training"]

    dataset_name = data_config.get("name", "synthetic").lower()
    seed = config["seed"]
    train_ratio = data_config.get("train_ratio", 0.8)
    test_dataset = None
    test_indices = []
    normalization = None

    if dataset_name == "synthetic":
        dataset = SyntheticEEGDataset(
            num_trials=data_config["num_trials"],
            num_channels=data_config["num_channels"],
            num_samples=data_config["num_samples"],
            num_classes=data_config["num_classes"],
            seed=seed,
        )

        train_size = int(train_ratio * len(dataset))
        val_size = len(dataset) - train_size

        train_dataset, val_dataset = random_split(
            dataset,
            [train_size, val_size],
            generator=torch.Generator().manual_seed(seed),
        )
        train_indices = [int(index) for index in train_dataset.indices]
        val_indices = [int(index) for index in val_dataset.indices]

        print("Dataset source: synthetic EEG")
        print(f"Training trials: {train_size}")
        print(f"Validation trials: {val_size}")

    elif dataset_name in {"bci2a", "bci_iv_2a"}:
        subject_data = load_bci2a_subject(
            subject_id=data_config["subject_id"],
            data_dir=data_config.get("data_dir", "data/moabb"),
            fmin=data_config.get("fmin", 8.0),
            fmax=data_config.get("fmax", 32.0),
            tmin=data_config.get("tmin", 0.0),
            tmax=data_config.get("tmax", 4.0),
        )

        x = torch.from_numpy(subject_data.x_train).float()
        y = torch.from_numpy(subject_data.y_train).long()

        num_trials = x.shape[0]
        train_size = int(train_ratio * num_trials)
        val_size = num_trials - train_size

        if train_size <= 0 or val_size <= 0:
            raise ValueError(
                f"Invalid train/validation split: "
                f"train={train_size}, val={val_size}"
            )

        generator = torch.Generator().manual_seed(seed)
        shuffled_indices = torch.randperm(
            num_trials,
            generator=generator,
        )

        train_indices = shuffled_indices[:train_size]
        val_indices = shuffled_indices[train_size:]

        x_train = x[train_indices]
        y_train = y[train_indices]

        x_val = x[val_indices]
        y_val = y[val_indices]
        x_test = torch.from_numpy(subject_data.x_test).float()
        y_test = torch.from_numpy(subject_data.y_test).long()

        if data_config.get("normalize", True):
            channel_mean = x_train.mean(
                dim=(0, 2),
                keepdim=True,
            )
            channel_std = x_train.std(
                dim=(0, 2),
                keepdim=True,
            ).clamp_min(1e-6)

            x_train = (x_train - channel_mean) / channel_std
            x_val = (x_val - channel_mean) / channel_std
            x_test = (x_test - channel_mean) / channel_std
            normalization = {
                "source": "train_subset",
                "mean": channel_mean.squeeze().cpu().tolist(),
                "std": channel_std.squeeze().cpu().tolist(),
            }

        train_dataset = TensorDataset(x_train, y_train)
        val_dataset = TensorDataset(x_val, y_val)
        test_dataset = TensorDataset(x_test, y_test)
        train_indices = [int(index) for index in train_indices.tolist()]
        val_indices = [int(index) for index in val_indices.tolist()]
        test_indices = list(range(int(subject_data.x_test.shape[0])))

        # The model is built after this function, so update the
        # dimensions using the actual loaded data.
        data_config["num_channels"] = int(x.shape[1])
        data_config["num_samples"] = int(x.shape[2])
        data_config["num_classes"] = 4

        print("Dataset source: BCI Competition IV 2a")
        print(f"Subject: A{data_config['subject_id']:02d}")
        print(f"Official train shape: {tuple(subject_data.x_train.shape)}")
        print(f"Official test shape:  {tuple(subject_data.x_test.shape)}")
        print(f"Training trials: {train_size}")
        print(f"Validation trials: {val_size}")
        print(f"Test trials: {subject_data.x_test.shape[0]}")
        print(f"Channels: {data_config['num_channels']}")
        print(f"Samples per trial: {data_config['num_samples']}")
        print(f"Sampling rate: {subject_data.sampling_rate}")
        print("Official test session is not used during training.")

    else:
        raise ValueError(
            f"Unsupported dataset name: {dataset_name}"
        )

    train_loader = DataLoader(
        train_dataset,
        batch_size=training_config["batch_size"],
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=training_config["batch_size"],
        shuffle=False,
    )

    test_loader = None
    if test_dataset is not None:
        test_loader = DataLoader(
            test_dataset,
            batch_size=training_config["batch_size"],
            shuffle=False,
        )

    return DataBundle(
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        train_indices=train_indices,
        val_indices=val_indices,
        test_indices=test_indices,
        normalization=normalization,
    )


def build_model(config):
    """
    Build EEGNet model from config.

    Parameters
    ----------
    config : dict
        Configuration dictionary.

    Returns
    -------
    torch.nn.Module
        EEGNet model.
    """

    data_config = config["data"]
    model_config = config["model"]

    if model_config["name"] != "eegnet":
        raise ValueError(f"Unsupported model name: {model_config['name']}")

    model = EEGNet(
        num_channels=data_config["num_channels"],
        num_samples=data_config["num_samples"],
        num_classes=data_config["num_classes"],
        f1=model_config["f1"],
        d=model_config["d"],
        f2=model_config["f2"],
        kernel_length=model_config["kernel_length"],
        dropout=model_config["dropout"],
    )

    return model


def save_training_history(history, config):
    """
    Save training history to a CSV file.

    Parameters
    ----------
    history : list
        List of dictionaries containing epoch-level metrics.
    config : dict
        Configuration dictionary.
    """

    output_config = config["output"]
    table_dir = output_config["table_dir"]
    output_path = os.path.join(
        table_dir,
        output_config["training_history_file"],
    )

    os.makedirs(table_dir, exist_ok=True)

    fieldnames = [
        "epoch",
        "train_loss",
        "train_accuracy",
        "val_loss",
        "val_accuracy",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row in history:
            writer.writerow(row)

    print(f"Saved training history to: {output_path}")


def get_output_path(config, key, default_filename):
    """Resolve an output filename inside the configured table directory."""

    output_config = config["output"]
    table_dir = output_config["table_dir"]
    return os.path.join(
        table_dir,
        output_config.get(key, default_filename),
    )


def save_json(payload, output_path, message):
    """Save a JSON artifact with stable formatting."""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write("\n")

    print(f"{message}: {output_path}")


def save_yaml(payload, output_path, message):
    """Save a YAML artifact with the final resolved configuration."""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        yaml.safe_dump(payload, file, sort_keys=True)

    print(f"{message}: {output_path}")


def save_split_indices(data_bundle, config):
    """Save train/validation/test indices used by this run."""

    output_path = get_output_path(
        config,
        "split_indices_file",
        "split_indices.json",
    )
    payload = {
        "train_indices": data_bundle.train_indices,
        "validation_indices": data_bundle.val_indices,
        "test_indices": data_bundle.test_indices,
    }
    save_json(payload, output_path, "Saved split indices")


def save_resolved_config(config):
    """Save the final parsed config after dataset-derived fields are resolved."""

    output_path = get_output_path(
        config,
        "resolved_config_file",
        "resolved_config.yaml",
    )
    save_yaml(config, output_path, "Saved resolved config")


def save_run_summary(summary, config):
    """Save best validation and final test metrics."""

    output_path = get_output_path(
        config,
        "run_summary_file",
        "run_summary.json",
    )
    save_json(summary, output_path, "Saved run summary")


def get_checkpoint_path(config):
    """Resolve the best-validation checkpoint path."""

    return get_output_path(
        config,
        "best_checkpoint_file",
        "best_validation_checkpoint.pt",
    )


def save_best_checkpoint(model, epoch, val_loss, val_accuracy, config):
    """Persist the best validation model state."""

    checkpoint_path = get_checkpoint_path(config)
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)

    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": copy.deepcopy(model.state_dict()),
            "best_validation_metrics": {
                "loss": val_loss,
                "accuracy": val_accuracy,
            },
            "config": copy.deepcopy(config),
        },
        checkpoint_path,
    )

    return checkpoint_path


def restore_best_checkpoint(model, config, device):
    """Load the best validation checkpoint back into the model."""

    checkpoint_path = get_checkpoint_path(config)
    checkpoint = torch.load(
        checkpoint_path,
        map_location=device,
    )
    model.load_state_dict(checkpoint["model_state_dict"])

    return checkpoint


def save_audit_summary(summary, config):
    """
    Save artifact audit summary to a CSV file.

    Parameters
    ----------
    summary : dict
        Audit summary dictionary.
    config : dict
        Configuration dictionary.
    """

    output_config = config["output"]
    table_dir = output_config["table_dir"]
    output_path = os.path.join(
        table_dir,
        output_config["audit_summary_file"],
    )

    os.makedirs(table_dir, exist_ok=True)

    fieldnames = [
        "masked_channels",
        "clean_accuracy",
        "masked_accuracy",
        "accuracy_drop",
        "relative_drop",
        "masked_loss",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(summary)

    print(f"Saved audit summary to: {output_path}")


def run_artifact_audit(model, val_loader, criterion, device, config, clean_val_acc):
    """
    Run a simple artifact channel masking audit.

    Parameters
    ----------
    model : torch.nn.Module
        Trained EEG classification model.
    val_loader : torch.utils.data.DataLoader
        Validation dataloader.
    criterion : torch.nn.Module
        Loss function.
    device : torch.device
        Evaluation device.
    config : dict
        Configuration dictionary.
    clean_val_acc : float
        Validation accuracy without channel masking.

    Returns
    -------
    dict or None
        Audit summary if audit is enabled, otherwise None.
    """

    audit_config = config.get("audit", {})

    if not audit_config.get("enabled", False):
        return None

    artifact_channels = audit_config.get("artifact_channels", [])

    masked_val_loss, masked_val_acc = evaluate_channel_masking(
        model=model,
        dataloader=val_loader,
        criterion=criterion,
        device=device,
        channel_indices=artifact_channels,
    )

    summary = summarize_channel_masking_audit(
        clean_accuracy=clean_val_acc,
        masked_accuracy=masked_val_acc,
    )

    summary["masked_channels"] = str(artifact_channels)
    summary["masked_loss"] = masked_val_loss

    print("")
    print("Artifact channel masking audit")
    print("--------------------------------")
    print(f"Masked channels: {artifact_channels}")
    print(f"Clean val acc:   {summary['clean_accuracy']:.4f}")
    print(f"Masked val acc:  {summary['masked_accuracy']:.4f}")
    print(f"Accuracy drop:   {summary['accuracy_drop']:.4f}")
    print(f"Relative drop:   {summary['relative_drop']:.4f}")
    print(f"Masked val loss: {masked_val_loss:.4f}")

    return summary


def is_better_validation_result(
    val_accuracy,
    val_loss,
    best_val_accuracy,
    best_val_loss,
):
    """Use validation accuracy, then validation loss, for model selection."""

    if val_accuracy > best_val_accuracy:
        return True

    if val_accuracy == best_val_accuracy and val_loss < best_val_loss:
        return True

    return False


def run_training(
    config,
    device=None,
    train_epoch_fn=train_one_epoch,
    evaluate_fn=evaluate_classifier,
):
    """Run training, checkpoint the best validation model, then test once."""

    set_seed(config["seed"])

    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    data_bundle = build_dataloaders(config)
    save_split_indices(data_bundle, config)
    save_resolved_config(config)

    model = build_model(config).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=config["training"]["learning_rate"],
        weight_decay=config["training"].get("weight_decay", 0.0),
    )

    history = []
    best_epoch = None
    best_val_loss = float("inf")
    best_val_accuracy = -float("inf")
    checkpoint_path = None

    for epoch in range(1, config["training"]["epochs"] + 1):
        train_loss, train_acc = train_epoch_fn(
            model,
            data_bundle.train_loader,
            criterion,
            optimizer,
            device,
        )

        val_loss, val_acc = evaluate_fn(
            model,
            data_bundle.val_loader,
            criterion,
            device,
        )

        epoch_result = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_accuracy": train_acc,
            "val_loss": val_loss,
            "val_accuracy": val_acc,
        }

        history.append(epoch_result)

        if is_better_validation_result(
            val_accuracy=val_acc,
            val_loss=val_loss,
            best_val_accuracy=best_val_accuracy,
            best_val_loss=best_val_loss,
        ):
            best_epoch = epoch
            best_val_loss = val_loss
            best_val_accuracy = val_acc
            checkpoint_path = save_best_checkpoint(
                model=model,
                epoch=epoch,
                val_loss=val_loss,
                val_accuracy=val_acc,
                config=config,
            )

        print(
            f"Epoch {epoch:02d} | "
            f"train loss: {train_loss:.4f} | "
            f"train acc: {train_acc:.4f} | "
            f"val loss: {val_loss:.4f} | "
            f"val acc: {val_acc:.4f}"
        )

    if best_epoch is None:
        raise RuntimeError("No best validation checkpoint was created.")

    checkpoint = restore_best_checkpoint(
        model=model,
        config=config,
        device=device,
    )
    best_validation_metrics = checkpoint["best_validation_metrics"]

    final_test_metrics = None
    if data_bundle.test_loader is not None:
        test_loss, test_acc = evaluate_fn(
            model,
            data_bundle.test_loader,
            criterion,
            device,
        )
        final_test_metrics = {
            "loss": test_loss,
            "accuracy": test_acc,
        }
        print(
            "Final official test | "
            f"loss: {test_loss:.4f} | "
            f"acc: {test_acc:.4f}"
        )

    summary = {
        "best_epoch": best_epoch,
        "best_validation_metrics": best_validation_metrics,
        "final_test_metrics": final_test_metrics,
        "best_checkpoint": checkpoint_path,
        "normalization": data_bundle.normalization,
    }
    save_run_summary(summary, config)

    return {
        "model": model,
        "data_bundle": data_bundle,
        "history": history,
        "summary": summary,
        "criterion": criterion,
        "device": device,
    }


def main():
    """
    Run a configurable EEGNet training smoke test.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        default="configs/baseline.yaml",
        help="Path to YAML configuration file.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"Using device: {device}")
    print(f"Using config: {args.config}")
    print("Starting configurable EEGNet training smoke test...")

    result = run_training(config=config, device=device)

    print("Training smoke test finished.")

    save_training_history(result["history"], config)

    audit_summary = run_artifact_audit(
        model=result["model"],
        val_loader=result["data_bundle"].val_loader,
        criterion=result["criterion"],
        device=result["device"],
        config=config,
        clean_val_acc=result["summary"]["best_validation_metrics"]["accuracy"],
    )

    if audit_summary is not None:
        save_audit_summary(audit_summary, config)


if __name__ == "__main__":
    main()
