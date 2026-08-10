# Final design report outline

This is the evidence-backed structure for the assignment report. It preserves
the reasoning path, including rejected alternatives, while describing only the
current internal review console as active architecture. The option 2 interface
completes the Human Review slice; it does not complete the assignment's entire
intake, extraction, and automated-policy service.

## 1. Executive summary

State the outcome first:

- Expense Agent keeps probabilistic extraction separate from deterministic
  monetary decisions.
- The implemented assessment slice is an internal, non-technical human-review
  console served by FastAPI with plain HTML/CSS/JavaScript.
- SQLite is the system of record for review evidence, authenticated human
  decisions, workflow state, and append-only review-lifecycle audit.
- The accepted, not-yet-implemented production target uses one CloudFront/WAF
  origin, private S3, API Gateway/Python Lambda, Cognito with an opaque BFF
  session, SQS, and Aurora PostgreSQL Serverless v2 with a transactional outbox.
- Employee intake, live OCR/LLM integration, and the required deterministic
  baseline policy remain outside the implemented slice.

Key evidence: 60 tests, a passing Ruff check, JavaScript syntax validation, and
prior browser validation covering three locales, filters, table/cards/detail
views, 10 + 6 item queue cursor pages without overlap, and an auditable
`201 Created` decision with no console errors. The new timeline is covered by
automated API, persistence, security, pagination, and static-UI tests rather
than a new manual browser run.

## 2. Requirements interpretation and compliance matrix

Explain how the solution interprets mission-critical financial correctness,
human judgment, mandatory reasoning, and traceability. Include this honest
matrix rather than claiming full assignment compliance:

| Assignment requirement | Current status | Evidence or missing work |
| --- | --- | --- |
| Receive and process reimbursement requests | Not implemented | No intake endpoint or processing orchestrator. Demo/helper code accepts an already-built pending case. |
| Extract/validate receipt evidence with AI/OCR | Partial contract | Extraction objects and full invocation trace are modeled and persisted; no provider adapter or evaluation is implemented. |
| Auto-approve eligible requests at or below BRL 200 when checks pass | Planned | Domain supports `auto_approved`; the baseline rule executor is absent. |
| Always route requests above BRL 2,000 to human review | Planned | Domain supports `pending_review`; no amount policy is executed. |
| Reject receipts older than 90 days | Planned | The required rule and its precedence against the high-value gate remain unimplemented. |
| Classify every request and explain the result | Partial | Decision/reason/rule objects and persistence exist for supplied cases; there is no end-to-end classifier. |
| Make judgment cases available to humans and record their decision | Implemented slice | Authenticated queue/UI, evidence view, rationale, immutable decision, and final state. |
| Full traceability and reproducibility | Partial | Enqueue and human-decision events plus extraction/automatic-decision evidence are persisted, and the two events are available through a sanitized reviewer timeline. The authoritative intake/provider/policy pipeline, complete event coverage, 1:N technical trace, evidence-access audit, and immutable original-file path are absent. |

Discuss the threshold/age precedence ambiguity rather than choosing silently.
Source: [project journal](project-journal.md) and
[assumptions register](assumptions.md).

## 3. Scope and implementation status

Use a clear implemented/partial/not-implemented table:

| Implemented | Partial or assessment-only | Not implemented |
| --- | --- | --- |
| Domain state machine and exact money | Structured extraction contract and persisted trace | Submission intake |
| Review queue, evidence view, decision, and sanitized two-event timeline | Limited review-lifecycle event coverage | Live OCR/LLM adapter |
| Atomic SQLite review persistence | HTTP Basic + PBKDF2 identity adapter | Baseline policy rules |
| Same-origin web screen and security guards | Opaque attachment locations only | Attachment content access |
| ETag concurrency and immutable audit/decision triggers | SQLite single-instance deployment | Standalone managed identity and HA data platform |

Avoid implying that demo fixtures are a production ingestion pipeline.

## 4. Architecture

Cover:

- ports-and-adapters boundaries and inward dependencies;
- static browser screen, FastAPI routes, `ReviewService`, domain aggregate, and
  `SqliteReviewRepository`;
- same-origin `fetch` calls as ordinary authenticated HTTP, not webhooks;
- the trusted HTTPS ingress and production identity replacement boundary;
- the accepted AWS target: private S3 shell, CloudFront/WAF, API Gateway and
  Python Lambda, Cognito/BFF session, SQS workers, versioned evidence S3, and
  Aurora/RDS Proxy authoritative persistence;
