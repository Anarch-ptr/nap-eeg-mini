"""
Configurable training pipeline for NAP-EEG-Mini.

This script trains EEGNet on a synthetic EEG dataset and optionally runs
a simple artifact channel masking audit.

This is still a pipeline smoke test, not a real EEG experiment.
"""

import argparse
import csv
import os

import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader, random_split

from src.audit import evaluate_channel_masking
from src.audit import summarize_channel_masking_audit
from src.datasets import SyntheticEEGDataset
from src.evaluate import evaluate_classifier
from src.models.eegnet import EEGNet


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
    Build train and validation dataloaders from config.

    Parameters
    ----------
    config : dict
        Configuration dictionary.

    Returns
    -------
    tuple
        Train and validation dataloaders.
    """

    data_config = config["data"]
    training_config = config["training"]

    dataset = SyntheticEEGDataset(
        num_trials=data_config["num_trials"],
        num_channels=data_config["num_channels"],
        num_samples=data_config["num_samples"],
        num_classes=data_config["num_classes"],
        seed=config["seed"],
    )

    train_size = int(data_config["train_ratio"] * len(dataset))
    val_size = len(dataset) - train_size

    train_dataset, val_dataset = random_split(
        dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(config["seed"]),
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=training_config["batch_size"],
        shuffle=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=training_config["batch_size"],
        shuffle=False,
    )

    return train_loader, val_loader


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

    torch.manual_seed(config["seed"])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_loader, val_loader = build_dataloaders(config)

    model = build_model(config).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=config["training"]["learning_rate"],
    )

    print(f"Using device: {device}")
    print(f"Using config: {args.config}")
    print("Starting configurable EEGNet training smoke test...")

    history = []
    last_val_acc = 0.0

    for epoch in range(1, config["training"]["epochs"] + 1):
        train_loss, train_acc = train_one_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            device,
        )

        val_loss, val_acc = evaluate_classifier(
            model,
            val_loader,
            criterion,
            device,
        )

        last_val_acc = val_acc

        epoch_result = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_accuracy": train_acc,
            "val_loss": val_loss,
            "val_accuracy": val_acc,
        }

        history.append(epoch_result)

        print(
            f"Epoch {epoch:02d} | "
            f"train loss: {train_loss:.4f} | "
            f"train acc: {train_acc:.4f} | "
            f"val loss: {val_loss:.4f} | "
            f"val acc: {val_acc:.4f}"
        )

    print("Training smoke test finished.")

    save_training_history(history, config)

    audit_summary = run_artifact_audit(
        model=model,
        val_loader=val_loader,
        criterion=criterion,
        device=device,
        config=config,
        clean_val_acc=last_val_acc,
    )

    if audit_summary is not None:
        save_audit_summary(audit_summary, config)


if __name__ == "__main__":
    main()