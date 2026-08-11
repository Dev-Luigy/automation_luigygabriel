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
| D-015 | Persist decision-command binding, human decision, status transition, and audit event atomically. | accepted |
| D-016 | Maintain a living question, assumption, and decision history. | accepted |
| D-017 | Serve same-origin HTML/CSS/vanilla-JavaScript submitter and reviewer screens. | accepted |
| D-018 | Avoid a separate React/Next.js runtime until infrastructure evidence justifies it. | accepted |
| D-019 | Use HTTPS in production with same-origin APIs, CSRF defense, and secure browser headers. | accepted |
| D-020 | Use role-bearing HTTP Basic principals only as a replaceable assessment authentication adapter. | accepted with production replacement |
| D-021 | Combine HTTP ETags, a durable command key, and a serialized database version/state check. | accepted |
| D-022 | Append review lifecycle events and enforce database immutability. | accepted |
| D-023 | Store and display attachment locations only in the assessment. | superseded by D-051 |
| D-024 | Retain the raw model response for audit but omit it from the reviewer API. | accepted |
| D-025 | Keep n8n as a rejected orchestration alternative, not the assessment runtime. | accepted |
| D-026 | Use a hybrid AWS serverless production target. | accepted target; not implemented or deployed |
| D-027 | Store receipt bytes in S3 and authoritative relationships in SQL. | accepted target; not implemented |
| D-028 | Do not require a VPN without a confirmed network-access requirement. | proposed; awaiting security confirmation |
| D-029 | Preserve originals and approve retention before lifecycle deletion. | proposed; awaiting legal and governance confirmation |
| D-030 | Derive serverless reviewer identity automatically through corporate OIDC/SSO. | superseded by standalone identity direction |
| D-031 | Separate the submitter status experience from the internal evidence-review workspace. | superseded; incorrectly assumed an existing client channel |
| D-032 | Build standalone submitter, reviewer, and audit/administration surfaces. | accepted; submitter/reviewer implemented, audit/admin UI pending |
| D-033 | Use server-side indexed filtering, sorting, search, and cursor pagination with multiple review views. | accepted; implemented for reviewer slice |
| D-034 | Localize the product interface in Portuguese, English, and Spanish. | accepted; implemented for submitter and reviewer surfaces |
| D-035 | Use an application-owned managed identity service rather than an existing corporate IdP. | accepted target; not implemented |
| D-036 | Make discovery database-scoped across the authorized dataset; retain keyset pagination and add exact all-status/history/audit lookup. | accepted; pending search and exact all-status lookup implemented, history/audit search planned |
| D-037 | On case selection, separate reviewer evidence and business timeline from privileged technical trace, with authorized on-demand access to the immutable original. | accepted; managed original and business timeline implemented, privileged audit UI pending |
| D-038 | Expose reviewer business history through a dedicated sanitized, cursor-paginated endpoint. | accepted and implemented for current business event types |
| D-039 | Use a same-origin CloudFront edge and Cognito-backed serverless BFF session. | accepted production target; not implemented |
| D-040 | Keep the Aurora business ledger authoritative and export its transactional outbox to immutable storage. | accepted production target; not implemented |
| D-041 | Evaluate Kubernetes/EKS as a container runtime without replacing the accepted serverless target. | superseded by D-042; evaluated and not selected |
| D-042 | Retain the hybrid AWS serverless target and close Kubernetes as a current deployment option. | accepted |
| D-043 | Reject receipts older than 90 days before applying human-review route precedence. | partially superseded by D-049; age boundary retained |
| D-044 | Compose an offline deterministic extractor by default and keep live HTTPS extraction optional/configurable. | accepted and implemented |
| D-045 | Persist the v1→v3 workflow through short transactions, leases, and immutable one-to-many invocation attempts. | accepted and implemented |
| D-046 | Provide strict authenticated intake and safe all-status lookup with request-ID plus fingerprint idempotency. | accepted and implemented |
| D-047 | Record every HTTP attempt locally while blocking production until outbox/export and governance exist. | accepted; partially superseded by D-050 |
| D-048 | Package a one-command AWS assessment sandbox without redefining the production target. | accepted and implemented artifact; not provisioned |
| D-049 | Make high-value review non-bypassable and constrain mandatory-reject cases. | accepted and implemented |
| D-050 | Append one privacy-bounded operational audit event for every HTTP attempt. | accepted and implemented locally |
| D-051 | Use managed immutable filesystem evidence for the assessment. | accepted and implemented locally |
| D-052 | Enforce explicit assessment roles, owner reads, and self-review prohibition. | accepted and implemented |
| D-053 | Recover expired processing leases on identical retry and fence stale workers. | accepted and implemented |
| D-054 | Block automatic approval when receipt evidence is missing. | accepted and implemented |
| D-055 | Provide a standalone trilingual submit-and-exact-track portal. | accepted and implemented |
| D-056 | Make human decision commands durably idempotent. | accepted and implemented |
| D-057 | Revalidate original evidence at human-decision time and fail closed for approval. | accepted and implemented |
| D-058 | Enforce four-eyes against the authenticated submission actor inside the application service. | accepted and implemented |
| D-059 | Bind operations and decisions to an immutable build ID and effective-configuration hash. | accepted and implemented |
| D-060 | Use canonical category codes, 128-bit request IDs, and bounded review paths. | accepted and implemented |
| D-061 | Seed the AWS sandbox with a distinct non-interactive actor. | accepted and implemented |
| D-062 | Detect possible cross-request receipt reuse without automatic rejection. | proposed production control; not implemented |

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
failure, repeated decisions, and two concurrent writers against the same
pending version: exactly one commits, the other conflicts, one decision
remains, and the case advances exactly once.

