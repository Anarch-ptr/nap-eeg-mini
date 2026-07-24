# Phase II-B B0-B2 Pre-Merge Governance Record

Status: `PRE_MERGE_INTEGRATION_ACCEPTED`

This record covers opaque-byte acquisition foundations only. It grants no
dataset, network, scientific parsing, preprocessing, training, evaluation, or
metrics authority.

## Integration identity

- Feature branch: `feat/external-boundary-replication-phase-ii-b-acquisition`
- Feature commit: `0c533056cd56265583b4c238255daf9d79c8bd51`
- Target branch: `feat/external-boundary-replication-implementation`
- Target commit: `bba212d85610e88ea447a8d37ce2d9f270c22565`
- Merge base: `bba212d85610e88ea447a8d37ce2d9f270c22565`
- Feature-only commits: `480103b`, `0c53305`
- Simulated integrated tree: `7a331da73e143714e7c3f6cfb327933cd1cb2b4e`
- Feature tree: `7a331da73e143714e7c3f6cfb327933cd1cb2b4e`
- Merge conflicts: none
- Integrated collection: 489 unique tests
- Integrated result: 489 passed; 106 successful nested subtests
- Skipped, xfailed, xpassed, deselected, failed, and errored tests: none

The integration simulation was local, temporary, uncommitted, and unpushed.
Post-merge verification remains required on the eventual merged commit.

An initial local-clone harness packed remote refs. The protocol identity gate
correctly rejected that unsupported repository layout with
`UNSUPPORTED_GIT_LAYOUT_PACKED_REFS`, causing 14 identity-dependent targeted
failures. The required annotated tag was materialized as a loose ref and only
the temporary clone's `packed-refs` file was removed. The staged merge tree
remained `7a331da7...` before and after this harness correction. The corrected
supported-layout harness then passed all targeted and full tests.

## B0-B2 requirement-to-evidence matrix

All criteria are mandatory and passed. Test names refer to the repository test
node containing the stated evidence. Manual evidence is used only for static
scope or import-boundary claims.

