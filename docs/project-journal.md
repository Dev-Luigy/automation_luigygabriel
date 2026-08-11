# Project journal

This is the chronological source for the final design report. It records the
questions raised during discovery, the reasoning discussed, and the resulting
direction. Questions originally asked in Portuguese are translated to English
so the final repository remains compliant with the assignment requirement that
all documentation be written in English.

The journal is append-only: later decisions may supersede earlier ones, but the
earlier context is retained.

## 2026-08-05 - J-001 - Assignment interpretation

**Question:** What does the assignment require, how difficult is it, and what
would be an appropriate project?

**Discussion:** The assignment asks for a Python service that receives expense
reimbursement requests and classifies them as auto-approved, human review, or
rejected. It requires explanations, human-review recording, and full
traceability because probabilistic model output influences financial activity.

**Direction:** Treat the project as a small production service. Use AI for
document understanding, but keep the financial decision in deterministic,
versioned policy rules. Route ambiguity to a human.

**Important ambiguity:** The policy says requests above BRL 2,000 must always
be reviewed and receipts older than 90 days must be rejected. The precedence
when both conditions are true must be explicitly documented and tested.

## 2026-08-05 - J-002 - Domain object design

**Question:** Which software-engineering objects should represent the
application?

**Discussion:** API DTOs, ORM rows, provider responses, and business objects
should not be the same classes. Financial invariants should be protected before
FastAPI, SQLite, or an LLM provider is introduced.

**Direction:** Create immutable value objects and records around a controlled
`ReimbursementCase` aggregate. The resulting model includes `Money`,
`ReimbursementSubmission`, `ExtractionResult`, `ReceiptFacts`, model invocation
trace, automated and human decisions, rule evaluations, and audit-event
contracts.

**Result:** Domain state transitions and invariants were implemented and tested.

## 2026-08-05 - J-003 - ClickUp as a CRM and review queue

**Question:** Could every reimbursement become a ClickUp card, be organized
automatically by status, assign a person or team for pending review, and contain
the source file, detected problem, and OCR object?

**Initial discussion:** ClickUp can be modeled as an external projection. One
`request_id` maps to one ClickUp `task_id`; synchronization creates or updates
the same task and uploads original files plus a versioned OCR JSON attachment.
Pending-review cards can be assigned and given a review SLA.

**Initial result:** A ClickUp adapter, synchronization service, SQLite binding,
file fingerprinting, tests, and integration documentation were implemented.

**Later correction:** Evaluator feedback clarified that the human decision must
live in the service itself. ClickUp must not be the heart or system of record
for review. This initial implementation is therefore optional integration work,
not the target core review mechanism. See J-007 and decisions D-007 through
D-011.

## 2026-08-05 - J-004 - CRM identity mapping

**Question:** Does the SQLite mapping contain both the reimbursement
`request_id` and the ClickUp card ID?

**Answer:** Yes. `crm_task_bindings` stores `request_id`, ClickUp `task_id`, the
optional task URL, uploaded file fingerprints, and the last update time. The
primary purpose is retry idempotency: a repeated synchronization updates the
same external task and does not upload identical file content twice.

**Constraint discovered later:** The current database is only an integration
database. Reimbursements, extractions, decisions, and audit events are not yet
persisted.

## 2026-08-05 - J-005 - Living system documentation

**Question:** Create documentation showing the current system, database, object
models, and application features, with diagrams.

**Direction:** Create a version-controlled documentation set with Mermaid
diagrams and visibly separate implemented, partial, and planned components.

**Result:** Architecture, current and target database, domain model, feature,
and ClickUp integration documents were created. Twenty-seven Mermaid diagrams
were rendered successfully during documentation QA.

## 2026-08-05 - J-006 - OCR plus two LLMs

**Question:** Given the mission-critical financial and traceability
requirements, would using OCR plus two different LLMs be too expensive, and
what latency and engineering cost would it add?

**Discussion:** Generic OCR plus two small models can have a low per-request
inference price. Specialized expense parsers can dominate the price. Two models
run in parallel add the slower model to the critical path rather than the sum of
both latencies, but increase tail latency, external calls, provider-failure
modes, privacy exposure, and audit volume.

**Important correction:** OCR and two LLMs are not three independent votes. If
both models consume the same incorrect OCR output, they may agree on the same
wrong value. A low error rate must be demonstrated with an evaluation dataset;
it cannot be inferred from model count.

**Proposed direction:** Use OCR as evidence, a primary structured extractor, a
deterministic reconciler and policy engine, and human review on uncertainty. A
secondary model may be invoked only for auto-approval candidates, discrepancies,
or a monitoring sample. The final model/provider choice remains open.

## 2026-08-05 - J-007 - Evaluator feedback on human review

**Question:** Given feedback that reliance on ClickUp or email weakens internal
traceability, which alternatives better match the assignment?

**Feedback summarized:** Human review should be part of the service. A human
decision must become an auditable internal record containing who decided, what
they decided, when, and why. The interface is secondary and replaceable. A SaaS
dependency should not control the authoritative financial decision.

**Direction:** Implement an internal review queue and decision endpoint. Obtain
reviewer identity from an authentication context, never from a freely supplied
request-body field. Write the human decision, case transition, and audit event
in one database transaction. External tools, if retained, may only notify and
deep-link to the internal review surface.

**Recommended MVP interface:** FastAPI endpoints plus its generated Swagger UI.
A small server-rendered page may be added if time remains. The authentication
adapter for the assessment remains to be selected; production is expected to
integrate with corporate OIDC/SSO.

## 2026-08-10 - J-008 - Continuous decision capture

**Question:** Preserve every meaningful question and decision so a final report
can explain what was considered and why each solution was selected.

**Direction:** Maintain this chronological journal, a structured decision log,
an assumptions register, and a final-report outline. New material decisions
must be recorded with status, alternatives, rationale, consequences, and links
to affected implementation or tests.

## 2026-08-10 - J-009 - Non-technical internal review console