## D-016 - Living decision history

**Decision:** Update the journal, decision register, and assumptions register as
part of each meaningful design or implementation change.

**Rationale:** The final report must explain not only the resulting code, but the
questions, alternatives, compromises, and evidence that led to it.

## D-017 - Same-origin framework-free product screens

**Decision:** The Python service serves independent submitter and reviewer HTML,
CSS, and vanilla-JavaScript assets. JavaScript uses same-origin `fetch` for file
upload, intake/tracking, queue/detail/timeline, and decision actions.

**Rationale:** This provides an accessible non-technical interface without a
Node build pipeline, a second deployment artifact, hydration, or a separate
frontend server for two bounded workflows.

**Security consequence:** Reimbursement and OCR values are assigned with DOM
`textContent`, never inserted as executable HTML.

## D-018 - No React or Next.js without deployment evidence

**Decision:** Do not add a React/Next.js runtime for the current two bounded
same-origin workflows.

**Alternatives considered:** Next.js server-side rendering, a separately hosted
single-page application, and static HTML/JavaScript served by FastAPI.

**Rationale:** The submitter and reviewer screens are bounded operational
workflows. Static same-origin assets have a small deployment and dependency
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

## D-021 - Version concurrency plus command idempotency

**Decision:** A case detail response carries an ETag derived from the request
identity and database version. The decision endpoint requires `If-Match` and a
durable command key, then the repository rechecks key binding, pending state,
and version inside `BEGIN IMMEDIATE`.

**Rationale:** The ETag gives the browser an explicit stale-view protocol, while
the serialized transaction closes the race between the HTTP precheck and the
write. The UI can distinguish a stale precondition (`412`) from a transaction-
time conflict (`409`).

**Consequence:** An identical ambiguous retry returns the original decision;
divergent key reuse or a competing command conflicts. Neither can create a
second human decision. Production storage must preserve equivalent semantics.

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

**Consequence:** This is complete for the local SQLite review transaction and
business timeline. Intake, extraction, policy, processing recovery, and every-
HTTP operational events are also implemented, but production still needs an
outbox, approved immutable export, access governance, retention, backup, and
recovery controls.