| ID | Requirement | Implementation evidence | Automated or manual evidence |
|---|---|---|---|
| B0-01 | Lee2019_MI role contract | `configs/external_replication/lee2019_mi_acquisition.json` | Config and documentation review |
| B0-02 | S1/S2 offline roles frozen | Acquisition config `dataset` object | Config review |
| B0-03 | Acquisition/science separation | `AcquisitionAuthorization` | `test_54_scientific_mode_cannot_request_acquisition` |
| B0-04 | Acquisition defaults DENY | `AcquisitionAuthorization.acquisition` | `test_55_default_authorization_remains_deny` |
| B0-05 | Network defaults DENY | `AcquisitionAuthorization.network` | `test_55_default_authorization_remains_deny` |
| B0-06 | Scientific execution DENY | `scientific_execution` | Default-deny and production-path tests |
| B0-07 | Dedicated cache policy | `validate_cache_root` | Cache-root tests |
| B0-08 | Global MNE/MOABB fallback denied | `known_global_cache_paths` | `test_global_cache_path_rejected_without_inspection` |
| B0-09 | Real data NOT_ACQUIRED | acquisition config and CLI status | CLI plan/default-deny test |
| B0-10 | No import-time acquisition/network | package and module import boundaries | import smoke and source review |
| B1-01 | Explicit request source of truth | `AcquisitionRequest` | production workflow tests |
| B1-02 | Explicit injected dependencies | `AcquisitionDependencies` | fake-transport production test |
| B1-03 | Authorization before transport | `run_acquisition` | acquisition/network denial tests |
| B1-04 | Authorization before persistent artifacts | `run_acquisition` | denial tests assert cache absent |
| B1-05 | Atomic partial download | `atomic_download` | successful and interruption tests |
| B1-06 | Byte-count validation | `atomic_download` | zero/count mismatch tests |
| B1-07 | Hash before archive publication | `atomic_download` | hash-mismatch and production tests |
| B1-08 | No silent final overwrite | non-overwriting hard-link publication | final-conflict tests |
| B1-09 | Staged safe extraction | `safe_extract_archive` | safe/unsafe extraction tests |
| B1-10 | Exact inventory before raw publication | `pre_publish_validator` | inventory mismatch asserts no raw publication |
| B1-11 | Deterministic raw manifest | `ExtractedManifest.to_bytes` | deterministic round-trip test |
| B1-12 | Manifest self-identity | payload SHA-256 and atomic reread | mutation and self-verification tests |
| B1-13 | Inventory identity | `InventoryExpectation` and completion binding | inventory and substitution tests |
| B1-14 | Raw identity gate | `evaluate_raw_identity_gate` | gate pass/failure/corruption tests |
| B1-15 | Completion published last | `_publish_json_atomic` after gate | completion/gate failure tests |
| B1-16 | Completion binds all identities | `_completion_payload` and `_verify_complete` | recomputed-manifest substitution test |
| B1-17 | No automatic repair | incomplete-cache refusal | no-repair test |
| B1-18 | No automatic redownload | verified-complete path | rerun transport-count tests |
| B1-19 | Structured reason codes | `WorkflowFailureReason` | exact reason assertions |
| B1-20 | Thin CLI adapter | `scripts/acquire_lee2019_mi.py` | CLI help/plan/default-deny test |
| B1-21 | CLI default deny | `_authorization` | CLI default-deny test |
| B1-22 | No scientific pipeline trigger | acquisition import graph | import smoke and source review |
| B2-01 | Production end-to-end synthetic path | `run_acquisition` | production-path completion test |
| B2-02 | Fake uses production transport contract | `RecordingTransport.open` | same test, one call |
| B2-03 | First acquisition succeeds | workflow transaction | production-path completion test |
| B2-04 | Verification rerun uses no transport | `_verify_complete` | production-path rerun test |
| B2-05 | Repeated acquisition does not overwrite | verified-complete branch | same test |
| B2-06 | Acquisition denial precedes transport | network policy | acquisition-denial test |
| B2-07 | Network denial precedes transport | network policy | network-denial test |
| B2-08 | Interrupted download cleanup | `atomic_download.finally` | interruption test |
| B2-09 | Zero-byte rejection | `atomic_download` | download identity failure subtest |
| B2-10 | Count mismatch rejection | `atomic_download` | download identity failure subtest |
| B2-11 | Hash mismatch rejection | `atomic_download` | download identity failure subtest |
| B2-12 | HTML/error rejection | payload/header validation | download identity failure subtest |
| B2-13 | Unsafe archive rejection | member path validation | unsafe archive tests |
| B2-14 | Resource-limit rejection | extraction policy | size/count/ratio tests |
| B2-15 | Manifest publication failure | `write_manifest_atomic` | manifest publication failure test |
| B2-16 | Manifest self-verification failure | atomic staged reread | self-verification failure test |
| B2-17 | Inventory mismatch | staged inventory callback | inventory mismatch test |
| B2-18 | Raw gate failure | gate-before-complete | gate failure test |
| B2-19 | Unknown cache rejection | managed-cache validation | pre-existing-state test |
| B2-20 | Corrupt complete rejection | `_verify_complete` | raw/marker/substitution tests |
| B2-21 | Partial archive refusal | incomplete-cache policy | pre-existing-state test |
| B2-22 | Extraction staging refusal | incomplete-cache policy | pre-existing-state test |
| B2-23 | Invalid manifest refusal | manifest and cache checks | pre-existing-state test |
| B2-24 | Failure never emits COMPLETE | completion-last transaction | all failure-path assertions |
| B2-25 | Local concurrency fail-closed | sibling exclusive lock | stale-lock test |
| B2-26 | Explicit deterministic recovery | incomplete-cache refusal | rerun/no-repair tests |
| B2-27 | Complete suite green | repository test suite | 489 passed |

## Test-accounting interpretation

Pytest collected 489 unique test node IDs. There were no duplicate node IDs,
collection errors, skips, xfails, xpasses, deselections, or warnings. The 106
reported subtests are successful `unittest.TestCase.subTest` cases nested
inside collected test nodes. They provide subcase evidence but are not added to
the 489 collected-test count.

