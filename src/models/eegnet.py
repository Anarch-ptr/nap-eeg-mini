"""
EEGNet baseline model for NAP-EEG-Mini.

Input shape:
    x: [batch_size, num_channels, num_samples]

Internal shape:
    x: [batch_size, 1, num_channels, num_samples]

Output shape:
    logits: [batch_size, num_classes]
"""

import torch
import torch.nn as nn


class EEGNet(nn.Module):
    """
    A compact EEGNet-style baseline for EEG decoding.

    Parameters
    ----------
    num_channels : int
        Number of EEG channels.
    num_samples : int
        Number of time samples per trial.
    num_classes : int
        Number of output classes.
    f1 : int
        Number of temporal filters.
    d : int
        Depth multiplier for spatial filters.
    f2 : int
        Number of separable convolution output filters.
    kernel_length : int
        Temporal convolution kernel length.
    dropout : float
        Dropout probability.

    Returns
    -------
    torch.Tensor
        Classification logits with shape [batch_size, num_classes].
    """

    def __init__(
        self,
        num_channels: int,
        num_samples: int,
        num_classes: int,
        f1: int = 8,
        d: int = 2,
        f2: int = 16,
        kernel_length: int = 64,
        dropout: float = 0.25,
    ):
        super().__init__()

        self.num_channels = num_channels
        self.num_samples = num_samples
        self.num_classes = num_classes

        self.block1 = nn.Sequential(
            nn.Conv2d(
                in_channels=1,
                out_channels=f1,
                kernel_size=(1, kernel_length),
                padding=(0, kernel_length // 2),
                bias=False,
            ),
            nn.BatchNorm2d(f1),
            nn.Conv2d(
                in_channels=f1,
                out_channels=f1 * d,
                kernel_size=(num_channels, 1),
                groups=f1,
                bias=False,
            ),
            nn.BatchNorm2d(f1 * d),
            nn.ELU(),
            nn.AvgPool2d(kernel_size=(1, 4)),
            nn.Dropout(dropout),
        )

        self.block2 = nn.Sequential(
            nn.Conv2d(
                in_channels=f1 * d,
                out_channels=f1 * d,
                kernel_size=(1, 16),
                padding=(0, 8),
                groups=f1 * d,
                bias=False,
            ),
            nn.Conv2d(
                in_channels=f1 * d,
                out_channels=f2,
                kernel_size=(1, 1),
                bias=False,
            ),
            nn.BatchNorm2d(f2),
            nn.ELU(),
            nn.AvgPool2d(kernel_size=(1, 8)),
            nn.Dropout(dropout),
        )

        feature_dim = self._get_feature_dim()
        self.classifier = nn.Linear(feature_dim, num_classes)

    def _forward_features(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through convolutional feature extractor.
        """

        x = self.block1(x)
        x = self.block2(x)
        return x

    def _get_feature_dim(self) -> int:
        """
        Infer flattened feature dimension using a dummy input.
        """

        with torch.no_grad():
            dummy = torch.zeros(1, 1, self.num_channels, self.num_samples)
            features = self._forward_features(dummy)
            feature_dim = features.view(1, -1).shape[1]

        return feature_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Parameters
        ----------
        x : torch.Tensor
            EEG input tensor with shape [batch_size, num_channels, num_samples]
            or [batch_size, 1, num_channels, num_samples].

        Returns
        -------
        torch.Tensor
            Classification logits.
        """

        if x.dim() == 3:
            x = x.unsqueeze(1)

        if x.dim() != 4:
            raise ValueError(
                "Expected input shape [batch, channels, samples] "
                "or [batch, 1, channels, samples]."
            )

        features = self._forward_features(x)
        features = features.view(features.size(0), -1)
        logits = self.classifier(features)

        return logits


if __name__ == "__main__":
    torch.manual_seed(0)

    batch_size = 8
    num_channels = 22
    num_samples = 1000
    num_classes = 4

    model = EEGNet(
        num_channels=num_channels,
        num_samples=num_samples,
        num_classes=num_classes,
    )

    x = torch.randn(batch_size, num_channels, num_samples)
    logits = model(x)

    print("Input shape:", x.shape)
    print("Output shape:", logits.shape)

    assert logits.shape == (batch_size, num_classes)

    print("EEGNet smoke test passed.")
    