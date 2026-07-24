# Phase II-B B3 Lee2019_MI Source and License Review

Status: `B3_PREAUTHORIZATION_BLOCKED`

Reviewed at: `2026-07-24T11:29:14Z`

This is a metadata-only governance record. It authorizes no acquisition,
scientific parsing, preprocessing, training, evaluation, metrics, or
visualization. No Lee2019_MI data file was requested, downloaded, opened, or
inspected.

## Executive status

| Field | Status |
|---|---|
| START_STATE_VALIDATION | PASS |
| DATASET_IDENTITY | VERIFIED |
| PAPER_IDENTITY | VERIFIED |
| DATA_DOI | VERIFIED |
| OFFICIAL_SOURCE | VERIFIED_OFFICIAL |
| MOABB_SOURCE_ALIGNMENT | PARTIAL |
| RELEASE_VERSION | UNKNOWN |
| UPSTREAM_SESSION_ROLE_DEFINITION | AMBIGUOUS |
| PROJECT_S1_S2_ROLE_ASSIGNMENT | PROJECT_DEFINED |
| RAW_DATA_LICENSE | VERIFIED |
| MOABB_GPL_3_0_INTERPRETATION | TOOLBOX_OR_CODE_LICENSE |
| AUTOMATED_DOWNLOAD_PERMISSION | UNVERIFIED |
| RESEARCH_USE_PERMISSION | PERMITTED |
| REDISTRIBUTION_PERMISSION | PERMITTED |
| CITATION_REQUIREMENT | VERIFIED |
| CREDENTIAL_REQUIREMENT | NOT_REQUIRED |
| OFFICIAL_ARCHIVE_SHA256 | NOT_AVAILABLE |
| OFFICIAL_ARCHIVE_SIZE | NOT_AVAILABLE |
| FIRST_ACQUISITION_POLICY | QUARANTINE_THEN_HUMAN_APPROVAL |
| DESTINATION_REVIEW | PASS_CURRENT_BASIC_CHECKS |
| SAFE_EXTRACTION_TOCTOU_APPROVAL | PENDING_HUMAN_APPROVAL |
| B3_AUTHORIZATION_TEMPLATE | DRAFT_ONLY |
| REAL_DATA_ACQUISITION_AUTHORIZATION | DENY |
| SCIENTIFIC_EXECUTION_AUTHORIZATION | DENY |
| LEE2019_MI_DATA_ACCESS | NONE |
| REAL_DATA_FILE_REQUEST | NONE |
| REAL_ARCHIVE_DOWNLOAD | NONE |
| SCIENTIFIC_METADATA_INSPECTION | NONE |
| MOABB_ACQUISITION | NOT_RUN |
| MNE_ACQUISITION | NOT_RUN |
| COMPLETE_TEST_SUITE | PASS |
| PUSHED | NO |

The source, dataset, paper, and license identities are sufficiently supported
for this review. B3 is nevertheless blocked because the original GigaDB
objects have no named release/version or authoritative cryptographic
identities, the GigaDB service does not explicitly state automated-download
permission, finite resource limits remain unset, the source is a 108-file
collection rather than the single archive assumed by the current acquisition
workflow, and human authorization and destination-specific TOCTOU acceptance
remain pending.

## Start-state validation

- Repository root: `E:/nap-eeg-mini`
- Branch: `feat/external-boundary-replication-implementation`
- HEAD: `424e8c6a958f169d2896321255c727700472bbe7`
- Worktree: clean
- Index: clean
- Remote: `origin https://github.com/Anarch-ptr/nap-eeg-mini.git`
- Result: `PASS`

## Source register

### B3-GIGADB-DOI

- TITLE: Data DOI `10.5524/100542`
- URL: `https://doi.org/10.5524/100542`
- DOMAIN: `doi.org`
- SOURCE_TYPE: `DOI_METADATA`
- AUTHORITY: `PRIMARY`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: DOI resolution to GigaDB record 100542. The resolver exposed an
  `http://gigadb.org/dataset/100542` target; the same landing page is available
  directly over HTTPS, so authorization must use HTTPS directly and prohibit
  downgrade.
- DATA_TRANSFER_TRIGGERED: `NO`

### B3-GIGADB-RECORD

- TITLE: Supporting data for "EEG Dataset and OpenBMI Toolbox for Three BCI
  Paradigms: An Investigation into BCI Illiteracy"
- URL: `https://gigadb.org/dataset/100542`
- DOMAIN: `gigadb.org`
- SOURCE_TYPE: `OFFICIAL_DATASET`
- AUTHORITY: `PRIMARY`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: canonical dataset citation, authors, release date, Data DOI,
  paper linkage, OpenBMI repository linkage, total visible record file count,
  file-name/path examples, sizes, and official Wasabi object URLs.
- DATA_TRANSFER_TRIGGERED: `NO`

### B3-GIGADB-TERMS

- TITLE: GigaDB Terms of use
- URL: `https://gigadb.org/term`
- DOMAIN: `gigadb.org`
- SOURCE_TYPE: `DATA_REPOSITORY`
- AUTHORITY: `PRIMARY`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: default CC0 waiver for datasets associated with GigaScience
  articles unless stated otherwise; citation/acknowledgement etiquette;
  third-party constraints; software-license separation; service-abuse
  restriction.
