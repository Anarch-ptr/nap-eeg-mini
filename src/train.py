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
from torch.utils.data import DataLoader, TensorDataset, random_split

from src.audit import evaluate_channel_masking
from src.audit import summarize_channel_masking_audit
from src.datasets import SyntheticEEGDataset
from src.data import load_bci2a_subject
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

        train_dataset = TensorDataset(x_train, y_train)
        val_dataset = TensorDataset(x_val, y_val)

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
    weight_decay=config["training"].get("weight_decay", 0.0),
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