## D-023 - Attachment reference boundary

**Status:** Superseded by D-051. Retained as the historical boundary before
managed evidence was implemented.

The current assessment uploads and serves integrity-checked local bytes. The
production concerns originally identified here—versioned object storage,
malware quarantine, retention, OCR binding, and richer authorization—remain.

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

**Boundary when this superseded proposal was written:** The repository then
implemented only the internal pending queue, case detail, and approve/reject
action. D-043 through D-046 subsequently implemented OCR-text extraction,
deterministic policy, intake, and exact all-status results. Attachment bytes,
submitter/audit screens, and audit export remain absent.

**Evidence required:** Confirm the existing employee channel, intake ownership,
how final results are returned (polling, event, or approved notification),
which rejection explanations may be shown, reviewer receipt-preview policy,
and whether auditors need a dedicated read-only interface in the first release.

## D-032 - Standalone product surfaces

**Status:** Accepted by explicit user direction; submitter and reviewer
surfaces are implemented, while privileged audit/administration remains open.

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

**Current boundary:** `/submit` now owns managed upload, claim entry, safe
submission, and exact-ID tracking. `/reviews` owns queue discovery,
detail/timeline/original evidence, and idempotent human decisions. Both are
trilingual and role-aware. A privileged cross-case audit/administration screen
is not implemented.

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

**Status:** Accepted and implemented for both submitter and reviewer surfaces.

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

**Status:** Accepted. Server-side pending discovery and exact lookup across all
retained statuses are implemented; completed-case list/history and cross-case
audit search remain planned.

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
currently visible page. `GET /api/requests/{request_id}` is now an indexed,
authenticated direct lookup across received, processing, automated-final, and
human-final statuses. Completed-case list navigation and cross-case audit-event
search remain absent. Regression tests cover both cross-page pending discovery
and safe all-status exact lookup.

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

**Status:** Accepted direction. Reviewer evidence, sanitized business timeline,
immutable 1:N attempts, case-bound managed-file delivery, integrity checks, and
file-access auditing are implemented. A privileged cross-case technical/audit
surface remains open.

**Question:** When a reviewer selects a card, can that person see the evidence,
traceability, and original receipt required to make and later explain a
financial decision?

**Current implementation:** Selecting a request loads claim data, raw OCR,
normalized facts, detected problems, policy version, rule evaluations, managed
attachment metadata, and a case-bound original-file action. The detail API also
carries safe model-invocation metadata and automated-decision data, while raw
provider output remains protected. The screen independently loads a sanitized,
cursor-paginated timeline over append-only processing and review business
events. It is a case-scoped reviewer projection, not the privileged cross-case
audit search. The filesystem evidence adapter uses opaque IDs, immutable
envelopes, media/size/SHA-256 verification on every read, and operationally
audited delivery. `processing_invocation_attempts` supports immutable attempts
by processing run, stage, and attempt; expired runs recover on an identical
retry, but there is no background scheduler or secondary verifier.

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

**Trace multiplicity implementation:** The automated pipeline persists a
running attempt before extractor execution and terminal status/raw output/hash
after it. `processing_invocation_attempts` is identified by `invocation_id`,
processing run, stage, and attempt; terminal attempts are immutable. Each links
its input hash to an output hash, provider/model/prompt configuration, timing,
result, and protected raw output/error. The legacy one-row trace remains only a
final compatibility projection. Retry/reprocessing orchestration is still
future work, but earlier attempts no longer need to be overwritten.

**Production attachment contract:** Replace assessment filesystem envelopes
with stable attachment IDs and protected relational metadata linking the
request to the exact S3 object version, SHA-256 checksum, detected media type,
byte size, scan result, and retention/legal-hold classification. Serve only the
same clean, pinned version used by the extraction trace; preserve derived safe
previews separately from the byte-for-byte original. The content path must use
safe `Content-Disposition`, range semantics where needed, private no-store
responses, and fail closed for pending, failed, unsupported, or malicious
scans.

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

