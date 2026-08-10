# Architecture and product decision log

This register is the compact index of material decisions. The chronological
reasoning behind them is preserved in [the project journal](project-journal.md).

Status meanings:

- `accepted`: current direction.
- `proposed`: recommended but not yet confirmed or implemented.
- `open`: material choice still under evaluation.
- `superseded`: retained for history but no longer the current direction.

## Decision index

| ID | Decision | Status |
| --- | --- | --- |
| D-001 | Keep financial decisions deterministic and use AI for evidence extraction. | accepted |
| D-002 | Model workflow through a `ReimbursementCase` aggregate. | accepted |
| D-003 | Represent BRL amounts with `Decimal` through `Money`. | accepted |
| D-004 | Preserve complete model invocation metadata. | accepted |
| D-005 | Represent decision justification as reason codes plus rule evaluations. | accepted |
| D-006 | Create one external CRM task per reimbursement with a persistent ID binding. | superseded and removed |
| D-007 | Never treat ClickUp, email, or another SaaS as the financial system of record. | accepted |
| D-008 | Make human review an internal application capability. | accepted |
| D-009 | Derive reviewer identity from authentication context, not request payload. | accepted |
| D-010 | Use an internal review API behind a non-technical web screen. | accepted |
| D-011 | Use external tools only for notification and deep links, if retained. | superseded for MVP; no external integration |
| D-012 | Use OCR plus two LLMs for every request. | open; not justified yet |
| D-013 | Support an optional, risk-based secondary verifier. | proposed |
| D-014 | Keep current and planned architecture visibly separate in documentation. | accepted |
| D-015 | Persist the human decision, status transition, and audit event atomically. | accepted |
| D-016 | Maintain a living question, assumption, and decision history. | accepted |
| D-017 | Serve one same-origin HTML/CSS/vanilla-JavaScript review screen. | accepted |
| D-018 | Avoid a separate React/Next.js runtime until infrastructure evidence justifies it. | accepted |
| D-019 | Use HTTPS in production with same-origin APIs, CSRF defense, and secure browser headers. | accepted |
| D-020 | Use HTTP Basic only as a replaceable assessment authentication adapter. | accepted with production replacement |
| D-021 | Combine HTTP ETags with a serialized database version/state check. | accepted |
| D-022 | Append review lifecycle events and enforce database immutability. | accepted |
| D-023 | Store and display attachment locations only in the assessment. | implemented limitation; content access remains open |
| D-024 | Retain the raw model response for audit but omit it from the reviewer API. | accepted |
| D-025 | Keep n8n as a rejected orchestration alternative, not the assessment runtime. | accepted |
| D-026 | Use a hybrid AWS serverless production target. | accepted target; not implemented or deployed |
| D-027 | Store receipt bytes in S3 and authoritative relationships in SQL. | accepted target; not implemented |
| D-028 | Do not require a VPN without a confirmed network-access requirement. | proposed; awaiting security confirmation |
| D-029 | Preserve originals and approve retention before lifecycle deletion. | proposed; awaiting legal and governance confirmation |
| D-030 | Derive serverless reviewer identity automatically through corporate OIDC/SSO. | superseded by standalone identity direction |
| D-031 | Separate the submitter status experience from the internal evidence-review workspace. | superseded; incorrectly assumed an existing client channel |
| D-032 | Build standalone submitter, reviewer, and audit/administration surfaces. | accepted; implementation partial |
| D-033 | Use server-side indexed filtering, sorting, search, and cursor pagination with multiple review views. | accepted; implemented for reviewer slice |
| D-034 | Localize the product interface in Portuguese, English, and Spanish. | accepted; implemented for reviewer slice |
| D-035 | Use an application-owned managed identity service rather than an existing corporate IdP. | accepted target; not implemented |
| D-036 | Make discovery database-scoped across the authorized dataset; retain keyset pagination and add exact all-status/history/audit lookup. | accepted; pending-queue scope implemented, broader discovery planned |
| D-037 | On case selection, separate reviewer evidence and business timeline from privileged technical trace, with authorized on-demand access to the immutable original. | accepted; business timeline implemented, technical trace and content access partial/planned |
| D-038 | Expose reviewer business history through a dedicated sanitized, cursor-paginated endpoint. | accepted and implemented for current event types |
| D-039 | Use a same-origin CloudFront edge and Cognito-backed serverless BFF session. | accepted production target; not implemented |
| D-040 | Keep the Aurora business ledger authoritative and export its transactional outbox to immutable storage. | accepted production target; not implemented |
| D-041 | Evaluate Kubernetes/EKS as a container runtime without replacing the accepted serverless target. | superseded by D-042; evaluated and not selected |
| D-042 | Retain the hybrid AWS serverless target and close Kubernetes as a current deployment option. | accepted |

## D-001 - Deterministic financial authority

**Decision:** Language models may extract or verify receipt facts, but a
versioned deterministic policy engine produces the automated financial route.

**Rationale:** The same structured facts and policy version must produce the
same outcome. Model output is probabilistic and cannot, by itself, satisfy
reproducibility or explain policy thresholds precisely.

**Consequence:** Missing, ambiguous, or inconsistent facts route to human review
instead of being silently guessed.

## D-002 - Reimbursement aggregate

**Decision:** `ReimbursementCase` owns status transitions and append-only
decision history.

**Alternatives considered:** Public mutable status fields; state transitions in
API routes; status controlled by ORM entities.

**Rationale:** The aggregate prevents invalid transitions regardless of which
interface or repository invokes the domain.