- why framework-free same-origin assets remain appropriate for the first
  standalone console while the presentation boundary stays replaceable;
- the standalone submitter, reviewer, and audit/administration surfaces, with
  an honest implemented-versus-planned boundary;
- server-side indexed queue discovery, keyset pagination, maintained summary
  metrics, and table/card/focus views designed for high-cardinality operation;
  million-case latency remains a load-test acceptance criterion, not a proven
  result;
- trilingual presentation with stable language-neutral business/audit codes.

Source: [architecture](architecture.md).

## 5. Domain and application model

Explain:

- `ReimbursementCase` as aggregate root and its state machine;
- `Money` with exact `Decimal` BRL values and timezone-aware timestamps;
- `ExtractionResult`, `ReceiptFacts`, and `ModelInvocationTrace`;
- explained `AutomatedDecision` and versioned `RuleEvaluation` values;
- `ReviewerIdentity` from authentication, immutable `HumanDecision`, and
  `AuditEvent`;
- queue/detail read models, sanitized business-event page/query models, and the
  `ReviewRepository` port.

Source: [domain model](domain-model.md).

## 6. Reviewer workflow

Describe the user-facing sequence:

1. Reviewer authenticates and opens `/reviews`.
2. The page gets canonical identity and a reviewer-bound CSRF token.
3. The page sends a bounded query with search, filters, sort, page size, and an
   optional opaque cursor; the default order prioritizes the oldest cases. The
   query runs against the complete pending scope in the database, not only the
   visible page.
4. Selecting a case loads claim data, raw OCR, structured facts, detected
   problems, policy evidence, and attachment locations. An independent bounded
   request loads the sanitized enqueue/decision business timeline without
   blocking the evidence read. State honestly that the current screen does not
   show the protected technical trace or original bytes and that completed-case
   navigation is still absent.
5. Reviewer enters a mandatory rationale and confirms approve/reject.
6. The API verifies same origin, CSRF, content type, and current ETag.
7. One database transaction records identity/outcome/reason/time, changes state,
   increments version, and appends the audit event.
8. The UI displays the audit event, keeps the completed case open, reloads its
   timeline, hides the decision controls, and refreshes the pending queue.

Then describe the accepted completion target: a separate exact-ID/all-status
request explorer and audit search; a selected-case view divided into reviewer
evidence, sanitized business timeline, and separately authorized technical
trace; and on-demand access to a safe preview or exact immutable original. Do
not present numeric page jumps over high offsets as the way to find a request.

Source: [feature flows](features.md).

## 7. Persistence and auditability

Cover the 12-table physical schema and emphasize:

- normalized evidence, decision reasons, and rule evaluations;
- full raw model response retained in protected persistence but omitted from
  the browser response;
- the present one-row-per-request invocation trace as a known limitation, with
  the accepted but unimplemented immutable 1:N run/stage/attempt model for OCR,
  model calls, retries, and reprocessing;
- the accepted but unimplemented checksum chain from exact attachment object
  version through a canonical processing-input manifest and invocation
  input/output hashes;
- exact decimal strings, UTC timestamps, and canonical JSON;
- atomic pending-case ingestion plus `review_case_enqueued`;
- atomic reviewer decision plus `human_review_decided`;
- propagated correlation IDs (the demo/helper alone provides a derived
  fallback when its caller omits one);
- `BEGIN IMMEDIATE`, WAL, `synchronous=FULL`, foreign keys, busy timeout,
  field checks, and version/state rechecks;
- triggers that reject update/delete of `human_decisions` and `audit_events`;
- rollback evidence for a late audit insertion failure.

Source: [database model](database.md).

## 8. Concurrency and idempotency

Explain the layered behavior:

- GET returns an ETag derived from request identity and version.
- Missing `If-Match` produces `428`; a stale ETag produces `412`.
- SQLite serializes the writer and rechecks pending state and version.
- A race, repeated action, or unique-record collision produces `409`.
- The decision, state update, review completion, and audit event either all
  commit or all roll back.

Do not claim distributed idempotency beyond the implemented repository.

## 9. Security and privacy

Separate implemented controls from production replacements.

Implemented assessment controls:

- HTTPS requirement flag and HSTS on HTTPS responses;
- explicit trusted hosts and configured trusted proxy IP/CIDR;
- salted PBKDF2-SHA256 reviewer passwords and constant-time comparison;
- canonical reviewer identity established server-side;
- same-origin validation, `Sec-Fetch-Site`, HMAC CSRF, and strict JSON DTO;
- CSP, `no-store`, anti-framing, `nosniff`, restricted referrer and permissions;
- safe DOM text creation and no sensitive local/session storage;
- raw model response withheld from the reviewer API;
- database checks for non-blank reviewer/audit identity fields and a rationale
  of 1–2,000 trimmed characters.

Production replacements/work:

- application-owned managed OIDC, roles/groups, authorization, provisioning,
  recovery, session revocation, deprovisioning, and access reviews;
- approved TLS ingress, secret manager, rotation, and security testing;
- data classification, field-level redaction, retention, legal hold, and read
  auditing;
- an authorized attachment-content path with object-level access checks;
- safe derivative preview versus original download, malware fail-closed state,
  object version/checksum pinning, and a distinct append-only access audit.

## 10. AI/OCR strategy

Explain why model agreement is not equivalent to correctness:

- multiple models can inherit the same OCR error;
- two providers increase inference cost, slower-provider tail latency, rate-
  limit and outage surfaces, privacy exposure, vendor governance, and audit
  volume;
- deterministic policy, not an LLM, remains financial authority;
- a secondary verifier should be accepted only after a labeled evaluation
  shows a favorable accuracy/cost/latency trade-off, potentially for high-risk
  auto-approval candidates or a monitoring sample.

The live provider choice remains open; do not fabricate price or accuracy data.

## 11. Testing and evidence

Summarize the 60 tests by risk rather than listing filenames:

- domain precision and invalid transitions;
- extraction and explainability contracts;
- review application identity and stale-state behavior;
- database round trip, correlation propagation, enqueue audit, atomic decision,
  rollback, conflicts, durability PRAGMAs, constraints, and immutability
  triggers;
- password hashing, authentication, CSRF identity binding and expiry;
- strict startup settings, HTTPS defaults, host/proxy validation, and no
  wildcard trust;
- HTTP authentication, headers, HTTPS, origins, content type, preconditions,
  server-derived identity, and safe response projection;
- queue filters, stable sorts, exact money, keyset traversal, cursor signing,
  query binding, snapshot behavior, migration/backfill, and index use;
- timeline authentication and sanitization, chronological tie-breaking,
  purpose/query-bound restart-safe cursors, pagination, decision integration,
  and frontend state/i18n/whitelist wiring;
- browser JavaScript safe-DOM/no-storage assertions, translation-catalog parity,
  bounded discovery controls, distinct states, and absence of dead navigation.

Record the manual browser evidence: PT-BR/English/Spanish switching, working
category filtering, table/cards/detail modes, cursor pages `10 + 6` with no
overlap, decision response `201`, refreshed queue/KPIs, audit toast, and no
console errors. Include the exact verification commands:

```bash
uv run pytest
uv run ruff check src tests
uv build
```

Also record that the build produced sdist and wheel, and that the wheel contains
the three static UI assets plus the three CLI entry points.

## 12. Alternatives and trade-offs

Preserve the decision path honestly:

- **ClickUp/CRM as the review core — rejected and removed.** It could present
  cards, but authoritative decisions in a third-party SaaS weaken control over
  identity, rationale, transactionality, retention, and audit continuity.
- **Email/chat replies as decisions — rejected.** They are notification media,
  not the financial system of record.
- **API-only reviewer flow — rejected.** Expected users are non-programmers; an
  API without its invoking client does not make review usable.
- **React/Next.js — deferred.** It adds a separate runtime/build/deployment
  trade-off without evidence that one simple screen requires it.
- **Plain same-origin HTML/JavaScript — accepted.** Small operational footprint,
  safe text rendering, and replaceable presentation boundary.
- **HTTP Basic — assessment only.** Small demonstrable identity adapter, but
  inferior to application-owned managed OIDC for production lifecycle and UX.
- **SQLite — accepted for the assessment.** Supports a rigorous local
  transaction; production HA and concurrency needs require datastore review.
- **Two LLMs on every request — open/not justified.** Requires empirical
  accuracy, latency, cost, and privacy evidence.
- **n8n as the application runtime — technically viable but rejected for the
  assessment.** A self-hosted workflow could invoke providers or a governed
  local model, but it would not remove the need for the reviewer UI,
  authentication, deterministic policy, authoritative persistence, atomic
  audit writes, concurrency control, and tests. It also adds workflow/runtime
  governance while the assignment explicitly requests Python. Retain n8n only
  as a possible future peripheral integration orchestrator, never as the
  financial system of record.
