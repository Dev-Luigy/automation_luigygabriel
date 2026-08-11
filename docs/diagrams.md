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

**Status: Implemented assessment**, with the optional HTTPS extractor available
as an adapter but not composed by default.

```mermaid
flowchart LR
    caller["Authenticated API caller"]
    reviewer["Finance reviewer"]

    subgraph serviceBoundary ["Expense Agent Python process"]
        console["HTML, CSS and vanilla JS console"]
        api["FastAPI adapter"]
        processing["ProcessingService"]
        review["ReviewService"]
        extractor["Offline deterministic extractor"]
        policy["BaselinePolicy v1"]
        repository["SqliteReviewRepository"]
    end

    sqlite[("File-backed SQLite")]
    optionalProvider["Optional HTTPS JSON extractor"]

    caller -->|"Intake and result"| api
    reviewer -->|"Assessment authentication"| console
    console -->|"Same-origin requests"| api
    api --> processing
    api --> review
    processing --> extractor
    extractor --> policy
    processing --> repository
    review --> repository
    repository --> sqlite
    processing -.->|"Replaceable adapter"| optionalProvider
```

The executable accepts supplied OCR text and attachment reference strings. It
does not upload receipt bytes, run a binary OCR engine, use a secondary verifier,
or depend on ClickUp, email, n8n, or an existing RecargaPay system.

## 2. Reimbursement lifecycle and aggregate versions

**Status: Implemented assessment.** Both automated and human rejection use the
domain status `rejected`; the transition label records whether the aggregate
reached it at v3 or v4.

```mermaid
stateDiagram-v2
    direction LR

    [*] --> Received: intake accepted v1
    Received --> Processing: run claimed v2
    Processing --> AutoApproved: all rules pass v3
    Processing --> PendingReview: review required v3
    Processing --> Rejected: reject rule v3
    PendingReview --> ApprovedAfterReview: approve with rationale v4
    PendingReview --> Rejected: reject with rationale v4
```

The implemented old-receipt rule takes precedence over review routing, and
exactly 90 days remains valid. That precedence and the literal BRL 2,000 boundary
are tested assessment interpretations pending policy-owner validation.

## 3. Summarized persistence model

**Status: Implemented assessment** in normalized SQLite. The diagram omits the
compatibility projection and repository metadata table to keep the operational
ledger readable; [database.md](database.md) documents the complete schema.

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
        text status
    }
    PROCESSING_INVOCATION_ATTEMPTS {
        text invocation_id PK
        text processing_run_id FK
        integer attempt
        text status
        text input_hash
        text output_hash
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
        text correlation_id
    }
```

`request_id` is the aggregate identity and public idempotency key. Processing
run, invocation, automated decision, human decision, and event identifiers stay
independent so retries and evidence cannot be mistaken for the business request.

## 4. Processing sequence and durable boundaries

**Status: Implemented assessment.** The extractor call runs outside a database
transaction; durable invocation intent and completion surround it.

```mermaid
sequenceDiagram
    title New reimbursement processing
    participant Caller
    participant FastAPI
    participant ProcessingService
    participant SQLite
    participant ReceiptExtractor
    participant BaselinePolicy

    Caller->>FastAPI: POST /api/requests
    FastAPI->>ProcessingService: Process validated submission
    ProcessingService->>SQLite: Register received v1
    ProcessingService->>SQLite: Start run and processing v2
    ProcessingService->>SQLite: Begin invocation attempt
    ProcessingService->>ReceiptExtractor: Extract supplied OCR text
    ReceiptExtractor-->>ProcessingService: Facts or bounded failure
    ProcessingService->>SQLite: Finish attempt with trace
    ProcessingService->>BaselinePolicy: Evaluate exact facts
    BaselinePolicy-->>ProcessingService: Route, reasons and rules
    ProcessingService->>SQLite: Atomically finalize v3
    SQLite-->>ProcessingService: Stored result
    ProcessingService-->>FastAPI: Safe result
    FastAPI-->>Caller: 201 with result location
