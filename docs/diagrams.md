# Diagram gallery

This page is the central visual index for Expense Agent. It consolidates the
main views already accepted in the detailed documentation without changing the
underlying decisions. The diagrams distinguish executable assessment behavior
from production targets and future delivery work.

## Status legend

| Label | Meaning |
| --- | --- |
| **Implemented assessment** | Exists in this repository and is exercised by automated tests. |
| **Partial / release gate** | A useful assessment slice exists, but a control or production capability is incomplete. |
| **Accepted target — not implemented** | The production direction is accepted, but this repository contains no corresponding production adapters/resources or production IaC. |
| **Packaged and validated — not provisioned** | Deployment artifacts pass local checks, but no cloud account or live resource was changed. |

The source-of-truth details remain in [system architecture](architecture.md),
[database model](database.md), [domain model](domain-model.md), [feature
catalog](features.md), and the [decision log](decision-log.md).

## 1. Assessment context and request flow

**Status: Implemented assessment.** The deterministic extractor is the default;
the HTTPS+JSON adapter is selectable only through explicit strict environment
configuration. The SAM sandbox remains deterministic because it has no NAT.

```mermaid
flowchart LR
    submitter["Authenticated submitter"]
    reviewer["Reviewer or auditor"]

    subgraph serviceBoundary ["Expense Agent Python process"]
        submitPortal["HTML, CSS and vanilla JS\nsubmit-and-track portal"]
        reviewConsole["HTML, CSS and vanilla JS\nreview console"]
        api["FastAPI adapter"]
        authz["Configured roles\nowner + four-eyes checks"]
        processing["ProcessingService"]
        review["ReviewService"]
        extractor["Configured extractor\ndeterministic default"]
        policy["BaselinePolicy v3\nrule 1.2.0"]
        execution["ExecutionIdentity\nbuild_id + configuration_hash"]
        repository["SqliteReviewRepository"]
        attachmentStore["Immutable filesystem attachment store\nprivate directories + trusted owner UID"]
        operationAudit["All-HTTP operational audit"]
    end

    sqlite[("File-backed SQLite")]
    attachmentRoot[("Private owner-validated attachment root")]
    optionalProvider["Optional HTTPS JSON extractor"]

    submitter -->|"Assessment authentication"| submitPortal
    reviewer -->|"Assessment authentication"| reviewConsole
    submitPortal -->|"Upload, intake and exact tracking"| api
    reviewConsole -->|"Discovery, evidence and decision"| api
    api --> authz
    api --> processing
    api --> review
    api --> attachmentStore
    api --> operationAudit
    processing --> extractor
    extractor --> policy
    execution --> processing
    execution --> review
    execution --> operationAudit
    processing --> repository
    review --> repository
    operationAudit --> repository
    repository --> sqlite
    attachmentStore --> attachmentRoot
    extractor -.->|"Explicit http_json mode"| optionalProvider
```

The executable uploads bounded JPEG/PNG/PDF bytes, returns an opaque managed
reference, and accepts supplied OCR text in the subsequent claim. It does not
derive OCR from those exact bytes, scan for malware, use a secondary verifier,
or depend on ClickUp, email, n8n, or an existing RecargaPay system. Store
directories must be private, non-symlink paths owned by the configured trusted
POSIX UID; local execution defaults to the process effective UID. New HTTP
intake rejects arbitrary legacy attachment strings with `422`; only seeded or
upgraded persisted rows remain readable, and those strings do not prove file
existence.

The current execution identity is not a UI label. Processing runs bind policy,
build, and effective configuration digest in `pipeline_version`; intake,
processing-start, human-decision, and operational HTTP evidence retain the
relevant `build_id` and `configuration_hash` without copying cleartext settings.

## 2. Reimbursement lifecycle and aggregate versions

**Status: Implemented assessment.** Both automated and human rejection use the
domain status `rejected`; the transition records whether automation or a human
produced it. Versions increase on every aggregate mutation.

```mermaid
stateDiagram-v2
    direction LR

    [*] --> Received: intake accepted v1
    Received --> Processing: leased run claimed v2
    Processing --> Processing: expired lease recovered, next run vN to vN+1
    Processing --> AutoApproved: all rules pass and evidence exists, next version
    Processing --> PendingReview: review rule or amount above BRL 2,000, next version
    Processing --> Rejected: reject rule without high-value gate, next version
    PendingReview --> ApprovedAfterReview: approve with rationale and no reject rule, next version
    PendingReview --> Rejected: reject with rationale, next version
    PendingReview --> Rejected: mandatory reject confirmation when a reject rule exists, next version
```

