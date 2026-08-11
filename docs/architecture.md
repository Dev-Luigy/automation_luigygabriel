# System architecture

## Architectural position

Expense Agent is a layered, standalone reimbursement service. The executable
assessment owns intake, evidence extraction from supplied OCR text,
deterministic routing, exact-ID result lookup, and internal human review. It
does not depend on ClickUp, email, n8n, an existing RecargaPay application, or
an existing identity/database platform.

The key invariant is simple: probabilistic or heuristic components produce
evidence; versioned deterministic policy produces the financial route.

## Executable assessment context

```mermaid
flowchart LR
    Caller["Authenticated API caller"]
    Reviewer["Finance reviewer"]

    subgraph Service["Expense Agent — one Python process"]
        Static["HTML/CSS/vanilla JS\nreview console"]
        HTTP["FastAPI adapter"]
        Processing["ProcessingService"]
        Review["ReviewService"]
        Extractor["DeterministicReceiptExtractor\ndefault, offline"]
        Policy["BaselinePolicy v1"]
        Repository["SqliteReviewRepository"]
    end

    DB[("File-backed SQLite")]
    Optional["Optional HTTPS+JSON\nextractor endpoint"]

    Caller -->|"intake / result"| HTTP
    Reviewer -->|"Basic auth"| Static
    Static -->|"same-origin fetch"| HTTP
    HTTP --> Processing
    HTTP --> Review
    Processing --> Extractor --> Policy
    Processing --> Repository
    Review --> Repository
    Repository --> DB
    Processing -. "adapter can be explicitly replaced" .-> Optional
```

### Current capabilities and boundaries

| Boundary | Current behavior |
| --- | --- |
| Presentation | Reviewer screen plus authenticated JSON APIs. There is no submitter or privileged audit screen. |
| Identity | HTTP Basic with configured PBKDF2 hashes. The verified principal becomes the audit actor; no actor ID is accepted in a command body. |
| Intake | Strict JSON with supplied OCR text and attachment reference strings. No binary upload or OCR engine. |
| Processing | One synchronous extraction attempt followed by deterministic policy. No SQS, retry scheduler, or secondary verifier. |
| Evidence | Structured receipt facts, protected raw extractor response, input/output hashes, and immutable attempt metadata. |
| Persistence | Normalized file-backed SQLite with explicit transactions and immutability triggers. |
| Result | Exact authenticated lookup across received, processing, automated final, and human final statuses; technical secrets/raw responses are omitted. |
| Review | Search/filter/sort/keyset-paginated pending queue, evidence detail, sanitized business timeline, and atomic individual decision. |

`HttpJsonReceiptExtractor` is implemented as a replaceable adapter with HTTPS-
only configuration, request timeout, response-size limit, strict JSON/schema
validation, redirect rejection, and bounded failures. The environment entry
point intentionally
composes the offline deterministic extractor, so no live provider or secret is
required for the assessment.

## Code layers and dependency direction

```mermaid
flowchart TB
    Presentation["presentation\nFastAPI, static UI, auth/config, CLI"]
    Application["application\nprocessing and review use cases + ports"]
    Domain["domain\nmoney, submissions, extraction, policy, decisions, audit"]
    Infrastructure["infrastructure\nSQLite and extractor adapters"]

    Presentation --> Application
    Presentation --> Infrastructure
    Application --> Domain
    Infrastructure --> Application
    Infrastructure --> Domain
```

- The domain imports neither FastAPI nor SQLite.
- Application services depend on repository/extractor protocols and domain
  values.
- Infrastructure implements those ports and protects provider/database details.
- The composition root chooses concrete adapters.

## End-to-end processing flow

No database transaction is held while an extractor may perform network I/O.
Instead, intent and completion are durable transaction boundaries around the
call.