**Status:** Accepted and implemented for the current business event vocabulary.

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

**Boundary:** The business projection now covers reimbursement received,
processing started, automated decision, review enqueue, and human decision.
Model-invocation start/completion are deliberately technical events; intake
replay/conflict are security events. Reviewer/auditor/admin read capabilities
and evidence-access audit are now explicit. Cross-case event search/export,
team/tenant/case-assignment predicates, privileged technical UI, and cursor-key
rotation remain production work.

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
envelopes remain assessment adapters and must never become pod-local production
state.

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

**Scope consequence:** This confirmation does not claim that live AWS
infrastructure is provisioned. The repository contains a bounded SAM assessment
sandbox, not the accepted production target. Do not add Kubernetes manifests
or EKS provisioning. Production deployment still requires the separately
documented AWS, security, data-governance, load, and recovery inputs.

## D-043 - Old-receipt precedence and time anchor

**Status:** Age boundary/time anchor retained; route precedence superseded by D-049.

**Question:** What happens when a receipt is both older than 90 days and above
the mandatory human-review amount, and which date anchors age?

**Current decision:** Evaluate all rules. A receipt more than 90 calendar days
old rejects automatically when the claim is at or below BRL 2,000. Above BRL
2,000, D-049 makes human review non-bypassable and the reject evaluation
prevents approval. Exactly 90 days is valid. Convert supplied
`submission.submitted_at` to `America/Sao_Paulo`; `decided_at` cannot change the
route.

**Rationale:** The assignment says both that old receipts reject and that a
high-value request must always be reviewed. The current constraint satisfies
both literal requirements while retaining complete evidence. Anchoring to the
immutable assessment input makes processing delays deterministic, but policy
ownership still must validate production semantics.

**Production blocker:** The assessment follows the assignment object, whose
`submitted_at` is supplied by the caller. A real monetary deployment must not
let a client choose the authoritative age anchor. It must add a server-owned
`received_at` (or separately model claimed and authoritative timestamps),
define clock/timezone semantics, and use the authoritative value in policy.

**Evidence:** Acceptance tests cover exactly 90 days, a decision made much
later, and a 91-day-old claim above BRL 2,000.

## D-044 - Default and optional extractor strategy

**Status:** Accepted and implemented.

**Decision:** Compose `DeterministicReceiptExtractor` in the assessment entry
point. It parses explicit fields from the supplied OCR text offline and produces
a complete trace. Keep `HttpJsonReceiptExtractor` as an optional explicitly
configured adapter with HTTPS-only endpoints, timeouts, response-size limits,
strict UTF-8/JSON/schema validation, redirect and duplicate-key rejection,
bounded failures, and secret-safe representation. Do not require a live LLM or
a second provider.

**Rationale:** The repository must run and be assessed without external
credentials, nondeterministic availability, or variable cost. The port proves
that a provider is replaceable while the policy remains deterministic. Two
models on every request are not justified until labeled quality/cost/latency
evidence exists.

**Consequence:** Any extraction warning/failure routes to review. The
composition root selects the HTTP adapter only when
`EXPENSE_AGENT_EXTRACTOR_MODE=http_json` and its strict settings validate;
deterministic remains the offline default. A secondary verifier remains a
proposed risk-based experiment.

**Production blocker:** Assessment intake accepts caller-supplied
`raw_ocr_text`. Managed bytes, checksum and media validation now exist, but OCR
is not derived from or cryptographically bound to that object and there is no
malware state or S3 version. The current extractor path therefore cannot
authorize real monetary decisions.

## D-045 - Durable processing transactions and 1:N attempts

**Status:** Accepted and implemented.

**Decision:** Persist the no-recovery workflow in short transaction boundaries:

1. submission, attachments, and `reimbursement_received` at received v1;
2. running processing run, state transition, and start event at processing v2;
3. running invocation attempt and technical start event before extractor I/O;
4. terminal attempt/raw output/hash and technical completion event after I/O;
5. extraction, automated decision/reasons/rules, terminal run, reimbursement
   route, business event, and optional review enqueue atomically at v3;
6. human decision, review/status transition, and audit event atomically at v4.

Every recovered processing lease advances the aggregate once before a new run,
so recovered paths use later versions rather than inferring v3/v4 from status.

Do not hold a SQL transaction across extractor I/O. Store attempts one-to-many
by invocation ID, processing run, stage, and attempt; terminal attempts and
financial evidence are immutable. Retain the historical one-row trace only as
a final compatibility projection.

**Rationale:** Recording invocation intent before the call preserves evidence
of abandoned work. Separating I/O avoids long locks. Atomic finalization avoids
status without decision/evidence/audit. 1:N identities allow retries and
reprocessing to append rather than overwrite.

**Implementation evidence:** Tests force extractor failure, multiple attempts,
direct mutation rejection, and a late audit-event collision; the last leaves
the request at processing v2 with no leaked extraction/decision/review rows.

**Current recovery boundary:** The synchronous service runs one primary attempt
per run and uses a five-minute lease. An identical retry after expiry appends
abandonment/resume evidence and fences the stale worker. Production still needs
heartbeat/watchdog supervision, retry budgets/backoff, SQS/DLQ replay, and
operator controls.

## D-046 - Authenticated intake, safe result, and fingerprint idempotency

**Status:** Accepted and implemented.

**Decision:** Add strict `POST /api/requests` and authenticated exact-ID
`GET /api/requests/{request_id}`. The write requires JSON, same origin, CSRF,
and a server-derived business actor with literal type `submitter`, distinct
from claimed `submitted_by`; the operational HTTP actor type is
`authenticated_principal`. Reject binary64 JSON floats at/above `2**46`, where cents can
collapse, while allowing exact decimal strings. Normalize the typed submission
and compute a canonical SHA-256 fingerprint. A new ID returns `201`; the same ID
and hash returns its stored result with `200` and no second extraction; the same
ID with a different hash appends a security event and returns `409`.

The result projection works across every retained status while omitting raw OCR,
attachment references, raw provider response, processing/invocation internals,
provider parameters, technical/security events, and reviewer identity.

**Rationale:** `request_id` alone detects a duplicate but cannot distinguish a
safe retry from accidental or malicious payload reuse. A canonical fingerprint
provides explicit idempotency while keeping normal responses least-privilege.
The exact-ID path prevents users from searching page by page through a large
pending queue.

**Authorization boundary:** Assessment roles, owner result reads, and
self-review denial are implemented. Production still lacks managed account
lifecycle and durable team, tenant, case-assignment, purpose, and value-authority
predicates. Managed identity alone remains insufficient.

**Evidence:** Real FastAPI-to-SQLite tests cover create/replay/conflict, strict
validation, actor derivation, safe serialization, all-status lookup, and
security-event persistence.

## D-047 - Processing trace versus all-operation traceability

**Status:** Accepted release gate.

**Question:** Does the new run/attempt/event model satisfy the requirement for
full traceability of all operations?

**Decision:** The original answer was no. D-050 now appends one sanitized row
for every HTTP request attempt in addition to processing and financial events.
This includes authentication, authorization, reads, searches, validation/error,
static assets, upload, and download without recording bodies or sensitive query
values.

**Remaining coverage:** There is no cross-case audit query/export UI, exact
search-expression digest policy, transactional outbox, approved immutable
archive, or administrator-resistant WORM guarantee outside SQLite.

**Consequence:** Production financial activation is blocked until accountable
security/compliance owners define the required event taxonomy, sensitive-field
redaction, retention/access controls, correlation/sequence semantics, immutable
export, monitoring, and verification. Operational infrastructure logs may
corroborate this ledger but cannot replace business identity, reason, policy,
and evidence facts.

