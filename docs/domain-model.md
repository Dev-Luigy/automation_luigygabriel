# Domain and application object model

## Modeling approach

Financial objects are separate from HTTP DTOs, database rows, and provider SDK
types. Immutable dataclasses validate values at construction time, while the
`ReimbursementCase` aggregate is the only object allowed to perform workflow
transitions. The application layer then coordinates that aggregate with an
abstract repository.

## Core reimbursement objects

```mermaid
classDiagram
    class Money {
        +Decimal amount
        +Currency currency
        +brl(str) Money
    }
    class AttachmentReference {
        +str location
    }
    class ReimbursementSubmission {
        +str request_id
        +str submitted_by
        +datetime submitted_at
        +str raw_ocr_text
        +str claimed_category
        +Money claimed_amount
        +AttachmentReference[] attachments
    }
    class ReimbursementCase {
        -ReimbursementStatus status
        -DecisionRecord[] decisions
        +str request_id
        +start_processing()
        +record_automated_decision(decision)
        +record_human_decision(decision)
    }
    class AutomatedDecision {
        +str decision_id
        +str request_id
        +PolicyDecisionRoute route
        +datetime decided_at
        +str policy_version
        +DecisionReason[] reasons
        +RuleEvaluation[] rule_evaluations
    }
    class HumanDecision {
        +str decision_id
        +str request_id
        +ReviewOutcome outcome
        +str reviewer
        +str reason
        +datetime decided_at
    }
    class DecisionReason {
        +str code
        +str message
        +Mapping evidence
    }
    class RuleEvaluation {
        +str rule_id
        +str rule_version
        +RuleOutcome outcome
        +str message
        +Mapping facts
    }

    ReimbursementCase *-- ReimbursementSubmission
    ReimbursementSubmission *-- Money
    ReimbursementSubmission *-- AttachmentReference
    ReimbursementCase *-- AutomatedDecision
    ReimbursementCase *-- HumanDecision
    AutomatedDecision *-- DecisionReason
    AutomatedDecision *-- RuleEvaluation
```

`Money` only accepts finite, non-negative `Decimal` values with at most two
decimal places; BRL is the currently supported currency. Time-bearing objects
require timezone-aware datetimes. IDs and explanations must be non-blank.

## Aggregate state machine

```mermaid
stateDiagram-v2
    [*] --> RECEIVED
    RECEIVED --> PROCESSING: start_processing()
    PROCESSING --> AUTO_APPROVED: AUTO_APPROVED route
    PROCESSING --> PENDING_REVIEW: HUMAN_REVIEW route
    PROCESSING --> REJECTED: REJECTED route
    PENDING_REVIEW --> APPROVED_AFTER_REVIEW: APPROVED outcome
    PENDING_REVIEW --> REJECTED: REJECTED outcome
```

The aggregate rejects a human decision before `PENDING_REVIEW`, a second
automated decision after leaving `PROCESSING`, a decision for another
`request_id`, or any direct assignment of a final state. `ReviewService`
rehydrates the relevant submission and automated decision, replays the domain
transition, and gives the resulting state to the repository transaction.

## Extraction and reproducibility objects

```mermaid
classDiagram
    class ExtractionResult {
        +str request_id
        +ExtractionStatus status
        +ModelInvocationTrace trace
        +ReceiptFacts facts
        +str error
    }
    class ReceiptFacts {
        +date receipt_date
        +Money total
        +str category
        +str merchant_name
        +str tax_id
        +Mapping evidence
        +str[] warnings
    }
    class ModelInvocationTrace {
        +str provider
        +str model
        +str prompt_version
        +str prompt_hash
        +str input_hash
        +str raw_response
        +datetime invoked_at
        +int duration_ms
        +Mapping parameters
    }
    ExtractionResult *-- ReceiptFacts
    ExtractionResult *-- ModelInvocationTrace
    ReceiptFacts *-- Money
```

A successful extraction can contain partial facts. Missing values are not
guessed: deterministic policy should route material uncertainty to review. A
failed extraction has an error and cannot contain facts. The full invocation
trace is persisted for audit; the browser response intentionally omits its raw
model response.