- DATA_TRANSFER_TRIGGERED: `NO`

### B3-PAPER

- TITLE: EEG dataset and OpenBMI toolbox for three BCI paradigms: an
  investigation into BCI illiteracy
- URL: `https://doi.org/10.1093/gigascience/giz002`
- DOMAIN: `academic.oup.com`
- SOURCE_TYPE: `PAPER`
- AUTHORITY: `PRIMARY`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: paper identity, authors and institution, experiment structure,
  two-session semantics, source-code GPL statement, GigaDB supporting-data
  statement, and the article's separate CC BY 4.0 license.
- DATA_TRANSFER_TRIGGERED: `NO`

### B3-OPENBMI-CODE

- TITLE: PatternRecognition/OpenBMI
- URL: `https://github.com/PatternRecognition/OpenBMI`
- DOMAIN: `github.com`
- SOURCE_TYPE: `OFFICIAL_CODE`
- AUTHORITY: `CORROBORATING`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: author-maintained OpenBMI project identity and toolbox scope.
- DATA_TRANSFER_TRIGGERED: `NO`

### B3-MOABB-DOC

- TITLE: moabb.datasets.Lee2019_MI
- URL:
  `https://moabb.neurotechx.com/docs/generated/moabb.datasets.Lee2019_MI.html`
- DOMAIN: `moabb.neurotechx.com`
- SOURCE_TYPE: `MOABB_OFFICIAL`
- AUTHORITY: `CORROBORATING`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: user-provided page facts plus current public documentation for
  dataset code, subjects, sessions, channels, sampling rate, trial duration,
  classes, download/cache behavior, and displayed GPL 3.0 metadata.
- DATA_TRANSFER_TRIGGERED: `NO`

### B3-MOABB-LEE-SOURCE

- TITLE: `moabb/datasets/Lee2019.py`
- URL:
  `https://github.com/NeuroTechX/moabb/blob/develop/moabb/datasets/Lee2019.py`
- DOMAIN: `github.com`
- SOURCE_TYPE: `MOABB_OFFICIAL`
- AUTHORITY: `CORROBORATING`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: class hierarchy, DOI, dataset code, subject/session selection,
  run semantics, GigaDB Wasabi base URL, per-file path construction, NEMAR
  identifier, and parsing behavior. The moving `develop` branch is not an
  immutable source revision.
- DATA_TRANSFER_TRIGGERED: `NO`

### B3-MOABB-DOWNLOAD-SOURCE

- TITLE: `moabb/datasets/download.py`
- URL:
  `https://github.com/NeuroTechX/moabb/blob/develop/moabb/datasets/download.py`
- DOMAIN: `github.com`
- SOURCE_TYPE: `MOABB_OFFICIAL`
- AUTHORITY: `CORROBORATING`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: MNE cache fallback, automatic Pooch download, self-derived
  local hash behavior, force-update deletion, and HTTP downloader TLS
  verification configuration.
- DATA_TRANSFER_TRIGGERED: `NO`

### B3-MOABB-BASE-SOURCE

- TITLE: `moabb/datasets/base.py`
- URL:
  `https://github.com/NeuroTechX/moabb/blob/develop/moabb/datasets/base.py`
- DOMAIN: `github.com`
- SOURCE_TYPE: `MOABB_OFFICIAL`
- AUTHORITY: `CORROBORATING`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: generic `download(..., accept=False)` routing, NEMAR-first
  behavior, fallback behavior, and proof that `accept` is passed only when a
  dataset-specific `data_path` declares that parameter.
- DATA_TRANSFER_TRIGGERED: `NO`

### B3-NEMAR-MIRROR

- TITLE: Lee et al. 2019 (Motor Imagery), `nm000338`
- URL: `https://ww2.nemar.org/dataset/nm000338`
- DOMAIN: `ww2.nemar.org`
- SOURCE_TYPE: `DATA_REPOSITORY`
- AUTHORITY: `CORROBORATING`
- ACCESSED_AT: `2026-07-24T11:29:14Z`
- CONTENT_USED: derived BIDS dataset identity, NEMAR DOI, version `v1.0.1`,
  publication date, 24.8 GB archive display, explicit automated-download
  methods, GPL-3.0 catalog field, and `IsDerivedFrom` links to the GigaDB and
  paper DOIs.
- DATA_TRANSFER_TRIGGERED: `NO`

No secondary source was needed for a governing conclusion.

## Dataset identity and release

CLAIM: The canonical upstream record title is "Supporting data for 'EEG
Dataset and OpenBMI Toolbox for Three BCI Paradigms: An Investigation into BCI
Illiteracy'".

STATUS: `OFFICIAL_SOURCE_CONFIRMED`

EVIDENCE: `B3-GIGADB-RECORD`

CLAIM: `Lee2019_MI` is the MOABB class name; its MOABB dataset code is
`Lee2019-MI`. Neither is the upstream GigaDB release title.

STATUS: `MOABB_IMPLEMENTATION_CONFIRMED`

EVIDENCE: `B3-MOABB-DOC`, `B3-MOABB-LEE-SOURCE`