**Question:** An API-only interface is unsuitable because expected reviewers are
probably not programmers. Should the service instead provide one simple web
screen, possibly with Next.js, or plain HTML and JavaScript? The existing
external CRM integration must be removed without runtime residue.

**Accepted direction:** Build one internal review screen with HTML, CSS, and
vanilla JavaScript served by FastAPI. The JavaScript invokes same-origin JSON
endpoints with `fetch`; these browser calls are not webhooks. Do not add
React/Next.js while the deployment topology, existing RecargaPay frontend
platform, server-memory trade-offs, and user devices are unknown.

**Security direction:** Production uses HTTPS through a trusted deployment
boundary. The service still needs authenticated reviewer identity, CSRF
protection, restrictive response headers, safe DOM rendering, mandatory
rationale, optimistic concurrency, and an atomic decision/status/audit write.
HTTPS alone is necessary but insufficient.

**Removal direction:** Delete the external CRM adapter, configuration,
dependencies, tests, and active architecture documentation. Preserve only this
historical explanation that the alternative was evaluated and rejected.

**Durability direction:** `AGENTS.md` now contains accepted constraints and must
be read with the decision log before every material action.

## 2026-08-10 - J-010 - Option 2 implementation and verification

**Question:** Does the implemented application now match the accepted option 2,
and how does it behave for a non-technical reviewer without relying on the
removed external review mechanism?

**Implementation result:** FastAPI now serves one responsive HTML/CSS/vanilla-
JavaScript screen at `/reviews`. The browser uses authenticated same-origin
`fetch` requests to load identity, queue summaries, and evidence details, then
submits approve/reject with a mandatory rationale. No case data is embedded in
the HTML, and untrusted OCR and merchant values are created as DOM text nodes.

**Security result:** The assessment authenticates configured reviewers through
HTTP Basic with salted PBKDF2-SHA256 hashes. The server derives the canonical
reviewer ID/email/name; an identity supplied in the JSON is rejected. State
changes require JSON, same origin, a reviewer-bound expiring HMAC CSRF token,
and the current `If-Match` ETag. Responses include a restrictive CSP, HSTS on
HTTPS, anti-frame/cache/sniffing controls, and trusted-host enforcement. HTTP
can be enabled only explicitly for local development; production is expected to
use a trusted HTTPS ingress and replace Basic auth with corporate OIDC/SSO.

**Persistence result:** The old external binding database was replaced by 11
normalized review/evidence/audit tables. Pending-case ingestion uses one
transaction, propagates a correlation ID (with a derived fallback only for the
demo/helper), and appends `review_case_enqueued`. Reviewer decisions use
`BEGIN IMMEDIATE`, recheck state/version, insert the immutable decision and
authenticated identity snapshot, update both statuses/version, append
`human_review_decided`, and commit or roll back together. SQLite uses foreign
keys, WAL, a busy timeout, `synchronous=FULL`, field checks, and triggers that
reject update/delete of human decisions and audit events.

**Completeness result:** Option 2 satisfies the Human Review slice, not the full
assignment. There is no request intake endpoint, authoritative processing
orchestrator, live OCR/LLM provider, or implementation of the required baseline
rules (`<= BRL 200` eligible auto-approval when checks pass, `> BRL 2,000`
mandatory human review, and receipts older than 90 days rejected). The UI shows
attachment locations but cannot download or preview content. It shows raw OCR
and structured facts but withholds the persisted raw model response. No
reviewer/session tables are part of the assessment schema.

**Removal result:** The ClickUp/CRM runtime, configuration, tests, and active
architecture were removed. Its mention remains only in historical decision
material to explain why the direction changed.

**Validation evidence at that stage:** The then-current automated run reported
39 passing tests and a passing Ruff check. A real two-thread repository test gives both writers
version 1 and proves exactly one decision commits, the other conflicts, only one
human-decision row exists, and the case reaches version 2. Browser validation
loaded two pending cases, recorded a decision with HTTP `201`, refreshed the
queue from two to one, displayed a toast containing the audit event ID, and
produced no browser-console errors. `uv build` produced both sdist and wheel;
the wheel contains the three static UI assets and all three CLI entry points.

## 2026-08-10 - J-011 - n8n as an orchestration alternative

**Question:** Could the project instead run as an n8n automation, including
invoking a model available in the self-hosted Linux environment through a
command-line integration and returning its output to the workflow?

**Assessment:** The design is technically viable if that installation permits
and secures the required execution capability. n8n can coordinate triggered or
scheduled work, provider calls, branching, and integration steps. It would not,
however, supply the complete financial application boundary by itself: the
reviewer still needs a usable client, authenticated commands, deterministic
policy, authoritative storage, atomic decision and audit writes, concurrency
semantics, and application-level tests.

**Accepted direction:** Retain the Python backend and its same-origin static web
screen. The assignment requested Python, and implementing the present scope
directly is smaller and clearer than distributing domain behavior across n8n
nodes, custom scripts, and a separately built reviewer surface. Do not add n8n
to the current runtime or active architecture.

**Trade-off retained for the final report:** n8n could be reconsidered as a
replaceable peripheral orchestrator where RecargaPay already operates an
approved instance. It must not own the authoritative human or monetary
decision. Shell or local-model execution would require explicit controls for
least privilege, isolation, credentials, input/output validation, timeouts,
failure recovery, and invocation audit.

**Affected records:** D-025 and A-028.

## 2026-08-10 - J-012 - Cloud scale, storage, VPN, and AWS cost

**Question:** With no knowledge of RecargaPay's database or deployment
environment, should receipt images live on a Linux host, in a NoSQL database, or
in cloud object storage? For millions of requests, should the Python service use
an AWS VPS/EC2 host or Lambda? Is a VPN necessary, how should retention and
compression work, and what would the alternatives cost?

**Analysis:** Local host storage is cheap only in the smallest demonstration and
creates affinity, replication, backup, failover, and scaling problems. A NoSQL
database does not need to contain image bytes to preserve linkage. S3 can own
the bytes while a relational attachment row owns the stable object identity,
checksum, version, and request foreign key. This retains the accepted domain
relationships and SQL transaction for status, decision, and audit.