Without recovery the states are received v1, processing v2, automated final v3,
and human final v4. Each recovered lease consumes another version before
finalization, so API clients use the returned version and ETag rather than a
status-derived constant.

`baseline-v3`/rule `1.2.0` makes the above-BRL-2,000 review gate non-bypassable.
An old high-value receipt therefore reaches a human, while the aggregate forbids
approval and requires rejection with rationale. Missing receipt evidence also
blocks automatic approval. Exactly 90 days remains valid. Collision semantics,
the literal BRL 2,000 boundary, and the caller-supplied age anchor still require
policy-owner validation before production.

## 3. Summarized persistence model

**Status: Implemented assessment** in normalized SQLite plus a private immutable
filesystem attachment tree. The diagram omits the compatibility projection and
repository metadata table to keep the operational ledger readable;
[database.md](database.md) documents the complete sixteen-table schema.

```mermaid
erDiagram
    direction LR

    REIMBURSEMENTS ||--o{ ATTACHMENTS : has
    REIMBURSEMENTS ||--o{ PROCESSING_RUNS : executes
    PROCESSING_RUNS ||--o{ PROCESSING_INVOCATION_ATTEMPTS : contains
    REIMBURSEMENTS ||--o| EXTRACTIONS : selects
    PROCESSING_RUNS ||--o| EXTRACTIONS : finalizes
    PROCESSING_INVOCATION_ATTEMPTS ||--o| EXTRACTIONS : sources
    REIMBURSEMENTS ||--o| AUTOMATED_DECISIONS : receives
    PROCESSING_RUNS ||--o| AUTOMATED_DECISIONS : produces
    AUTOMATED_DECISIONS ||--|{ DECISION_REASONS : explains
    AUTOMATED_DECISIONS ||--|{ RULE_EVALUATIONS : proves
    AUTOMATED_DECISIONS ||--o| REVIEW_CASES : routes
    REVIEW_CASES ||--o{ REVIEW_PROBLEMS : exposes
    REVIEW_CASES ||--o| HUMAN_DECISIONS : resolves
    REVIEW_CASES ||--o| REVIEW_DECISION_IDEMPOTENCY : binds
    HUMAN_DECISIONS ||--o| REVIEW_DECISION_IDEMPOTENCY : replays
    AUDIT_EVENTS ||--o| REVIEW_DECISION_IDEMPOTENCY : returns
    REIMBURSEMENTS ||--o{ AUDIT_EVENTS : records

    REIMBURSEMENTS {
        text request_id PK
        text submission_hash UK
        text status
        integer version
    }
    ATTACHMENTS {
        text request_id PK, FK
        integer ordinal PK
        text location
    }
    PROCESSING_RUNS {
        text processing_run_id PK
        text request_id FK
        integer run_number
        text pipeline_version
        text status
        datetime lease_expires_at
        datetime abandoned_at
    }
    PROCESSING_INVOCATION_ATTEMPTS {
        text invocation_id PK
        text processing_run_id FK
        integer attempt
        text status
        text input_hash
        text output_hash
        datetime abandoned_at
    }
    EXTRACTIONS {
        text request_id PK, FK
        text processing_run_id FK
        text source_invocation_id FK
    }
    AUTOMATED_DECISIONS {
        text decision_id PK
        text request_id FK
        text route
        text policy_version
    }
    DECISION_REASONS {
        text decision_id PK, FK
        integer ordinal PK
        text code
    }
    RULE_EVALUATIONS {
        text decision_id PK, FK
        integer ordinal PK
        text rule_id
        text outcome
    }
    REVIEW_CASES {
        text request_id PK
        text source_decision_id FK
        text status
    }
    REVIEW_PROBLEMS {
        text request_id PK, FK
        integer ordinal PK
        text code
    }
    HUMAN_DECISIONS {
        text decision_id PK
        text request_id FK
        text reviewer_id
        text outcome
    }
    AUDIT_EVENTS {
        text event_id PK
        text request_id FK
        text event_scope
        text actor_type
        text correlation_id
        text payload_json
    }
    REVIEW_DECISION_IDEMPOTENCY {
        text idempotency_key_hash PK
        text command_fingerprint
        text request_id FK, UK
        text decision_id FK, UK
        text audit_event_id FK, UK
        integer resulting_version
    }
    OPERATIONAL_AUDIT_EVENTS {
        text event_id PK
        text correlation_id
        text request_id
        text actor_type
        text actor_id
        text operation_type
        text route
        integer status_code
        text authentication
        integer duration_ms
        text metadata_json
    }
```