## D-048 - One-command AWS assessment sandbox

**Status:** Accepted and implemented as a locally validated artifact; not
provisioned.

**Question:** How can an evaluator run the existing assessment on AWS with the
fewest manual steps without presenting assessment adapters as production
architecture or creating resources in an unknown account?

**Decision:** Provide a SAM deployment sandbox that packages the existing
FastAPI service as a Python 3.12 x86_64 Lambda through Mangum, exposes it through
an HTTP API, and mounts encrypted EFS for SQLite plus managed evidence. Create two
private subnets and security groups, enable EFS backups and retention, cap
Lambda reserved concurrency at four, retain 14-day sanitized API/Lambda logs,
enable X-Ray, and add error/throttle alarms. Keep the deterministic extractor,
one interactive config-backed admin, a distinct non-interactive seed actor,
same-origin CSRF controls, and direct `execute-api` HTTPS URL. Do not add NAT or
a live model provider. Seed only the three synthetic assignment examples after
deployment.

`deploy/aws/deploy.sh` checks local prerequisites and AWS identity, asks for an
explicit billable-resource confirmation, reads the review password without
echo, passes only PBKDF2 hashes and a generated CSRF secret through NoEcho
parameters, derives a build ID from a clean Git commit and the `uv.lock` hash
(or accepts an explicitly audited CI identity), prepares an exact-pinned
minimal dependency context, validates, builds in the official
Lambda-compatible container, deploys, uploads synthetic in-memory PDF evidence,
and seeds through the public HTTPS API with the distinct actor.

**Alternatives considered:** An EC2/EBS host would fit SQLite locking better but
would abandon the requested serverless path and add host operations. App Runner
or Fargate would still require a durable database and more infrastructure. The
accepted Aurora/Cognito/S3/SQS/CloudFront production topology cannot honestly be
made plug-and-play until its application adapters and governance inputs exist.
Lambda plus EFS is therefore limited to a reproducible evaluation sandbox.

**Rationale:** This preserves the current executable behavior and gives an
evaluator one command while keeping the production plan and its release gates
explicit. Python 3.12 is required because the Lambda Python 3.11 image exposed
an SQLite version too old for the schema's partial index.

**Consequences and trade-offs:** SQLite over EFS/NFS can still suffer locking,
latency, and corruption failure modes; rollback journal `DELETE` only avoids the
known WAL incompatibility. Reserved concurrency four is a browser-demo bound,
not evidence of scale. HTTP Basic is not production identity/authorization.
Stack deletion retains EFS by design, so it can continue to incur charges and
requires separately authorized removal. No real receipt or monetary data is
allowed, and D-026/D-039/D-040/D-042 remain the production target.

**Evidence:** Automated tests, Ruff, JavaScript syntax, ShellCheck, SAM lint, a
containerized x86_64 SAM build, and import/schema initialization in the matching
Lambda Python 3.12 runtime passed at this milestone. No live
stack, EFS recovery, load, security, or account-level test has been performed,
and no AWS resource was created.

**Affected code and documentation:** `lambda_handler.py`, configurable SQLite
journal mode, `deploy/aws/`, AWS deployment tests, the AWS runbook, architecture,
database, feature, diagram, final-report, journal, assumption, and time records.

## D-049 - Non-bypassable high-value review

**Status:** Accepted and implemented in `baseline-v3`, rule set `1.2.0`.

**Decision:** A claim above BRL 2,000 always reaches human review. All
deterministic rules still run. If one produces `reject`, the domain prevents a
human approval and requires the reviewer to confirm rejection with a rationale.

**Rationale:** This satisfies both literal assignment statements without
silently skipping the required human act or allowing judgment to override a
mandatory age rule. Exactly BRL 2,000 remains in the intermediate review band;
exactly 90 days remains valid.

## D-050 - Privacy-bounded audit for every HTTP attempt

**Status:** Accepted and implemented locally.

