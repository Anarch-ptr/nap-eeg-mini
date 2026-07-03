"""
Evaluation utilities for NAP-EEG-Mini.

This module provides reusable evaluation functions for EEG classifiers.
"""

import torch


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