`request_id` is the aggregate identity and public idempotency key. Processing
run, invocation, automated decision, human decision, and event identifiers stay
independent so retries and evidence cannot be mistaken for the business request.
Human decisions additionally use an irreversible idempotency-key hash and a
full command fingerprint. `OPERATIONAL_AUDIT_EVENTS` deliberately has no required
case foreign key because login failures, static reads, and unmatched routes may
occur before a valid request exists. The `ATTACHMENTS.location` relationship may
hold an opaque managed reference; exact bytes and checksum/media/filename
metadata remain in the filesystem envelope rather than a SQLite blob.
`PROCESSING_RUNS.pipeline_version` binds policy/build/configuration. Whitelisted
business payloads store the execution identity and decision evidence state;
operational metadata stores the execution identity for every HTTP attempt.

## 4. Processing sequence and durable boundaries

**Status: Implemented assessment.** The extractor call runs outside a database
transaction; durable invocation intent and completion surround it.

```mermaid
sequenceDiagram
    title Receipt upload, new processing and expired-lease recovery
    participant Submitter
    participant FastAPI
    participant AttachmentStore
    participant ProcessingService
    participant ExecutionIdentity
    participant SQLite
    participant ReceiptExtractor
    participant BaselinePolicy

    Submitter->>FastAPI: POST /api/attachments with raw bytes
    FastAPI->>AttachmentStore: Store immutable bounded object
    AttachmentStore-->>FastAPI: Opaque identity plus checksum metadata
    FastAPI-->>Submitter: 201 managed reference
    Submitter->>FastAPI: POST /api/requests with managed reference
    FastAPI->>AttachmentStore: Verify managed evidence integrity
    FastAPI->>ProcessingService: Process validated submission
    ProcessingService->>ExecutionIdentity: Bind policy, build and configuration
    ExecutionIdentity-->>ProcessingService: Auditable pipeline version
    ProcessingService->>SQLite: Register or read same-hash request plus execution identity
    alt different payload under same request ID
        SQLite-->>ProcessingService: Conflict plus security event
        ProcessingService-->>FastAPI: Conflict
        FastAPI-->>Submitter: 409
    else identical terminal request
        SQLite-->>ProcessingService: Stored final result
        ProcessingService-->>FastAPI: replayed true
        FastAPI-->>Submitter: 200
    else new, received, or processing request
        ProcessingService->>SQLite: Claim five-minute run lease under pipeline version
        alt identical retry while lease active
            SQLite-->>ProcessingService: acquired false and current processing version
            ProcessingService-->>FastAPI: replayed true without extractor call
            FastAPI-->>Submitter: 200
        else new request or existing received v1
            SQLite-->>ProcessingService: acquired true and processing v2
        else identical retry after lease expiry
            ProcessingService->>SQLite: Abandon old run or attempt and atomically claim next run
            SQLite-->>ProcessingService: acquired true, recovered true, next run
        end
        opt acquired lease owner
            ProcessingService->>SQLite: Begin invocation attempt
            ProcessingService->>ReceiptExtractor: Extract supplied OCR text
            ReceiptExtractor-->>ProcessingService: Facts or bounded failure
            ProcessingService->>SQLite: Finish attempt with trace
            ProcessingService->>BaselinePolicy: Evaluate exact facts
            BaselinePolicy-->>ProcessingService: Route, reasons and rules
            ProcessingService->>SQLite: Atomically finalize at next version
            SQLite-->>ProcessingService: Stored result
            ProcessingService-->>FastAPI: Safe result
            FastAPI-->>Submitter: 201 if new, otherwise 200
        end
    end
```

Before a new run starts, the repository compares `request_id` and the canonical
submission hash. A matching terminal/active replay returns stored state and
records a security event; a different payload records a conflict event and
returns HTTP 409. After the five-minute lease expires, one identical retry
atomically preserves abandonment evidence and owns a new numbered run; stale
workers cannot finalize. No background watchdog, heartbeat, retry budget,
queue/DLQ, or operator replay surface exists, so this remains an assessment
recovery mechanism rather than production orchestration.

## 5. Human review and audit projection

### Human decision

**Status: Implemented assessment.** Reviewer identity and role are derived from
verified credentials. The HTTP adapter and `ReviewService` both enforce
four-eyes separation from the immutable intake actor. Every new decision
revalidates original evidence; approval requires `verified`, while rejection may
preserve an unavailable/corrupt/unverifiable state. Rationale is mandatory, and
the decision is an atomic next-version write guarded by `ETag`/`If-Match` plus a
command `Idempotency-Key`.

