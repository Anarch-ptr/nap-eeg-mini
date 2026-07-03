"""
Dataset utilities for NAP-EEG-Mini.

This module currently provides a synthetic EEG dataset for pipeline testing.
It is not intended to replace real EEG data.
"""

import torch
from torch.utils.data import Dataset


class SyntheticEEGDataset(Dataset):
    """
    Synthetic EEG dataset for testing the training pipeline.

    Parameters
    ----------
    num_trials : int
        Number of EEG trials.
    num_channels : int
        Number of EEG channels.
    num_samples : int
        Number of time samples per trial.
    num_classes : int
        Number of classes.
    seed : int
        Random seed for reproducibility.
    """

    def __init__(
        self,
        num_trials: int = 512,
        num_channels: int = 22,
        num_samples: int = 1000,
        num_classes: int = 4,
        seed: int = 0,
    ):
        super().__init__()

        generator = torch.Generator().manual_seed(seed)

        self.x = torch.randn(
            num_trials,
            num_channels,
            num_samples,
            generator=generator,
        )

        self.y = torch.randint(
            low=0,
            high=num_classes,
            size=(num_trials,),
            generator=generator,
        )

        # Add a weak class-dependent signal so the model has something learnable.
        time = torch.linspace(0, 1, num_samples)

        for class_id in range(num_classes):
            class_mask = self.y == class_id
            frequency = 8 + class_id * 4
            signal = torch.sin(2 * torch.pi * frequency * time)

            # Inject signal into a few channels.
            self.x[class_mask, class_id::num_classes, :] += 0.5 * signal

    def __len__(self):
        return len(self.y)

    def __getitem__(self, index):
        return self.x[index], self.y[index]