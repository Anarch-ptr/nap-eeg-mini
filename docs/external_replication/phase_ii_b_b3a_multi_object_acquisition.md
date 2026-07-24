# Phase II-B B3a Multi-Object Opaque-Byte Acquisition

## Status and scope

B3a implements synthetic-tested infrastructure for the original GigaDB
`Lee2019_MI` representation. That representation is 108 independent objects:
54 approved subject identifiers by two approved session identifiers, with
canonical paths `session1/sN/sess01_subjNN_EEG_MI.mat` and
`session2/sN/sess02_subjNN_EEG_MI.mat`.

An archive transaction cannot accurately express independent URLs, per-object
evidence, partial-collection restart, or collection identity. The archive
workflow is therefore retained unchanged and a separate collection workflow
is used. It performs no extraction. A `.mat` suffix is only an opaque filename;
no MATLAB, EEG, label, channel, trial, or subject metadata is read from bytes.

`GIGADB_ORIGINAL_MAT_OBJECTS` is an exact representation identity.
`NEMAR_BIDS_DERIVATIVE` is different and cannot satisfy that request.

Real-data and scientific-execution authorization remain `DENY`;
`LEE2019_MI_DATA_ACCESS` remains `NONE`.

## Architecture and identity

`CollectionObjectPlan` binds one object ID, canonical relative path, exact URL,
optional expected size and SHA-256, approved subject/session plan fields,
source role, and opaque content kind. The frozen
`MultiObjectAcquisitionRequest` binds the immutable tuple, representation,
counts, resource envelope, exact host/path policy, authorization identity,
baseline commit, and destination. Input ordering is canonicalized.

`MultiObjectDependencies` injects the byte transport, clock, and event sink.
The application constructs no transport and contains no real object URL.
`MultiObjectAcquisitionResult` binds plan and candidate-manifest hashes,
representation, baseline commit, gate, state history, and transport-call count.

The identity layers are deliberately separate:

1. The plan SHA-256 covers canonical JSON for schema, dataset, representation,
   and every exact planned object field.
2. Candidate object identity covers planned identity, redirects/final URL,
   observed count/SHA-256, transport metadata, time, and unapproved status.
3. Candidate collection identity covers the canonical ordered records and a
   self-identity digest; the last-published marker binds it to plan, dataset,
   representation, authorization, and baseline.
4. `ApprovedCollectionIdentity` is separately supplied and must bind exact
   plan/manifest hashes, ordered object IDs/sizes/hashes, approval ID, named
   approver, timestamp, baseline, destination, authenticity evidence, and
   license review. Acquisition cannot create it.
5. Scientific trial identity would cover parsing, event semantics,
   preprocessing, labels, and trials. It is outside B3a and denied.

## State machine and recovery

| State | Preconditions and validation | Artifacts/publication | Failure, cleanup, retry, restart |
|---|---|---|---|
| `ABSENT` | No cache assumption | None | Offline validation starts; no transport |
| `PLAN_VALIDATED` | Exact representation, counts, URLs, paths, IDs, limits | In-memory plan/hash | Invalid plan fails before transport |
| `CACHE_VALIDATED` | Dedicated managed cache policy passes | Managed marker may initialize | Unknown top-level state fails |
| `COLLECTION_LOCKED` | Exclusive creation after authorization | Deterministic root lock | Any existing lock refuses; only owned exact lock removed |
| `OBJECT_STAGING` | Lock held; target absent | `<target>.partial` | Owned partial removed; foreign partial retained |
| `OBJECT_VERIFIED` | Nonzero, response/size/hash policy passes | Closed/fsynced partial | Failure publishes no object |
| `OBJECT_PUBLISHED` | Verified partial; final absent | Non-overwriting hard link | Matching object rehashes on restart; mismatch never repairs |
| `COLLECTION_OBJECTS_COMPLETE` | Exact set/count; no extras/partials | Opaque object files | Matching interrupted collection may resume |
| `CANDIDATE_MANIFEST_STAGED` | Every actual byte rehashed | Fsynced `.staging` JSON | Owned stage removed; no marker |
| `CANDIDATE_MANIFEST_VERIFIED` | Disk self-hash and plan binding pass | Non-overwritten manifest | Tampering fails closed |
| `CANDIDATE_COLLECTION_COMPLETE` | Valid manifest/plan | Marker published last | Marker failure is incomplete |
| `AWAITING_HUMAN_APPROVAL` | Offline gate is `UNAPPROVED_CANDIDATE` | No approval artifact | Repeat run makes zero transport calls |
| `APPROVED_COLLECTION_VERIFIED` | Separate complete approval matches rehashed bytes | No automatic write | Test/future-only; acquisition cannot reach it |

A collection is complete only with the exact plan/set/counts, known size and
SHA-256 for every object, deterministic self-identifying manifest, and no
partial, staging, lock, or unresolved failure. File existence is insufficient.