```mermaid
sequenceDiagram
    title Human review decision
    participant Reviewer
    participant ReviewConsole
    participant FastAPI
    participant ReviewService
    participant AttachmentStore
    participant SQLite

    Reviewer->>ReviewConsole: Open pending case
    ReviewConsole->>FastAPI: GET review detail
    FastAPI->>ReviewService: Load authorized evidence
    ReviewService->>SQLite: Read case and version
    SQLite-->>ReviewService: Case, evidence and version
    ReviewService-->>FastAPI: Authorized detail
    FastAPI-->>ReviewConsole: Evidence and ETag
    Reviewer->>ReviewConsole: Select outcome and rationale
    ReviewConsole->>FastAPI: POST decision with If-Match and Idempotency-Key
    FastAPI->>ReviewService: Find immutable command replay
    ReviewService->>SQLite: Lookup key hash and command fingerprint
    alt identical key and command already committed
        SQLite-->>ReviewService: Original decision and audit ID
        ReviewService-->>FastAPI: replayed true
        FastAPI-->>ReviewConsole: 200 original result
    else new command
        FastAPI->>ReviewService: Reload decision detail
        ReviewService->>SQLite: Read earliest immutable submitter intake actor
        SQLite-->>ReviewService: submission_actor_id and current version
        ReviewService-->>FastAPI: Decision detail
        alt actor unavailable or matches reviewer
            FastAPI-->>ReviewConsole: 403, separation of duties not proven
        else different immutable actors
            FastAPI->>FastAPI: Classify missing, legacy or invalid references
            FastAPI->>AttachmentStore: Reread and validate every managed original
            AttachmentStore-->>FastAPI: Managed objects verified, missing or failed
            FastAPI->>FastAPI: Resolve bounded evidence-integrity state
            alt approval without verified evidence
                FastAPI-->>ReviewConsole: 409, no financial decision recorded
            else verified approval or rejection with observed state
                FastAPI->>ReviewService: Decide with observed evidence state
                ReviewService->>SQLite: Reload case and immutable intake actor
                ReviewService->>ReviewService: Repeat four-eyes and approval-evidence checks
                ReviewService->>SQLite: Commit decision, next version, event and key binding
                Note right of SQLite: Event stores evidence_integrity, build_id and configuration_hash
                SQLite-->>ReviewService: Decision and audit ID
                ReviewService-->>FastAPI: Stored result
                FastAPI-->>ReviewConsole: 201 and new ETag
            end
        end
    end
```

The stored key is an irreversible SHA-256 digest. Its command fingerprint binds
request, reviewer, outcome, normalized rationale, and expected version. Reusing
the same key for different content returns `409`; an exact retry returns the
original result and creates no second decision or business event.

The intake business actor type is literally `submitter`; the repository derives
`submission_actor_id` from that append-only event. The corresponding HTTP
operation uses `actor_type=authenticated_principal`. A failed approval evidence
check is retained in operational audit metadata; a rejection
that proceeds stores the observed state in the authoritative decision event.

### Audit projection

**Status: Implemented local HTTP-attempt coverage with production release
gates.** Processing and decision history is authoritative; a separate bounded
event records every HTTP request attempt.

```mermaid
flowchart LR
    identity["ExecutionIdentity\nbuild_id + configuration_hash"] --> transaction
    identity --> sanitizer
    command["Financial command or processing result"] --> transaction["Authoritative SQLite transaction"]
    transaction --> aggregate["Aggregate state and version"]
    transaction --> evidence["Extraction and decision evidence"]
    transaction --> events["Append-only audit events"]

    events --> business["Business scope"]
    events --> technical["Technical scope"]
    events --> security["Security scope"]

    business --> timeline["Sanitized reviewer timeline"]
    technical -.-> protected["Protected database trace"]
    security -.-> protected

    attempt["Every HTTP attempt"] --> sanitizer["Route, auth, actor, outcome, duration\nbounded safe metadata"]
    sanitizer --> operational["Append-only operational audit\nseparate transaction"]
    operational -.-> protected
```

Authentication outcomes, authorization decisions, ordinary reads/searches,
validation failures, unmatched routes, evidence upload/access, and server errors
now produce operational events. Request/response bodies, raw OCR, query strings,
credentials, cookies, tokens, and secrets are deliberately excluded. The
reviewer timeline also excludes raw provider output and technical/security event
payloads. Because operational writes are separate from business transactions and
there is no exact query replay, privileged search/export UI, transactional
outbox, off-host immutable archive, or WORM control, this is not yet complete
production traceability.

## 6. Accepted AWS production target