The repository contains the extraction contract and demo data, but no live OCR
or language-model adapter. The model count and secondary-verifier strategy
remain open decisions pending measured quality, cost, latency, and privacy data.

## Human-review application objects

```mermaid
classDiagram
    class ReviewService {
        +list_pending() ReviewQueueItem[]
        +search_pending(query) ReviewQueuePage
        +get(request_id) ReviewCaseDetails
        +list_events(request_id, query) ReviewEventPage
        +decide(request_id, outcome, reason, reviewer, expected_version, correlation_id) ReviewDecisionResult
    }
    class ReviewRepository {
        <<Protocol>>
        +list_pending()
        +search_pending(query, as_of)
        +get(request_id)
        +list_business_events(request_id, query)
        +record_human_decision(...)
    }
    class ReviewQueueQuery {
        +str search
        +str category
        +str problem_code
        +Money min_amount
        +Money max_amount
        +datetime submitted_from
        +datetime submitted_to
        +datetime pending_before
        +PendingAgeBucket age_bucket
        +ReviewQueueSort sort
        +int page_size
        +str cursor
    }
    class ReviewQueuePage {
        +ReviewQueueItem[] items
        +int page_size
        +ReviewQueueSort sort
        +bool has_more
        +str next_cursor
        +ReviewQueueSummary summary
    }
    class ReviewQueueSummary {
        +int total_pending
        +int over_24h
        +int high_value
        +int amount_mismatch
        +Money high_value_threshold
        +datetime as_of
    }
    class ReviewEventQuery {
        +int page_size
        +str cursor
    }
    class ReviewBusinessEvent {
        +str event_id
        +str request_id
        +str event_type
        +datetime occurred_at
        +AuditActor actor
        +str correlation_id
        +Mapping payload
    }
    class ReviewEventPage {
        +ReviewBusinessEvent[] items
        +int page_size
        +bool has_more
        +str next_cursor
    }
    class ReviewerIdentity {
        +str reviewer_id
        +str email
        +str display_name
    }
    class ReviewQueueItem {
        +str request_id
        +str submitted_by
        +datetime submitted_at
        +str claimed_category
        +Money claimed_amount
        +datetime pending_since
        +int version
        +str merchant_name
        +Money extracted_amount
        +ReviewProblem primary_problem
        +str[] problem_codes
    }
    class ReviewCaseDetails {
        +ReimbursementSubmission submission
        +ReimbursementStatus status
        +int version
        +ReviewCaseStatus review_status
        +ExtractionResult extraction
        +ReviewProblem[] problems
        +AutomatedDecision automated_decision
        +HumanDecision human_decision
        +ReviewerIdentity reviewed_by
    }
    class ReviewProblem {
        +str code
        +str message
        +Mapping evidence
    }
    class ReviewDecisionResult {
        +HumanDecision decision
        +ReimbursementStatus resulting_status
        +int version
        +str audit_event_id
    }

    ReviewService --> ReviewRepository
    ReviewService --> ReviewerIdentity
    ReviewService --> ReviewDecisionResult
    ReviewService --> ReviewQueueQuery
    ReviewService --> ReviewQueuePage
    ReviewService --> ReviewEventQuery
    ReviewService --> ReviewEventPage
    ReviewRepository --> ReviewQueueItem
    ReviewQueuePage *-- ReviewQueueItem
    ReviewQueuePage *-- ReviewQueueSummary
    ReviewEventPage *-- ReviewBusinessEvent
    ReviewBusinessEvent *-- AuditActor
    ReviewRepository --> ReviewCaseDetails
    ReviewCaseDetails *-- ReviewProblem
    ReviewCaseDetails *-- ReviewerIdentity
```

`ReviewerIdentity` is an application value supplied by a trusted authentication
adapter. The HTTP command does not contain it. `HumanDecision.reviewer` stores
the canonical ID, while persistence snapshots the ID, email, and display name
that were authenticated at decision time.