## D-003 - Exact money

**Decision:** Use `Decimal` through the `Money` value object and explicitly
carry currency.

**Rationale:** Binary floating-point values are unsafe for equality and threshold
checks in financial rules.

## D-004 - Model invocation trace

**Decision:** Record provider, exact model, prompt version and hash, input hash,
raw response, parameters, invocation time, and duration.

**Rationale:** A temperature setting alone does not make a probabilistic model
reproducible. Auditors need the original input/output and exact configuration.

## D-005 - Explainable decisions

**Decision:** An `AutomatedDecision` is invalid without at least one human-readable
reason and one versioned `RuleEvaluation`.

**Rationale:** A route such as `rejected` is insufficient evidence for audit or
support investigation.

## D-006 - External CRM task binding

**Initial decision:** Persist `request_id` to an external task ID and uploaded
file hashes so retries update one card.

**Status:** Superseded as a core human-review mechanism after evaluator feedback.
The user subsequently decided to remove the integration entirely from runtime,
configuration, tests, and active technical documentation. It remains only as a
historical alternative in this decision record.

## D-007 - Internal system of record

**Decision:** Neither external task status changes nor email/chat replies are
authoritative reimbursement decisions.

**Rationale:** The service must control reviewer identity, rationale, timestamps,
state transitions, and audit records. External SaaS state can be unavailable,
edited, deleted, or governed by unrelated permissions.

## D-008 - Internal human review

**Decision:** Pending cases must be queryable and decidable through the service.

**Expected behavior:** A reviewer can see original input, attachments, extracted
facts, problems, rule evaluations, and decision history before approving or
rejecting with a mandatory reason.

## D-009 - Authenticated reviewer identity

**Decision:** The decision command does not accept a freely chosen `reviewer_id`.
An identity adapter resolves it from credentials or a trusted upstream identity.

**Implementation choice:** Use HTTP Basic credentials with PBKDF2 password
hashes as a small, replaceable assessment adapter. D-035 supersedes the former
corporate-SSO proposal with application-owned managed OIDC, without changing
review-domain or application code.

## D-010 - Review API behind a human web interface

**Decision:** Implement internal JSON endpoints, but expose the reviewer workflow
through a dedicated browser screen. OpenAPI/Swagger, if enabled in a development
environment, is engineering documentation rather than the reviewer interface;
the shipped HTTP adapter currently disables those routes.

**Rationale:** Expected reviewers are not programmers. An API without the client
that invokes it does not make review practically available to them.

## D-011 - External notification only

**Status:** No external notification integration is part of the MVP. The generic
option remains an architectural possibility, but no related runtime residue is
kept in the assessment implementation.

## D-012 - Two LLMs for every request

**Status:** Open and currently not recommended for the assessment MVP.

**Benefits considered:** Cross-provider disagreement detection and potentially
better extraction recall.

**Costs considered:** Token price, tail latency, provider failure modes, rate
limits, twice the sensitive-data exposure, vendor approval, audit volume, and
additional evaluation work. Agreement does not prove correctness when models
share the same OCR error.

**Required evidence before acceptance:** Representative labeled dataset,
field-level accuracy, false auto-approval/rejection rates, disagreement rate,
human-review rate, P95/P99 latency, and unit cost.

## D-013 - Risk-based secondary verifier

**Proposal:** Define a `SecondaryVerifier` port and invoke it for candidates that
would otherwise be auto-approved, discrepancies, low-quality OCR, and a random
monitoring sample.

**Rationale:** Redundancy is most valuable where the system is about to make an
automatic monetary decision. Human-review cases already have another control.

## D-014 - Honest architecture documentation

**Decision:** Documentation diagrams classify components as implemented,
partial, or planned.

**Rationale:** A diagram must not imply that an API, policy engine, database
table, or audit repository exists when only its domain contract is present.

## D-015 - Atomic review transaction

**Decision:** In one transaction, verify the case is pending, insert the immutable
human decision, transition the case, and append the audit event. A competing or
repeated decision receives a conflict response.

**Rationale:** Partial writes can produce a final status without a decision or a
decision without an audit trail.

**Implementation evidence:** `SqliteReviewRepository` uses `BEGIN IMMEDIATE`,
rechecks both workflow statuses and the expected version, inserts the decision,
conditionally updates the reimbursement and review case, appends the audit
event, and commits. Any failure rolls back the unit. Tests cover a late audit
failure, repeated decisions, and two concurrent writers that read version 1:
exactly one commits, the other conflicts, one decision remains, and the case is
at version 2.

## D-016 - Living decision history

**Decision:** Update the journal, decision register, and assumptions register as
part of each meaningful design or implementation change.

**Rationale:** The final report must explain not only the resulting code, but the
questions, alternatives, compromises, and evidence that led to it.

## D-017 - Single same-origin review screen

**Decision:** The Python service serves one static HTML document, one stylesheet,
and one vanilla-JavaScript module. JavaScript uses same-origin `fetch` calls to
load the queue, open a case, and submit approve/reject actions.

**Rationale:** This provides an accessible non-technical interface without a
Node build pipeline, a second deployment artifact, hydration, or a separate
frontend server for one simple workflow.

**Security consequence:** Reimbursement and OCR values are assigned with DOM
`textContent`, never inserted as executable HTML.

## D-018 - No React or Next.js without deployment evidence

**Decision:** Do not add a React/Next.js runtime for the current one-screen UI.

