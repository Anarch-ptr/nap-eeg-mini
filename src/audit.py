"""
Artifact audit utilities for NAP-EEG-Mini.

This module provides simple reliability checks for EEG classifiers.
The current version focuses on channel masking audit:

1. Evaluate the model normally.
2. Mask selected channels that may contain artifact-related information.
3. Re-evaluate the model.
4. Measure the accuracy drop.

A large accuracy drop after masking suspicious channels may suggest that
the model relies heavily on those channels.
"""

import torch


def zero_selected_channels(x, channel_indices):
    """
    Set selected EEG channels to zero.

    Parameters
    ----------
    x : torch.Tensor
        EEG input tensor with shape [batch, channels, samples]
        or [batch, 1, channels, samples].
    channel_indices : list
        List of channel indices to zero out.

    Returns
    -------
    torch.Tensor
        A copied tensor with selected channels zeroed.
    """

    x_masked = x.clone()

    if len(channel_indices) == 0:
        return x_masked

    if x_masked.dim() == 3:
        x_masked[:, channel_indices, :] = 0.0
    elif x_masked.dim() == 4:
        x_masked[:, :, channel_indices, :] = 0.0
    else:
        raise ValueError(
            "Expected input shape [batch, channels, samples] "
            "or [batch, 1, channels, samples]."
        )

    return x_masked


def evaluate_channel_masking(
    model,
    dataloader,
    criterion,
    device,
    channel_indices,
):
    """
    Evaluate a model after masking selected EEG channels.

    Parameters
    ----------
    model : torch.nn.Module
        EEG classification model.
    dataloader : torch.utils.data.DataLoader
        Evaluation dataloader.
    criterion : torch.nn.Module
        Loss function.
    device : torch.device
        Evaluation device.
    channel_indices : list
        List of channels to mask.

    Returns
    -------
    tuple
        A tuple containing average loss and accuracy after channel masking.
    """

    model.eval()

    total_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for x, y in dataloader:
            x = x.to(device)
            y = y.to(device)

            x_masked = zero_selected_channels(x, channel_indices)

            logits = model(x_masked)
            loss = criterion(logits, y)

            total_loss += loss.item() * x.size(0)

            predictions = torch.argmax(logits, dim=1)
            correct += (predictions == y).sum().item()
            total += y.size(0)

    average_loss = total_loss / total
    accuracy = correct / total

    return average_loss, accuracy


def summarize_channel_masking_audit(clean_accuracy, masked_accuracy):
    """
    Summarize channel masking audit results.

    Parameters
    ----------
    clean_accuracy : float
        Accuracy without channel masking.
    masked_accuracy : float
        Accuracy after channel masking.

    Returns
    -------
    dict
        Audit summary containing clean accuracy, masked accuracy,
        absolute accuracy drop, and relative accuracy drop.
    """

    accuracy_drop = clean_accuracy - masked_accuracy

    if clean_accuracy > 0:
        relative_drop = accuracy_drop / clean_accuracy
    else:
        relative_drop = 0.0

    summary = {
        "clean_accuracy": clean_accuracy,
        "masked_accuracy": masked_accuracy,
        "accuracy_drop": accuracy_drop,
        "relative_drop": relative_drop,
    }

    return summary