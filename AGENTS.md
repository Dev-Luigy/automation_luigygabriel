# Expense Agent working agreement

Read this file and `docs/decision-log.md` before every material implementation
or architecture action in this repository.

## Accepted product direction

- Human review is a first-class capability of Expense Agent and must not depend
  on an external task-management or messaging SaaS.
- The submitter and reviewer experiences use plain HTML, CSS, and vanilla
  JavaScript. The assessment serves those assets from the
  Python service; the accepted AWS target serves the same data-free shell from
  private S3 through CloudFront while Python Lambda owns the APIs. Do not add
  React, Next.js, or a separate frontend runtime unless new infrastructure
  facts make that trade-off demonstrably worthwhile.
- Browser JavaScript calls same-origin authenticated JSON endpoints with
  `fetch`. Do not describe these browser calls as webhooks. Webhooks are only
  outbound server-to-server notifications after an authoritative event.
- The authoritative human decision is recorded inside the application with the
  authenticated reviewer identity, outcome, mandatory rationale, timestamp,
  request version, and audit context.
- Reviewer identity comes from verified authentication context and never from
  a freely supplied request-body field.
- Bind four-eyes to the authenticated submission actor recorded in the
  immutable intake event, not only to claimed email. Enforce it inside the
  application service and fail closed when authorship cannot be verified.
- Revalidate every managed original immediately before a human decision.
  Approval requires `verified` evidence; missing, corrupt, invalid, or legacy
  evidence may only be rejected with a mandatory reason and audited integrity
  state.
- Persist the decision-command binding, human decision, reimbursement status
  transition, and audit event atomically. An identical retry replays the
  original result; divergent key reuse or a competing command conflicts.
- Production traffic is HTTPS. Local HTTP is permitted only for development and
  tests. Keep deployment-specific TLS termination explicit in documentation.
- Render all untrusted reimbursement/OCR values through safe text operations;
  never interpolate them as executable HTML.
- Keep financial decisions deterministic. Probabilistic models extract or
  verify evidence but are not the policy authority.
- Carry a validated immutable build ID and SHA-256 of effective configuration
  through processing, human decisions, timelines, and operational audit. Never
  persist configuration secrets merely to make the digest reproducible.
- Treat Expense Agent as a standalone product. It owns its submitter upload and
  tracking experience, internal reviewer operations console, and controlled
  audit/administration experience. Do not depend on an existing RecargaPay
  frontend, identity provider, database, task manager, or notification channel.
- Every collection intended for operational use must be searched, filtered,
  sorted, and cursor-paginated on the server. Never load an unbounded review
  queue into the browser. Keep financial approve/reject actions individual.
- Apply search to the complete authorized database result set, never only to
  the page already loaded in the browser. Keep the pending operational queue,
  an exact-ID/all-status request explorer, and audit search as distinct read
  experiences. Prefer stable keyset cursors to numbered offset page jumps.
- A selected case must ultimately expose its decision evidence, a sanitized
  business-event timeline, a separate protected technical trace, and
  authorized on-demand access to the exact original attachment version. Link
  that version and its checksum to the OCR/model input, and audit protected
  evidence access without exposing an internal object-storage location.
- Make the product interface available in Brazilian Portuguese, English, and
  Spanish. Keep API/status/reason codes language-neutral and preserve original
  OCR/model/human text for audit; translate presentation labels, not evidence.
- The accepted production deployment target is an application-owned AWS hybrid
  serverless stack: CloudFront/WAF and private S3 for the static shell, API
  Gateway and Python Lambda for short APIs/workers, SQS/DLQs for asynchronous
  backpressure, versioned private S3 for evidence, Aurora PostgreSQL Serverless
  v2 through RDS Proxy for authoritative financial state/audit/outbox, Cognito
  for standalone OIDC, and DynamoDB only for short-lived BFF sessions/OAuth
  transactions or measured disposable projections. This target is accepted but
  not implemented or deployed in the repository.
- Production browser authentication uses an application-owned Cognito flow and
  a serverless backend-for-frontend. The browser receives only an opaque
  `Secure`, `HttpOnly`, `SameSite` session cookie; Cognito tokens remain on the
  server side. A Lambda authorizer derives the actor from the session, while
  service/SQL authorization enforces roles, teams, assignments, value limits,
  purpose, and separation of duties before search or mutation.
- Keep the application business ledger authoritative in Aurora. Commit state,
  decision, audit event, and transactional outbox together; export committed
  events idempotently to an approved immutable S3 archive. CloudTrail,
  CloudWatch, and distributed traces are complementary infrastructure evidence,
  never replacements for the human rationale or deterministic policy record.

## Removed direction

- Do not add an active ClickUp or generic CRM integration. Historical notes may
  mention that this alternative was evaluated and rejected, but no runtime
  code, dependency, configuration, active architecture diagram, or feature may
  depend on it.
