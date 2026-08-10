# Expense Agent

Expense Agent is an auditable Python service for corporate reimbursement
decisions. The implemented assessment slice provides a non-technical internal
review console: FastAPI serves one HTML/CSS/vanilla-JavaScript screen, the
browser calls authenticated same-origin JSON endpoints, and SQLite records the
human decision, case transition, and audit event atomically.

Financial state transitions remain deterministic and isolated from the web and
database adapters. OCR/LLM objects preserve evidence and invocation metadata,
but no model is the authority for a monetary decision.

## What is implemented

- Exact BRL money through `Decimal` and a protected `ReimbursementCase` state
  machine.
- A bounded pending-review queue with server-side search, filters, five stable
  sort modes, 10–100 item cursor pages, KPI overview, table/cards, and a focused
  evidence view; attachment content access remains a documented gap.
- A trilingual reviewer interface (`pt-BR`, English, and Spanish) that localizes
  presentation while preserving original OCR and free-text evidence.
- A separate sanitized business timeline with chronological keyset pagination,
  actor/correlation metadata, and explicit loading, error, empty, retry, and
  load-more states. Its current coverage is enqueue and human decision only.
- Approve/reject actions with a mandatory rationale and server-derived reviewer
  identity.
- Optimistic concurrency through `ETag`/`If-Match`, plus a serialized SQLite
  transaction for the final write.
- Immutable human decisions and append-only audit events enforced by database
  triggers.
- Assessment authentication with HTTP Basic and PBKDF2 password hashes, CSRF
  defense, same-origin enforcement, restrictive browser headers, and production
  HTTPS enforcement.
- Demo fixtures, password-hash tooling, and automated tests.

The intake API, OCR/provider adapter, and baseline policy engine are not yet
implemented. Demo cases enter the system after the automated decision has
already routed them to human review. See the [documentation index](docs/README.md)
for the exact implemented/partial/production boundary.

The accepted production target is a standalone AWS hybrid serverless stack:
CloudFront/WAF and private S3 for the shell, API Gateway and Python Lambda for
the service, Cognito plus a server-side opaque session for identity, SQS for
asynchronous work, versioned S3 for evidence, and Aurora PostgreSQL Serverless
v2 through RDS Proxy for authoritative state, audit, and transactional outbox.
That cloud target is documented but not implemented or deployed; HTTP Basic
and SQLite remain the executable assessment adapters.

## Local demonstration

Requires Python 3.11 or newer and `uv`.

```bash
uv sync --all-groups
uv run expense-agent-hash-password
```

Copy `.env.example` to a local, ignored `.env`, replace the reviewer hash and
CSRF secret, and use these local-only values:

```text
EXPENSE_AGENT_REQUIRE_HTTPS=false
EXPENSE_AGENT_ALLOWED_HOSTS=localhost,127.0.0.1
EXPENSE_AGENT_HOST=127.0.0.1
EXPENSE_AGENT_PORT=8000
```

The application deliberately does not load `.env` files itself. Export the
variables with your shell or process manager, then seed and run it:

```bash
uv run expense-agent-seed-demo
uv run expense-agent-review
```

Open `http://127.0.0.1:8000/reviews`. The browser displays its native HTTP Basic
credential prompt; enter the `username` and the plaintext password whose hash
you placed in `EXPENSE_AGENT_REVIEWERS_JSON`. There is deliberately no default
usable password. After verification, the server derives the canonical reviewer
ID, email, and display name; the user never types an internal reviewer ID.
Plain HTTP is only for this local flow. Production must keep
`EXPENSE_AGENT_REQUIRE_HTTPS=true` behind a correctly configured trusted TLS
ingress.

## Verification

```bash
uv run pytest
uv run ruff check src tests
uv build
```

The latest recorded verification completed 60 automated tests, Ruff, and
JavaScript syntax validation. Coverage includes the authenticated and sanitized
business-timeline endpoint, signed event cursors, pagination without duplicate
events, and the decision-to-timeline integration. The prior browser flow covered
three locales, filters, table/cards/detail modes, a 10 + 6 item queue traversal
without overlap, and an auditable `201 Created` decision with no console errors.
Packaging also produced both sdist and wheel; the wheel contains the
HTML/CSS/JavaScript assets and all three command-line entry points.