Monthly totals alone are misleading: 1M cases/month averages 0.39 cases/second
and 10M averages 3.86. Peak RPS, file size, pages, processing time, provider
limits, and retention drive capacity. The proposed flow therefore commits
intake, uploads directly to S3, queues asynchronous OCR/LLM work through SQS,
and returns without waiting for inference.

**Proposed direction:** Use a hybrid AWS reference in `sa-east-1`: HTTP API plus
Python Lambda for short operations, S3 for private objects, SQS for backpressure,
and Aurora PostgreSQL/RDS Proxy for authoritative relational data. Fargate or
EC2 remains an escape hatch for long or heavy workers; a single VPS is rejected
for mission-critical production. This is a recommendation pending actual
RecargaPay infrastructure facts, not an implementation decision.

**VPN direction:** Do not assume a VPN. HTTPS plus OIDC/SSO, MFA, authorization,
private stores, security groups, and VPC endpoints is the default. Add a VPN
only if corporate policy requires private-network reviewer access or the
service must reach an on-premises/private dependency.

**Retention direction:** No deletion period was invented. Preserve originals,
generate separately versioned derivatives, and obtain an approved retention
and legal-hold matrix before enabling lifecycle expiration. A 90-day period is
used only as a cost sensitivity example.

**Cost result:** Under the documented assumptions, API/Lambda/SQS is about USD
43.67 for 1M cases/month and USD 440.30 for 10M. A complete model including 1 MB
per case retained for 90 days and assumed Aurora capacity is roughly USD
608.60-1,020.32 at 1M and USD 3,619.30-5,266.18 at 10M, before OCR, LLM, WAF,
logs, KMS, backups, transfer, disaster recovery, tax, discounts, and labor.
OCR/LLM may dominate this infrastructure subtotal.

**Affected records:** D-026 through D-029, A-029 through A-034, and the
[AWS deployment study](aws-deployment-study.md).

## 2026-08-10 - J-013 - Serverless traceability without manual identity entry

**Question:** Can the review service remain serverless and fully traceable
without asking a reviewer to type an employee or reviewer code, and does that
require authentication?

**Analysis:** Yes. Lambda being stateless only means that a particular runtime
instance is disposable; durable financial state and audit evidence remain in
PostgreSQL, the transactional outbox, and approved immutable storage. A human
decision cannot be attributed reliably from an editable form field, IP address,
or browser metadata. It requires an authenticated principal and an explicit
authorization check.

**Proposed direction:** Reuse corporate OIDC/SSO. A reviewer opens the internal
screen; an existing SSO session can make the flow silent, otherwise the identity
provider requests login and possibly MFA. API Gateway or a trusted ingress
validates the token and passes verified claims to the Python Lambda. The service
keys identity by `(issuer, subject)`, checks the reviewer role/scope, and derives
the actor automatically. The form contains only approve/reject and a mandatory
rationale; no client-supplied identity is accepted.

Direct Authorization Code with PKCE is viable. A backend-for-frontend with an
opaque `Secure`, `HttpOnly` cookie is preferred if corporate standards require
browser token isolation or centrally revocable sessions. Cognito can broker an
existing corporate OIDC provider or supply managed login, but a new standalone
user directory would create avoidable user-lifecycle responsibility and is the
fallback, not the default.

**Traceability:** The terminal review transaction writes the decision, case
state, business audit event, and outbox atomically. It records stable identity,
display and authorization snapshots, reason, before/after state, version,
request/correlation/trace IDs, and time, but not raw tokens. CloudTrail and an
Object-Lock archive may strengthen infrastructure and forensic evidence; they
cannot explain the business decision and therefore do not replace this record.

**Open evidence:** RecargaPay's identity provider, claims, roles, MFA, session
and revocation standards, separation-of-duty policy, trusted ingress, and
retention requirements remain unknown.

**Affected records:** D-030, A-035, the AWS deployment study, and the final
report outline.

## 2026-08-10 - J-014 - Initial receipt and result experience

**Question:** How will the initial system work, and how will clients see
receipts and processing results?

**Clarification:** There are at least two materially different users. The
employee/submitter needs submission acknowledgement and a safe status/result.
The internal finance reviewer needs enough evidence to make an accountable
decision. Combining both into one screen would expose unnecessary internal data
and blur authorization boundaries.

**Current implementation:** The repository already supplies the internal
reviewer workspace. Its left queue shows request ID, claimed amount, submitter,
category, and submission time. Selecting a case shows claimed values, detected
problems, raw OCR text, a normalized receipt object, deterministic rule
evaluations, attachment locations, and the approve/reject form with mandatory
rationale. It authenticates the reviewer and commits a decision, status change,
and audit event atomically. It does not yet display the receipt image/PDF bytes.

**Proposed first complete MVP:** Receive a request from an existing RecargaPay
channel, persist receipt metadata in SQL and bytes in private object storage,
process asynchronously, and expose a sanitized status/result back to that
channel. Auto-approved/rejected cases return without entering the review queue.
Only `pending_review` cases appear in the internal workspace, where an
authorized short-lived receipt preview complements the OCR, extracted facts,
problems, and rule results. The human decision then becomes the final status
and is propagated to the originating channel.

**Information boundary:** The submitter sees request reference, processing
state, final outcome, and an approved explanation. Reviewers see protected
evidence and policy details. Auditors use authoritative audit data or a later
read-only search/export surface. Raw model responses and tokens remain outside
browser payloads.

**Open evidence:** Whether RecargaPay already has the employee channel, how it
expects status delivery, which explanations are permitted, attachment-preview
rules, and whether an auditor UI belongs in the initial release.

**Affected records:** D-031, A-036, system architecture, features, and final
report outline.

**Later correction:** The assumption that an existing RecargaPay client channel
would own submission and status was explicitly rejected in J-015. D-031 and
A-036 are superseded/rejected; only the separation of information by role
remains useful.