CLAIM: The dataset authors are Min-Ho Lee, O-Yeon Kwon, Yong-Jeong Kim,
Hong-Kyung Kim, Young-Eun Lee, John Williamson, Siamac Fazli, and Seong-Whan
Lee; the primary institution is Korea University.

STATUS: `OFFICIAL_SOURCE_CONFIRMED`

EVIDENCE: `B3-GIGADB-RECORD`, `B3-PAPER`

CLAIM: The paper DOI is `10.1093/gigascience/giz002` and the data DOI is
`10.5524/100542`.

STATUS: `OFFICIAL_SOURCE_CONFIRMED`

EVIDENCE: `B3-GIGADB-RECORD`, `B3-PAPER`, `B3-GIGADB-DOI`

CLAIM: GigaDB is the primary official data repository and its record was
released on 24 January 2019.

STATUS: `OFFICIAL_SOURCE_CONFIRMED`

EVIDENCE: `B3-GIGADB-RECORD`, `B3-PAPER`

CLAIM: The original GigaDB record exposes no named release or version for the
downloadable objects.

STATUS: `UNVERIFIED`

EVIDENCE: `B3-GIGADB-RECORD`

CLAIM: The GigaDB record uses unversioned paths under `live/pub/.../100542/`;
the empty visible History table does not establish immutability or replacement
history.

STATUS: `INFERRED`

EVIDENCE: `B3-GIGADB-RECORD`, `B3-MOABB-LEE-SOURCE`

CLAIM: NEMAR `nm000338` is a 2026, versioned, DOI-backed BIDS derivative
(`v1.0.1`), not proof of the byte identity of the original GigaDB MATLAB
objects.

STATUS: `OFFICIAL_SOURCE_CONFIRMED`

EVIDENCE: `B3-NEMAR-MIRROR`, `B3-MOABB-LEE-SOURCE`

The GigaDB page currently reports 436 files, whereas the paper describes
approximately 209 GB in 433 files. This repository-level discrepancy does not
change the MI calculation of 108 subject/session MATLAB objects established by
the official path pattern, but it is evidence that the overall live record has
changed or is counted differently and that stable URLs must not be treated as
immutable byte identities.

## Scientific structure and role interpretation

UPSTREAM_DATASET_STRUCTURE:
The paper documents 54 subjects, two sessions on different days, 62 EEG
channels at 1000 Hz, and MI training/offline and test/online phases of 100
balanced left/right trials each. Both sessions used the same experimental
protocol. The paper calculated session decoding accuracies independently and
describes session-to-session transfer as a possible research use.

MOABB_LOADING_SEMANTICS:
`Lee2019_MI` defaults to sessions 1 and 2, exposes each session independently,
uses `train_run=True` for the offline phase, defaults `test_run` to false for
MI, and warns that MI online/test trials exposed by MOABB have no labels and
cannot be used for classification. It uses 4-second intervals and class labels
`left_hand` and `right_hand`.

PROJECT_SCIENTIFIC_ROLE_ASSIGNMENT:
The frozen project protocol assigns S1 offline labeled data to
training/validation and S2 offline labeled data to independent evaluation; it
excludes online/unlabeled material.

ASSESSMENT: `PROJECT_DEFINED`

The upstream paper does not designate session 1 as the only training source or
session 2 as the official independent evaluation set. The assignment is
compatible with the documented repeated-session structure and a
session-transfer question, but it remains a project-defined protocol choice.

## MOABB implementation review

- Class hierarchy: `Lee2019_MI -> Lee2019 -> BaseDataset`.
- Dataset code: `Lee2019-MI`.
- Subjects: integers 1 through 54.
- Sessions: 1 and 2; both are default.
- GigaDB base:
  `https://s3.ap-northeast-1.wasabisys.com/gigadb-datasets/live/pub/10.5524/100001_101000/100542/`.
- MI path pattern:
  `session{session}/s{subject}/sess{session:02d}_subj{subject:02d}_EEG_MI.mat`.
- Structure: 108 independent MI MATLAB files, one per subject/session; MI,
  ERP, SSVEP, and Artifact use separate suffixes.
- `train_run` exposes the `EEG_MI_train` offline run.
- `test_run` exposes the `EEG_MI_test` online run and is false by default for
  MI; MOABB warns that these test trials lack classification labels.
- `resting_state` is false by default and can expose pre/post train/test rest.
- `data_path()` calls `data_dl()` and may download automatically.
- Cache selection uses `MNE_DATASETS_<SIGN>_PATH`, then `MNE_DATA`, then
  `~/mne_data`; this is incompatible with the project's dedicated-cache
  requirement.
- Current `download()` attempts NEMAR first because `nemar_id="nm000338"` and
  falls back to the GigaDB `data_path` downloader on a NEMAR error.
- Generic `accept=False` is not enforced by `Lee2019.data_path`, because that
  method has no `accept` parameter; it is documentation/API surface, not a
  Lee-specific click-through gate.
- For a new GigaDB file, `data_dl()` supplies no authoritative known hash. For
  an existing file it computes a hash from that same local file, which is not
  independent upstream identity evidence.
- MOABB records no official Lee file sizes or hashes in this implementation.
- `force_update=True` unlinks the existing destination before retrieving new
  bytes; it does not preserve an approved identity automatically.