One OS conditional in the environment suite selects the Windows junction or
POSIX symlink construction mechanism. It does not skip or disable the test.

## Checkout identity governance

Git history approves the raw LF byte sequence. Exact-path `.gitattributes`
rules enforce LF checkout representation. Runtime SHA-256 checks the actual
worktree bytes consumed by the program.

Fresh local clones at the feature commit passed with `core.autocrlf=true`,
`input`, and `false`. In all three:

- index and worktree were LF;
- Python and PowerShell hashes agreed;
- no BOM was present;
- exactly one terminal LF was present;
- the environment manifest SHA-256 was
  `dd0ca1c0a1229a79c35a040741e351efd4fe134a91b203c750292c552d921b0a`.

The task brief used a singular artifact-manifest filename in one command
example. The tracked and runtime-consumed path is the plural
`manifests/external_boundary_replication_environment_artifacts_v1.json`; the
verification used that authoritative path.

## Risk record

RISK_ID: `SAFE-EXTRACTION-TOCTOU-001`

SEVERITY: `MEDIUM`

STATUS: `PENDING_HUMAN_APPROVAL`

RISK_OWNER: `External Replication Maintainer`

APPROVER: `PENDING_HUMAN_APPROVAL`

ACCEPTED_SCOPE:

- synthetic validation;
- a dedicated local filesystem owned by the acquisition operator;
- single-host operation;
- no untrusted concurrent writer;
- ordinary Windows local-volume exclusive-create, hard-link, rename, fsync,
  symlink, and junction semantics.

FORBIDDEN_ENVIRONMENTS:

- UNC, SMB, NFS, distributed, shared, or remotely synchronized storage;
- symlinked or junctioned cache/destination ancestors;
- directories writable by untrusted users;
- filesystems without reliable exclusive-create, hard-link, rename, or fsync;
- operation under an active hostile filesystem mutator.

COMPENSATING_CONTROLS:

- explicit cache-root validation;
- link/junction ancestor rejection where exposed by the platform;
- exclusive sibling lock;
- non-overwriting same-filesystem publication;
- archive SHA-256 before and after extraction;
- extraction into an owned private staging directory;
- exact staged-file hashes before raw publication;
- completion marker published only after manifest, inventory, and gate pass;
- fail-closed recovery with no automatic repair or redownload.

REVIEW_TRIGGERS:

- any B3 acquisition authorization;
- a new operating system, Python version, filesystem, archive format, or
  concurrency model;
- allowing shared or network storage;
- changing extraction or publication primitives;
- any link, reparse, race, overwrite, or cleanup incident.

B3_BLOCKING: `YES` until a named human approver accepts this operating
envelope for the exact B3 destination.

Remaining partial extraction items concern hostile filesystem races and
platform-specific test coverage. Basic hostile archive inputs are rejected by
automated tests and are not part of the accepted limitation.

## Tooling provenance

ID: `TOOLING-PROVENANCE-001`

ORIGIN: `PROCESS_DEVIATION`

- Repository Black configuration: none.
- Repository virtual environment Black availability: no.
- External executable: local Anaconda Black executable; personal absolute path
  intentionally not recorded in repository content.
- External Black version: `24.8.0`, CPython `3.12.8`.
- External configuration source: none identified.
- Files formatted: the two new workflow implementation/test files in commit
  `0c53305`.
- Formatter output is not acceptance evidence.
- Semantic diff review: pass.
- Semantic acceptance rests on diff review and the targeted/full test suites.

This is non-blocking because no dependency or formatter configuration entered
the repository and the resulting semantic diff was independently reviewed.

## Decision

LOCAL_PHASE_ACCEPTANCE: `PASS`

PRE_MERGE_INTEGRATION_ACCEPTANCE: `PASS`

MERGE_READINESS: `READY`

POST_MERGE_VERIFICATION: `REQUIRED`

REAL_DATA_ACQUISITION_AUTHORIZATION: `DENY`