`ReviewCaseDetails` is a reviewer read model, not a mutable aggregate or an ORM
entity. It combines the evidence needed for judgment without exposing database
implementation details.

`ReviewQueueQuery` validates the operational discovery contract before it
reaches persistence: optional text values are trimmed and bounded, money uses
`Money`, all timestamps require timezones, the amount and submission ranges
must be ordered, `pending_before` and `age_bucket` are mutually exclusive, and
page size is restricted to 10 through 100. Its language-neutral enums are:

- `ReviewQueueSort`: `pending_oldest`, `pending_newest`, `amount_asc`,
  `amount_desc`, and `submitted_newest`;
- `PendingAgeBucket`: `under_4h`, `4h_to_24h`, and `over_24h`.

`ReviewQueuePage` is the bounded application result. It couples a tuple of
compact queue rows with `has_more`, an opaque forward cursor, and operational
summary counts evaluated at one `as_of`. `ReviewQueueItem` now carries merchant,
extracted total, primary problem, and problem codes so a reviewer can triage
without loading every full case. The original problem message remains evidence;
the browser translates known codes and interface labels rather than mutating
stored text.

Cursor signing and keyset SQL are infrastructure responsibilities. The
application model treats the cursor as an opaque string and does not expose its
sort key or HMAC payload. The old `list_pending()` method remains only for
internal compatibility; the HTTP collection uses `search_pending()` and never
loads the complete queue into the browser.

`ReviewEventQuery` independently bounds one case's business-history read to
1–100 events. `ReviewBusinessEvent` is not the stored `AuditEvent`: it is a
reviewer-safe projection with an event-specific scalar payload whitelist.
`ReviewEventPage` returns stable chronological keyset metadata without exposing
the cursor boundary or HMAC. This distinction prevents the normal review screen
from becoming an accidental privileged technical-trace surface.

## Audit objects and lifecycle facts

```mermaid
classDiagram
    class AuditActor {
        +str actor_type
        +str actor_id
    }
    class AuditEvent {
        +str event_id
        +str request_id
        +str event_type
        +datetime occurred_at
        +AuditActor actor
        +str correlation_id
        +Mapping payload
    }
    AuditEvent *-- AuditActor
```

Both records are immutable domain values. The implemented repository appends a
`review_case_enqueued` event when it persists a routed case and a
`human_review_decided` event when it records the reviewer action. Database
triggers prevent updates and deletes of every audit row.

```mermaid
sequenceDiagram
    participant Policy as Deterministic producer
    participant Repo as Review repository
    participant Reviewer as Authenticated reviewer
    participant Service as ReviewService

    Policy->>Repo: Persist pending case
    Repo->>Repo: Append review_case_enqueued
    Reviewer->>Service: Outcome + rationale
    Service->>Service: Create HumanDecision and AuditEvent
    Service->>Repo: Commit at expected version
    Repo->>Repo: Persist decision + state + human_review_decided atomically
```

## Object catalog