- Pooch/requests redirect following is implementation-dependent and not
  constrained here to approved hosts.
- Current download helper code sets `verify=False` for HTTP/DOI downloader
  types. This is unacceptable for an approved acquisition route even when the
  URL begins with HTTPS.
- No Lee-specific Google Drive, Figshare, FTP, or cloud-form flow is present
  in `data_path`; the original file host is GigaDB's Wasabi object store.
- MOABB's current NEMAR-first route is a distinct versioned BIDS derivative,
  not a byte-equivalent substitute for the original GigaDB MATLAB collection.

MOABB_SOURCE_ALIGNMENT: `PARTIAL`

MOABB aligns on dataset/paper DOI, subject/session structure, and the official
GigaDB object paths. Its default cache, automatic retrieval, non-pinned hash
behavior, TLS setting, force-update behavior, and current preference for a
derived NEMAR route do not satisfy this project's controlled-acquisition
policy.

## License and permissions matrix

### RAW_DATA_LICENSE

- CONCLUSION: `PERMITTED`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`, `B3-GIGADB-RECORD`
- EVIDENCE: GigaDB states that datasets associated with GigaScience articles
  are released under CC0 unless stated otherwise. No exception is displayed on
  record 100542.
- CONFIDENCE: `HIGH`
- LIMITATION: CC0 governs dataset reuse; it does not by itself approve a
  particular automated retrieval method or establish byte identity.

### RESEARCH_USE

- CONCLUSION: `PERMITTED`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`, `B3-PAPER`
- EVIDENCE: CC0 permits reuse, and the paper presents the dataset for broad BCI
  research and education.
- CONFIDENCE: `HIGH`
- LIMITATION: Scientific execution remains separately denied by project
  governance.

### AUTOMATED_DOWNLOAD

- CONCLUSION: `UNVERIFIED`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`, `B3-NEMAR-MIRROR`
- EVIDENCE: GigaDB publishes public direct object links and warns against use
  that impairs service, but does not explicitly grant unattended automated
  retrieval. NEMAR explicitly documents CLI, DataLad, git-annex, and direct
  methods for its own derived version only.
- CONFIDENCE: `MEDIUM`
- LIMITATION: NEMAR's permission and instructions cannot be transferred to
  GigaDB's original MATLAB endpoints.

### REDISTRIBUTION

- CONCLUSION: `PERMITTED`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`
- EVIDENCE: The CC0 waiver permits copying and redistribution.
- CONFIDENCE: `HIGH`
- LIMITATION: Third-party material or a future record-specific exception would
  require separate review; none was found on this record.

### COMMERCIAL_USE

- CONCLUSION: `PERMITTED`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`
- EVIDENCE: CC0 places no non-commercial restriction on the covered dataset.
- CONFIDENCE: `HIGH`
- LIMITATION: No statement is made about patents, trademarks, or third-party
  rights.

### DERIVATIVES

- CONCLUSION: `PERMITTED`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`
- EVIDENCE: CC0 permits adaptation and derived works.
- CONFIDENCE: `HIGH`
- LIMITATION: Derived scientific processing remains outside B3 authorization.

### CITATION

- CONCLUSION: `PERMITTED`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`, `B3-GIGADB-RECORD`
- EVIDENCE: GigaDB says CC0 waives a legal attribution requirement but asks
  users to cite and acknowledge the dataset as scientific etiquette; record
  100542 provides the citation.
- CONFIDENCE: `HIGH`
- LIMITATION: `PERMITTED` here means reuse is not conditioned on citation under
  CC0; project publications should nevertheless cite both data and paper.

### ATTRIBUTION

- CONCLUSION: `NOT_EXPLICITLY_FOUND`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`
- EVIDENCE: No legal attribution condition was found; acknowledgement is
  expected as a norm.
- CONFIDENCE: `HIGH`
- LIMITATION: The paper itself is separately licensed CC BY 4.0 and must not be
  conflated with the dataset's CC0 waiver.

### CREDENTIALS

- CONCLUSION: `PERMITTED`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-RECORD`, `B3-MOABB-LEE-SOURCE`
- EVIDENCE: The landing page and direct file links are public and MOABB
  constructs them without credentials.
- CONFIDENCE: `MEDIUM`
- LIMITATION: No dataset file endpoint was requested, so response-time
  authentication behavior was deliberately not tested.

### PRIVACY

- CONCLUSION: `NOT_EXPLICITLY_FOUND`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`, `B3-PAPER`
- EVIDENCE: No additional download-time privacy term or deletion obligation
  was found in the reviewed sources.
- CONFIDENCE: `LOW`
- LIMITATION: Human EEG data still require responsible handling; absence of a
  displayed special term is not a general privacy conclusion.

### INSTITUTIONAL_RESTRICTION

- CONCLUSION: `NOT_EXPLICITLY_FOUND`
- AUTHORITATIVE_SOURCE: `B3-GIGADB-TERMS`, `B3-GIGADB-RECORD`
- EVIDENCE: No geographic, institutional, or account restriction is displayed.
- CONFIDENCE: `MEDIUM`
- LIMITATION: This does not replace an organization's own compliance review.

