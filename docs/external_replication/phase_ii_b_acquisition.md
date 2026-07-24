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

## Controlled lifecycle and transaction state

The required order is:

The persisted transaction advances monotonically through:

`ABSENT -> CACHE_VALIDATED -> DOWNLOADING -> ARCHIVE_VERIFIED ->
ARCHIVE_PUBLISHED -> EXTRACTING_TO_STAGING -> EXTRACTED_VERIFIED ->
MANIFEST_STAGED -> INVENTORY_VERIFIED -> GATE_PASSED -> COMPLETE`.

`COMPLETE` is published last as a canonical JSON marker. It binds the archive
name and SHA-256, manifest payload SHA-256, exact inventory-expectation
SHA-256, expected file and subject counts, dataset identity, gate state, and
marker schema. A later invocation
with the same frozen request re-hashes the archive, validates the manifest,
completion marker, inventory, and raw gate, and returns `VERIFIED_COMPLETE`
without calling the injected transport.

Before any cache write, the application validates source identity and both
authorization switches. Download streams into `target.partial`; byte count,
payload type, and SHA-256 are verified before non-overwriting hard-link
publication. Extraction validates the complete member set before writing,
uses `raw.extracting`, compares every staged byte identity with the
caller-supplied exact inventory, and only then publishes the directory. The
manifest uses an fsynced `.staging` file, self-verifies from
disk, and is published without overwriting. The raw identity gate must pass
before the completion marker is staged, fsynced, and published.

## Recovery, idempotency, and concurrency

The sibling `<cache-root>.phase_ii_b.lock` is acquired exclusively. A second
process, or a lock left by a crashed process, is refused deterministically;
stale-lock removal is an explicit operator action. The workflow removes only
temporary files and locks it created and still owns. It never deletes or
repairs published archives, raw data, manifests, completion markers, or
unknown files.

A failure before completion can therefore leave a deliberately recognizable
incomplete cache. Any cache containing published artifacts but no valid
completion marker is refused with `INCOMPLETE_CACHE_REQUIRES_OPERATOR`.
Corrupt or inconsistent complete caches are also refused, without download.
This makes retries safe: only a fully valid cache is a verification-only no-op;
all other pre-existing states require inspection rather than implicit repair.

The lock is a single-host filesystem exclusion mechanism. Publication uses
same-filesystem, non-overwriting operations and is supported for the Windows
reference environment and local filesystems with ordinary exclusive-create,
hard-link, and rename semantics. Distributed/network filesystems that do not
honor those semantics are outside this guarantee.

## Archive security model

ZIP and TAR containers are supported. Member paths reject absolute, UNC,
drive-qualified, dot-segment, repeated-separator, mixed-separator traversal,
control-character, Windows-reserved, illegal-character, trailing-dot, and
trailing-space names. Symbolic links, hard links, special device/FIFO members,
duplicate paths, case-fold collisions, and Unicode-normalization collisions
are rejected. File-count, single-file size, total expanded size, and expansion
ratio limits are enforced before extraction. The archive SHA-256 is checked
before and after extraction to detect replacement during the transaction.

Nested archives are ordinary opaque files and are not recursively extracted.
Archived permissions, owners, and timestamps are not restored. Extraction
creates regular files and directories under a new private sibling staging
directory. Existing symlink and, where the Python platform exposes it, Windows
junction/reparse ancestors are rejected. The dedicated cache and its ancestors
must still be operator-controlled against hostile replacement during a running
transaction; pre-existing targets and staging paths are rejected.

The implementation supports injected transports and an injected clock, so
production orchestration is exercised using only synthetic bytes. The CLI is
a thin adapter: it validates both authorization switches before constructing
the real urllib transport and requires a caller-supplied exact inventory plan.
No acquisition import performs network or dataset access.

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
