# Phase II-B Controlled-Acquisition Contract

This contract adds operational acquisition and raw-byte identity foundations.
It does not authorize access to Lee2019_MI and does not amend the frozen
scientific protocol.

## Dataset and scientific roles

- Dataset identity: `Lee2019_MI`; expected cohort: 54 subjects.
- Intended classes: left and right motor imagery.
- S1 offline labeled trials are the training/validation source.
- S2 offline labeled trials are the independent evaluation source.
- Online and unlabeled material is outside the authorized scientific role.

The source URL, archive filename, archive byte count, and archive SHA-256 are
not yet frozen. They remain `null` in the machine-readable contract rather than
being guessed.

## Authorization separation

Acquisition authorization, network authorization, and scientific-execution
authorization are independent and default to `DENY`. Acquisition may download,
verify, safely extract, inventory, and write identity manifests only when both
acquisition and network authorization are explicit. It must not preprocess,
train, evaluate, or compute scientific metrics. Scientific execution must be
offline and cannot request acquisition. Scientific execution remains denied.

The real-data cache root must be supplied explicitly and remain outside the Git
repository. The global MNE and MOABB cache locations are rejected by path
identity without inspecting their contents. A system temporary directory is
not persistent real-data storage. Tests may opt into isolated temporary roots.
Existing unknown directories and unmanaged files fail closed and are never
deleted or repaired automatically.

## Controlled lifecycle

The required order is:

1. verify explicit acquisition authorization;
2. validate the dedicated cache root;
3. verify explicit network authorization;
4. stream into `target.partial`;
5. verify nonzero byte count and any frozen expected length;
6. calculate SHA-256 and verify any frozen expected digest;
7. publish the final archive atomically without overwriting;
8. validate every archive member before extraction;
9. extract into a private staging directory and publish without overwriting;
10. stream-hash every extracted file;
11. generate structural inventory and deterministic manifests;
12. verify manifest self-identity;
13. evaluate the raw-data identity gate without download or repair.

The implementation supports injected transports so all tests use synthetic
bytes. A real transport is reachable only after explicit command-line
authorization. No acquisition import performs network or dataset access.

## Three identity layers

1. **Download/archive identity** binds source metadata, redirects, HTTP
   metadata when observed, byte count, and archive SHA-256. Content-Length is
   metadata, never identity by itself.
2. **Extracted raw-file identity** binds normalized relative path, size,
   SHA-256, source-archive SHA-256, and optional structural subject/session/run
   and role fields. Deterministic manifest bytes carry a self-identity digest.
3. **Scientific trial identity** covers signal loading, event semantics,
   preprocessing, epochs, labels, and trial accounting. It is outside Phase
   II-B controlled acquisition and is not implemented or authorized here.

The real Lee2019_MI raw-data identity state in this phase is `NOT_ACQUIRED`.
Only a fully controlled synthetic fixture may produce `PASS`.