```mermaid
sequenceDiagram
    autonumber
    actor C as Authenticated caller
    participant A as FastAPI
    participant W as ProcessingService
    participant R as SQLite repository
    participant X as ReceiptExtractor
    participant P as BaselinePolicy

    C->>A: POST /api/requests + CSRF + Origin
    A->>W: process(submission, verified actor, correlation ID)
    W->>R: register_received(hash, event)
    alt same ID and same normalized payload
        R-->>W: stored result
        W-->>A: replayed=true
        A-->>C: 200
    else same ID and different payload
        R-->>W: conflict + security event
        A-->>C: 409
    else new request
        R-->>W: received v1
        W->>R: start_processing(run, event)
        R-->>W: processing v2
        W->>R: begin_invocation(running, technical event)
        W->>X: extract(supplied OCR text)
        X-->>W: facts or bounded failure + trace
        W->>R: finish_invocation(raw output, hash, technical event)
        W->>P: evaluate(submission, extraction)
        P-->>W: route + reasons + rule evaluations
        W->>R: complete extraction + policy + route + events
        R-->>W: final v3
        W-->>A: safe result
        A-->>C: 201 + Location + correlation ID
    end
```

`complete_processing` atomically commits the immutable extraction projection,
automated decision, reasons, rule evaluations, terminal processing run, final
reimbursement status, business event, and—when needed—review case, problems,
and enqueue event. A late failure rolls the entire v2→v3 outcome back.

## State and version flow

```mermaid
stateDiagram-v2
    [*] --> Received: intake accepted / v1
    Received --> Processing: run claimed / v2
    Processing --> AutoApproved: all policy rules pass / v3
    Processing --> PendingReview: review outcome present / v3
    Processing --> Rejected: any reject rule / v3
    PendingReview --> ApprovedAfterReview: approve + rationale / v4
    PendingReview --> Rejected: reject + rationale / v4
```

At this version, any receipt older than 90 days creates a reject rule, and reject
outcomes take precedence over review outcomes. Thus an old receipt above BRL
2,000 is rejected, while retaining the high-value review reason/evaluation as
evidence. Exactly 90 days is valid. The assessment's age anchor is immutable
after intake but is still caller-supplied; a trusted server-owned `received_at`
is a mandatory production replacement. Reject-over-review precedence and the
literal high-value collision are implemented interpretations pending policy-
owner validation, not confirmed stakeholder rules.

## Audit architecture

```mermaid
flowchart LR
    Command["Command / processing step"] --> Transaction["SQLite transaction"]
    Transaction --> State["Aggregate state + version"]
    Transaction --> Evidence["Extraction / decision evidence"]
    Transaction --> Events["Append-only audit_events"]

    Events --> Business["business\nreviewer-safe projection"]
    Events --> Technical["technical\ninvocation start/completion"]
    Events --> Security["security\nreplay/conflict attempts"]

    Business --> Timeline["GET /api/reviews/{id}/events"]
    Technical -. "not exposed by normal APIs" .-> Protected["DB-only assessment trace"]
    Security -. "not exposed by normal APIs" .-> Protected
```

Important identifiers remain distinct: request, submission hash, processing
run, invocation attempt, automated decision, human decision, event, correlation
ID, aggregate version, provider/model/prompt/input/output hashes. The current
reviewer timeline whitelists business event fields and never serializes raw
provider output, technical parameters, credentials, or attachment locations.

This is processing/decision traceability, not full traceability of every
operation. Authentication success/failure, ordinary reads, searches, validation
failures, every orchestration exception, and evidence-access facts are not
comprehensively audited. In addition, a crash can leave v2/a running attempt
stranded; no lease, watchdog, resume, retry, or replay recovery exists. Both
gaps block production use.

## Trust boundaries and controls

```mermaid
flowchart TB
    Browser["Untrusted browser/input"] -->|"Basic over local HTTP only\nHTTPS required otherwise"| FastAPI
    FastAPI -->|"authenticated principal"| Authorization["Application command boundary"]
    Authorization -->|"typed domain values"| Services["Processing / review services"]
    Services -->|"explicit transactions"| SQLite
    Services -. "optional HTTPS call" .-> Provider["External extractor trust boundary"]

    FastAPI -. "strict DTO, no extras" .-> Browser
    Provider -. "bounded bytes + strict JSON" .-> Services
```

Implemented controls include explicit allowed hosts and proxy IPs, HTTPS fail-
closed configuration, HSTS on HTTPS, CSP, no framing, `nosniff`, `no-store`,
same-origin resource policy, CSRF tokens bound to the authenticated reviewer,
exact `Origin` validation, strict JSON input, capped strings/collections,
timezone-aware timestamps, exact money, ETag preconditions, and safe DOM text
rendering.

Assessment limitations remain material: every configured Basic user currently
has the same effective scope; there is no role/team/case authorization,
four-eyes constraint, session revocation, MFA, account lifecycle, attachment-
object authorization, or protected technical-trace API.