The paper's `GPL 3.0` statement appears under "Availability of source code and
requirements" for the BMIdataset/OpenBMI MATLAB project. Its separate
"Availability of supporting data" statement points to GigaDB. The paper itself
is CC BY 4.0. Therefore the MOABB page's GPL display must not be used as the
raw GigaDB data license.

## Source authenticity

- Data DOI resolution: verified to GigaDB record 100542.
- Official landing domain: `gigadb.org`.
- Official object host: the GigaDB record itself publishes
  `s3.ap-northeast-1.wasabisys.com` object links under the 100542 prefix.
- Paper cross-link: the paper names GigaDB and cites data DOI 100542.
- Author-maintained cross-link: GigaDB links the PatternRecognition/OpenBMI
  repository.
- MOABB alignment: direct `data_path` uses the same GigaDB Wasabi prefix.
- Mirror: NEMAR `nm000338` is DOI-backed and explicitly `IsDerivedFrom` the
  GigaDB and paper DOIs, but it is a derived BIDS release and not assumed
  byte-equivalent to GigaDB.
- Deprecation: no official statement that GigaDB is deprecated was found.
- Redirects: the DOI resolver exposed an HTTP landing target; no data-file
  redirect was tested. An approved route must begin with direct HTTPS and fail
  closed on any unapproved redirect or downgrade.
- Cryptographic backing: no GigaDB SHA-256, SHA-512, MD5, signed checksum, or
  other cryptographic identity was found.
- Replacement history: the visible record History table contained no entries.
- Mutability: the `live/pub` paths are unversioned, so immutability is not
  established.

SOURCE_AUTHENTICITY: `VERIFIED_OFFICIAL`

This classification authenticates the source organization and record. It does
not authenticate any particular future byte response.

## Download endpoint metadata

- Scheme: `https`.
- Exact original host: `s3.ap-northeast-1.wasabisys.com`.
- Landing page: `https://gigadb.org/dataset/100542`.
- Base path:
  `/gigadb-datasets/live/pub/10.5524/100001_101000/100542/`.
- MI object pattern:
  `session{1|2}/s{1..54}/sess{01|02}_subj{01..54}_EEG_MI.mat`, with the
  session directory and filename session number required to match.
- Structure: 108 independent `.mat` objects, not one upstream archive.
- Authentication: none displayed.
- Registration: none displayed.
- Cookies: none required for public landing/link discovery.
- Click-through: none displayed.
- Credentials: no personal credentials are used by the official MOABB GigaDB
  path.
- Stable/versioned: the URLs are structurally stable but not versioned.
- Redirects: unverified because no file endpoint was requested.
- HTTPS end to end: unverified for actual file responses; no downgrade is
  acceptable.
- Metadata: GigaDB displays filenames and human-readable per-file sizes. It
  reports 436 total record files. File attributes are shown as `--`; no
  checksum was found.
- Original file endpoints deliberately not requested: every 100542 `.mat`
  object.
- NEMAR data endpoints deliberately not requested: the `v1.0.1` ZIP, direct
  files, S3 content, and annex objects.
- HEAD requests: none.

## Archive and collection identity evidence

| Field | Value | Source | Authority |
|---|---|---|---|
| GigaDB release/version name | UNKNOWN | B3-GIGADB-RECORD | UNKNOWN |
| GigaDB release date | 2019-01-24 | B3-GIGADB-RECORD | STRONG |
| GigaDB repository record | 100542 / DOI 10.5524/100542 | B3-GIGADB-RECORD | STRONG |
| Original MI archive filename | UNKNOWN; source is individual files | B3-GIGADB-RECORD | STRONG |
| Original MI expected file count | 108 | B3-GIGADB-RECORD, B3-MOABB-LEE-SOURCE | MODERATE |
| Original MI filename pattern | `sessSS_subjNN_EEG_MI.mat` | B3-GIGADB-RECORD, B3-MOABB-LEE-SOURCE | STRONG |
| Original per-file sizes | Published individually; not frozen in this review | B3-GIGADB-RECORD | MODERATE |
| Original collection byte size | UNKNOWN | B3-GIGADB-RECORD | UNKNOWN |
| Original SHA-256 | UNKNOWN | B3-GIGADB-RECORD | UNKNOWN |
| Original SHA-512 | UNKNOWN | B3-GIGADB-RECORD | UNKNOWN |
| Original MD5 | UNKNOWN | B3-GIGADB-RECORD | UNKNOWN |
| Signed checksum | UNKNOWN | B3-GIGADB-RECORD | UNKNOWN |
| ETag | UNKNOWN; no file request made | NONE | UNKNOWN |
| Last-Modified | UNKNOWN; no file request made | NONE | UNKNOWN |
| Repository object IDs | GigaDB record and path names only | B3-GIGADB-RECORD | WEAK |
| Changelog/replacement/withdrawal history | No entries displayed | B3-GIGADB-RECORD | WEAK |
| NEMAR derivative version | v1.0.1 | B3-NEMAR-MIRROR | STRONG |
| NEMAR derivative archive size | 24.8 GB display value | B3-NEMAR-MIRROR | MODERATE |

Filename, size, DOI, ETag, and Last-Modified are not cryptographic identity.
The NEMAR derivative's version and size do not establish identity for the
original GigaDB MATLAB collection.