## 2026-08-10 - J-015 - Standalone, scalable, trilingual product UX

**User correction:** Do not depend on anything RecargaPay currently has. The
current reviewer interface is not acceptable UX, a one-by-one queue does not
work for millions of requests, and the product must serve Portuguese-, English-,
and Spanish-speaking teams.

**Decision:** Expense Agent becomes a standalone product with its own submitter
upload/tracking surface, reviewer operations console, and controlled
audit/administration capability. Existing RecargaPay applications, identity,
databases, messaging, and workflows are not prerequisites. The implemented
slice remains reviewer-only until the standalone intake and other surfaces are
built.

**Scale direction:** Replace the unbounded oldest-first queue response with
bounded server-side search, selective filters, stable sorting, and opaque
keyset/cursor pagination. The reviewer console provides table and card scanning
views plus focused case detail, active-filter visibility, page-size control,
and summary/SLA indicators. The browser never receives the full result set.
Production PostgreSQL uses exact monetary types, composite indexes, and a
maintained summary/read model; SQLite is only the functional assessment
adapter. No bulk approve/reject action is introduced.

**Language direction:** Support `pt-BR`, `en`, and `es` throughout navigation,
controls, statuses, validation, errors, and locale formatting. API enums and
audit codes remain stable. OCR, receipt text, provider output, and human
rationale remain in their original language so changing the UI locale cannot
rewrite evidence.

**Identity consequence:** The previous corporate-SSO assumption is no longer a
valid dependency. A standalone managed OIDC directory such as Cognito becomes
the production reference, including provisioning, MFA, roles, recovery,
revocation, and deprovisioning. HTTP Basic remains only the current assessment
adapter.

**Implementation boundary:** The current change targets the scalable reviewer
query and trilingual operations console. Standalone submitter intake/tracking,
attachment-byte preview, production identity, audit administration, OCR/LLM,
and deterministic policy remain separate unfinished capabilities.

**Implementation result:** The reviewer query now accepts bounded server-side
search, category/problem, amount, submission-time and pending-age filters; five
stable sorts; page sizes from 10 to 100; and an opaque HMAC-signed cursor bound
to the query and a frozen first-page snapshot. SQLite stores exact minor units,
backfills compatible legacy databases, and has queue/search/filter indexes. The
response enriches each row with merchant, extracted value, primary/all problem
codes, page metadata, and global pending KPIs. Production still requires a
maintained aggregate/search plan and measured high-cardinality SLOs.

The console was rebuilt with KPI overview, debounced search, an expandable
filter panel, active chips, stable sorting, page-size control, dense table,
visual cards, focused evidence detail, claimed-versus-extracted comparison,
explicit loading/error/empty states, individual confirmed decisions, keyboard
shortcuts, and responsive layout. Its catalogs support `pt-BR`, `en`, and `es`;
known presentation labels are localized while raw OCR and free-text evidence
remain unchanged. Browser QA found and corrected two presentation defects:
container helpers inserted stray em dashes, and filter chips rendered the
definition object instead of the selected value.

**Validation result:** Fifty-three automated tests and Ruff passed, JavaScript
syntax validation passed, and `uv build` produced sdist and wheel. Manual browser
QA covered all three locales, a `client_meal` filter, table/cards/detail modes,
a first cursor page of 10 and second page of six with no duplicated IDs, and an
approved decision returning HTTP 201 with refreshed queue/KPIs and an audit-event
toast. Browser logs were empty. These checks validate behavior and navigation;
they do not prove a million-case latency SLO.

**Affected records:** D-030 and D-031 superseded; D-032 through D-035 added;
A-014, A-035, and A-036 superseded/rejected; A-037 and A-038 added. Architecture,
features, database, final-report, and AWS reference documentation require the
same correction.

## 2026-08-10 - J-016 - Cross-page discovery and evidence access

**User questions:** Pagination must keep large result sets from being loaded
destructively from the database, but how does an operator find a specific
request that is not on the current page, and which additional scenarios are
still missing? When a person selects a card, are the case information,
traceability, and original file actually available?

**Current answer - discovery:** The pending reviewer endpoint already applies
search, filters, sorting, and a bounded 10-100 item limit on the server before
returning a page. Its HMAC-signed keyset cursor is bound to the query and a
stable first-page snapshot. Search therefore examines the permitted pending
dataset rather than only the current browser page. Numeric page jumps are not
part of the design because high-offset reads become expensive and page numbers
move under concurrent intake. Exact indexed search and filters are the way to
reach a record. The current executable still lacks exact product-wide lookup
across processing and final statuses, completed-case history, saved views, and
audit-event search.

An explicit regression now seeds more pending cases than one page can contain,
confirms that the target is absent from the first unfiltered page, and then
confirms that a new server-side search returns it. This protects the
page-independent pending-search behavior rather than relying only on code
inspection.

**Validation result for this change:** The full suite now contains 54 passing
tests, including the new cross-page search regression, and Ruff passes.

**Current answer - selected case:** The drawer currently exposes the claim,
submission data, claimed-versus-extracted comparison, OCR text, normalized
facts, problems, policy version, rule evaluations, and attachment references.
The API contains additional safe automated/model trace metadata, but the screen
does not render the complete trace. Enqueue and human-decision audit events are
persisted append-only, yet no sanitized timeline or audit query is exposed.
Most importantly, an attachment is currently only a `location` string. No
authenticated preview/download or original-byte access exists, and case/file
reads are not audited.

**Accepted target:** Keep discovery database-scoped and bounded, add an indexed
exact request-ID path across all authorized statuses, and build separate
cursor-paginated history and audit queries. Selecting a case will present the
reviewer's evidence and a sanitized business timeline, while protected raw
technical trace remains a separate auditor capability. File bytes load only
after an explicit authorized action; the UI distinguishes a safe derivative
preview from the original download.