## AWS assessment sandbox — packaged, not provisioned

```mermaid
flowchart LR
    Browser["Reviewer browser"] -->|"HTTPS + Basic"| Gateway["API Gateway HTTP API"]
    Gateway --> Lambda["Python 3.12 Lambda\nMangum + FastAPI"]
    Lambda --> EFS["Encrypted retained EFS\nSQLite journal DELETE"]
    Lambda --> Observability["CloudWatch logs/alarms + X-Ray"]
    SAM["SAM + minimal pinned build context"] --> Gateway
    SAM --> Lambda
    SAM --> EFS
```

The repository includes a one-command SAM deployment for synthetic assessment
use. Its template, x86_64 build artifact, shell script, and Lambda import are
locally validated; no AWS account or stack was mutated. API Gateway supplies a
direct HTTPS origin. Lambda runs with bounded concurrency in two private
subnets, while EFS persists the SQLite file through an access point.

This bridge is not production persistence. SQLite warns about remote filesystem
locking/sync behavior; `DELETE` journal removes the literal WAL incompatibility
but not the NFS risk. Basic authentication, global reviewer scope, synchronous
processing, attachment references, and lack of live load/restore evidence keep
the sandbox outside the financial-production trust boundary. See the
[sandbox runbook](../deploy/aws/README.md).

## Accepted AWS production target — not implemented

```mermaid
flowchart LR
    User["Submitter / reviewer / auditor"] --> Edge["CloudFront + WAF + ACM"]
    Edge --> Shell["Private S3 static shell"]
    Edge --> API["API Gateway"]
    API --> Auth["Lambda authorizer + Cognito BFF session"]
    API --> Lambda["Python Lambda APIs/workers"]
    Lambda --> Queue["SQS + DLQ"]
    Queue --> Workers["Lambda workers"]
    Lambda --> Proxy["RDS Proxy"]
    Workers --> Proxy
    Proxy --> Aurora["Aurora PostgreSQL Serverless v2\nauthoritative ledger + outbox"]
    Lambda --> Evidence["Versioned private S3\noriginals + safe derivatives"]
    Aurora --> Export["Idempotent audit exporter"]
    Export --> Archive["Approved immutable S3 archive"]
    Auth --> Sessions["DynamoDB opaque-session records"]
```

Production keeps the same domain/application boundaries but replaces local
adapters and synchronous execution:

| Assessment | Accepted production replacement |
| --- | --- |
| HTTP Basic/PBKDF2 | Application-owned Cognito OIDC, MFA, opaque secure BFF cookie, RBAC/ABAC. |
| One FastAPI process | Same-origin CloudFront/WAF edge, API Gateway, short Lambda paths. |
| Synchronous extraction | S3 event/intake + SQS/DLQ workers with idempotent delivery and backpressure. |
| SQLite | Aurora PostgreSQL Serverless v2 through RDS Proxy, authoritative transactions and outbox. |
| Attachment reference string | Private versioned S3 object, SHA-256/version/media/scan metadata, authorized access audit. |
| DB-only audit | Transactional outbox plus approved immutable export; CloudTrail/observability are complementary. |

No production Cognito pool/BFF, SQS queue, Aurora cluster/repository, receipt S3
store, CloudFront/WAF edge, outbox/exporter, DNS, or provisioned cloud resource
exists in this repository. The SAM assessment sandbox above is deliberately not
the production IaC described here. Region, account/network layout, workload,
SLO, RPO/RTO, retention, legal hold, provider approval, and production cost
still require accountable validation. Kubernetes/EKS was evaluated and
explicitly not selected.

## Repository map

```text
expense-agent/
├── .github/workflows/ci.yml
├── examples/sample_requests.json
├── deploy/aws/                    # non-production SAM sandbox and runbook
├── src/expense_agent/
│   ├── domain/                 # deterministic financial model and policy
│   ├── application/            # processing/review use cases and ports
│   ├── infrastructure/
│   │   ├── extraction/         # offline and optional HTTPS+JSON adapters
│   │   └── review/             # SQLite workflow/review repository
│   └── presentation/           # FastAPI, Lambda adapter, security, UI, CLIs
├── tests/                       # domain, adapter, integration, API, AWS assets
└── docs/                        # architecture, decisions, evidence, report
```