## First-acquisition identity policy

FIRST_ACQUISITION_POLICY: `QUARANTINE_THEN_HUMAN_APPROVAL`

This policy is a design record only and is not authorized to execute.

1. `QUARANTINE_ACQUISITION`
   - Retrieve only the exact approved source variant and exact 108-object
     allowlist.
   - Stream opaque bytes into a dedicated quarantine.
   - Record byte count, SHA-256, exact URL, redirect chain, response status,
     selected headers, and retrieval time for each object.
   - Do not load MATLAB, parse scientific metadata, inspect labels, or invoke
     MOABB/MNE.
   - Produce `UNAPPROVED_CANDIDATE_IDENTITY` for every object and a canonical
     collection manifest.
2. `INDEPENDENT_IDENTITY_VERIFICATION`
   - Calculate SHA-256 independently with at least two tools.
   - Require exact per-file and collection byte-count agreement.
   - Validate all 108 exact filenames and paths and reject extras/missing
     objects.
   - Compare official displayed sizes where captured.
   - Validate the exact HTTPS source and redirect chain.
   - Preserve response metadata.
   - A repeated acquisition may be compared only if separately permitted and
     operationally justified; it is not an automatic requirement for this
     large collection.
3. `HUMAN_APPROVAL`
   - Bind a named approver, timestamp, evidence record, dataset identity,
     project-local immutable release label, exact 108 URLs, every SHA-256 and
     byte size, canonical collection-manifest SHA-256, destination, resource
     limits, and reason.
   - Only that explicit approval may promote the candidate to
     `APPROVED_RAW_ARCHIVE_IDENTITY` (interpreted here as an approved raw
     collection identity).

Changed-source behavior:

- `SAME_URL_DIFFERENT_HASH`: `SOURCE_IDENTITY_CHANGED`; fail closed, quarantine
  the new candidate, preserve the old approved identity, and require new
  source/version review.
- `DIFFERENT_URL_SAME_HASH`: `SOURCE_MIGRATION_CANDIDATE`; require
  source-authenticity review and never update authorization silently.
- `SAME_FILENAME_DIFFERENT_SIZE`: `FAIL_CLOSED`.
- `NO_OFFICIAL_VERSION`: create a project-local immutable acquisition identity
  bound to the complete approved manifest; never call it an upstream version.
- Automatic hash or approval updates: prohibited.

## Destination review

- Destination: `E:\nap-eeg-mini-data\lee2019_mi`.
- Repository separation: outside `E:\nap-eeg-mini`.
- Filesystem: user-established NTFS.
- Drive: user-established fixed E drive.
- Health: user-established healthy.
- Link status: current `Get-Item` shows ordinary `Directory`, empty `LinkType`,
  and no target.
- Write/delete: user-established tests passed; not repeated in this read-only
  review.
- Empty directory: current read-only `Get-ChildItem` returned zero items.
- Current result: `PASS_CURRENT_BASIC_CHECKS`.
- Remaining approval: `SAFE_EXTRACTION_TOCTOU_APPROVAL =
  PENDING_HUMAN_APPROVAL`.

The exact absolute path is retained in the draft because the requested human
approval must bind to that exact candidate destination. It remains a
machine-specific draft value and grants no authority.

## B3 evidence checklist

| Gate | Current evidence | Status |
|---|---|---|
| Dataset/paper/data DOI | GigaDB, paper, DOI resolver | VERIFIED |
| Official source authenticity | GigaDB record and paper cross-link | VERIFIED_OFFICIAL |
| Original source exact host/path | GigaDB record plus MOABB source | CANDIDATE_NOT_AUTHORIZED |
| Upstream release/version | No named GigaDB version | UNKNOWN |
| Original cryptographic identity | No authoritative checksum | UNKNOWN |
| Raw-data license | GigaDB default CC0, no record exception | VERIFIED |
| Automated GigaDB retrieval permission | No explicit statement | UNVERIFIED |
| Research/redistribution | CC0 | PERMITTED |
| Credentials | No credentials displayed or used by MOABB GigaDB path | NOT_REQUIRED |
| Source structure | 108 independent MI MATLAB objects | VERIFIED |
| Acquisition workflow compatibility | Current workflow assumes one archive | BLOCKED |
| First-acquisition policy | Quarantine and human approval | DEFINED |
| Finite resource limits | All unset | REQUIRED |
| Exact destination | Recorded and read-only checked | PASS_CURRENT_BASIC_CHECKS |
| TOCTOU approval | Not yet granted | PENDING_HUMAN_APPROVAL |
| Named approver and authorization identity | Unset | REQUIRED |
| Scientific capabilities | All deny | PASS |

## Findings

### B3-SOURCE-001

- SEVERITY: `HIGH`
- ORIGIN: `GOVERNANCE_GAP`
- BLOCKING: `YES`
- BLOCKS: `B3`
- STATUS: `OPEN`
- OBSERVED: The official original source is a 108-file GigaDB collection,
  while the controlled workflow and template center on one archive.
- EXPECTED: Exact collection-aware source identity and workflow semantics.
- EVIDENCE: `B3-GIGADB-RECORD`, `B3-MOABB-LEE-SOURCE`
- REMEDIATION: Select the authorized source variant and add a separately
  reviewed multi-object acquisition design before authorization.