**Alternatives considered:** Next.js server-side rendering, a separately hosted
single-page application, and static HTML/JavaScript served by FastAPI.

**Rationale:** The standalone reviewer console is one bounded operational
workflow. Static same-origin assets have a small deployment and dependency
footprint, avoid a second runtime, and preserve the option to replace the
presentation layer later if product complexity grows.

## D-019 - Browser and transport security

**Decision:** Production requests use HTTPS, normally terminated by a trusted
reverse proxy. The application uses no cross-origin API access, requires a CSRF
token for state changes, emits a restrictive Content Security Policy, disables
framing and caching of sensitive pages, and does not put credentials or review
data in browser storage.

**Rationale:** Serving HTML over HTTPS encrypts transport but does not by itself
prevent XSS, CSRF, clickjacking, stale sensitive caches, or identity spoofing.

## D-020 - Replaceable assessment authentication

**Decision:** Use HTTP Basic authentication backed by configured PBKDF2 password
hashes for the assessment. Resolve the canonical reviewer identity on the
server. Never accept it from the decision JSON.

**Trade-off:** HTTP Basic has limited UX and session controls, but over HTTPS it
provides a small demonstrable authentication boundary. The application-facing
identity port allows production OIDC/SSO to replace it without changing the
review workflow.

## D-021 - Layered optimistic concurrency

**Decision:** A case detail response carries an ETag derived from the request
identity and database version. The decision endpoint requires `If-Match`, then
the repository rechecks pending state and version inside `BEGIN IMMEDIATE`.

**Rationale:** The ETag gives the browser an explicit stale-view protocol, while
the serialized transaction closes the race between the HTTP precheck and the
write. The UI can distinguish a stale precondition (`412`) from a transaction-
time conflict (`409`).

**Consequence:** Repeated or competing submissions cannot create a second human
decision. Production database replacement must preserve equivalent semantics.

## D-022 - Review lifecycle audit and database immutability

**Decision:** Persist `review_case_enqueued` in the same transaction as a
pending case and `human_review_decided` in the same transaction as the human
decision. Propagate the caller's correlation ID; only the demo/helper path may
derive a fallback. Use database triggers to reject update or delete of human
decisions and audit events. Configure SQLite with WAL, foreign keys, a busy
timeout, and `synchronous=FULL`.

**Rationale:** An auditor needs to see how the case entered the human queue as
well as how it left. Application-level immutability alone does not protect
against accidental direct SQL mutation.

**Consequence:** This is complete for the implemented review lifecycle, not for
the future authoritative intake/extraction/policy pipeline. Production still
needs broader event coverage, access governance, retention, backup, and
recovery controls.

## D-023 - Attachment reference boundary

**Current implementation boundary:** The assessment persists and displays only
`AttachmentReference.location`. It does not implement file upload, preview,
download, signed URLs, or attachment-content authorization.

**Rationale:** A safe content path requires application-owned object storage,
malware scanning, retention rules, and attachment authorization that are not
part of the implemented slice. Displaying the reference makes the missing
boundary visible without inventing insecure file access.

**Status:** This is a visible limitation, not a claim that attachment references
alone satisfy the final reviewer workflow. The standalone production storage
and authorization contract remains an open product decision.

## D-024 - Protected model response

**Decision:** Persist `ModelInvocationTrace.raw_response` for audit and
reproducibility, but exclude it from the reviewer-facing detail JSON. Return the
structured facts and safe trace metadata needed for review.

**Rationale:** Reviewers need the receipt evidence and normalized object, not
necessarily the complete provider response. Minimizing browser exposure reduces
sensitive-data surface while retaining the protected audit artifact.

## D-025 - n8n orchestration alternative

**Decision:** Keep the assessment as a Python service and do not introduce n8n
as an application runtime or workflow dependency.

**Alternative considered:** A self-hosted n8n installation could orchestrate
event-driven processing and, where its Linux environment and security policy
allow it, invoke a configured local model or a command-line integration and
consume the result inside a workflow.

**Rationale:** This is technically viable, but it does not eliminate the core
work required by this financial service: a non-technical review interface,
authenticated commands, deterministic policy execution, an authoritative data
model, atomic decision/status/audit persistence, concurrency control, and
tests. Modeling and governing those requirements across workflow nodes and
custom scripts would add implementation and operational work for the current
scope. The assignment also explicitly requests Python, for which a small
backend and same-origin static screen provide the shortest clear path.

**Consequences and trade-offs:** n8n may be useful later as a replaceable
integration or notification orchestrator, but it must not become the financial
system of record. Shell execution and local-model access would also require
explicit infrastructure approval, sandboxing, least privilege, secret
management, timeouts, output validation, and complete invocation audit. No n8n
runtime, workflow export, credential, dependency, or active architecture
component is part of the assessment.

**Revisit condition:** Reconsider only if the standalone product deliberately
adopts and owns an approved n8n platform, its security and identity boundaries,
and a concrete peripheral integration need whose benefit exceeds the added
operational surface.

## D-026 - Hybrid AWS serverless production target

**Status:** Accepted by the user as the production target; not implemented or
deployed.

**Decision:** Use one HTTPS CloudFront/WAF edge, private S3 static assets, API
Gateway HTTP API and Python Lambda for short operations, SQS/DLQs for
asynchronous backpressure, versioned private S3 for receipt objects, and Aurora
PostgreSQL Serverless v2 through RDS Proxy for authoritative financial state.
Use an application-owned Cognito User Pool and a small DynamoDB BFF-session
store. Move long or specialized workers to Fargate, SageMaker, or EC2 only when
their measured runtime exceeds Lambda's safe operating boundary.