**Integrity and security direction:** Attachment metadata must link one stable
attachment ID to the request, exact object version, SHA-256 checksum, detected
MIME, size, scan state, and approved retention classification. The service must
never accept a client-selected storage key, must fail closed unless the exact
version is clean, and must log authorization and byte-delivery outcomes as
different append-only events. On-demand loading also avoids downloading
evidence that the reviewer never opens.

**Additional scenarios identified:** Cross-case object reference attacks;
pending, failed, unsupported, or stale malware scans; a file version changing
between scan, OCR, and review; misleading MIME/filename or active PDF/HTML/SVG;
large/range-abuse downloads; several browser range requests for one PDF;
expired retention or legal hold; revoked users with an active access grant;
object-store event duplication; orphaned uploads; original-versus-derivative
confusion; and sensitive browser/CDN caching. Exact read semantics also matter:
the system can prove that access was authorized and bytes were delivered, but
cannot prove that a human cognitively read the receipt. The current
one-trace-per-request schema is also insufficient for OCR plus primary model,
optional verifier, retries, and reprocessing; production trace must append one
record per stage and attempt and preserve their input/output hash chain.

**Implementation boundary:** D-036 and D-037 record the accepted design. Only
pending-scope discovery and the partial evidence detail exist today. Broader
lookup, timelines, attachment metadata/content, scanning, and access audit
remain planned and require implementation and production validation.

**Affected records:** D-036, D-037, A-039, A-040, and A-041.

## 2026-08-10 - J-017 - Reviewer timeline, current entry, and architecture audit

**User questions:** Implement the traceability timeline. How does a person enter
the system today? Is the implementation still following the agreed
architecture correctly?

**Current entry flow:** The assessment has no application-owned login form and
no default password. An operator hashes a chosen local password with
`expense-agent-hash-password`, places the result with `username`, canonical
reviewer ID, email, and display name in `EXPENSE_AGENT_REVIEWERS_JSON`, exports
the environment, seeds demo data, and starts `expense-agent-review`. Opening
`http://127.0.0.1:8000/reviews` with local HTTPS enforcement explicitly disabled
causes the browser's native HTTP Basic prompt to appear. After credential
verification, the server derives `ReviewerPrincipal` and `ReviewerIdentity`;
the user never supplies a reviewer ID in a decision. `/api/session` returns the
canonical identity and a one-hour reviewer-bound CSRF token held only in memory.

This is intentionally assessment-only. It has no application logout, password
recovery, MFA, lockout, user administration, role/team/object scope, or
authentication-event audit. Every configured reviewer currently has global
review access. The production direction remains an application-owned managed
OIDC directory with service-enforced roles, object authorization, lifecycle,
revocation, and separation of duties; it must not depend on an existing
RecargaPay identity surface.

**Implemented timeline:** Case detail now loads a second read independently from
the evidence snapshot: `GET /api/reviews/{request_id}/events`. The application
contract caps pages at 100 (25 in the UI), and SQLite orders by
`occurred_at ASC, event_id ASC` using the existing case/time index and
`LIMIT n + 1`. The opaque HMAC cursor is persistent across adapter restarts,
purpose-separated from the queue cursor, and bound to request, limit, sort, and
version. Invalid, tampered, cross-case, cross-limit, or cross-purpose cursors
fail closed.

The normal reviewer response contains event identity/type/time, actor,
correlation, and an event-specific whitelist of scalar business fields. Raw
model responses, tokens, provider parameters, nested values, internal file
locations, and unknown-event payloads are omitted. The browser applies a second
defensive whitelist and safe text rendering. The trilingual drawer supplies
loading, error, empty, retry, content, and load-more states; switching cases or
closing the drawer aborts stale timeline reads. Evidence and timeline load
independently so timeline failure does not block a financial decision. After a
successful decision, the case drawer stays open and reloads the completed
snapshot plus timeline while the pending queue refreshes, making the newly
committed human-decision event immediately visible.

**Architecture verdict:** The code still follows the accepted ports-and-adapters
direction for the implemented human-review slice: the application defines the
query/read models, SQLite owns keyset/HMAC mechanics and projection,
presentation owns strict HTTP DTOs and safe rendering, identity is server
derived, and the authoritative decision/status/event write remains atomic. No
ClickUp, external RecargaPay system, React/Next.js runtime, or browser-side
financial policy was introduced.

The accurate claim is narrower than “production ready” or “fully traceable.”
Only enqueue and human-decision events exist. The product still lacks
all-status/completed-case discovery, a 1:N OCR/model/retry trace, original-file
bytes and checksum/version/scan linkage, evidence-access audit, RBAC/ABAC and
four-eyes controls, the real intake/OCR/policy pipeline, a production HA data
platform, retention controls, observability, and representative million-case
load evidence. A decision event can be retrieved by known request ID, but the
current pending-only UI does not yet provide later navigation back to completed
cases after that drawer is closed.

**Validation result:** 60 automated tests and Ruff pass; JavaScript syntax and
the package build pass. Coverage includes authentication, sanitization,
chronological pagination, equal-time tie-breaking, cursor restart/tamper/query
and purpose isolation, frontend state/i18n wiring, and an integrated decision
whose `human_review_decided` event is then read through the timeline endpoint.
No new manual browser run was performed for this increment.

**Affected records:** D-037, D-038, A-040, and A-042.

## 2026-08-10 - J-018 - Accepted AWS user access and traceability flow

**Question:** Given that AWS serverless is now the defined deployment model,
how will users enter and use the system without manually supplying identity,
and how will the service preserve complete traceability across disposable
Lambda executions?

**Accepted direction:** Treat the hybrid AWS serverless topology as the
production target, not merely a comparison. A single CloudFront/WAF HTTPS
origin serves the data-free HTML/CSS/JavaScript shell from private S3 and routes
`/auth/*` and `/api/*` to API Gateway and Python Lambda. An application-owned,
invitation-only Cognito User Pool performs managed login and MFA. A serverless
BFF uses Authorization Code with PKCE, maps verified `(issuer, subject)` claims
to an immutable application actor, and gives the browser only an opaque
`Secure`, `HttpOnly`, `SameSite` session cookie. The user never types a reviewer
ID, employee code, token, or attribution value.