### B3-VERSION-001

- SEVERITY: `HIGH`
- ORIGIN: `GOVERNANCE_GAP`
- BLOCKING: `YES`
- BLOCKS: `B3`
- STATUS: `OPEN`
- OBSERVED: GigaDB publishes no named original release/version and uses a
  `live/pub` path.
- EXPECTED: Exact upstream version or an explicitly approved project-local
  immutable acquisition identity.
- EVIDENCE: `B3-GIGADB-RECORD`
- REMEDIATION: Use first-seen quarantine and bind a human-approved collection
  manifest; do not label it an upstream version.

### B3-LICENSE-001

- SEVERITY: `LOW`
- ORIGIN: `DISCOVERED`
- BLOCKING: `NO`
- BLOCKS: `NONE`
- STATUS: `FIXED`
- OBSERVED: The raw-data license had previously been unresolved.
- EXPECTED: Primary-source license evidence.
- EVIDENCE: GigaDB's default CC0 waiver applies to this associated dataset,
  with no exception displayed.
- REMEDIATION: Preserve the source/limitation record and re-review if GigaDB
  terms or record-specific terms change.

### B3-MOABB-GPL-001

- SEVERITY: `MEDIUM`
- ORIGIN: `GOVERNANCE_GAP`
- BLOCKING: `NO`
- BLOCKS: `NONE`
- STATUS: `FIXED`
- OBSERVED: MOABB displays GPL 3.0 without scope explanation.
- EXPECTED: Separate code/toolbox, article, original data, and derivative
  licenses.
- EVIDENCE: The paper places GPL 3.0 under source-code requirements; GigaDB
  applies CC0 to the dataset; the article is CC BY 4.0.
- REMEDIATION: Keep the explicit scope distinction.

### B3-AUTOMATION-001

- SEVERITY: `HIGH`
- ORIGIN: `UNCERTAIN`
- BLOCKING: `YES`
- BLOCKS: `B3`
- STATUS: `OPEN`
- OBSERVED: GigaDB does not explicitly grant unattended automated retrieval,
  although it publishes direct links. NEMAR documents automation only for its
  derived version.
- EXPECTED: Explicit source-specific automated-download permission.
- EVIDENCE: `B3-GIGADB-TERMS`, `B3-NEMAR-MIRROR`
- REMEDIATION: Obtain and record authoritative GigaDB confirmation or choose a
  separately reviewed, scientifically acceptable source with explicit terms.

### B3-REDISTRIBUTION-001

- SEVERITY: `LOW`
- ORIGIN: `DISCOVERED`
- BLOCKING: `NO`
- BLOCKS: `NONE`
- STATUS: `FIXED`
- OBSERVED: Redistribution had not been established.
- EXPECTED: Primary-source permission.
- EVIDENCE: GigaDB CC0 waiver.
- REMEDIATION: Retain attribution/citation etiquette despite no CC0 legal
  attribution condition.

### B3-HASH-001

- SEVERITY: `HIGH`
- ORIGIN: `GOVERNANCE_GAP`
- BLOCKING: `YES`
- BLOCKS: `B3`
- STATUS: `OPEN`
- OBSERVED: No authoritative cryptographic identity was found for the original
  GigaDB MATLAB files.
- EXPECTED: Predeclared hashes or quarantine plus explicit first-seen approval.
- EVIDENCE: GigaDB file attributes show no checksum; MOABB uses no upstream
  pinned hash.
- REMEDIATION: Apply the collection-aware quarantine policy and never
  auto-update approved hashes.

### B3-CREDENTIALS-001

- SEVERITY: `LOW`
- ORIGIN: `DISCOVERED`
- BLOCKING: `NO`
- BLOCKS: `NONE`
- STATUS: `ACCEPTED_LIMITATION`
- OBSERVED: Public links and MOABB require no credentials, but file endpoints
  were deliberately not requested.
- EXPECTED: No personal credential dependency.
- EVIDENCE: `B3-GIGADB-RECORD`, `B3-MOABB-LEE-SOURCE`
- REMEDIATION: Fail closed if any later endpoint requests authentication,
  cookies, registration, or click-through acceptance.

### B3-S1-S2-ROLE-001

- SEVERITY: `MEDIUM`
- ORIGIN: `GOVERNANCE_GAP`
- BLOCKING: `NO`
- BLOCKS: `NONE`
- STATUS: `ACCEPTED_LIMITATION`
- OBSERVED: Upstream documents equivalent protocols across two sessions but
  does not designate S1 training and S2 independent evaluation.
- EXPECTED: Label the role assignment as project-defined.
- EVIDENCE: `B3-PAPER`, frozen project protocol.
- REMEDIATION: Preserve the distinction and do not claim upstream provenance.

### B3-DESTINATION-001

- SEVERITY: `LOW`
- ORIGIN: `DISCOVERED`
- BLOCKING: `NO`
- BLOCKS: `NONE`
- STATUS: `FIXED`
- OBSERVED: Candidate path exists, is an ordinary empty directory, and remains
  outside the repository.