Aurora is the self-contained pricing reference for the standalone product, not
a dependency on an existing database. The application repository port keeps
the domain unchanged if that owned deployment choice is revised later.

**Rationale:** This design absorbs unknown bursts without operating an EC2
fleet, while retaining SQL transactions and allowing heavy inference to scale
independently. One EC2/VPS host is not a comparable production alternative
because it is a single point of failure.

**Still required before production:** Confirm region/account topology, peak
RPS, execution duration and memory, OCR/LLM topology and data residency, SLOs,
database load, recovery objectives, and AWS enterprise pricing. Acceptance of
the topology does not claim that these capacity/governance parameters or the
infrastructure itself already exist.

**Reference:** [AWS deployment and cost study](aws-deployment-study.md).

## D-027 - Object storage plus relational authority

**Status:** Accepted production target; not implemented.

**Decision:** Store original and derived receipt bytes in private S3 objects.
Store the attachment ID, request foreign key, bucket/key/version, checksum,
MIME, size, lifecycle classification, and processing state in PostgreSQL.

**Rationale:** Linux local storage creates host affinity and failover problems;
putting image bytes in SQL or one NoSQL item is inefficient and does not improve
the financial relationship model. S3 plus a relational reference preserves the
existing cardinalities and keeps the atomic decision/status/audit transaction.

**Consequence:** S3 and SQL cannot share one transaction. Intake needs an
explicit `awaiting_upload` state, checksum verification, idempotent S3/SQS event
handling, and cleanup for abandoned uploads.

## D-028 - Conditional VPN

**Status:** Proposed, not implemented or accepted.

**Proposal:** Do not require a VPN by default. Use HTTPS, application-owned
managed OIDC, MFA, API authorization, private data stores, security groups, and
VPC endpoints.
Add Client VPN only for a confirmed reviewer network policy, or Site-to-Site
VPN/Direct Connect for a confirmed on-premises dependency.

**Rationale:** VPN controls network reachability; it neither establishes the
reviewer's business authorization nor replaces encryption and audit. In São
Paulo, two Client VPN subnet associations alone are approximately USD 219/month
before connection hours, so the control must answer a real threat or policy.

## D-029 - Evidence retention and safe derivatives

**Status:** Proposed, pending Legal, Privacy, Finance, Data Governance, Security,
and product-owner confirmation.

**Proposal:** Preserve the original receipt byte-for-byte with checksum and
version. Produce separate OCR/UI derivatives. Configure lifecycle transition,
expiration, Object Lock, and legal holds only from an approved retention matrix.

**Rationale:** Destructive compression weakens evidentiary traceability, while
an invented deletion period creates legal and privacy risk. Storage classes and
compression should be selected from measured retrieval patterns, cost, and OCR
accuracy.

## D-030 - Serverless reviewer identity and audit context

**Status:** Superseded by D-035 after the user explicitly rejected dependencies
on existing RecargaPay systems. Retained as historical reasoning.

**Proposal:** Reuse RecargaPay's corporate OIDC/SSO. Prefer direct validation at
API Gateway or another trusted corporate ingress. Use Amazon Cognito only as an
OIDC broker or managed-login fallback when the company platform requires it;
creating a separate application-owned user directory is the last alternative.

The reviewer may need to sign in or complete MFA when no corporate session is
active, but must never type a reviewer ID, employee code, API key, or other
identity value into the decision form. The decision request contains only the
outcome, mandatory rationale, concurrency precondition, and idempotency data.
The backend constructs `ReviewerIdentity` from validated authentication claims.

**Identity and authorization:** Use the stable `(issuer, subject)` pair as the
identity key. Email and display name are audit snapshots rather than primary
keys. Require a reviewer role or scope such as `expense:review`; authentication
alone is not authorization. Confirm whether separation of duties must prevent
a claimant from reviewing their own reimbursement.

**Audit boundary:** In one PostgreSQL transaction, validate state/version,
append the immutable human decision, transition the case, append the business
audit event, and append an outbox event. Store the identity key, display
snapshots, roles/scopes snapshot, outcome, rationale, before/after state,
request/correlation/trace IDs, policy and application versions, and timestamp.
Do not persist a raw access or ID token. CloudTrail and immutable S3 exports are
complementary infrastructure/forensic evidence; they do not replace the
authoritative business audit record.

**Browser-session choice still open:** Authorization Code with PKCE and a
short-lived access token is viable. A backend-for-frontend with a short-lived,
opaque, `Secure`, `HttpOnly` session cookie is preferable when corporate
standards require stronger browser token isolation or immediate session
revocation. Either path keeps authorization and identity derivation on the
server and retains same-origin CSRF protections where cookies are used.

**Evidence required:** Corporate issuer, audience, stable subject claim,
groups/scopes, MFA policy, login and logout flow, token/session lifetimes,
revocation and deprovisioning behavior, trusted ingress, reviewer assignment,
and audit-retention requirements.

## D-031 - Initial user experiences and information exposure

**Status:** Superseded by D-032. The information separation remains valid, but
the assumption that an existing RecargaPay client channel would own the
submitter experience was explicitly rejected.

**Proposal:** Treat the application as two presentation boundaries over one
authoritative workflow:

1. An existing RecargaPay employee/client channel calls the intake and status
   APIs. The submitter sees a request reference, processing state, final result,
   and an approved, sanitized explanation. Do not expose raw OCR, model output,
   policy internals, reviewer identity, or the protected audit payload there.