**Authorization flow:** A Lambda authorizer validates the hashed session,
expiry, and revocation held in DynamoDB and supplies canonical actor context.
Authentication is not sufficient authorization: application services and SQL
queries enforce role, team, assignment, object, value, purpose, and four-eyes
rules before search, pagination, evidence access, or a decision. Mutation
payloads contain the decision, mandatory rationale, expected aggregate version,
idempotency command ID, and CSRF proof; reviewer identity always comes from the
verified session.

CloudFront overwrites a rotated origin-verification header and API authorization
rejects direct-origin requests without it; the API Gateway default endpoint is
disabled. Aurora, not Cognito or DynamoDB, owns actor identity links, roles,
teams, assignments, limits, and their administrative history. Role changes
invalidate sessions issued under the older authorization version.

**Traceability flow:** Aurora PostgreSQL Serverless v2 through RDS Proxy is the
authoritative ledger. One SQL transaction checks state and authorization and
commits the aggregate change, immutable decision or processing record,
append-only business event, and transactional-outbox row. The reviewer can see
that committed event immediately. An idempotent dispatcher later exports the
outbox to queues and an approved versioned audit bucket; CloudTrail,
CloudWatch, and distributed traces corroborate operations but do not replace
the application's business record or human rationale.

Original evidence is stored in private, versioned S3. SQL binds each attachment
ID to the exact S3 version and checksum used by a processing run. SQS/Lambda
workers are idempotent because delivery may repeat; retries and reprocessing
append distinct run/invocation records instead of overwriting history. Normal
reviewers receive a sanitized, cursor-paginated business timeline. Technical
OCR/model trace, cross-case audit, and original-file access are separate
authorized capabilities, and every file access grant records its actor,
purpose, attachment version, outcome, and correlation context.

**Current implementation boundary:** This is accepted production architecture,
not deployed infrastructure. The repository still runs FastAPI/Uvicorn with
HTTP Basic and file-backed SQLite. It has no Lambda adapter, infrastructure as
code, Cognito/BFF/session implementation, Aurora repository, RDS Proxy, S3
object adapter, SQS worker, transactional-outbox exporter, or immutable archive.
Those replacements must be implemented and tested before the service can be
described as AWS-ready or production-ready.

**Open governance inputs:** AWS account/region and data residency, user
invitation/bootstrap ownership, MFA and recovery policy, roles and separation
of duties, session/revocation SLOs, RPO/RTO, retention/legal hold, evidence-read
audit strength, peak load, and production latency targets remain subject to
accountable approval and representative tests.

**Affected records:** D-026, D-027, D-035, D-039, D-040, and A-043 through
A-046.

## 2026-08-10 - J-019 - Live local demonstration

**Question:** Is there a way to see the system working now?

**Result:** Started the implemented assessment slice against a disposable
SQLite database containing two fictional pending-review fixtures. Verified the
reviewer dashboard in the in-app browser, including authenticated reviewer
identity, queue summary, two result rows, bounded page controls, one selected
case, claimed-versus-extracted comparison, detected problem, raw OCR evidence,
normalized facts, deterministic rule evidence, and the one-event business
timeline. The browser console contained no warnings or errors during the final
read-only verification.

**Demonstration boundary:** This demonstrates the local FastAPI/SQLite reviewer
slice, not the accepted AWS infrastructure. Cognito/BFF login, Lambda/API
Gateway, Aurora, S3 evidence bytes, SQS workers, and immutable export remain
unimplemented. The original attachment is therefore still a reference rather
than a downloadable object.

**Temporary access accommodation:** The embedded browser did not reuse the HTTP
Basic navigation credential for same-origin `fetch` calls. A localhost-only
temporary gateway on port 8001 supplies fictional demo credentials to the
unchanged service on port 8000. It exists under `/private/tmp`, exposes only the
disposable fictional database on `127.0.0.1`, and is not source code,
production authentication, or evidence of the Cognito flow.

**Affected records:** No architecture decision changed. This entry is runtime
demonstration evidence for the implemented boundary described by D-020, D-033,
D-034, D-037, and D-038.

## 2026-08-10 - J-020 - Kubernetes provisioning alternative

**Question:** Can the service be provisioned on Kubernetes?

**Analysis:** Technically yes. FastAPI/BFF and processing workers can run as
containers on an application-owned Amazon EKS cluster. CloudFront/private S3,
Cognito, DynamoDB sessions, SQS, versioned evidence S3, Aurora, the
transactional outbox, and the immutable audit archive remain managed AWS
services outside the cluster. Kubernetes changes the compute and operational
boundary; it does not replace application authorization or the financial
ledger.

A full alternative routes `/auth/*` and `/api/*` from CloudFront/WAF through an
ALB/Ingress to replicated API/BFF pods. SQS workers run as separate Deployments
or Jobs and scale from queue depth/age. EKS Auto Mode is the preferred full-EKS
shape if Kubernetes becomes mandatory because AWS manages more node,
networking, load-balancing, DNS, storage, scaling, and patching work. EKS on
Fargate can host lightweight pods but has material limitations for GPU,
DaemonSets, Spot, privileged containers, and EBS. A worker-only EKS pool is a
lower-risk path for future local models, GPU, or tasks outside Lambda's runtime
boundary.

**Cost and operations:** Every standard-support EKS cluster has a fixed
control-plane charge before compute. Production also needs ALB, EC2/Auto Mode
or Fargate capacity, networking, image registry, logging, upgrades,
autoscaling, policy enforcement, incident response, and on-call ownership.
Millions of monthly cases do not establish steady utilization; peak rate,
duration, memory/GPU demand, and SLOs determine whether warm pods are worth
that fixed surface.

**Current direction:** This was a feasibility question, not an explicit change
of deployment decision. D-026 remains the accepted production target. EKS is
an evaluated alternative only. Reconsider first for a measured long-running or
GPU worker; reconsider a full migration only with explicit platform ownership
and total-cost/load evidence.