- Do not replace the Python service with n8n for the assessment. A self-hosted
  n8n workflow was considered technically viable for orchestration and for
  invoking a locally available model, but it is a rejected MVP alternative:
  the assignment calls for Python, and n8n would not remove the need for the
  internal reviewer UI, authenticated API, authoritative datastore, or atomic
  audit writes. Preserve it only in historical trade-off documentation unless
  new RecargaPay infrastructure evidence changes the decision.
- Do not assume that an existing RecargaPay application or corporate identity
  surface will host, authenticate, notify, or display this product. Historical
  notes may retain that rejected assumption only when clearly marked
  superseded.

## Current completeness boundary

- The implemented assessment executable covers a standalone trilingual
  upload/track portal, managed receipt evidence, authenticated request intake,
  deterministic receipt-text extraction, policy v3, all three automated routes,
  exact all-status lookup, the internal review queue, and an idempotent atomic
  approve/reject command.
- The default extractor is an offline deterministic parser for supplied OCR
  text. A bounded HTTPS/JSON provider is explicitly environment-selectable, but
  no live provider is configured and binary OCR bound to uploaded bytes remains
  outside the assessment.
- New public intake accepts only managed JPEG/PNG/PDF evidence. The local store
  preserves exact bytes and metadata in immutable envelopes and revalidates
  SHA-256/media on case-scoped authenticated reads. It has no malware scan,
  uploader ownership, S3 version, OCR binding, or retention workflow.
- Request-ID replay protects one request, not receipt reuse across request IDs.
  Cross-case duplicate detection remains an unimplemented production control;
  do not automatically reject equal bytes without approved merchant/date/
  amount/actor/window policy.
- The detail UI exposes a sanitized, cursor-paginated business timeline covering
  intake, processing start, automated routing, review enqueue, and human
  decision where applicable. Immutable 1:N processing attempts and separate
  technical/security events are persisted but deliberately have no normal
  reviewer API or UI. Every HTTP attempt is also appended to a separate
  privacy-bounded operational ledger. Cross-case audit search/export and a
  controlled audit/admin UI remain outside the implemented flow.
- Assessment roles, owner-only submitter result reads, and self-review denial
  are implemented. They do not replace managed identity lifecycle or
  team/tenant/assignment/value/purpose authorization in production.
- Expired processing leases recover on an identical retry and fence stale
  workers. There is no heartbeat, watchdog, retry cap, asynchronous queue/DLQ,
  or operator replay control.
- SQLite, HTTP Basic, and the direct API Gateway/Lambda/EFS deployment are
  assessment adapters. The repository includes a locally validated, still
  unprovisioned SAM sandbox; it is not the accepted production deployment and
  must use synthetic data only. SQLite on EFS/NFS remains unsafe for production
  even with rollback journal mode and bounded concurrency.
- The sandbox provisions one interactive admin and one distinct non-interactive
  seed actor. The admin can review seed cases but cannot review a request they
  submit; a multi-operator demo needs additional configured principals.
- The AWS hybrid serverless topology is the accepted production target, but its
  Aurora/outbox, Cognito/BFF authorization, S3 evidence, SQS/DLQ workers, and
  CloudFront/WAF adapters are not implemented or deployed. No AWS account was
  mutated while preparing the sandbox.
  `sa-east-1` remains a cost/data-residency assumption rather than a confirmed
  region. Do not select a retention duration, enable automated deletion, enable
  Object Lock Compliance mode, require a VPN, or claim a production SLO until
  the accountable product, security, privacy, finance, legal, and governance
  owners approve those boundaries.
- Cognito plus the BFF session pattern is the accepted production identity
  target, while HTTP Basic remains the executable assessment adapter. Cloud
  implementation still needs invitation/bootstrap rules, MFA and recovery,
  idle/absolute session limits, refresh/revocation/logout, RBAC/ABAC/four-eyes,
  auth/access audit, and security testing. DynamoDB TTL is cleanup only; every
  request must reject an expired or revoked session synchronously.
- Amazon EKS was evaluated and explicitly not selected for the current project;
  D-042 reaffirms the AWS hybrid serverless target and closes D-041 as a current
  option. Do not create Kubernetes artifacts, present the repository as
  Kubernetes-ready, or assume an existing RecargaPay cluster or platform team
  unless a later explicit decision reopens that scope.

## Engineering and documentation rules

- Keep domain, application, presentation, and infrastructure concerns separate.
- Use exact `Decimal` money and timezone-aware timestamps.
- Keep audit records append-only and decisions immutable.
- Update `docs/project-journal.md`, `docs/decision-log.md`,
  `docs/assumptions.md`, and `docs/time-log.md` when a material question,
  decision, assumption, trade-off, or implementation result changes.
- Keep deliverable documentation in English.
- Clearly label implemented, partial, proposed, and superseded behavior.
- Run tests and static checks after meaningful changes.