```

Before a new run starts, the repository compares `request_id` and the canonical
submission hash. A matching replay returns the stored result and records a
security event; a different payload for the same ID records a conflict event and
returns HTTP 409. A process crash can still strand v2/running state because
lease, watchdog, retry, DLQ, and recovery orchestration are release gates.

## 5. Human review and audit projection

### Human decision

**Status: Implemented assessment.** Reviewer identity is derived from verified
credentials, rationale is mandatory, and the decision is an atomic v3 to v4
write guarded by `ETag` and `If-Match`.

```mermaid
sequenceDiagram
    title Human review decision
    participant Reviewer
    participant ReviewConsole
    participant FastAPI
    participant ReviewService
    participant SQLite

    Reviewer->>ReviewConsole: Open pending case
    ReviewConsole->>FastAPI: GET review detail
    FastAPI->>ReviewService: Load authorized evidence
    ReviewService->>SQLite: Read case and version
    SQLite-->>ReviewService: Case, evidence and version
    ReviewService-->>FastAPI: Authorized detail
    FastAPI-->>ReviewConsole: Evidence and ETag
    Reviewer->>ReviewConsole: Select outcome and rationale
    ReviewConsole->>FastAPI: POST decision with If-Match
    FastAPI->>ReviewService: Apply server-derived identity
    ReviewService->>SQLite: Commit decision, v4 and audit event
    SQLite-->>ReviewService: Decision and audit ID
    ReviewService-->>FastAPI: Stored result
    FastAPI-->>ReviewConsole: 201 and new ETag
```

### Audit projection

**Status: Partial / release gate.** Processing and decision history is durable;
audit coverage of every service operation is not yet complete.

```mermaid
flowchart LR
    command["State-changing command"] --> transaction["Explicit SQLite transaction"]
    transaction --> aggregate["Aggregate state and version"]
    transaction --> evidence["Extraction and decision evidence"]
    transaction --> events["Append-only audit events"]

    events --> business["Business scope"]
    events --> technical["Technical scope"]
    events --> security["Security scope"]

    business --> timeline["Sanitized reviewer timeline"]
    technical -.-> protected["Protected database trace"]
    security -.-> protected
```

Authentication outcomes, ordinary reads, searches, validation and orchestration
errors, authorization decisions, evidence access, and administrative actions are
not comprehensively audited. The reviewer timeline deliberately excludes raw
provider output and technical/security event payloads.

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
    aurora --> exporter["Idempotent audit exporter"]
    exporter --> archive[("Approved immutable S3 archive")]
```

The target replaces assessment-only HTTP Basic, synchronous execution, SQLite,
attachment references, and database-only audit with application-owned managed
identity and authorization, queued idempotent processing, an authoritative SQL
ledger/outbox, versioned evidence, and approved immutable export. There is no
production Cognito pool/BFF, queue, Aurora cluster/repository, receipt bucket,
CloudFront/WAF edge, outbox/exporter, DNS record, AWS account selection, or live
cloud deployment in this repository. The SAM sandbox below is deliberately not
the production topology.

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
    lambda --> efs["Encrypted retained EFS\nSQLite journal DELETE"]
    lambda --> telemetry["14-day logs, X-Ray, alarms"]
    deploy --> seed["Synthetic HTTPS seed"]
    seed --> gateway

    risk["Assessment only\nSQLite over NFS risk\nBasic/global scope"] -.-> efs
    target["Production target\nAurora + Cognito + S3 + SQS"] -.-> lambda
```

The SAM template defines a new VPC, two private subnets, Lambda/EFS security
groups, an encrypted backed-up EFS access point, a direct HTTPS API, bounded
Lambda concurrency, least-privilege EFS access, log retention, and alarms. The
script prompts before billable changes, derives only a PBKDF2 hash from the
hidden password, generates a CSRF secret, seeds public fixtures, and prints the
review URL.

Local evidence proves the template and build path, not AWS operation: no account
was mutated and there is no live endpoint, EFS recovery test, concurrency/load
result, or security approval. SQLite's rollback journal avoids the direct WAL
incompatibility but does not make network-filesystem persistence safe enough for
real financial state. The accepted production target remains unchanged.