**Traceability boundary:** EKS audit/control-plane and container logs remain
operational evidence. Human decisions, policy results, state changes, events,
outbox rows, attachment versions/checksums, and processing attempts continue in
the application-owned Aurora/S3 audit chain. No authoritative state belongs on
a pod filesystem.

**Current implementation boundary:** The executable remains local
FastAPI/Uvicorn, HTTP Basic, and SQLite. No container image or Kubernetes
deployment artifact exists.

**Affected records:** D-026, D-039, D-040, D-041, A-043, and A-047.

## 2026-08-10 - J-021 - Serverless architecture reaffirmed

**Question:** After evaluating Kubernetes, should the project keep the prior
architecture?

**Decision:** Yes. The user explicitly chose to retain the accepted AWS hybrid
serverless target. D-041 is closed as an evaluated but unselected alternative,
and D-042 reaffirms D-026. No Kubernetes deployment artifact will be added
without a later explicit scope change.

**Consequence:** This is an architecture decision, not a claim that AWS has
already been provisioned. The current executable remains the local assessment
adapter, and the cloud topology remains a documented production target.

## 2026-08-10 - J-022 - Completion audit and remaining user inputs

**Question:** What is still required from the user to finish the project?

**Scope assumption:** “Finish” means complete the Python GitHub assessment
deliverable described by the assignment, not provision a production AWS
environment. See A-048.

**Audit result:** The human-review slice is implemented, but the end-to-end
assignment service is not. Remaining engineering work is intake, an executable
and traceable extraction adapter, the deterministic baseline policy, persistence
and audit for automated approval/rejection as well as review routing, result
lookup, acceptance tests over the supplied sample dataset, and conversion of the
report outline into the final written report. These are implementation tasks and
do not require RecargaPay infrastructure information.

**Inputs required from the user before final delivery:** Provide an honest rough
time-investment estimate and choose the GitHub repository destination/visibility
or elect to push the prepared repository personally. A provider/model choice and
locally configured secret are required only if the final demonstration must make
a live external LLM call; deterministic fakes can keep tests reproducible and no
secret belongs in the repository or conversation.

**Defaults that can unblock implementation:** Use BRL, timezone-aware ISO 8601
submission timestamps, `DD/MM/YYYY` receipt dates from the supplied OCR text,
`America/Sao_Paulo` for calendar interpretation, exactly 90 days as valid,
BRL 200 as inclusive, BRL 200.01 through BRL 2,000 as human review, mandatory
rejection before routing when a receipt is older than 90 days, one configurable
primary extractor, and an optional secondary verifier disabled by default. Each
default remains explicit and testable rather than being hidden in code.

**Not blockers for the assessment:** AWS account/region/DNS, Cognito production
policies, retention/legal hold, RPO/RTO, VPN, real employee data, a production
SLO, two LLMs, and production-scale load evidence remain deployment or governance
inputs rather than prerequisites for completing the repository.

**Affected records:** D-012, D-013, D-026, D-041, D-042, A-004 through A-012,
A-043, A-047, A-048, the final-report outline, and the time log.

## 2026-08-10 - J-023 - End-to-end assessment completion

**Question:** Could the missing assignment path be completed without inventing
RecargaPay infrastructure, live-provider credentials, or artificial work/commit
timestamps?

**Decision:** Yes. Treat D-042's AWS topology as the accepted but unimplemented
production target and finish the code-assessment path locally. Keep commits
small and aligned with real milestones—policy, extractor adapters,
acceptance/CI, workflow persistence, and HTTP APIs—without backdating commits or
delaying them to simulate elapsed work.

**Implementation result:** The repository now contains:

- `BaselinePolicy` with exact BRL thresholds, `America/Sao_Paulo` receipt age,
  exactly-90-day acceptance, old-receipt reject precedence, mismatch/uncertainty
  review, and complete reason/rule evidence;
- an offline deterministic extractor composed by default and an optional
  bounded HTTPS+JSON adapter with no committed provider secret;
- synchronous `ProcessingService` orchestration around short durable
  transactions, received v1 → processing v2 → automated final v3, and existing
  human pending v3 → final v4 behavior;
- canonical submission fingerprints, safe replay versus divergent-ID conflict,
  processing runs, immutable 1:N invocation attempts, protected raw output, and
  business/technical/security event scopes;
- strict authenticated/CSRF/same-origin `POST /api/requests` and safe exact-ID
  all-status `GET /api/requests/{request_id}`;
- follow-up hardening that rejects provider redirects, unsafe large JSON floats,
  duplicate canonical reviewer IDs, and mutation of derived minor units even
  when upgrading a database with the older trigger definition;
  separates the verified `authenticated_caller` actor from claimed
  `submitted_by`; and makes legacy backfill atomic;
- the exact three assignment samples, boundary/integration/security/rollback
  tests, pinned CI/build backends, pip/Actions Dependabot coverage, local run
  instructions, and a final report.

**Validation:** The final local run passed 140/140 automated tests with warnings
treated as errors, Ruff, JavaScript syntax validation, and `git diff --check`.
Acceptance results are `REQ-0001` and `REQ-0002` auto-approved and `REQ-0003`
routed to human review. Real FastAPI-to-SQLite tests prove creation, replay,
conflict, all-status lookup, trace protection, and pending v3 to human v4.

**Release-gate finding:** Completing the assessment exposed blockers for real
monetary use, not optional backlog: caller-controlled `submitted_at` currently
anchors receipt age; caller-controlled `raw_ocr_text` can drive policy without
application-owned bytes/checksum/trusted OCR; every Basic account has global
scope without owner/role/case authorization or separation of duties; audit does
not cover authentication, reads, searches, validation/orchestration errors, or
evidence access comprehensively; and a crash can strand v2/running state without
recovery. The assessment follows the supplied object contract, but production
must close these gates before financial activation.