- EXPECTED: Exact dedicated destination with basic isolation checks.
- EVIDENCE: Current read-only `Test-Path`, `Get-Item`, and `Get-ChildItem` plus
  user-established drive/write/delete facts.
- REMEDIATION: Revalidate at authorization time.

### B3-TOCTOU-APPROVAL-001

- SEVERITY: `MEDIUM`
- ORIGIN: `PRE_EXISTING`
- BLOCKING: `YES`
- BLOCKS: `B3`
- STATUS: `PENDING_HUMAN_APPROVAL`
- OBSERVED: Basic destination checks do not eliminate ancestor replacement or
  concurrent-writer risk.
- EXPECTED: Human acceptance bound to the exact local fixed NTFS path,
  non-shared/non-synced/non-reparse ancestry, trusted writer context, and
  single-host operation.
- EVIDENCE: Phase II-B pre-merge risk record and current destination check.
- REMEDIATION: Obtain explicit named approval in a later task.

### B3-MOABB-TLS-001

- SEVERITY: `HIGH`
- ORIGIN: `DISCOVERED`
- BLOCKING: `YES`
- BLOCKS: `B3`
- STATUS: `OPEN`
- OBSERVED: Current MOABB download helper sets TLS verification false for
  HTTP/DOI downloader types.
- EXPECTED: Certificate verification and exact redirect-host policy.
- EVIDENCE: `B3-MOABB-DOWNLOAD-SOURCE`
- REMEDIATION: Do not use the MOABB downloader for authorized acquisition;
  retain the project's stricter transport and verify TLS end to end.

### B3-NEMAR-DERIVATIVE-001

- SEVERITY: `MEDIUM`
- ORIGIN: `DISCOVERED`
- BLOCKING: `YES`
- BLOCKS: `B3`
- STATUS: `OPEN`
- OBSERVED: Current MOABB `download()` prefers a 2026 NEMAR BIDS derivative,
  while direct `data_path()` uses original GigaDB MATLAB objects.
- EXPECTED: One explicitly selected scientific/source identity; no silent
  substitution between raw original and derived representation.
- EVIDENCE: `B3-MOABB-LEE-SOURCE`, `B3-MOABB-BASE-SOURCE`,
  `B3-NEMAR-MIRROR`
- REMEDIATION: Decide source representation in a later reviewed protocol task.

## Research and command record

Research used text-only web retrieval and a background browser inspection for
the dynamic GigaDB record and terms. The browser did not click any file link.
Successfully reviewed domains were `doi.org`, `gigadb.org`,
`academic.oup.com`, `github.com`, `moabb.neurotechx.com`, and
`ww2.nemar.org`. Attempts to open the GigaDB robots page, DataCite API record,
and NEMAR metadata manifest were blocked by the client before usable content
was returned. They provided no evidence and transferred no dataset content.

HEAD requests: none.

Deliberately uncontacted endpoints:

- every GigaDB/Wasabi `.mat` data object;
- NEMAR ZIP and direct/annex/S3 data objects;
- MOABB, MNE, NEMAR, DataLad, git-annex, curl, wget, or other acquisition
  helpers.

Repository commands used for the evidence phase were read-only Git identity and
status commands, source/config inspection, exact destination `Test-Path`,
`Get-Item`, and `Get-ChildItem`, and later validation commands recorded by the
commit that contains this document.

Validation results:

- `git diff --check`: pass; Git emitted only its configured LF-to-CRLF working
  tree notice for the changed JSON file.
- Changed JSON parse: `JSON_VALID`.
- Targeted B3/acquisition/workflow/execution/environment tests: `114 passed,
  68 subtests passed`.
- Complete suite with bytecode and pytest cache disabled: `496 passed, 106
  subtests passed`; no pytest cache warning.
- CLI `--help`: pass.
- CLI `plan`: pass and reported:
  - `LEE2019_MI_DATA_ACCESS=NONE`
  - `NETWORK_AUTHORIZATION=DENY`
  - `ACQUISITION_AUTHORIZATION=DENY`
  - `RAW_DATA_IDENTITY_GATE=NOT_ACQUIRED`
  - `SCIENTIFIC_EXECUTION_AUTHORIZATION=DENY`
  - `PLAN_WRITES_DATA=NO`

## Safety declaration

- Lee files searched locally: `NO`
- Lee files stat-ed locally: `NO`
- Real dataset file URL requested: `NO`
- Real archive downloaded: `NO`
- Data response body retained: `NO`
- Scientific formats opened: `NO`
- Labels inspected: `NO`
- Channels inspected from data: `NO`
- Subjects inspected from data: `NO`
- Sessions parsed from data: `NO`
- Trials parsed: `NO`
- MOABB acquisition run: `NO`
- MNE acquisition run: `NO`
- Preprocessing run: `NO`
- Training run: `NO`
- Evaluation run: `NO`
- Metrics run: `NO`
- Credentials used: `NO`
- Packages installed or updated: `NO`
- Anything pushed: `NO`

## Decision

DECISION: `B3_PREAUTHORIZATION_BLOCKED`

REAL_DATA_ACQUISITION_AUTHORIZATION: `DENY`

SCIENTIFIC_EXECUTION_AUTHORIZATION: `DENY`

A later explicit human approval task is required before any acquisition.