2. An authenticated internal finance reviewer uses the implemented evidence
   workspace. Pending cases show the claim, original receipt through an
   authorized object-storage preview, raw OCR evidence, normalized receipt,
   detected problems, deterministic rule results, and decision controls.

The initial product does not create a second employee portal when RecargaPay
already has an appropriate submission channel. If no such channel exists, a
minimal submit-and-track screen becomes an explicit new scope decision rather
than being hidden inside the reviewer interface.

**Rationale:** Submitters and reviewers have different jobs and least-privilege
needs. The reviewer needs detailed evidence to make an accountable decision;
the submitter needs a comprehensible result without access to model traces,
internal controls, or another person's identity. Reusing an existing company
surface also avoids duplicating authentication and product navigation.

**Current boundary:** The repository implements only the internal pending queue,
case detail, and approve/reject action. It persists and displays attachment
locations but does not yet retrieve or preview bytes. Intake, OCR/LLM
orchestration, deterministic policy, submitter status, result notification, and
audit search/export remain planned.

**Evidence required:** Confirm the existing employee channel, intake ownership,
how final results are returned (polling, event, or approved notification),
which rejection explanations may be shown, reviewer receipt-preview policy,
and whether auditors need a dedicated read-only interface in the first release.

## D-032 - Standalone product surfaces

**Status:** Accepted by explicit user direction; implementation is partial.

**Decision:** Expense Agent owns three independently authorized experiences:

1. A submitter portal for authenticated receipt upload, claim entry, request
   acknowledgement, status tracking, and final explanation.
2. An internal operations console for reviewers to search and triage pending
   cases, inspect protected evidence, and record individual decisions.
3. A controlled audit/administration surface for trace search/export, identity
   lifecycle, roles, and operational configuration. Its exact first-release
   scope remains to be prioritized.

Do not assume or require an existing RecargaPay frontend, IdP, CRM, database,
notification mechanism, or workflow. Integration adapters may be added later,
but the product must remain usable and auditable without them.

**Current boundary:** Only the authenticated reviewer queue/detail/decision
slice exists. Submitter intake/tracking and audit/administration screens remain
planned and must not be represented as implemented.

## D-033 - Scalable review discovery and views

**Status:** Accepted and implemented for the reviewer slice. Production-scale
SLO validation remains open.

**Decision:** The browser never downloads the complete queue. Review discovery
uses bounded server-side queries with validated filters, stable ordering, and
keyset/cursor pagination. Support direct search plus filters for category,
problem, exact amount range, submission time, and pending age. Provide dense
table, visual card, and focused case-detail modes over the same query state.

**Scale model:** The standalone production reference assumes an
application-owned PostgreSQL-compatible or equivalent highly available
relational adapter. Composite indexes support the primary review order and
selective filters; exact monetary filtering uses minor units or a fixed-scale
numeric type. Search may start with normalized indexes/trigram support. A
separate search projection is introduced only after measured latency or query
complexity justifies it. Queue metrics use a maintained/materialized aggregate
in production rather than repeated full-table counts. SQLite may compute exact
demonstration summaries but is not the scale claim.

**Safety and UX:** Cursor values are opaque, validated, and bound to their query
shape. Sorting always has a unique tie-breaker. Page sizes are capped. Filters
are represented in the URL/query state where safe. Approve/reject remains an
individual, confirmed action; no bulk monetary decision is added.

**Implementation evidence:** `GET /api/reviews` validates every filter and a
10–100 item limit, returns an HMAC-signed query-bound cursor, freezes a traversal
at its first-page timestamp, and uses exact minor-unit amount columns. The
console implements debounced search, filter chips, five sort orders, table and
card views, focused details, and previous/next cursor history. Automated tests
cover filters, sorts, tampering, restart persistence, snapshot traversal, and
no-duplicate pages; browser QA traversed a 10-item first page and six-item
second page with no overlap. This validates the contract and UI behavior, not a
million-row latency SLO.

## D-034 - Trilingual presentation

**Status:** Accepted and implemented for the reviewer slice.

**Decision:** Product navigation, controls, statuses, validation, empty/error
states, date/number formatting, and known problem/rule labels support `pt-BR`,
`en`, and `es`. The UI chooses a supported user preference or browser language
and exposes a visible language switcher with a deterministic fallback.

API enums, status values, rule IDs, problem codes, audit event types, and stored
facts remain stable and language-neutral. Raw OCR, provider output, receipt
text, and human rationale are preserved in their original language, with
language metadata when available. Presentation may show an explicitly labeled
translation later, but it never replaces the audit source text.

**Consequence:** Translation catalogs must be versioned and tested for key
parity. Locale changes formatting and display strings, never financial values,
policy behavior, stored state, or audit identity.

**Implementation evidence:** The three catalogs have automated key-parity
checks. Browser QA switched among all three locales and verified localized
navigation, filters, states, money, dates, cards, and evidence detail while the
original English problem/rule messages and receipt OCR remained unchanged.

## D-035 - Standalone managed identity

**Status:** Accepted production identity target; not implemented.

**Decision:** Use an application-owned managed OIDC service, with Amazon Cognito
User Pools as the AWS reference, rather than an existing corporate IdP. The
service owns invitations/provisioning, MFA, account recovery, revocation,
deprovisioning, and role/group assignment for submitters, reviewers, auditors,
and administrators. Reviewer identity still derives from verified `(iss, sub)`
claims and is never typed into a decision form.

