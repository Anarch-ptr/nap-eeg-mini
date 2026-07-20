# Related Work and Project Positioning

> **Historical positioning note:** This document captures the literature
> framing used before the formal audits were completed. Later evidence did not
> support selective artifact-shortcut dependency and did not establish a
> mechanism that authorizes NAP-A. NAP-A was not implemented. The current
> contribution is the completed falsification and reliability evidence chain
> summarized in the README and the final instability-reliability review.

## 1. EEG Artifact Removal

Electroencephalography (EEG) recordings are vulnerable to non-neural contamination, including ocular, muscular, cardiac, motion-related, and environmental artifacts. Traditional EEG pipelines often rely on preprocessing methods such as filtering, regression-based correction, Independent Component Analysis (ICA), Canonical Correlation Analysis (CCA), and other blind source separation methods.

These methods are important, but they also introduce practical limitations. ICA-based methods usually require multichannel recordings and may involve manual or semi-automatic component rejection. CCA-based methods can be useful for separating certain artifact sources, especially muscle-related contamination, but they are still preprocessing techniques rather than direct guarantees of robust downstream decoding.

For this project, artifact removal methods are treated as background context rather than the main contribution. NAP-EEG-Mini does not attempt to replace ICA, CCA, or other denoising pipelines. Instead, it asks a downstream reliability question:

> After training an EEG decoder, can we audit whether the model is relying on artifact-prone signals?

## 2. Deep Learning for EEG Decoding

Deep learning has become an important approach for EEG decoding because it can learn temporal, spatial, and spectral features directly from EEG-like input tensors. EEGNet is a representative compact convolutional architecture designed for EEG-based brain-computer interface tasks. It uses depthwise and separable convolutions to reduce model size while preserving EEG-specific inductive biases.

Other convolutional EEG models, such as DeepConvNet and ShallowConvNet, have also shown that neural networks can learn useful EEG representations and that visualization methods can help inspect what the model has learned.

In NAP-EEG-Mini, EEGNet is used as a baseline model because it is compact, recognizable, and suitable for a small reproducible project. It is not treated as the novelty of the project.

## 3. Artifact Sensitivity in EEG Decoding

A high EEG classification accuracy does not necessarily imply that a model has learned meaningful neural patterns. EEG artifacts can be statistically correlated with labels due to experimental design, subject behavior, task difficulty, or recording conditions. When such correlations exist, a deep model may exploit artifact-related features because they are easier and stronger than the underlying neural signal.

This creates a reliability problem. A model may perform well on a standard validation set but fail when artifact distributions change. Therefore, accuracy alone is insufficient for evaluating EEG decoding reliability.

NAP-EEG-Mini addresses this issue by introducing explicit artifact-sensitivity checks, including artifact-only evaluation and noise-injection testing.

## 4. Shortcut Learning

Shortcut learning describes a situation in which a model learns decision rules that perform well on a benchmark but fail under distribution shifts or more challenging test conditions. In the EEG setting, artifacts can function as shortcut features when they are easier to detect than neural activity and happen to correlate with labels.

This project treats artifact reliance as a shortcut-learning hypothesis. The goal is not to assume that every EEG model always learns artifacts. The goal is to build an audit pipeline that can test whether such reliance exists under controlled conditions.

The artifact-only experiment is therefore central to the project. If a model achieves high artifact-only accuracy, that result suggests that label-relevant information may be present in the artifact channel. This does not automatically prove biological invalidity, but it raises a serious reliability warning.

## 5. Robust EEG Decoding

Robust EEG decoding research explores how models behave under noisy, corrupted, missing, or distribution-shifted inputs. Some methods use spatial filtering, attention mechanisms, channel reweighting, data augmentation, or corruption-aware training to improve reliability.

NAP-EEG-Mini is positioned close to this line of work, but with a narrower scope. It does not initially propose a large new architecture. Instead, it first builds a reproducible audit framework:

1. Train a compact EEGNet baseline.
2. Visualize training behavior.
3. Test whether artifacts alone can support classification.
4. Inject controlled noise and measure degradation.
5. Only then introduce the NAP-A reliability module.
6. Evaluate NAP-A using ablation studies.

This ordering is important because it prevents circular reasoning. If NAP-A is introduced before the artifact-sensitivity problem is measured, then later experiments may only prove that the project’s own module was designed to win its own test.

## 6. Project Positioning

The current position of NAP-EEG-Mini is:

- **Baseline:** EEGNet is used as a compact, established decoding baseline.
- **Dataset:** Synthetic EEG is used only for pipeline verification and smoke testing.
- **Audit method:** Channel masking and artifact-only evaluation are used as diagnostic tools.
- **Research focus:** The core contribution is a reproducible artifact-sensitivity and robustness evaluation workflow.
- **Future direction:** Real EEG datasets are required before making stronger claims about generalization or neuroscience relevance.

## References

- Jiang, X., Bian, G. B., & Tian, Z. (2019). Removal of artifacts from EEG signals: A review. *Sensors*, 19(5), 987.
- Lawhern, V. J., Solon, A. J., Waytowich, N. R., Gordon, S. M., Hung, C. P., & Lance, B. J. (2018). EEGNet: A compact convolutional network for EEG-based brain-computer interfaces. *Journal of Neural Engineering*, 15(5), 056013.
- Schirrmeister, R. T., Springenberg, J. T., Fiederer, L. D. J., et al. (2017). Deep learning with convolutional neural networks for EEG decoding and visualization. *Human Brain Mapping*, 38(11), 5391–5420.
- Geirhos, R., Jacobsen, J. H., Michaelis, C., et al. (2020). Shortcut learning in deep neural networks. *Nature Machine Intelligence*, 2, 665–673.
- Banville, H., Wood, S. U. N., Aimone, C., Engemann, D. A., & Gramfort, A. (2022). Robust learning from corrupted EEG with dynamic spatial filtering. *NeuroImage*, 251, 118994.