**Decision:** Middleware appends one `operational_audit_events` row for every
HTTP attempt, including failed authentication, authorization denial,
validation/error responses, reads, searches, static assets, uploads, downloads,
404s, and 500s. The event includes route classification, actor when known,
request/correlation identity, auth/outcome/status/duration, and bounded safe
metadata; it excludes bodies, OCR, query values, credentials, and tokens.

**Boundary:** This closes local HTTP-attempt coverage, not production
traceability. The row is written in a separate SQLite transaction and there is
no query UI, transactional outbox, approved retention policy, or off-host WORM
archive.

## D-051 - Managed immutable assessment evidence

**Status:** Accepted and implemented locally.

**Decision:** The public API streams allowlisted JPEG/PNG/PDF bytes into a
private immutable filesystem envelope and returns an opaque `evidence:att_*`
reference. The envelope carries safe filename, media type, size, and SHA-256;
every read revalidates the structure, checksum, and signature. Reviewer,
auditor, or admin access first proves case membership and is operationally
audited. New public intake rejects arbitrary legacy references.

**Boundary:** Seeded/migrated legacy references remain readable as text but
cannot support approval; they may be rejected with `unverifiable` recorded. The
adapter has no malware quarantine, uploader ownership, OCR-to-object binding,
S3 version, lifecycle/legal hold, or production authorization.

## D-052 - Explicit assessment authorization

**Status:** Accepted and implemented.

**Decision:** Credentials carry closed roles: `submitter`, `reviewer`,
`auditor`, or `admin`. Non-admin submitters can submit only their authenticated
email. Exact result reads are owner-only unless the principal can review or
audit. Only reviewer/admin can decide, auditor is read-only, and a submitter
cannot decide their own request. The authenticated actor from the immutable
intake event, not only claimed email, drives this check inside `ReviewService`;
the HTTP adapter also denies early. The browser hides actions it cannot perform,
while the server remains authoritative.

**Boundary:** Configuration-backed accounts do not provide MFA, recovery,
revocation, durable role administration, team/tenant/assignment/value/purpose
policy, or complete production separation of duties.

## D-053 - Retry-triggered processing lease recovery

**Status:** Accepted and implemented.

**Decision:** A run receives a five-minute lease. An identical request after
expiry atomically marks the old run and unfinished attempt abandoned, appends
recovery evidence, and starts the next run. One caller owns recovery; the stale
worker cannot finalize. The response reports `recovered` separately from a
terminal `replayed` result.

**Boundary:** No heartbeat, background watchdog, retry budget/backoff, operator
replay UI, SQS, or DLQ exists. A provider call longer than the lease may execute
twice, although state/version checks prevent a second financial decision.

## D-054 - Receipt evidence gates automatic approval

**Status:** Accepted and implemented in `baseline-v3`.

**Decision:** No attachment produces `MISSING_RECEIPT_EVIDENCE` and human
review; it can never auto-approve. The HTTP adapter additionally verifies every
new managed reference through an integrity read before processing.

## D-055 - Standalone trilingual submitter portal

**Status:** Accepted and implemented.

**Decision:** `/submit` provides an English, Portuguese, and Spanish
framework-free screen for receipt upload, immutable authenticated submitter
identity, exact decimal claim data, supplied assessment OCR text, safe
submission, and exact-ID tracking across statuses. It stores no sensitive data
in browser storage and recovers ambiguous network outcomes with the same
request ID.

**Trade-off:** The assessment remains synchronous and pastes OCR text. At scale,
the production target uses direct S3 upload and asynchronous SQS workers.

## D-056 - Idempotent human decision commands

**Status:** Accepted and implemented.

**Decision:** Decision POSTs require both the original `If-Match` and an
8–128-character visible-ASCII `Idempotency-Key`. SQLite stores only the key's
SHA-256 plus a fingerprint of request, outcome, normalized rationale,
authenticated reviewer, and expected version. Binding, decision, the next
aggregate state/version, and business audit event commit atomically. An exact
retry returns the original
result with `200`/`replayed: true`; divergent key reuse returns `409`.