- **One Linux VPS with local receipt storage — rejected for production.** It is
  a single failure and scaling domain and makes file replication, backup, and
  failover application concerns.
- **S3 plus relational metadata — accepted production target, not implemented.** Object
  storage owns original and derived bytes; PostgreSQL preserves attachment
  identity, checksums, versions, relationships, financial state, and atomic
  audit transitions.
- **Lambda versus Fargate/EC2 — accepted hybrid target.** Lambda handles short and
  bursty API/orchestration work; SQS applies backpressure; long or specialized
  workers may move to Fargate, SageMaker, or EC2 after measurement.
- **Amazon EKS/Kubernetes — evaluated and not selected.** The feasibility study
  showed that the BFF/API and workers could run as containers while durable
  services remained managed, but D-042 explicitly reaffirmed the AWS hybrid
  serverless target. Kubernetes remains historical trade-off evidence rather
  than current implementation or roadmap scope.
- **VPN — conditional, not a default.** OIDC/SSO, MFA, application authorization,
  HTTPS, and private data stores remain mandatory. VPN is added only for a
  confirmed private-network or on-premises connectivity requirement.
- **Serverless identity — accepted target and automatic.** Use an
  application-owned Cognito User Pool with Authorization Code + PKCE through a
  BFF. Derive the reviewer from stable `(issuer, subject)` claims, keep provider
  tokens server-side, and give the browser only an opaque HttpOnly session
  cookie. The user authenticates or completes MFA but never types an identity
  code into the decision form.
- **Business audit versus infrastructure audit.** The atomic PostgreSQL
  decision/status/audit/outbox transaction is authoritative for who decided
  what and why. CloudTrail and an immutable S3 export add forensic evidence but
  cannot replace the decision rationale and domain state transition.
- **Standalone user experiences, one workflow.** Expense Agent owns the
  submitter upload/tracking portal, reviewer operations console, and controlled
  audit/administration surface. Receipt evidence, OCR, normalized facts, rules,
  reviewer identity, and decision controls remain role-restricted.

Sources: [decision log](decision-log.md) and the
[AWS deployment and cost study](aws-deployment-study.md).

## 13. Known limitations and production roadmap

Prioritize rather than overpromise:

1. Confirm policy ambiguities and implement the required deterministic baseline
   (`<= BRL 200` eligible auto-approval when checks pass, `> BRL 2,000` human
   review, receipts older than 90 days rejected) with boundary/precedence tests.
2. Add intake, authorized attachment access, OCR/extraction adapters, and a
   representative labeled evaluation dataset.
3. Implement the standalone managed identity and authorization boundary.
   Confirm provisioning, issuer, audience, stable subject, roles/groups, MFA,
   recovery, logout, revocation, deprovisioning, separation of duties, and the
   selected Cognito/BFF session-policy values.
4. Implement the accepted Aurora/S3 data platform with migrations, encryption,
   backups, recovery tests, retention, and audit export/search.
   Implement the accepted AWS serverless target after explicit product
   decisions set region, account/network layout, recovery, SLO, retention, and
   pricing constraints.
5. Add full-operation audit coverage, metrics, traces, alerts, provider timeout/
   retry policy, and operational runbooks.
6. Complete standalone submitter and audit/admin surfaces, reviewer assignment
   and escalation, large-cardinality load tests, translation review, and
   accessibility/usability testing with real users in all three languages.

## 14. Time invested

Use [the time log](time-log.md). Preserve `estimate required` where exact start
and finish times were not captured; do not create false precision. Group the
final total by discovery, domain, persistence/audit, human review, security,
testing, browser QA, and documentation.

## Appendices

### Appendix A — decision register

Include every accepted, superseded, proposed, and open decision with its status
and one-paragraph rationale. Preserve the evolution from the rejected external
review idea to the internal console.

### Appendix B — assumptions

Include each assumption and distinguish assessment constraints from standalone
product choices that still require measured load, security, privacy, retention,
recovery, and policy acceptance criteria.

### Appendix C — evidence checklist

- [ ] Test and lint output captured at the final commit.
- [ ] Browser validation result and environment recorded.
- [ ] Mermaid diagrams rendered without syntax errors.
- [ ] Active documentation matches implemented endpoints and schema.
- [ ] No secret, real receipt, reviewer password, or production identity data
  included.
- [ ] Known gaps labeled rather than implied complete.