**Rationale:** This keeps the product independently deployable without building
password storage and token validation from scratch. It adds real ownership of
user lifecycle and support, which must be included in production scope and
cost rather than hidden behind an unknown dependency.

**Selected session direction:** D-039 selects a server-side BFF cookie so tokens
do not enter browser JavaScript. Invitation and approval flow, MFA/step-up
strength, idle/absolute limits, refresh rotation, tenant model, bootstrap
administrators, and recovery operations still require concrete policies.

## D-036 - Database-scoped discovery beyond the visible page

**Status:** Accepted. Server-side discovery over the current pending-review
scope is implemented; exact lookup across all statuses, completed-case history,
and audit search are planned and not implemented.

**Question:** How can an operator find one request among millions without
walking page by page or limiting the search to the rows already rendered in the
browser?

**Decision:** Search, filters, sorting, and authorization are evaluated by the
server against the entire permitted dataset before pagination. The browser
receives only a bounded page. Exact request-ID lookup must use an indexed direct
path and must eventually cover pending, processing, completed, rejected, and
otherwise retained cases. Completed-case history and the future audit surface
must have their own bounded, indexed, cursor-paginated queries rather than being
folded into the operational pending queue.

**Current implementation:** `GET /api/reviews` applies pending-queue search,
filters, sorting, and a 10-100 row limit in SQLite before returning data. Its
opaque HMAC-signed keyset cursor is tied to the query and a first-page snapshot.
This means matching pending requests can be found even when they are not on the
currently visible page. It does not yet provide a product search across final
or processing states, completed-case navigation, or audit-event search. A
regression test proves the distinction by placing a target outside the first
unfiltered page and finding it with a new server-side query.

**Pagination consequence:** Retain keyset/cursor pagination rather than numeric
`OFFSET` pages. A "jump to page 47,821" control is neither stable under
concurrent writes nor an efficient discovery mechanism at high cardinality.
Operators reach a specific record through exact lookup, indexed search,
filters, saved views, and deep links; next/previous traversal remains available
for sequential work.

**Production boundary:** The PostgreSQL-compatible adapter needs indexes and
query plans for each accepted access pattern, authorization predicates in the
query boundary, capped page sizes, stable unique tie-breakers, and load tests at
representative one-million and ten-million row cardinalities. Search-engine or
denormalized projections are introduced only after measured SQL behavior
justifies the additional consistency and operational cost.

## D-037 - Evidence detail, trace separation, and original-file access

**Status:** Accepted direction; partially implemented. Structured reviewer
evidence and a sanitized business timeline exist, but the privileged technical
trace surface, attachment-content authorization, and file-access auditing do
not.

**Question:** When a reviewer selects a card, can that person see the evidence,
traceability, and original receipt required to make and later explain a
financial decision?

**Current implementation:** Selecting a request loads claim data, raw OCR,
normalized facts, detected problems, policy version, rule evaluations, and
attachment locations. The detail API also carries safe model-invocation
metadata and automated-decision data, although the current screen does not
render that technical trace. The screen independently loads a sanitized,
cursor-paginated timeline over the append-only enqueue and human-decision
events. It is a case-scoped reviewer projection, not the privileged cross-case
audit search. The attachment model contains only a `location` string; it does not serve the
original bytes, preview them, verify a content checksum/version, or audit a
read. Its trace schema also permits only one invocation row per request, so it
cannot yet represent separate OCR, primary-model, verifier, retry, and
reprocessing attempts.

**Decision:** Case selection must provide three deliberately separated views:

1. Reviewer evidence: claim-versus-extraction comparison, original OCR,
   normalized object, problems, deterministic rules, decision history, and a
   sanitized chronological business timeline.
2. Privileged technical trace: full invocation, retry, correlation, processing,
   and infrastructure detail only through an independently authorized audit
   surface. Raw provider responses remain outside the normal reviewer payload.
3. Protected file access: attachment metadata appears with the case, while
   preview or original download occurs only after an explicit, on-demand,
   object-level authorization check. Opening a card must not automatically
   transfer every receipt byte.

**Trace multiplicity consequence:** Before the automated pipeline exists,
replace the one-row-per-request trace with immutable one-to-many invocations
identified by `invocation_id`, processing run, stage, and attempt. Each attempt
links its exact input manifest or preceding output hash to its own output hash,
provider/model/prompt configuration, timing, result, and protected raw output
or error. Earlier retries and reprocessing runs are appended, never overwritten.

**Attachment integrity and delivery contract:** Replace exposed storage
locations with stable attachment IDs and protected relational metadata linking
the request to the exact object version, SHA-256 checksum, detected media type,
byte size, scan result, and retention/legal-hold classification. Serve only the
same clean, pinned version used by the extraction trace; preserve derived safe
previews separately from the byte-for-byte original. The content path must use
safe `Content-Disposition`, single-range HTTP semantics where needed, private
no-store responses, and fail closed for pending, failed, unsupported, or
malicious scans.

**Authorization and audit consequence:** Identity remains server-derived. Each
detail, timeline, preview, download, and technical-trace request must enforce
its role/scope and object boundary, not trust a client-supplied bucket/key. The
separate append-only access audit distinguishes access authorization from bytes
actually served and records actor, request, attachment ID, object version,
checksum, action, range/byte result, time, and correlation/access IDs without
persisting credentials or signed URLs. Production object-store access and S3
data-event logs may complement this record, but do not replace the application
authorization fact.

