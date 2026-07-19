# Small-Sample Robustness Audit Protocol v1

## Research Question

> Does the sealed subject-specific BCI2a EEGNet baseline exhibit a stable,
> reproducible cross-session failure as its available training data decrease?

This protocol is designed to falsify that hypothesis. It is not a NAP model
proposal and is allowed to terminate without producing a new architecture.

## Frozen Matrix

- Subjects: A01--A09
- Training-data budgets: 100%, 50%, 25%
- Training seeds: 42, 43, 44
- Fixed split seed: 42
- Fixed subset seed: 20260719
- Official training session: `0train`
- Official final evaluation: complete, untouched `1test`
- Primary metric: accuracy, preserving the sealed baseline endpoint
- Secondary metrics: balanced accuracy, macro-F1, per-class recall, confusion matrix

The full formal matrix contains 81 runs. It must not be run until the
infrastructure and smoke outputs receive human review.

## Fixed Data Boundary

The baseline seed-42 `torch.randperm` split semantics define one fixed 80%
training pool and 20% validation set inside official `0train`. The same pool
and validation identities are used for every budget and all training seeds.
Validation samples never return to training. Official `1test` is used only
once per run after best-validation checkpoint selection.

Historically, sealed seeds 42, 43, and 44 also changed the random
train/validation split. Protocol v1 intentionally separates that role from
optimization randomness. Consequently, the 100%/training-seed-42 condition
is compatible with the sealed seed-42 training pool, while the other two
100% conditions use the newly frozen seed-42 split. Exact compatibility with
all three historical runs is impossible while also requiring a validation
set invariant across training seeds.

## Nested Stratified Subsets

For each subject and class, the fixed subset seed creates one permutation of
the fixed training-pool indices. A budget retains the prefix of length:

```text
max(1, floor(class training-pool count × budget))
```

The selected trials are restored to original training-pool order before
loading. This produces deterministic, subject-specific subsets with:

```text
25% ⊂ 50% ⊂ 100%
```

and guarantees that every class remains represented. Subset identity is
independent of training seeds 42, 43, and 44.

## Preprocessing and Normalization

The sealed 8--32 Hz, 0--4 s preprocessing definition is unchanged. Dataset-
level channel mean and standard deviation are recomputed using only the
selected budget subset. Validation and official test trials are transform-
only. No statistics, labels, or samples from validation or `1test` contribute
to subset construction or normalization.

## Training and Checkpoint Policy

Across budgets, preserve EEGNet, Adam, learning rate 0.001, batch size 32,
dropout 0.25, weight decay `1e-4`, maximum 50 epochs, and the existing rule:
select highest validation accuracy, breaking ties with validation loss, then
restore that checkpoint before official-test evaluation. The code performs
best-checkpoint model selection but does not stop training early.

The primary audit keeps 50 epochs. Smaller budgets therefore receive fewer
optimizer updates; the result measures the sealed recipe under reduced data,
not a pure information-theoretic sample effect. No budget-specific tuning is
allowed.

## Statistical Hierarchy and Primary Comparison

Subject is the biological unit. Seeds are optimization repetitions and are
first aggregated within subject. Trials are not independent group-level
samples.

The primary comparison is subject-level 25% versus 100% accuracy:

```text
Delta25(subject) = Accuracy25(subject) - Accuracy100(subject)
```

The 50% budget supports inspection of a 100% → 50% → 25% dose response; it
is not a separate primary hypothesis.

## Preregistered Decision Rule

Classify a **strong failure** only when all conditions hold:

1. median subject-level 25%-versus-100% degradation is at least 5 pp;
2. at least 7/9 subjects show at least 3 pp degradation;
3. group-level degradation direction is consistent across training seeds
   42, 43, and 44;
4. results show a broadly reasonable 100% → 50% → 25% dose response;
5. implementation bugs, leakage, normalization errors, class imbalance, and
   checkpoint artifacts do not explain the effect.

Classify a **mixed failure** when degradation is substantial but strongly
subject-dependent or seed-unstable. Before observing the formal matrix,
"meaningful" is frozen as either median degradation of at least 3 pp or at
least three subjects degrading by 3 pp or more. Classify **no meaningful
failure** when neither criterion is met. Classify **incomplete or invalid**
before scientific interpretation whenever matrix or provenance checks fail.

## Frozen Analysis Layer

Accuracy is stored as a fraction from 0 to 1. Deltas remain fractions, while
human-readable degradation is reported in percentage points:

```text
delta25 = mean_accuracy_25 - mean_accuracy_100
degradation25_pp = (mean_accuracy_100 - mean_accuracy_25) × 100
```

For each subject and budget, seeds 42, 43, and 44 are averaged and their
sample standard deviation is recorded. These three seeds are optimization
repetitions, not biological replicates. Group summaries operate on nine
subject-level values only.

Seed-direction consistency is a reproducibility diagnostic. Separately for
each seed, calculate each subject's 100%-minus-25% degradation and take the
median across A01--A09. Consistency passes only when all three seed-specific
medians are strictly positive. The three medians are not independent group
samples.

Dose-response support passes when the medians of the nine subject-aggregated
metrics satisfy:

```text
median_accuracy_100 >= median_accuracy_50 >= median_accuracy_25
```

Equality is allowed. The number of individual subjects satisfying the same
ordering is descriptive and is not an additional Strong Failure threshold.

Before classification, analysis requires exactly one completed cell for
every subject, budget, and training seed; fixed split seed 42; fixed subset
seed 20260719; represented classes whose counts sum to the logged training
count; consistent validation and official-test counts within subject;
monotonic training sample counts; non-empty checkpoint identity; and no
missing, duplicate, failed, or unexpected run keys. Any failure produces
`INCOMPLETE_OR_INVALID` with explicit errors rather than a scientific class.

If `STRONG_FAILURE` is observed, it does not justify NAP. The next mandatory
gate is an optimizer-update-matched small-sample diagnostic to determine
whether fewer optimization steps under fixed epochs explain the effect. That
diagnostic is not implemented or run in Protocol v1.

## Later Simple-Control Gate

The sealed baseline already contains dropout, weight decay, and best-
validation checkpoint selection. The latter is not true early stopping.
The one recommended later low-complexity control is the same EEGNet with a
single preregistered stronger weight decay (`1e-3`), evaluated on the exact
same frozen subsets. It must not be selected using official-test results.
This control is not part of Protocol v1 infrastructure validation and is not
automatically run.

## Stopping Rule

The audit may conclude that no actionable small-sample failure exists. Do not
add post-hoc budgets, k-shot values, architectures, or controls to obtain a
positive outcome. No NAP, gating, GRL, adaptation, or new encoder is permitted
by this protocol.