Recovery is conservative. Matching published objects may be reverified and
reused. Invalid/unknown objects, foreign partials, locks, manifests, and
markers are never deleted, overwritten, repaired, or redownloaded. Ambiguity
requires operator review; publication never uses last-writer-wins.

`CONCURRENCY_MODEL` is `SINGLE_COLLECTION_SINGLE_PROCESS`; object concurrency
is exactly one. The machine-readable lock is at the managed root, outside
object-controlled paths, and binds dataset and plan. Active, stale, corrupt,
and ambiguous locks all refuse. There is no automatic stale-lock deletion.

## Limits, paths, transport, and gate

Synthetic execution supplies finite object count, per-object/total bytes,
redirect, URL/path length, timeout, retry, and concurrency limits. Expected
count equals plan length. The injected transport has no implicit retries.
Redirects must pass the same exact HTTPS host/path policy before publication.
Production real-data limits remain unresolved; no sizes are guessed.

Plans reject duplicate object IDs, normalized/case-folded paths, URLs, and
subject/session pairs. Paths reject traversal, absolute/UNC/drive forms, mixed
separators, controls/illegal characters, Windows devices, alternate streams,
trailing dots/spaces, length excess, case collisions, and Unicode collisions.
URLs reject HTTP, wildcards, credentials, queries/tokens, fragments, ports,
unexpected hosts, and unexpected prefixes.

The offline gate never downloads, repairs, approves, or parses. It detects
missing/extra objects, partials/stages, locks, count/representation/plan/URL
substitution, manifest tampering, and actual size/hash changes by rehashing
every object.

## Success-path evidence (requirements 1–30)

The tests in `test_external_replication_multi_object_acquisition.py` map:

| Requirements | Implementation/test assertions | Result |
|---|---|---|
| 1–5 | 108/54/two/path validation and deterministic plan identity | PASS |
| 6–10 | 108 fake calls; injected-only boundary; authorization and lock before calls; partial staging | PASS |
| 11–15 | Pre-publication verification; no partial/extra; rehash; 108 records | PASS |
| 16–20 | Ordered self-hash; unapproved—not approved—gate; scientific DENY | PASS |
| 21–25 | Forbidden-import audit; repeat zero calls/overwrite; byte/plan consistency rehash | PASS |
| 26–30 | Marker last; baseline and GigaDB binding; NEMAR denial; no persistent fixture artifacts | PASS |

## Failure-path evidence (requirements 1–88)

Related requirements intentionally share table-driven tests and the same
fail-closed control.

| Requirements | Implementation/test assertions | Result |
|---|---|---|
| 1–6 | Acquisition/network/scientific conflicts, dataset and NEMAR mismatch fail before transport | PASS |
| 7–14 | HTTP, wildcard/unexpected host/path, query/credentials, URL/ID/path duplicates | PASS |
| 15–22 | 107/109, subject/session/pair/count mismatch; reversed input canonicalizes | PASS |
| 23–25 | Changed plan, rewritten manifest, and baseline binding reject substitution | PASS |
| 26–37 | Traversal, absolute/drive/UNC/mixed, case/Unicode, device, dot/space, ADS, length | PASS |
| 38–40 | First/middle/final interruption: no owned partial; matching restart resumes | PASS |
| 41–50 | Zero/wrong/HTML/status/redirect and finite byte limits; zero implicit retry | PASS |
| 51–58 | Existing valid rehash; invalid/unknown/partial/active-stale-corrupt locks refuse | PASS |
| 59–70 | Missing artifacts, changed/missing/extra object, tamper/substitution, publication/lock failures fail closed | PASS |
| 71–80 | Separate complete approval record; missing fields/object bindings fail; no auto-write | PASS |
| 81–88 | Audit excludes MOABB, MNE, SciPy, MATLAB loaders, training, metrics, and visualization | PASS |

Stale and corrupt locks are deliberately indistinguishable from active locks:
exclusive creation refuses without guessing ownership or age. Publication
failure tests verify that candidate completion and approval never appear.

## Approval and source changes

Acquisition emits only `UNAPPROVED_CANDIDATE`; it never adopts an observed hash
as approved and cannot rewrite approval. A same URL with a different hash is
`SOURCE_IDENTITY_CHANGED` and requires quarantine/review. A different URL with
the same hash is `SOURCE_MIGRATION_CANDIDATE` and requires separate source
authorization. Same filename with different size fails. An unversioned source
requires an immutable project-approved collection identity; a self-consistent
candidate rewrite cannot substitute for it.

## Remaining real-acquisition blockers

B3a infrastructure acceptance does not authorize B3. A later real quarantine
acquisition requires verified automated-download permission, finite reviewed
limits, an approved exact 108-URL plan, named human approver, approved
destination TOCTOU envelope, and separate execution authorization. Until then
there is no executable real request or approved collection identity.
