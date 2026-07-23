# Phase II-A Security and Portability Contract

This document describes implementation constraints only. It does not amend the
frozen scientific protocol and does not authorize Phase II-B or scientific
execution.

## Reference-platform reconstruction

The Phase II-A lock and artifact manifest are a platform-specific execution
appliance, not a universal Python environment. Exact-hash reconstruction is
supported only for:

- Windows on AMD64 (`win_amd64`);
- CPython 3.12.10;
- Python and ABI tags `cp312-cp312`, plus compatible audited universal and
  `abi3` wheels;
- Torch `2.12.1+cu130`, while scientific reference execution remains CPU-only.

No Windows release or minimum NVIDIA driver baseline is frozen. GPU hardware
and CUDA execution are not required or authorized. The CUDA-built Torch wheel
is part of the frozen artifact identity, but CUDA numerical equivalence has not
been demonstrated.

The reconstruction verifier rejects operating-system, architecture, Python,
ABI, and wheel-tag mismatches before invoking pip. It never substitutes another
wheel under the same environment identity. Linux, macOS, Apple Silicon,
32-bit Windows, other Python versions, and independently assembled CPU-only
environments are not equivalent. A reviewer must use the frozen reference
platform or create a separately frozen and audited platform lock.

The platform contract is read from the committed, hash-validated environment
manifest under the trusted repository root. The implementation does not accept a
caller-selected manifest path and does not derive the frozen platform contract
from the live host. Windows AMD64 architecture aliases are normalized only when
they represent the same `win_amd64` reference platform; ARM64, 32-bit Python,
Linux, macOS, and other Python patch versions fail closed.

Cross-platform scientific equivalence has not been demonstrated.

## Authorized startup command

The only Phase II-A scientific-boundary startup verification command is:

```powershell
E:\nap-eeg-mini\.venv\Scripts\python.exe -I -E -B -S E:\nap-eeg-mini\scripts\verify_external_replication_startup.py
```

For a clean clone at another physical location, replace `E:\nap-eeg-mini` with
that clone's absolute physical root in both paths.

The launcher requires isolated mode, ignores `PYTHON*` configuration, suppresses
user-site and normal `site` initialization, prevents current-working-directory
path injection, validates the canonical interpreter path, rejects unexpected
initial `sys.path` entries, and replaces `sys.path` with an explicit allowlist
containing only approved standard-library roots, canonical virtual-environment
site-packages, and the trusted clone root. Dependency paths precede the clone
root so the repository cannot shadow approved third-party top-level packages.
Project and scientific module origins are checked after import.
Consequently `.pth`, `sitecustomize.py`, and `usercustomize.py` are not executed
by this authorized launch path.

Protocol identity verification reads the required frozen Git refs and loose
objects directly from `.git`; it does not resolve or execute `git` through the
inherited `PATH`. This deliberately narrow reader verifies loose-object SHA-1
identity, uses bounded ref and tag traversal, and enforces a strict tree-entry
grammar for the frozen path lookup. It fails closed on unsupported Git layouts
such as packed refs, alternates, replacement refs, grafts, shallow state, or
packed objects. It is not a general Git client.

`-I` already implies environment isolation, user-site suppression, and safe
path behavior. `-E` is retained as explicit defense-in-depth documentation.
`-S` is additionally required because isolated mode alone still initializes
the canonical environment's `site` machinery.

Direct `python -m`, `python -c`, IDE, notebook, or shell launch paths do not
constitute Phase II-A authorization.

## Deferred raw-data boundary

Phase II-A contains no authorized Lee2019_MI acquisition or scientific loading
entry point. Historical reconnaissance utilities are hard-denied under Phase
II-A and have no mutable runtime authorization switch. They are not Phase II-B
entry points and must not be invoked for scientific execution.

Phase II-B must introduce a separate acquisition mode and raw-data identity
gate before any Lee2019_MI loading. It must use a dedicated explicitly
configured cache, prohibit implicit global MNE/MOABB caches, log immutable
source and retrieval metadata, hash complete raw bytes, validate atomic
downloads and safe extraction, prohibit silent overwrite or fallback mirrors,
freeze a raw-data manifest, and require offline scientific execution after
identity freeze. Scientific authorization remains denied until that separate
gate passes.

## Trust-model limits

These controls do not establish protection against a compromised operating
system, kernel, administrator, physical host, Python executable, canonical
virtual environment, Git executable/server, or replaced approved artifact
bytes. They do not establish hardware/driver equivalence or cross-platform
scientific equivalence. Server-side branch protection remains an external
GitHub governance requirement.