**Status: Accepted target — not implemented.** This is the production direction
recorded by D-026, D-039, D-040, and reaffirmed by D-042. It is not the current
runtime and does not claim a deployment.

```mermaid
flowchart LR
    users["Submitter, reviewer and auditor"] --> edge["CloudFront, WAF and ACM"]
    edge --> shell[("Private S3 web shell")]
    edge --> gateway["API Gateway"]
    gateway --> auth["Lambda authorizer and Cognito BFF"]
    gateway --> apiLambda["Python Lambda APIs"]
    auth --> sessions[("DynamoDB opaque sessions")]
    apiLambda -.-> queue["SQS and DLQ"]
    queue -.-> workers["Lambda workers"]
    apiLambda --> proxy["RDS Proxy"]
    workers --> proxy
    proxy --> aurora[("Aurora PostgreSQL Serverless v2")]
    apiLambda --> evidence[("Versioned private S3 evidence")]
    duplicateTarget["Open control target\ncross-case SHA + merchant/date/amount candidate matching"] -.-> workers
    aurora --> exporter["Idempotent audit exporter"]
    exporter --> archive[("Approved immutable S3 archive")]
```

The target replaces assessment-only HTTP Basic/configured roles, synchronous
execution with retry-triggered local leases, SQLite, filesystem evidence, and
SQLite-only audit with application-owned managed identity and authorization,
queued idempotent processing, an authoritative SQL ledger/outbox, versioned and
scanned object evidence, and approved immutable export. There is no
production Cognito pool/BFF, queue, Aurora cluster/repository, receipt bucket,
CloudFront/WAF edge, outbox/exporter, DNS record, AWS account selection, or live
cloud deployment in this repository. The SAM sandbox below is deliberately not
the production topology.

Cross-case duplicate-candidate detection using exact receipt SHA and normalized
merchant/date/amount signals remains an open production control target. The
assessment performs neither content deduplication nor cross-case matching, and
no such signal is currently an automatic approval/rejection rule.

## 7. AWS assessment sandbox delivery

**Status: Implemented and locally validated artifact; not provisioned.** This
packages the executable assessment for synthetic review, not real finance.

```mermaid
flowchart LR
    developer["Developer in a sandbox account"] --> deploy["deploy/aws/deploy.sh"]
    deploy --> prepare["Minimal source + exact dependency pins"]
    prepare --> validate["SAM lint + x86_64 container build"]
    validate --> cloudformation["SAM / CloudFormation"]
    cloudformation --> gateway["API Gateway HTTP API"]
    gateway --> lambda["Python 3.12 Lambda\nMangum + FastAPI"]
    lambda --> efs["Encrypted retained EFS access point UID 1000\nSQLite + attachment envelopes\njournal DELETE"]
    lambda --> telemetry["14-day logs, X-Ray, alarms"]
    deploy --> seed["Synthetic HTTPS seed"]
    seed --> gateway

    risk["Assessment only\nSQLite over NFS risk\nBasic + reviewer/seed actors\nno scan or trusted OCR binding"] -.-> efs
    target["Production target\nAurora + Cognito + S3 + SQS"] -.-> lambda
```

The SAM template defines a new VPC, two private subnets, Lambda/EFS security
groups, an encrypted backed-up EFS access point, a direct HTTPS API, bounded
Lambda concurrency, least-privilege EFS access, log retention, and alarms. The
EFS access-point POSIX user/root are UID/GID 1000, and Lambda sets
`EXPENSE_AGENT_ATTACHMENT_OWNER_UID=1000` so the filesystem adapter verifies the
same owner boundary. The script prompts before billable changes, derives only a
PBKDF2 hash from the
hidden password, assigns the reviewer the `admin` role, creates a separate
reserved seed `admin` actor with a random credential, derives a commit-and-lock
`build_id` by default, generates a CSRF secret, seeds the provided synthetic
fixtures, and prints the review URL. The seed secret is discarded, allowing the
reviewer actor to decide those cases while four-eyes still prevents either actor
from deciding its own submissions.
The application stores managed receipt envelopes under the same retained EFS
mount as a separate tree, and the HTTPS seeder uploads a synthetic managed PDF
for each sample. Any older upgraded legacy references remain metadata-only. The
sandbox also has no cross-case duplicate-candidate control.

Local evidence proves the template and build path, not AWS operation: no account
was mutated and there is no live endpoint, EFS recovery test, concurrency/load
result, or security approval. SQLite's rollback journal avoids the direct WAL
incompatibility but does not make network-filesystem persistence safe enough for
real financial state. The accepted production target remains unchanged.