| Object | Layer/classification | Mutable? | Primary responsibility |
| --- | --- | --- | --- |
| `Money` | Domain value object | No | Exact amount and currency. |
| `AttachmentReference` | Domain value object | No | Opaque location of externally stored content. |
| `ReimbursementSubmission` | Domain entity snapshot | No | Original employee input. |
| `ReimbursementCase` | Domain aggregate root | Controlled | Workflow state and append-only in-memory decision history. |
| `ReceiptFacts` | Domain value object | No | Structured evidence extracted from a receipt. |
| `ModelInvocationTrace` | Domain value object | No | Complete model invocation metadata for audit. |
| `ExtractionResult` | Domain result | No | Valid success or failure from extraction. |
| `DecisionReason` | Domain value object | No | Explainable decision code, message, and evidence. |
| `RuleEvaluation` | Domain value object | No | Versioned deterministic rule trace. |
| `AutomatedDecision` | Domain record | No | Automated route plus policy evidence. |
| `HumanDecision` | Domain record | No | Authenticated reviewer outcome and rationale. |
| `AuditEvent` / `AuditActor` | Domain records | No | Correlated, append-only lifecycle fact. |
| `ReviewerIdentity` | Application value | No | Canonical identity obtained from authentication. |
| `ReviewProblem` | Application value | No | Concrete issue presented for judgment. |
| `ReviewQueueQuery` | Application query | No | Validated search, filters, stable sort, page bound, and opaque cursor. |
| `ReviewQueueSort` / `PendingAgeBucket` | Application enums | No | Stable language-neutral discovery codes. |
| `ReviewQueueItem` | Application read model | No | Compact triage representation including merchant, extracted total, and problem summary. |
| `ReviewQueueSummary` | Application read model | No | Global pending, overdue, high-value, and amount-mismatch counts at one snapshot time. |
| `ReviewQueuePage` | Application read model | No | Bounded rows, forward cursor metadata, and summary. |
| `ReviewEventQuery` | Application query | No | Bounded page size and opaque cursor for one case timeline. |
| `ReviewBusinessEvent` | Application read model | No | Sanitized reviewer-visible business audit fact. |
| `ReviewEventPage` | Application read model | No | Chronological business events and forward cursor metadata. |
| `ReviewCaseDetails` | Application read model | No | Complete evidence snapshot for one case. |
| `ReviewDecisionResult` | Application result | No | Decision, final status, version, and audit ID. |
| `ReviewRepository` | Application port | N/A | Persistence operations required by review. |
| `ReviewService` | Application service | Controlled | Reads cases and coordinates authoritative decisions. |
| `ReviewerPrincipal` | Presentation security value | No | Identity established by the assessment auth adapter. |
| `ReviewQueueRequest` | Presentation DTO | No | Strict HTTP query model mapped to `ReviewQueueQuery`. |
| `ReviewEventRequest` | Presentation DTO | No | Strict timeline limit/cursor mapped to `ReviewEventQuery`. |
| `DecisionRequest` | Presentation DTO | No | Strictly `outcome` plus mandatory `reason`. |

## Invariants by boundary

```mermaid
mindmap
  root((Protected invariants))
    Money
      Decimal only
      Finite and non-negative
      Maximum two decimals
      BRL currently supported
    Submission
      Stable request ID
      Timezone-aware submission time
      Non-empty OCR and category
      Positive claim
    Extraction
      Success has facts and no error
      Failure has error and no facts
      Complete invocation trace persisted
    Automated decision
      Matching request ID
      At least one reason
      At least one versioned rule evaluation
    Human decision
      Pending-review state only
      Authenticated canonical reviewer
      Mandatory rationale
      One immutable record per request
    Audit
      Actor and correlation ID
      Enqueue and decision lifecycle events
      Append-only database triggers
    Concurrency
      Positive version
      ETag precondition
      Transactional state/version recheck
    Queue discovery
      Server-side bounded page
      Exact minor-unit amount comparison
      Timezone-aware ranges and age buckets
      Stable sort with request ID tie-breaker
      Opaque query-bound cursor
```

## Object-to-storage mapping

```mermaid
flowchart LR
    Submission["ReimbursementSubmission"] --> Reimbursements[("reimbursements")]
    Attachments["AttachmentReference[]"] --> AttachmentRows[("attachments locations")]
    Extraction["ExtractionResult"] --> ExtractionRows[("extractions + model_invocation_traces")]
    Automated["AutomatedDecision"] --> AutomatedRows[("automated_decisions + reasons + rules")]
    Problems["ReviewProblem[]"] --> ReviewRows[("review_cases + review_problems")]
    Human["HumanDecision + ReviewerIdentity"] --> HumanRows[("human_decisions")]
    Audit["AuditEvent"] --> AuditRows[("audit_events")]
    QueueQuery["ReviewQueueQuery"] --> QueueRows[("indexed reimbursements + review_cases + extractions + review_problems")]
    Cursor["opaque queue cursor"] --> Metadata[("application_metadata HMAC secret")]
    QueueRows --> QueuePage["ReviewQueuePage"]
```

No reviewer account/session object or attachment-content object is persisted in
the current schema. Standalone managed identity and authorized file access
are production responsibilities, not implied implemented features.
