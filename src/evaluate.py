"""
Evaluation utilities for NAP-EEG-Mini.

This module provides reusable evaluation functions for EEG classifiers.
"""

import torch


def evaluate_classifier_detailed(model, dataloader, device, num_classes):
    """Return backward-compatible audit metrics from fixed model predictions.

    This separate API leaves :func:`evaluate_classifier` and the frozen
    baseline training/evaluation path unchanged.
    """

    from sklearn.metrics import accuracy_score
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.metrics import confusion_matrix
    from sklearn.metrics import f1_score
    from sklearn.metrics import recall_score

    model.eval()
    targets = []
    predictions = []
    with torch.no_grad():
        for x, y in dataloader:
            logits = model(x.to(device))
            predictions.extend(torch.argmax(logits, dim=1).cpu().tolist())
            targets.extend(y.tolist())

    labels = list(range(num_classes))
    return {
        "accuracy": float(accuracy_score(targets, predictions)),
        "balanced_accuracy": float(
            balanced_accuracy_score(targets, predictions)
        ),
        "macro_f1": float(
            f1_score(
                targets,
                predictions,
                labels=labels,
                average="macro",
                zero_division=0,
            )
        ),
        "per_class_recall": recall_score(
            targets,
            predictions,
            labels=labels,
            average=None,
            zero_division=0,
        ).astype(float).tolist(),
        "confusion_matrix": confusion_matrix(
            targets,
            predictions,
            labels=labels,
        ).astype(int).tolist(),
    }


def evaluate_classifier(model, dataloader, criterion, device):
    """
    Evaluate a classifier on a dataloader.

    Parameters
    ----------
    model : torch.nn.Module
        The EEG classification model.
    dataloader : torch.utils.data.DataLoader
        DataLoader for evaluation data.
    criterion : torch.nn.Module
        Loss function.
    device : torch.device
        Device used for evaluation.

    Returns
    -------
    tuple
        A tuple containing average loss and accuracy.
    """

    model.eval()

    total_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for x, y in dataloader:
            x = x.to(device)
            y = y.to(device)

            logits = model(x)
            loss = criterion(logits, y)

            total_loss += loss.item() * x.size(0)

            predictions = torch.argmax(logits, dim=1)
            correct += (predictions == y).sum().item()
            total += y.size(0)

    average_loss = total_loss / total
    accuracy = correct / total

    return average_loss, accuracy