**Policy-validation finding:** Old-receipt reject precedence over a simultaneous
high-value review outcome, as well as the literal BRL 2,000 boundary treatment,
is a tested assessment interpretation. It has not been confirmed by a policy
owner and remains open for stakeholder validation.

**Remaining boundary:** Receipt-byte upload/access, submitter/audit UIs,
asynchronous queue/recovery, PostgreSQL/outbox, managed identity/authorization,
immutable external audit export, cloud IaC/deployment, accuracy/load/security/
recovery evidence, and approved retention remain absent. This is honest scope,
not a claim of production readiness.

**Timing:** The continuously recorded final implementation and documentation
block started at `2026-08-10T19:47:09Z`; its exact finish and duration are
recorded in `docs/time-log.md`. Earlier work remains untimed rather than assigned
fabricated durations.

**Affected records:** D-043 through D-047, A-004 through A-012, A-040 through
A-042, A-048 through A-053, the executable README, system documentation, final
report, and time log.

## 2026-08-11 - J-024 - Reported effort and diagram/deployment follow-up

**Status:** Superseded by J-025 for the deployment artifact. This entry records
the implementation boundary before the sandbox was built.

**Question:** How should the user's approximately 10-hour estimate and request
for diagrams and deployment follow-up be recorded without overstating measured
time or implying an AWS implementation decision?

**User input:** The user reports approximately 10 hours total across the
project and requested a central view of the diagrams together with deployment
and sandbox follow-up.

**Recording decision:** Treat approximately 10 hours as a rough, user-reported
total. The exactly measured `40m 29s` completion block is contained within that
estimate and must not be added again. Historical activities remain individually
unmeasured rather than receiving reconstructed durations.

**Documentation action at that point:** Add a central, English diagram gallery
that consolidates the implemented assessment, lifecycle, summarized data model,
processing sequence, review/audit flow, and the already accepted AWS production
target. The sandbox was still represented as a clearly labeled `pending
implementation` delivery placeholder; J-025 records its later implementation.

**Deployment boundary at that point:** This record did not choose an AWS account, region,
network, infrastructure-as-code tool, credentials, identity configuration,
database capacity, buckets, queues, DNS, or sandbox implementation. It does not
authorize cloud mutations. A later implementation step requires explicit scope,
authority, prerequisites, and review. D-026 and D-042 remain unchanged.

**Affected records:** A-054, `docs/time-log.md`, `docs/final-report.md`,
`docs/diagrams.md`, and the documentation indexes.

## 2026-08-11 - J-025 - Plug-and-play AWS assessment sandbox

**Question:** After reaffirming the AWS serverless direction, can the current
repository be made easy to run on Amazon without presenting SQLite/Basic as the
financial-production architecture?

**User direction:** Record approximately 10 hours as the rough project total,
provide AWS installation instructions, make the result as plug and play as
possible, and include the remaining diagrams.

**Options examined:** A faithful single EC2/EBS sandbox would keep SQLite on
local block storage but would diverge from the selected serverless direction
and require a separate safe HTTPS termination design. App Runner is unsuitable
for durable SQLite; Fargate/EFS repeats the network-filesystem issue. A direct
HTTP API/Lambda/EFS package follows the requested runtime shape and gets an AWS
managed HTTPS endpoint, but SQLite over NFS is not an acceptable authoritative
ledger. The full CloudFront/Cognito/S3/SQS/Aurora target cannot be produced by
IaC alone because the corresponding application adapters are intentionally
missing.

**Decision:** Add AWS SAM only as an explicit synthetic-data assessment
sandbox. Keep D-026/D-039/D-040/D-042 as the production target. Do not provision
an AWS account from this task and do not claim production readiness. The
sandbox uses API Gateway HTTP API, Python 3.12 Lambda through Mangum, a new
private VPC with two subnets, encrypted/backed-up/retained EFS, rollback journal
`DELETE`, bounded concurrency four, 14-day sanitized logs, X-Ray, and
error/throttle alarms. HTTP Basic/PBKDF2 and application CSRF/Origin checks stay
inside the assessment.

**Automation:** `deploy/aws/deploy.sh` checks prerequisites and AWS identity,
prompts before billable resources, reads a password without echo, sends only its
PBKDF2 hash to NoEcho CloudFormation parameters, generates the CSRF secret,
prepares a minimal pinned build context, runs SAM lint/build/deploy, reads the
stack URL, and seeds the three public assignment objects through the HTTPS API.
EFS is retained on stack deletion so cleanup cannot silently destroy the SQLite
evidence; the runbook calls out continuing charges and manual authorization.

**Validation finding:** A direct container smoke exposed that the AWS Lambda
Python 3.11 base carried SQLite too old for the partial index in the schema. The
package moved to Lambda Python 3.12/SQLite 3.40, and SAM's custom image path was
replaced with a reproducible x86_64 ZIP built in the official Python 3.12 build
container. The final evidence is 151 tests with warnings as errors, Ruff,
JavaScript syntax, diff checks, ShellCheck, SAM lint, a successful x86_64 SAM
build, and import/schema initialization inside the matching Lambda runtime.
No live stack test or EFS recovery test was run, and no AWS resource was
provisioned.

**Production consequence:** `DELETE` journal avoids the direct WAL limitation
but does not make SQLite over EFS/NFS safe. Four concurrent environments exist
only to let current browser asset/detail requests function; it is not a scale
claim. Real monetary or receipt data remains forbidden until Aurora/outbox,
Cognito/BFF and authorization, S3 evidence, SQS/DLQ workers, CloudFront/WAF,
complete audit, retention, load, security, backup, and recovery gates are built
and approved.

**Affected records:** D-048, A-043, A-048, A-054, A-055, the AWS runbook and SAM
assets, architecture/features/database documents, central diagram gallery,
final report, README, and time log. Implementation commits are `8d45af3` and
`2246ff0`.

## Entry template

```text
## YYYY-MM-DD - J-NNN - Topic

Question:
Context and alternatives:
Decision or current direction:
Rationale:
Consequences and trade-offs:
Evidence or affected files:
Open follow-up:
```