**Open implementation choices:** Direct authenticated streaming provides the
strongest application-level delivery audit but moves file bytes through the
service. Short-lived private object-store delivery scales more cheaply but must
be described as an access grant and correlated with storage data events rather
than overstated as proof that a human read the document.

## D-038 - Dedicated sanitized reviewer timeline

**Status:** Accepted and implemented for the two current review-lifecycle event
types.

**Question:** How should a normal reviewer inspect a case's business history
without receiving an unbounded audit collection or privileged technical/model
data?

**Decision:** Provide `GET /api/reviews/{request_id}/events` as a separately
authenticated, case-scoped read. Return chronological pages of at most 1–100
events, default 25, using an opaque HMAC cursor bound to request ID, page size,
sort, version, and endpoint purpose. Project each known event through a strict
server-side field whitelist and scalar-only filter; keep the technical trace,
raw model response, tokens, provider parameters, and internal file locations
outside this response. The browser repeats a defensive whitelist and renders
only text nodes.

**Rationale:** A separate bounded capability avoids enlarging every case
snapshot, lets the evidence drawer load independently, and preserves the
authorization boundary between reviewer-readable business history and a future
privileged technical/audit surface. Stable keyset pagination scales better than
an unbounded event array and prevents duplicate traversal at equal timestamps.

**Implementation evidence:** `ReviewEventQuery`, `ReviewBusinessEvent`, and
`ReviewEventPage` define the application contract; `SqliteReviewRepository`
uses `(request_id, occurred_at, event_id)` and a purpose-separated persistent
cursor key; FastAPI exposes the strict query; and the trilingual drawer provides
loading, error, empty, retry, content, and load-more states. Tests cover
authentication, `404`/`422`, sanitization, unknown events, restart-safe cursor
use, tampering/cross-query/cross-purpose rejection, tie ordering, frontend
whitelisting, and the actual decision-to-timeline path.

**Boundary:** The current event vocabulary is only `review_case_enqueued` and
`human_review_decided`. All assessment reviewers still share one global scope;
completed-case discovery, object authorization, access auditing, event search
and export, full intake/OCR/model/retry coverage, and key rotation remain
production work.

## D-039 - Same-origin edge and Cognito-backed BFF session

**Status:** Accepted production target; not implemented.

**Question:** In the serverless deployment, how does a person enter the product
without typing an internal identity code or exposing long-lived tokens to the
browser?

**Decision:** Publish the data-free HTML/CSS/JavaScript shell from a private S3
origin through CloudFront Origin Access Control, ACM HTTPS, and WAF. Route
`/auth/*` and `/api/*` from the same public origin to API Gateway. Disable the
default API Gateway endpoint; have CloudFront overwrite a rotated
origin-verification header, and reject API-origin requests that lack its valid
value so the WAF edge cannot be bypassed. An application-owned Cognito User
Pool supplies invitation-only managed OIDC login and MFA through Authorization
Code with PKCE.

The callback Lambda exchanges and validates the code, maps stable `(iss, sub)`
claims to an immutable application actor, and gives the browser only a random
opaque `__Host-` session cookie with `Secure`, `HttpOnly`, `SameSite=Lax`, no
`Domain`, and `Path=/`. Store only a hash of that session identifier plus actor,
auth/MFA context, idle/absolute expiration, and revocation state in DynamoDB;
encrypt any required refresh token server-side. DynamoDB TTL performs eventual
cleanup only—the authorizer must reject expiry/revocation synchronously.

**Authorization consequence:** A Lambda authorizer establishes the principal,
but the application and SQL predicates remain responsible for roles, teams,
assignment, value authority, purpose, tenancy, and four-eyes restrictions
before filtering, ordering, pagination, evidence reads, or commands. Cognito
authentication alone never grants access to every case. Decisions accept only
outcome, rationale, command/idempotency ID, CSRF, and expected version; actor
identity comes from the verified session.

Aurora owns immutable actors, `(issuer, subject)` identity links, role grants,
team membership, assignments, and their administrative audit. A grant change
increments an authorization version and revokes or invalidates older sessions;
the DynamoDB session is not an independent authorization system of record.

**Security consequence:** No access/ID/refresh token enters `localStorage`,
`sessionStorage`, IndexedDB, URLs, or the financial audit ledger. State-changing
calls retain session-bound CSRF plus exact `Origin` validation. Logout revokes
the application session and provider refresh context and appends an auth event.
Session authorization caches must be disabled or kept shorter than the required
revocation SLO.

**Why BFF:** Direct browser Authorization Code + PKCE with an API Gateway JWT
authorizer is technically valid and simpler. The BFF adds a session lookup and
small DynamoDB/Lambda cost, but isolates provider tokens from JavaScript and
provides application-controlled revocation, which is the preferred trade-off
for this mission-critical financial domain.

## D-040 - Authoritative serverless ledger and immutable export

**Status:** Accepted production target; not implemented.

**Question:** If Lambda instances are disposable and SQS may redeliver work,
where does complete, reproducible traceability live?

**Decision:** Aurora PostgreSQL remains the authoritative business ledger.
Every financial command commits aggregate state, immutable decision or
processing record, append-only business event, and transactional-outbox row in
one SQL transaction. An idempotent exporter publishes only committed outbox
rows to SQS/EventBridge consumers and to a separate versioned audit bucket;
approved retention may add S3 Object Lock and signed/hash manifests. CloudTrail
with log-integrity validation records AWS activity, while CloudWatch/X-Ray/OTel
record operations. Neither replaces the application ledger.