**Rationale:** Aggregate versioning prevents competing decisions, while command
idempotency resolves the different problem of an ambiguous transport retry
after a successful commit.

## D-057 - Decision-time original-evidence integrity

**Status:** Accepted and implemented.

**Decision:** Immediately before a new human decision, re-read every managed
original and verify its immutable envelope, size, SHA-256, and media signature.
`ReviewService` accepts approval only with the explicit `verified` state.
Missing, corrupt, invalid, or legacy/unverifiable evidence may only support
rejection with a mandatory reason; the integrity state is stored in the human
audit event and operational request event.

**Rationale:** A case can wait in the queue after intake. Successful verification
days earlier cannot authorize approval if the original later disappears or
changes. Rejection must remain available so missing-evidence cases do not become
permanently undecidable.

## D-058 - Application-owned four-eyes invariant

**Status:** Accepted and implemented.

**Decision:** Derive the authenticated submission actor from the immutable
`reimbursement_received` event and expose it with review details. Deny a
decision when that actor matches the reviewer, when claimed submitter email
matches reviewer email, or when legacy actor identity is unavailable. Enforce
the rule in `ReviewService` as well as the HTTP adapter. The compatibility
adapter gives only explicitly preprocessed fixtures a synthetic actor.

**Rationale:** Email-only comparison allowed an admin to submit on another
employee's behalf and then review the same request. A future adapter must not be
able to bypass the service's separation-of-duties invariant.

## D-059 - Executable and configuration identity

**Status:** Accepted and implemented.

**Decision:** Carry an immutable `build_id` and SHA-256 of the complete effective
configuration through processing runs, business events, human decisions, and
every operational HTTP event. Persist only the final configuration digest, not
its secrets. The AWS script derives the default build ID from a clean Git commit
and `uv.lock`; accountable CI may provide its own validated identity.

**Rationale:** Provider/prompt/policy hashes are insufficient to reproduce an
operation if the deployed code or effective security/extractor configuration is
unknown.

## D-060 - Scalable canonical client identifiers

**Status:** Accepted and implemented.

**Decision:** Use the canonical `transportation` category code across submitter
and review controls while retaining `transport` only as a legacy display alias.
Generate request IDs from 128 bits of browser randomness, retain backend
fingerprint conflict protection, and constrain every review request-ID path to
the same 1–128-character grammar.

**Rationale:** A 32-bit suffix has an unacceptable birthday-collision rate near
million-request workloads. Divergent category codes silently defeat filters,
and unbounded path identifiers create needless parsing/database risk.

## D-061 - Distinct synthetic AWS seed actor

**Status:** Accepted and implemented.

**Decision:** Provision one interactive sandbox admin and one reserved,
non-interactive `assessment:seed-submitter` identity with a random password used
only by the deployment process and discarded afterward. The interactive admin
can review seeded cases. Their own `/submit` request still requires another
reviewer, which the minimal sandbox does not provision automatically.

**Rationale:** Seeding with the same account used for review would correctly
make the supplied pending example unreviewable under D-058. The separate actor
keeps the sandbox executable without weakening four-eyes control.

## D-062 - Possible duplicate receipt control

**Status:** Proposed production control; not implemented.

**Decision:** Do not automatically reject equal bytes without an approved fraud
policy. In the production evidence ledger, index immutable object
checksum/version and evaluate reuse with merchant, receipt date, amount, actor,
and an approved time window. Route a `POSSIBLE_DUPLICATE_RECEIPT` signal to
human review and retain the comparison evidence.

**Rationale:** Request-ID idempotency prevents duplicate processing of one
request but does not stop identical receipt bytes under different IDs. Equal
bytes can indicate fraud or a legitimate retry/multi-line allocation, so policy
ownership and false-positive measurement are required.

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