**Trace identities:** Preserve distinct `request_id`, `event_id`, aggregate
version/sequence, `command_id`, `correlation_id`, `causation_event_id`,
`attachment_id` plus S3 version/checksum, `processing_run_id`, per-attempt
`invocation_id`, `decision_id`, and operational trace/AWS request IDs. A normal
reviewer timeline exposes only its authorized business projection; technical
invocations and cross-case audit search require separate scopes.

**Processing consequence:** S3 upload events and SQS/Lambda delivery are
treated as repeatable. Consumers use unique idempotency keys, append each retry
or reprocessing attempt rather than overwriting it, return partial batch
failures, and send exhausted work to DLQs with audited replay. A workflow engine
such as Step Functions is optional when the measured OCR/model graph needs
parallelism or durable orchestration; its execution history is operational
context, never the long-term financial ledger.

**Evidence consequence:** Original receipt objects are private, encrypted,
versioned, and checksum-bound to SQL metadata and every OCR/model input. An
authorized file-access grant targets the exact clean S3 version and is itself
audited. A short-lived presigned delivery is honestly recorded as a grant;
CloudTrail/S3 data evidence can corroborate retrieval but cannot prove that a
human cognitively read the receipt.

**Scale consequence:** Queue/list/timeline reads stay indexed and keyset
paginated; RDS Proxy protects Aurora from Lambda connection bursts; SQS caps
provider concurrency; materialized projections replace repeated global scans
when measured. “Millions per month” still requires peak-rate, skew, page-size,
provider-latency, RPO/RTO, and P95/P99 load evidence.

## D-041 - Kubernetes/EKS deployment alternative

**Status:** Superseded by D-042 after evaluation. Kubernetes was feasible but
was not selected, D-026 remains accepted, and no Kubernetes infrastructure is
implemented.

**Question:** Can Expense Agent be provisioned on Kubernetes?

**Finding:** Yes. The Python BFF/API and asynchronous workers can be
containerized and operated on an application-owned Amazon EKS platform. This
changes compute, ingress, workload identity, scaling, release, and operational
adapters; it does not change the domain, deterministic policy, Cognito user
identity, Aurora financial ledger, S3 evidence ownership, SQS backpressure, or
audit invariants.

**Alternatives considered:** A full EKS runtime behind CloudFront/WAF and an
ALB; EKS only for long-running, local-model, or GPU workers consuming SQS; EKS
on Fargate for node-free lightweight pods; and the accepted Lambda/SQS default
with Fargate, SageMaker, or EC2 fallbacks.

**Recommendation at evaluation time:** Do not replace D-026 from feasibility
alone. Keep short, bursty APIs and jobs on Lambda. If a measured long-running or
GPU workload appears, evaluate an EKS worker pool first while preserving the
serverless edge.
If full Kubernetes becomes an explicit product requirement, prefer EKS Auto
Mode unless a documented need for custom nodes or unsupported workloads
justifies managed node groups.

**Traceability consequence:** Kubernetes API/audit logs, container logs, image
digests, namespace/workload identity, and pod IDs are complementary operational
evidence. The authoritative path remains the authenticated actor plus one
Aurora state/decision/event/outbox transaction, exact S3 version/checksum, and
idempotent immutable audit export. Pod or node loss must not lose or redefine a
financial fact.

**Decision gate:** Reconsider D-026 only with evidence about sustained versus
bursty utilization, peak rate, task duration, GPU/runtime needs, latency SLOs,
standalone EKS cost, platform/SRE ownership, multi-AZ capacity, upgrades,
autoscaling, supply-chain security, observability, incident response, disaster
recovery, and representative load tests. Monthly case count alone is not this
evidence.

**Implementation boundary:** The repository has no Dockerfile, image pipeline,
Helm/Kustomize manifests, EKS infrastructure as code, ingress, probes,
PodDisruptionBudget, autoscaling policy, pod identity, secrets integration, or
production PostgreSQL adapter. SQLite, HTTP Basic, and local attachment
references remain assessment adapters and must never become pod-local
production state.

## D-042 - Reaffirm the hybrid AWS serverless target

**Status:** Accepted by explicit user direction.

**Question:** After evaluating Kubernetes/EKS, should the project change its
accepted production deployment architecture?

**Decision:** No. Retain D-026: CloudFront/WAF and private S3 for the static
shell, API Gateway and Python Lambda for short paths, SQS/DLQs for asynchronous
backpressure, versioned private S3 for evidence, Aurora PostgreSQL Serverless v2
through RDS Proxy for authoritative state/audit/outbox, Cognito for standalone
identity, and DynamoDB for short-lived BFF sessions. D-041 remains historical
trade-off evidence and is closed as a current option.

**Rationale:** The service has no measured long-running, GPU, sustained-load,
portability, or organizational Kubernetes requirement that offsets a cluster's
fixed cost and operational ownership. The accepted serverless topology better
matches the still-unknown and potentially bursty workload while preserving the
same domain, ledger, evidence, and traceability boundaries.

**Scope consequence:** This confirmation does not claim that AWS infrastructure
is implemented or required to complete the local code-assessment deliverable.
Do not add Kubernetes manifests or EKS provisioning. Production deployment
still requires the separately documented AWS, security, data-governance, load,
and recovery inputs.

## Decision template

```text
## D-NNN - Short title

Status:
Question or problem:
Decision:
Alternatives considered:
Rationale:
Consequences and trade-offs:
Evidence required or available:
Affected code and documentation:
```
