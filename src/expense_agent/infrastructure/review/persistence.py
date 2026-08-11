"""Normalized SQLite persistence for auditable human review."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from expense_agent.application.operational_audit import OperationalAuditEvent
from expense_agent.application.review import (
    PendingAgeBucket,
    ReviewBusinessEvent,
    ReviewCaseDetails,
    ReviewCaseStatus,
    ReviewConflictError,
    ReviewerIdentity,
    ReviewEventPage,
    ReviewEventQuery,
    ReviewNotFoundError,
    ReviewProblem,
    ReviewQueueItem,
    ReviewQueuePage,
    ReviewQueueQuery,
    ReviewQueueSort,
    ReviewQueueSummary,
)
from expense_agent.application.workflow import (
    ExtractionSnapshot,
    InvocationStatus,
    InvocationSummary,
    ProcessingRunStatus,
    ProcessingRunSummary,
    RequestConflictError,
    RequestNotFoundError,
    RequestResult,
    submission_fingerprint,
)
from expense_agent.domain._validation import require_aware_datetime, require_non_blank
from expense_agent.domain.audit import AuditActor, AuditEvent
from expense_agent.domain.decisions import (
    AutomatedDecision,
    DecisionReason,
    HumanDecision,
    PolicyDecisionRoute,
    ReviewOutcome,
    RuleEvaluation,
    RuleOutcome,
)
from expense_agent.domain.exceptions import DomainValidationError
from expense_agent.domain.extraction import (
    ExtractionResult,
    ExtractionStatus,
    ModelInvocationTrace,
    ReceiptFacts,
)
from expense_agent.domain.reimbursement import (
    AttachmentReference,
    ReimbursementCase,
    ReimbursementStatus,
    ReimbursementSubmission,
)
from expense_agent.domain.value_objects import Currency, Money

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS reimbursements (
    request_id TEXT PRIMARY KEY,
    submission_hash TEXT NOT NULL,
    submitted_by TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    raw_ocr_text TEXT NOT NULL,
    claimed_category TEXT NOT NULL,
    claimed_amount TEXT NOT NULL,
    claimed_amount_minor INTEGER NOT NULL CHECK (claimed_amount_minor >= 0),
    currency TEXT NOT NULL CHECK (currency IN ('BRL')),
    opened_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'received', 'processing', 'auto_approved', 'pending_review',
            'approved_after_review', 'rejected'
        )
    ),
    version INTEGER NOT NULL CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS attachments (
    request_id TEXT NOT NULL REFERENCES reimbursements(request_id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    location TEXT NOT NULL,
    PRIMARY KEY (request_id, ordinal)
);

CREATE TABLE IF NOT EXISTS model_invocation_traces (
    request_id TEXT PRIMARY KEY REFERENCES reimbursements(request_id),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    invoked_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    parameters_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extractions (
    request_id TEXT PRIMARY KEY REFERENCES reimbursements(request_id),
    processing_run_id TEXT,
    source_invocation_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed')),
    receipt_date TEXT,
    total_amount TEXT,
    total_amount_minor INTEGER CHECK (total_amount_minor IS NULL OR total_amount_minor >= 0),
    total_currency TEXT CHECK (total_currency IS NULL OR total_currency IN ('BRL')),
    category TEXT,
    merchant_name TEXT,
    tax_id TEXT,
    evidence_json TEXT,
    warnings_json TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS automated_decisions (
    decision_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE REFERENCES reimbursements(request_id),
    processing_run_id TEXT,
    route TEXT NOT NULL CHECK (route IN ('auto_approved', 'human_review', 'rejected')),
    decided_at TEXT NOT NULL,
    policy_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_reasons (
    decision_id TEXT NOT NULL REFERENCES automated_decisions(decision_id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    PRIMARY KEY (decision_id, ordinal)
);

CREATE TABLE IF NOT EXISTS rule_evaluations (
    decision_id TEXT NOT NULL REFERENCES automated_decisions(decision_id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    rule_id TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('pass', 'review', 'reject')),
    message TEXT NOT NULL,
    facts_json TEXT NOT NULL,
    PRIMARY KEY (decision_id, ordinal)
);

CREATE TABLE IF NOT EXISTS review_cases (
    request_id TEXT PRIMARY KEY REFERENCES reimbursements(request_id),
    source_decision_id TEXT NOT NULL UNIQUE REFERENCES automated_decisions(decision_id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed')),
    pending_since TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS review_problems (
    request_id TEXT NOT NULL REFERENCES review_cases(request_id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    PRIMARY KEY (request_id, ordinal)
);

CREATE TABLE IF NOT EXISTS human_decisions (
    decision_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE REFERENCES review_cases(request_id),
    outcome TEXT NOT NULL CHECK (outcome IN ('approved', 'rejected')),
    reviewer_id TEXT NOT NULL CHECK (length(trim(reviewer_id)) > 0),
    reviewer_email TEXT NOT NULL CHECK (length(trim(reviewer_email)) > 0),
    reviewer_display_name TEXT NOT NULL CHECK (length(trim(reviewer_display_name)) > 0),
    reason TEXT NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 2000),
    decided_at TEXT NOT NULL,
    expected_version INTEGER NOT NULL CHECK (expected_version >= 1)
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES reimbursements(request_id),
    event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
    occurred_at TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK (length(trim(actor_type)) > 0),
    actor_id TEXT NOT NULL CHECK (length(trim(actor_id)) > 0),
    correlation_id TEXT NOT NULL CHECK (length(trim(correlation_id)) > 0),
    event_scope TEXT NOT NULL DEFAULT 'business' CHECK (
        event_scope IN ('business', 'technical', 'security')
    ),
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_review_queue
    ON review_cases(status, pending_since, request_id);
CREATE INDEX IF NOT EXISTS idx_audit_request_time
    ON audit_events(request_id, occurred_at, event_id);

CREATE TRIGGER IF NOT EXISTS human_decisions_no_update
BEFORE UPDATE ON human_decisions
BEGIN
    SELECT RAISE(ABORT, 'human_decisions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS human_decisions_no_delete
BEFORE DELETE ON human_decisions
BEGIN
    SELECT RAISE(ABORT, 'human_decisions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;
"""

_WORKFLOW_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_audit_request_scope_time
    ON audit_events(request_id, event_scope, occurred_at, event_id);

CREATE TABLE IF NOT EXISTS processing_runs (
    processing_run_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES reimbursements(request_id),
    run_number INTEGER NOT NULL CHECK (run_number >= 1),
    pipeline_version TEXT NOT NULL CHECK (length(trim(pipeline_version)) > 0),
    input_hash TEXT NOT NULL CHECK (length(trim(input_hash)) > 0),
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT,
    correlation_id TEXT NOT NULL CHECK (length(trim(correlation_id)) > 0),
    UNIQUE (request_id, run_number),
    UNIQUE (processing_run_id, request_id),
    CHECK (
        (status = 'running' AND completed_at IS NULL AND error IS NULL)
        OR (status = 'completed' AND completed_at IS NOT NULL AND error IS NULL)
        OR (status = 'failed' AND completed_at IS NOT NULL AND length(trim(error)) > 0)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_processing_runs_one_running
    ON processing_runs(request_id) WHERE status = 'running';
CREATE INDEX IF NOT EXISTS idx_processing_runs_request_number
    ON processing_runs(request_id, run_number DESC);

CREATE TABLE IF NOT EXISTS processing_invocation_attempts (
    invocation_id TEXT PRIMARY KEY,
    processing_run_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (length(trim(stage)) > 0),
    attempt INTEGER NOT NULL CHECK (attempt >= 1),
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    provider TEXT NOT NULL CHECK (length(trim(provider)) > 0),
    model TEXT NOT NULL CHECK (length(trim(model)) > 0),
    prompt_version TEXT NOT NULL CHECK (length(trim(prompt_version)) > 0),
    prompt_hash TEXT NOT NULL CHECK (length(trim(prompt_hash)) > 0),
    input_hash TEXT NOT NULL CHECK (length(trim(input_hash)) > 0),
    output_hash TEXT,
    raw_response TEXT,
    error TEXT,
    invoked_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    parameters_json TEXT NOT NULL,
    UNIQUE (processing_run_id, stage, attempt),
    FOREIGN KEY (processing_run_id, request_id)
        REFERENCES processing_runs(processing_run_id, request_id),
    CHECK (
        (
            status = 'running' AND output_hash IS NULL AND raw_response IS NULL
            AND error IS NULL AND completed_at IS NULL AND duration_ms IS NULL
        ) OR (
            status = 'succeeded' AND length(trim(output_hash)) > 0
            AND raw_response IS NOT NULL AND error IS NULL
            AND completed_at IS NOT NULL AND duration_ms IS NOT NULL
        ) OR (
            status = 'failed' AND length(trim(output_hash)) > 0
            AND raw_response IS NOT NULL AND length(trim(error)) > 0
            AND completed_at IS NOT NULL AND duration_ms IS NOT NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_invocations_request_run
    ON processing_invocation_attempts(request_id, processing_run_id, stage, attempt);

CREATE TRIGGER IF NOT EXISTS processing_runs_terminal_no_update
BEFORE UPDATE ON processing_runs
WHEN OLD.status <> 'running'
BEGIN
    SELECT RAISE(ABORT, 'terminal processing runs are immutable');
END;

CREATE TRIGGER IF NOT EXISTS processing_runs_no_delete
BEFORE DELETE ON processing_runs
BEGIN
    SELECT RAISE(ABORT, 'processing runs are append-only');
END;

CREATE TRIGGER IF NOT EXISTS processing_invocations_terminal_no_update
BEFORE UPDATE ON processing_invocation_attempts
WHEN OLD.status <> 'running'
BEGIN
    SELECT RAISE(ABORT, 'terminal invocation attempts are immutable');
END;

CREATE TRIGGER IF NOT EXISTS processing_invocations_no_delete
BEFORE DELETE ON processing_invocation_attempts
BEGIN
    SELECT RAISE(ABORT, 'invocation attempts are append-only');
END;

CREATE TRIGGER IF NOT EXISTS reimbursements_submission_hash_required_insert
BEFORE INSERT ON reimbursements
WHEN NEW.submission_hash IS NULL OR length(trim(NEW.submission_hash)) = 0
BEGIN
    SELECT RAISE(ABORT, 'submission_hash is required');
END;

CREATE TRIGGER IF NOT EXISTS reimbursements_submission_hash_required_update
BEFORE UPDATE ON reimbursements
WHEN NEW.submission_hash IS NULL OR length(trim(NEW.submission_hash)) = 0
BEGIN
    SELECT RAISE(ABORT, 'submission_hash is required');
END;

CREATE TRIGGER IF NOT EXISTS reimbursements_submission_immutable
BEFORE UPDATE OF
    submission_hash, submitted_by, submitted_at, raw_ocr_text,
    claimed_category, claimed_amount, claimed_amount_minor, currency, opened_at
ON reimbursements
BEGIN
    SELECT RAISE(ABORT, 'reimbursement submission is immutable');
END;

-- A separate versioned trigger is intentional: SQLite does not replace the
-- older reimbursements_submission_immutable definition on an existing
-- database when CREATE TRIGGER IF NOT EXISTS runs during an upgrade.
CREATE TRIGGER IF NOT EXISTS reimbursements_claimed_amount_minor_immutable_v2
BEFORE UPDATE OF claimed_amount_minor ON reimbursements
BEGIN
    SELECT RAISE(ABORT, 'reimbursement submission is immutable');
END;

CREATE TRIGGER IF NOT EXISTS attachments_no_update
BEFORE UPDATE ON attachments
BEGIN
    SELECT RAISE(ABORT, 'attachments are immutable');
END;

CREATE TRIGGER IF NOT EXISTS attachments_no_delete
BEFORE DELETE ON attachments
BEGIN
    SELECT RAISE(ABORT, 'attachments are immutable');
END;
"""

_WORKFLOW_IMMUTABILITY_SCHEMA = """
CREATE TRIGGER IF NOT EXISTS model_invocation_traces_no_update
BEFORE UPDATE ON model_invocation_traces
BEGIN
    SELECT RAISE(ABORT, 'model invocation projections are immutable');
END;

CREATE TRIGGER IF NOT EXISTS model_invocation_traces_no_delete
BEFORE DELETE ON model_invocation_traces
BEGIN
    SELECT RAISE(ABORT, 'model invocation projections are immutable');
END;

CREATE TRIGGER IF NOT EXISTS extractions_no_update
BEFORE UPDATE ON extractions
BEGIN
    SELECT RAISE(ABORT, 'extractions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS extractions_no_delete
BEFORE DELETE ON extractions
BEGIN
    SELECT RAISE(ABORT, 'extractions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS automated_decisions_no_update
BEFORE UPDATE ON automated_decisions
BEGIN
    SELECT RAISE(ABORT, 'automated decisions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS automated_decisions_no_delete
BEFORE DELETE ON automated_decisions
BEGIN
    SELECT RAISE(ABORT, 'automated decisions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS decision_reasons_no_update
BEFORE UPDATE ON decision_reasons
BEGIN
    SELECT RAISE(ABORT, 'decision reasons are immutable');
END;

CREATE TRIGGER IF NOT EXISTS decision_reasons_no_delete
BEFORE DELETE ON decision_reasons
BEGIN
    SELECT RAISE(ABORT, 'decision reasons are immutable');
END;

CREATE TRIGGER IF NOT EXISTS rule_evaluations_no_update
BEFORE UPDATE ON rule_evaluations
BEGIN
    SELECT RAISE(ABORT, 'rule evaluations are immutable');
END;

CREATE TRIGGER IF NOT EXISTS rule_evaluations_no_delete
BEFORE DELETE ON rule_evaluations
BEGIN
    SELECT RAISE(ABORT, 'rule evaluations are immutable');
END;

CREATE TRIGGER IF NOT EXISTS review_problems_no_update
BEFORE UPDATE ON review_problems
BEGIN
    SELECT RAISE(ABORT, 'review problems are immutable');
END;

CREATE TRIGGER IF NOT EXISTS review_problems_no_delete
BEFORE DELETE ON review_problems
BEGIN
    SELECT RAISE(ABORT, 'review problems are immutable');
END;
"""

_QUEUE_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_reimbursements_queue_amount
    ON reimbursements(status, claimed_amount_minor, request_id);
CREATE INDEX IF NOT EXISTS idx_reimbursements_queue_submitted
    ON reimbursements(status, submitted_at DESC, request_id);
CREATE INDEX IF NOT EXISTS idx_reimbursements_queue_category_amount
    ON reimbursements(status, claimed_category COLLATE NOCASE, claimed_amount_minor, request_id);
CREATE INDEX IF NOT EXISTS idx_reimbursements_submitter_search
    ON reimbursements(submitted_by COLLATE NOCASE, request_id);
CREATE INDEX IF NOT EXISTS idx_extractions_merchant_search
    ON extractions(merchant_name COLLATE NOCASE, request_id);
CREATE INDEX IF NOT EXISTS idx_review_problems_code_request
    ON review_problems(code COLLATE NOCASE, request_id);

CREATE TRIGGER IF NOT EXISTS reimbursements_minor_units_required_insert
BEFORE INSERT ON reimbursements
WHEN NEW.claimed_amount_minor IS NULL OR NEW.claimed_amount_minor < 0
BEGIN
    SELECT RAISE(ABORT, 'claimed_amount_minor is required');
END;

CREATE TRIGGER IF NOT EXISTS reimbursements_minor_units_required_update
BEFORE UPDATE ON reimbursements
WHEN NEW.claimed_amount_minor IS NULL OR NEW.claimed_amount_minor < 0
BEGIN
    SELECT RAISE(ABORT, 'claimed_amount_minor is required');
END;
"""

_OPERATIONAL_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS operational_audit_events (
    event_id TEXT PRIMARY KEY CHECK (length(trim(event_id)) BETWEEN 1 AND 64),
    occurred_at TEXT NOT NULL,
    correlation_id TEXT NOT NULL CHECK (length(trim(correlation_id)) BETWEEN 1 AND 128),
    request_id TEXT CHECK (
        request_id IS NULL OR length(trim(request_id)) BETWEEN 1 AND 128
    ),
    actor_type TEXT CHECK (
        actor_type IS NULL OR length(trim(actor_type)) BETWEEN 1 AND 64
    ),
    actor_id TEXT CHECK (
        actor_id IS NULL OR length(trim(actor_id)) BETWEEN 1 AND 320
    ),
    operation_type TEXT NOT NULL CHECK (
        length(trim(operation_type)) BETWEEN 1 AND 64
    ),
    http_method TEXT NOT NULL CHECK (length(trim(http_method)) BETWEEN 1 AND 16),
    route TEXT NOT NULL CHECK (
        length(trim(route)) BETWEEN 1 AND 256
        AND instr(route, '?') = 0
        AND instr(route, '#') = 0
    ),
    status_code INTEGER NOT NULL CHECK (status_code BETWEEN 100 AND 599),
    outcome TEXT NOT NULL CHECK (
        outcome IN ('succeeded', 'client_error', 'server_error')
    ),
    authentication TEXT NOT NULL CHECK (
        authentication IN ('not_attempted', 'succeeded', 'failed')
    ),
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    metadata_json TEXT NOT NULL CHECK (length(metadata_json) <= 4096),
    CHECK (
        (actor_type IS NULL AND actor_id IS NULL)
        OR (actor_type IS NOT NULL AND actor_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_operational_audit_time
    ON operational_audit_events(occurred_at, event_id);
CREATE INDEX IF NOT EXISTS idx_operational_audit_correlation
    ON operational_audit_events(correlation_id, occurred_at, event_id);
CREATE INDEX IF NOT EXISTS idx_operational_audit_request
    ON operational_audit_events(request_id, occurred_at, event_id)
    WHERE request_id IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS operational_audit_events_no_update
BEFORE UPDATE ON operational_audit_events
BEGIN
    SELECT RAISE(ABORT, 'operational audit events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS operational_audit_events_no_delete
BEFORE DELETE ON operational_audit_events
BEGIN
    SELECT RAISE(ABORT, 'operational audit events are append-only');
END;
"""

_HIGH_VALUE_THRESHOLD = Money.brl("2000.00")
_AMOUNT_MISMATCH_CODES = ("AMOUNT_MISMATCH", "TOTAL_MISMATCH")
_BUSINESS_EVENT_PAYLOAD_FIELDS = {
    "reimbursement_received": (
        "attachment_count",
        "request_version",
        "submission_hash",
        "to_status",
    ),
    "reimbursement_processing_started": (
        "from_status",
        "pipeline_version",
        "processing_run_id",
        "request_version",
        "result_version",
        "to_status",
    ),
    "automated_decision_recorded": (
        "decision_id",
        "extraction_status",
        "from_status",
        "policy_version",
        "processing_run_id",
        "request_version",
        "result_version",
        "route",
        "to_status",
    ),
    "review_case_enqueued": (
        "attachment_count",
        "automated_decision_id",
        "extraction_status",
        "policy_version",
        "route",
        "to_status",
    ),
    "human_review_decided": (
        "decision_id",
        "from_status",
        "outcome",
        "reason",
        "request_version",
        "to_status",
    ),
}
_EVENT_CURSOR_CONTEXT = b"expense-agent:review-business-events:v1"


class SqliteReviewRepository:
    """SQLite repository with optimistic versions and serialized review writes."""

    def __init__(self, database_path: str | Path, *, journal_mode: str = "WAL") -> None:
        self.database_path = Path(database_path)
        if str(self.database_path) == ":memory:":
            raise ValueError("use a file-backed SQLite database for the review repository")
        normalized_journal_mode = journal_mode.strip().upper()
        if normalized_journal_mode not in {"WAL", "DELETE"}:
            raise ValueError("journal_mode must be WAL or DELETE")
        self.journal_mode = normalized_journal_mode
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_schema()

    def initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            connection.executescript(_OPERATIONAL_AUDIT_SCHEMA)
            self._migrate_minor_unit_columns(connection)
            self._migrate_workflow_columns(connection)
            connection.executescript(_QUEUE_SCHEMA)
            connection.executescript(_WORKFLOW_SCHEMA)
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._backfill_workflow_records(connection)
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
            connection.executescript(_WORKFLOW_IMMUTABILITY_SCHEMA)
            connection.execute(
                "INSERT OR IGNORE INTO application_metadata (key, value) VALUES (?, ?)",
                ("review_queue_cursor_secret", secrets.token_hex(32)),
            )
            cursor_secret = connection.execute(
                "SELECT value FROM application_metadata WHERE key = ?",
                ("review_queue_cursor_secret",),
            ).fetchone()
            if cursor_secret is None:
                raise RuntimeError("review queue cursor secret was not initialized")
            self._cursor_secret = bytes.fromhex(cursor_secret["value"])
            self._event_cursor_secret = hmac.new(
                self._cursor_secret,
                _EVENT_CURSOR_CONTEXT,
                hashlib.sha256,
            ).digest()

    @staticmethod
    def _migrate_minor_unit_columns(connection: sqlite3.Connection) -> None:
        """Backfill exact integer query columns for databases created by older builds."""

        reimbursement_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(reimbursements)")
        }
        if "claimed_amount_minor" not in reimbursement_columns:
            connection.execute("ALTER TABLE reimbursements ADD COLUMN claimed_amount_minor INTEGER")
        for row in connection.execute(
            "SELECT request_id, claimed_amount FROM reimbursements "
            "WHERE claimed_amount_minor IS NULL"
        ).fetchall():
            connection.execute(
                "UPDATE reimbursements SET claimed_amount_minor = ? WHERE request_id = ?",
                (_minor_units(Decimal(row["claimed_amount"])), row["request_id"]),
            )

        extraction_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(extractions)")
        }
        if "total_amount_minor" not in extraction_columns:
            connection.execute("ALTER TABLE extractions ADD COLUMN total_amount_minor INTEGER")
        for row in connection.execute(
            "SELECT request_id, total_amount FROM extractions "
            "WHERE total_amount IS NOT NULL AND total_amount_minor IS NULL"
        ).fetchall():
            connection.execute(
                "UPDATE extractions SET total_amount_minor = ? WHERE request_id = ?",
                (_minor_units(Decimal(row["total_amount"])), row["request_id"]),
            )

    @staticmethod
    def _migrate_workflow_columns(connection: sqlite3.Connection) -> None:
        """Additive migration for databases created by the review-only build."""

        reimbursement_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(reimbursements)")
        }
        if "submission_hash" not in reimbursement_columns:
            connection.execute("ALTER TABLE reimbursements ADD COLUMN submission_hash TEXT")

        audit_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(audit_events)")
        }
        if "event_scope" not in audit_columns:
            connection.execute(
                "ALTER TABLE audit_events ADD COLUMN event_scope TEXT NOT NULL "
                "DEFAULT 'business' CHECK (event_scope IN ('business', 'technical', 'security'))"
            )

        extraction_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(extractions)")
        }
        if "processing_run_id" not in extraction_columns:
            connection.execute("ALTER TABLE extractions ADD COLUMN processing_run_id TEXT")
        if "source_invocation_id" not in extraction_columns:
            connection.execute("ALTER TABLE extractions ADD COLUMN source_invocation_id TEXT")

        decision_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(automated_decisions)")
        }
        if "processing_run_id" not in decision_columns:
            connection.execute(
                "ALTER TABLE automated_decisions ADD COLUMN processing_run_id TEXT"
            )

        rows = connection.execute(
            """
            SELECT
                request_id, submitted_by, submitted_at, raw_ocr_text,
                claimed_category, claimed_amount, currency
            FROM reimbursements
            WHERE submission_hash IS NULL OR length(trim(submission_hash)) = 0
            """
        ).fetchall()
        for row in rows:
            attachments = tuple(
                AttachmentReference(location=item["location"])
                for item in connection.execute(
                    "SELECT location FROM attachments WHERE request_id = ? ORDER BY ordinal",
                    (row["request_id"],),
                ).fetchall()
            )
            submission = ReimbursementSubmission(
                request_id=row["request_id"],
                submitted_by=row["submitted_by"],
                submitted_at=_timestamp_from_db(row["submitted_at"]),
                raw_ocr_text=row["raw_ocr_text"],
                claimed_category=row["claimed_category"],
                claimed_amount=Money(
                    amount=Decimal(row["claimed_amount"]),
                    currency=Currency(row["currency"]),
                ),
                attachments=attachments,
            )
            connection.execute(
                "UPDATE reimbursements SET submission_hash = ? WHERE request_id = ?",
                (submission_fingerprint(submission), submission.request_id),
            )

    @staticmethod
    def _backfill_workflow_records(connection: sqlite3.Connection) -> None:
        """Attach old single-trace cases to deterministic legacy run/attempt IDs."""

        rows = connection.execute(
            """
            SELECT
                r.request_id, r.submission_hash, r.opened_at,
                ad.decision_id, ad.decided_at, ad.policy_version,
                t.provider, t.model, t.prompt_version, t.prompt_hash, t.input_hash,
                t.raw_response, t.invoked_at, t.duration_ms, t.parameters_json,
                e.status AS extraction_status, e.error AS extraction_error
            FROM reimbursements AS r
            LEFT JOIN automated_decisions AS ad ON ad.request_id = r.request_id
            LEFT JOIN model_invocation_traces AS t ON t.request_id = r.request_id
            LEFT JOIN extractions AS e ON e.request_id = r.request_id
            WHERE (ad.decision_id IS NOT NULL OR t.request_id IS NOT NULL)
              AND NOT EXISTS (
                  SELECT 1 FROM processing_runs AS pr WHERE pr.request_id = r.request_id
              )
            """
        ).fetchall()
        for row in rows:
            stable_suffix = hashlib.sha256(row["request_id"].encode("utf-8")).hexdigest()[:32]
            processing_run_id = f"legacy-run-{stable_suffix}"
            invocation_id = f"legacy-invocation-{stable_suffix}"
            completed_at = row["decided_at"] or row["invoked_at"] or row["opened_at"]
            started_at = row["invoked_at"] or row["opened_at"]
            correlation_row = connection.execute(
                """
                SELECT correlation_id FROM audit_events
                WHERE request_id = ? ORDER BY occurred_at ASC, event_id ASC LIMIT 1
                """,
                (row["request_id"],),
            ).fetchone()
            correlation_id = (
                correlation_row["correlation_id"]
                if correlation_row is not None
                else f"legacy:{stable_suffix}"
            )
            connection.execute(
                """
                INSERT INTO processing_runs (
                    processing_run_id, request_id, run_number, pipeline_version,
                    input_hash, status, started_at, completed_at, error, correlation_id
                ) VALUES (?, ?, 1, ?, ?, 'completed', ?, ?, NULL, ?)
                """,
                (
                    processing_run_id,
                    row["request_id"],
                    row["policy_version"] or "legacy-review-adapter-v1",
                    row["input_hash"] or row["submission_hash"],
                    started_at,
                    completed_at,
                    correlation_id,
                ),
            )
            source_invocation_id = None
            if row["provider"] is not None:
                source_invocation_id = invocation_id
                invocation_status = (
                    InvocationStatus.FAILED.value
                    if row["extraction_status"] == ExtractionStatus.FAILED.value
                    else InvocationStatus.SUCCEEDED.value
                )
                error = (
                    row["extraction_error"]
                    if invocation_status == InvocationStatus.FAILED.value
                    else None
                )
                connection.execute(
                    """
                    INSERT INTO processing_invocation_attempts (
                        invocation_id, processing_run_id, request_id, stage, attempt,
                        status, provider, model, prompt_version, prompt_hash, input_hash,
                        output_hash, raw_response, error, invoked_at, completed_at,
                        duration_ms, parameters_json
                    ) VALUES (?, ?, ?, 'primary_extractor', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invocation_id,
                        processing_run_id,
                        row["request_id"],
                        invocation_status,
                        row["provider"],
                        row["model"],
                        row["prompt_version"],
                        row["prompt_hash"],
                        row["input_hash"],
                        hashlib.sha256(row["raw_response"].encode("utf-8")).hexdigest(),
                        row["raw_response"],
                        error,
                        row["invoked_at"],
                        completed_at,
                        row["duration_ms"],
                        row["parameters_json"],
                    ),
                )
            connection.execute(
                """
                UPDATE extractions
                SET processing_run_id = ?, source_invocation_id = ?
                WHERE request_id = ?
                """,
                (processing_run_id, source_invocation_id, row["request_id"]),
            )
            connection.execute(
                """
                UPDATE automated_decisions SET processing_run_id = ?
                WHERE request_id = ?
                """,
                (processing_run_id, row["request_id"]),
            )

    def add_pending_case(
        self,
        case: ReimbursementCase,
        *,
        extraction: ExtractionResult | None = None,
        problems: Iterable[ReviewProblem] = (),
        correlation_id: str | None = None,
    ) -> None:
        """Persist a fully processed case that was routed to human review."""

        if not isinstance(case, ReimbursementCase):
            raise DomainValidationError("case must be a ReimbursementCase")
        if case.status is not ReimbursementStatus.PENDING_REVIEW:
            raise DomainValidationError("case must be pending_review before it is enqueued")
        automated_decisions = tuple(
            decision for decision in case.decisions if isinstance(decision, AutomatedDecision)
        )
        if len(automated_decisions) != 1:
            raise DomainValidationError("a pending case requires one automated decision")
        automated_decision = automated_decisions[0]
        if automated_decision.route is not PolicyDecisionRoute.HUMAN_REVIEW:
            raise DomainValidationError("automated decision must route to human review")
        if extraction is not None and extraction.request_id != case.request_id:
            raise DomainValidationError("extraction request_id does not match the case")
        normalized_problems = tuple(problems)
        if not all(isinstance(problem, ReviewProblem) for problem in normalized_problems):
            raise DomainValidationError("problems must contain ReviewProblem values")
        ingestion_correlation_id = (
            f"ingest:{case.request_id}"
            if correlation_id is None
            else require_non_blank(correlation_id, "correlation_id")
        )

        submission = case.submission
        submission_hash = submission_fingerprint(submission)
        stable_suffix = hashlib.sha256(case.request_id.encode("utf-8")).hexdigest()[:32]
        processing_run_id = f"preprocessed-run-{stable_suffix}"
        source_invocation_id = (
            f"preprocessed-invocation-{stable_suffix}" if extraction is not None else None
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO reimbursements (
                    request_id, submission_hash, submitted_by, submitted_at, raw_ocr_text,
                    claimed_category, claimed_amount, claimed_amount_minor, currency,
                    opened_at, status, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    submission.request_id,
                    submission_hash,
                    submission.submitted_by,
                    _timestamp_to_db(submission.submitted_at),
                    submission.raw_ocr_text,
                    submission.claimed_category,
                    _decimal_to_db(submission.claimed_amount.amount),
                    _minor_units(submission.claimed_amount.amount),
                    submission.claimed_amount.currency.value,
                    _timestamp_to_db(case.opened_at),
                    case.status.value,
                ),
            )
            connection.executemany(
                "INSERT INTO attachments (request_id, ordinal, location) VALUES (?, ?, ?)",
                (
                    (submission.request_id, ordinal, attachment.location)
                    for ordinal, attachment in enumerate(submission.attachments)
                ),
            )
            connection.execute(
                """
                INSERT INTO processing_runs (
                    processing_run_id, request_id, run_number, pipeline_version,
                    input_hash, status, started_at, completed_at, error, correlation_id
                ) VALUES (?, ?, 1, 'preprocessed-review-adapter-v1', ?, 'completed', ?, ?, NULL, ?)
                """,
                (
                    processing_run_id,
                    submission.request_id,
                    extraction.trace.input_hash if extraction is not None else submission_hash,
                    _timestamp_to_db(
                        extraction.trace.invoked_at if extraction is not None else case.opened_at
                    ),
                    _timestamp_to_db(automated_decision.decided_at),
                    ingestion_correlation_id,
                ),
            )
            if extraction is not None:
                assert source_invocation_id is not None
                self._insert_terminal_invocation(
                    connection,
                    request_id=case.request_id,
                    processing_run_id=processing_run_id,
                    invocation_id=source_invocation_id,
                    extraction=extraction,
                    completed_at=automated_decision.decided_at,
                )
                self._insert_extraction(
                    connection,
                    extraction,
                    processing_run_id=processing_run_id,
                    source_invocation_id=source_invocation_id,
                )
            self._insert_automated_decision(
                connection,
                automated_decision,
                processing_run_id=processing_run_id,
            )
            connection.execute(
                """
                INSERT INTO review_cases (
                    request_id, source_decision_id, status, pending_since, completed_at
                ) VALUES (?, ?, 'pending', ?, NULL)
                """,
                (
                    case.request_id,
                    automated_decision.decision_id,
                    _timestamp_to_db(automated_decision.decided_at),
                ),
            )
            connection.executemany(
                """
                INSERT INTO review_problems (
                    request_id, ordinal, code, message, evidence_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (
                        case.request_id,
                        ordinal,
                        problem.code,
                        problem.message,
                        _canonical_json(problem.evidence),
                    )
                    for ordinal, problem in enumerate(normalized_problems)
                ),
            )
            self._insert_audit_event(
                connection,
                AuditEvent(
                    event_id=f"review-enqueued:{case.request_id}",
                    request_id=case.request_id,
                    event_type="review_case_enqueued",
                    occurred_at=automated_decision.decided_at,
                    actor=AuditActor(
                        actor_type="system",
                        actor_id="deterministic-policy-engine",
                    ),
                    correlation_id=ingestion_correlation_id,
                    payload={
                        "attachment_count": len(submission.attachments),
                        "automated_decision_id": automated_decision.decision_id,
                        "extraction_status": (
                            extraction.status.value if extraction is not None else "not_available"
                        ),
                        "policy_version": automated_decision.policy_version,
                        "route": automated_decision.route.value,
                        "to_status": case.status.value,
                    },
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ReviewConflictError(
                f"review case {case.request_id!r} already exists or conflicts"
            ) from exc
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def register_received(
        self,
        submission: ReimbursementSubmission,
        *,
        submission_hash: str,
        opened_at: datetime,
        audit_event: AuditEvent,
    ) -> tuple[bool, RequestResult]:
        """Atomically register received input or audit an idempotent replay/conflict."""

        if not isinstance(submission, ReimbursementSubmission):
            raise DomainValidationError("submission must be a ReimbursementSubmission")
        normalized_hash = require_non_blank(submission_hash, "submission_hash")
        if normalized_hash != submission_fingerprint(submission):
            raise DomainValidationError("submission_hash does not match the submission")
        require_aware_datetime(opened_at, "opened_at")
        self._validate_workflow_event(
            audit_event,
            request_id=submission.request_id,
            event_type="reimbursement_received",
        )

        connection = self._connect()
        conflict = False
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT submission_hash, status, version FROM reimbursements WHERE request_id = ?",
                (submission.request_id,),
            ).fetchone()
            if existing is not None:
                same_submission = hmac.compare_digest(existing["submission_hash"], normalized_hash)
                replay_event = AuditEvent(
                    event_id=audit_event.event_id,
                    request_id=submission.request_id,
                    event_type=(
                        "reimbursement_intake_replayed"
                        if same_submission
                        else "reimbursement_intake_conflict_rejected"
                    ),
                    occurred_at=audit_event.occurred_at,
                    actor=audit_event.actor,
                    correlation_id=audit_event.correlation_id,
                    payload={
                        "incoming_submission_hash": normalized_hash,
                        "request_version": existing["version"],
                        "status": existing["status"],
                        **(
                            {}
                            if same_submission
                            else {"stored_submission_hash": existing["submission_hash"]}
                        ),
                    },
                )
                self._insert_audit_event(connection, replay_event, event_scope="security")
                result = self._read_request_result(connection, submission.request_id)
                if result is None:
                    raise RuntimeError("registered reimbursement disappeared during replay")
                connection.commit()
                conflict = not same_submission
                if conflict:
                    raise RequestConflictError(
                        f"request {submission.request_id!r} already exists with different input"
                    )
                return False, result

            connection.execute(
                """
                INSERT INTO reimbursements (
                    request_id, submission_hash, submitted_by, submitted_at,
                    raw_ocr_text, claimed_category, claimed_amount,
                    claimed_amount_minor, currency, opened_at, status, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'received', 1)
                """,
                (
                    submission.request_id,
                    normalized_hash,
                    submission.submitted_by,
                    _timestamp_to_db(submission.submitted_at),
                    submission.raw_ocr_text,
                    submission.claimed_category,
                    _decimal_to_db(submission.claimed_amount.amount),
                    _minor_units(submission.claimed_amount.amount),
                    submission.claimed_amount.currency.value,
                    _timestamp_to_db(opened_at),
                ),
            )
            connection.executemany(
                "INSERT INTO attachments (request_id, ordinal, location) VALUES (?, ?, ?)",
                (
                    (submission.request_id, ordinal, attachment.location)
                    for ordinal, attachment in enumerate(submission.attachments)
                ),
            )
            self._insert_audit_event(connection, audit_event)
            result = self._read_request_result(connection, submission.request_id)
            if result is None:
                raise RuntimeError("received reimbursement was not readable after insertion")
            connection.commit()
            return True, result
        except RequestConflictError:
            if not conflict:
                connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise RequestConflictError(
                f"request {submission.request_id!r} conflicts with an existing record"
            ) from exc
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def start_processing(
        self,
        *,
        request_id: str,
        processing_run_id: str,
        pipeline_version: str,
        input_hash: str,
        expected_version: int,
        started_at: datetime,
        correlation_id: str,
        audit_event: AuditEvent,
    ) -> int:
        """Atomically claim a received request and make its processing state visible."""

        normalized_request_id = require_non_blank(request_id, "request_id")
        normalized_run_id = require_non_blank(processing_run_id, "processing_run_id")
        normalized_pipeline = require_non_blank(pipeline_version, "pipeline_version")
        normalized_input_hash = require_non_blank(input_hash, "input_hash")
        normalized_correlation = require_non_blank(correlation_id, "correlation_id")
        require_aware_datetime(started_at, "started_at")
        if not isinstance(expected_version, int) or isinstance(expected_version, bool):
            raise DomainValidationError("expected_version must be an integer")
        self._validate_workflow_event(
            audit_event,
            request_id=normalized_request_id,
            event_type="reimbursement_processing_started",
        )

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            state = connection.execute(
                "SELECT status, version FROM reimbursements WHERE request_id = ?",
                (normalized_request_id,),
            ).fetchone()
            if state is None:
                raise RequestNotFoundError(f"request {normalized_request_id!r} was not found")
            existing_run = connection.execute(
                """
                SELECT processing_run_id, request_id, pipeline_version, input_hash
                FROM processing_runs WHERE processing_run_id = ?
                """,
                (normalized_run_id,),
            ).fetchone()
            if existing_run is not None:
                if (
                    existing_run["pipeline_version"] == normalized_pipeline
                    and existing_run["input_hash"] == normalized_input_hash
                    and existing_run["request_id"] == normalized_request_id
                    and state["status"] == ReimbursementStatus.PROCESSING.value
                ):
                    connection.rollback()
                    return state["version"]
                raise RequestConflictError("processing run ID conflicts with existing metadata")
            if (
                state["status"] != ReimbursementStatus.RECEIVED.value
                or state["version"] != expected_version
            ):
                raise RequestConflictError(
                    "request is no longer received at the expected version"
                )
            connection.execute(
                """
                INSERT INTO processing_runs (
                    processing_run_id, request_id, run_number, pipeline_version,
                    input_hash, status, started_at, completed_at, error, correlation_id
                ) VALUES (?, ?, 1, ?, ?, 'running', ?, NULL, NULL, ?)
                """,
                (
                    normalized_run_id,
                    normalized_request_id,
                    normalized_pipeline,
                    normalized_input_hash,
                    _timestamp_to_db(started_at),
                    normalized_correlation,
                ),
            )
            updated = connection.execute(
                """
                UPDATE reimbursements SET status = 'processing', version = version + 1
                WHERE request_id = ? AND status = 'received' AND version = ?
                """,
                (normalized_request_id, expected_version),
            )
            if updated.rowcount != 1:
                raise RequestConflictError("request changed while processing was started")
            self._insert_audit_event(connection, audit_event)
            new_version = expected_version + 1
            connection.commit()
            return new_version
        except (RequestConflictError, RequestNotFoundError):
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise RequestConflictError("processing start conflicts with existing state") from exc
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def begin_invocation(
        self,
        invocation: InvocationSummary,
        *,
        audit_event: AuditEvent,
    ) -> None:
        """Persist intent before calling an external extractor."""

        if not isinstance(invocation, InvocationSummary):
            raise DomainValidationError("invocation must be an InvocationSummary")
        if invocation.status is not InvocationStatus.RUNNING:
            raise DomainValidationError("begin_invocation requires a running invocation")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute(
                """
                SELECT request_id, status FROM processing_runs
                WHERE processing_run_id = ?
                """,
                (invocation.processing_run_id,),
            ).fetchone()
            if run is None:
                raise RequestNotFoundError("processing run was not found")
            if run["status"] != ProcessingRunStatus.RUNNING.value:
                raise RequestConflictError("processing run is no longer running")
            self._validate_workflow_event(
                audit_event,
                request_id=run["request_id"],
                event_type="model_invocation_started",
            )
            existing = connection.execute(
                "SELECT * FROM processing_invocation_attempts WHERE invocation_id = ?",
                (invocation.invocation_id,),
            ).fetchone()
            if existing is not None:
                if self._invocation_matches_row(invocation, existing):
                    connection.rollback()
                    return
                raise RequestConflictError("invocation ID conflicts with existing metadata")
            connection.execute(
                """
                INSERT INTO processing_invocation_attempts (
                    invocation_id, processing_run_id, request_id, stage, attempt,
                    status, provider, model, prompt_version, prompt_hash, input_hash,
                    output_hash, raw_response, error, invoked_at, completed_at,
                    duration_ms, parameters_json
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, NULL, NULL, ?)
                """,
                (
                    invocation.invocation_id,
                    invocation.processing_run_id,
                    run["request_id"],
                    invocation.stage,
                    invocation.attempt,
                    invocation.provider,
                    invocation.model,
                    invocation.prompt_version,
                    invocation.prompt_hash,
                    invocation.input_hash,
                    _timestamp_to_db(invocation.invoked_at),
                    _canonical_json(invocation.parameters),
                ),
            )
            self._insert_audit_event(connection, audit_event, event_scope="technical")
            connection.commit()
        except (RequestConflictError, RequestNotFoundError):
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise RequestConflictError("invocation attempt conflicts with existing state") from exc
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finish_invocation(
        self,
        invocation: InvocationSummary,
        *,
        raw_response: str,
        audit_event: AuditEvent,
    ) -> None:
        """Finish exactly one started attempt and make the terminal trace immutable."""

        if not isinstance(invocation, InvocationSummary):
            raise DomainValidationError("invocation must be an InvocationSummary")
        if invocation.status is InvocationStatus.RUNNING:
            raise DomainValidationError("finish_invocation requires a terminal invocation")
        if not isinstance(raw_response, str):
            raise DomainValidationError("raw_response must be a string")
        if hashlib.sha256(raw_response.encode("utf-8")).hexdigest() != invocation.output_hash:
            raise DomainValidationError("output_hash does not match raw_response")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM processing_invocation_attempts WHERE invocation_id = ?",
                (invocation.invocation_id,),
            ).fetchone()
            if row is None:
                raise RequestNotFoundError("invocation attempt was not found")
            self._validate_workflow_event(
                audit_event,
                request_id=row["request_id"],
                event_type="model_invocation_completed",
            )
            if row["status"] != InvocationStatus.RUNNING.value:
                if self._terminal_invocation_matches_row(invocation, raw_response, row):
                    connection.rollback()
                    return
                raise RequestConflictError("invocation already has a different terminal result")
            if not self._invocation_identity_matches_row(invocation, row):
                raise RequestConflictError("invocation completion metadata does not match start")
            updated = connection.execute(
                """
                UPDATE processing_invocation_attempts
                SET status = ?, output_hash = ?, raw_response = ?, error = ?,
                    invoked_at = ?, completed_at = ?, duration_ms = ?, parameters_json = ?
                WHERE invocation_id = ? AND status = 'running'
                """,
                (
                    invocation.status.value,
                    invocation.output_hash,
                    raw_response,
                    invocation.error,
                    _timestamp_to_db(invocation.invoked_at),
                    _timestamp_to_db(invocation.completed_at),
                    invocation.duration_ms,
                    _canonical_json(invocation.parameters),
                    invocation.invocation_id,
                ),
            )
            if updated.rowcount != 1:
                raise RequestConflictError("invocation changed while it was completed")
            self._insert_audit_event(connection, audit_event, event_scope="technical")
            connection.commit()
        except (RequestConflictError, RequestNotFoundError):
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise RequestConflictError("invocation completion conflicts with stored trace") from exc
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def complete_processing(
        self,
        *,
        request_id: str,
        processing_run_id: str,
        extraction: ExtractionResult,
        source_invocation_id: str,
        automated_decision: AutomatedDecision,
        problems: tuple[ReviewProblem, ...],
        expected_version: int,
        resulting_status: ReimbursementStatus,
        completed_at: datetime,
        decision_event: AuditEvent,
        review_event: AuditEvent | None,
    ) -> RequestResult:
        """Commit extraction, policy evidence, final route, and review enqueue atomically."""

        normalized_request_id = require_non_blank(request_id, "request_id")
        normalized_run_id = require_non_blank(processing_run_id, "processing_run_id")
        normalized_invocation_id = require_non_blank(source_invocation_id, "source_invocation_id")
        require_aware_datetime(completed_at, "completed_at")
        if extraction.request_id != normalized_request_id:
            raise DomainValidationError("extraction request_id does not match")
        if automated_decision.request_id != normalized_request_id:
            raise DomainValidationError("automated decision request_id does not match")
        expected_status = {
            PolicyDecisionRoute.AUTO_APPROVED: ReimbursementStatus.AUTO_APPROVED,
            PolicyDecisionRoute.HUMAN_REVIEW: ReimbursementStatus.PENDING_REVIEW,
            PolicyDecisionRoute.REJECTED: ReimbursementStatus.REJECTED,
        }[automated_decision.route]
        if resulting_status is not expected_status:
            raise DomainValidationError("resulting status does not match automated route")
        normalized_problems = tuple(problems)
        if not all(isinstance(problem, ReviewProblem) for problem in normalized_problems):
            raise DomainValidationError("problems must contain ReviewProblem values")
        if resulting_status is ReimbursementStatus.PENDING_REVIEW:
            if review_event is None:
                raise DomainValidationError("pending review requires a review event")
        elif review_event is not None or normalized_problems:
            raise DomainValidationError("only pending review may create review records")
        self._validate_workflow_event(
            decision_event,
            request_id=normalized_request_id,
            event_type="automated_decision_recorded",
        )
        if review_event is not None:
            self._validate_workflow_event(
                review_event,
                request_id=normalized_request_id,
                event_type="review_case_enqueued",
            )

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            state = connection.execute(
                """
                SELECT r.status, r.version, pr.status AS run_status
                FROM reimbursements AS r
                JOIN processing_runs AS pr ON pr.request_id = r.request_id
                WHERE r.request_id = ? AND pr.processing_run_id = ?
                """,
                (normalized_request_id, normalized_run_id),
            ).fetchone()
            if state is None:
                raise RequestNotFoundError("request or processing run was not found")
            if (
                state["status"] != ReimbursementStatus.PROCESSING.value
                or state["run_status"] != ProcessingRunStatus.RUNNING.value
                or state["version"] != expected_version
            ):
                raise RequestConflictError(
                    "request is no longer processing at the expected version"
                )
            invocation = connection.execute(
                """
                SELECT status, raw_response FROM processing_invocation_attempts
                WHERE invocation_id = ? AND processing_run_id = ? AND request_id = ?
                """,
                (normalized_invocation_id, normalized_run_id, normalized_request_id),
            ).fetchone()
            if invocation is None or invocation["status"] == InvocationStatus.RUNNING.value:
                raise RequestConflictError("source invocation is missing or incomplete")
            if invocation["raw_response"] != extraction.trace.raw_response:
                raise RequestConflictError("extraction does not match the source invocation")

            self._insert_extraction(
                connection,
                extraction,
                processing_run_id=normalized_run_id,
                source_invocation_id=normalized_invocation_id,
            )
            self._insert_automated_decision(
                connection,
                automated_decision,
                processing_run_id=normalized_run_id,
            )
            if resulting_status is ReimbursementStatus.PENDING_REVIEW:
                connection.execute(
                    """
                    INSERT INTO review_cases (
                        request_id, source_decision_id, status, pending_since, completed_at
                    ) VALUES (?, ?, 'pending', ?, NULL)
                    """,
                    (
                        normalized_request_id,
                        automated_decision.decision_id,
                        _timestamp_to_db(automated_decision.decided_at),
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO review_problems (
                        request_id, ordinal, code, message, evidence_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        (
                            normalized_request_id,
                            ordinal,
                            problem.code,
                            problem.message,
                            _canonical_json(problem.evidence),
                        )
                        for ordinal, problem in enumerate(normalized_problems)
                    ),
                )
            reimbursement_update = connection.execute(
                """
                UPDATE reimbursements SET status = ?, version = version + 1
                WHERE request_id = ? AND status = 'processing' AND version = ?
                """,
                (resulting_status.value, normalized_request_id, expected_version),
            )
            run_update = connection.execute(
                """
                UPDATE processing_runs
                SET status = 'completed', completed_at = ?
                WHERE processing_run_id = ? AND status = 'running'
                """,
                (_timestamp_to_db(completed_at), normalized_run_id),
            )
            if reimbursement_update.rowcount != 1 or run_update.rowcount != 1:
                raise RequestConflictError("processing state changed during finalization")
            self._insert_audit_event(connection, decision_event)
            if review_event is not None:
                self._insert_audit_event(connection, review_event)
            result = self._read_request_result(connection, normalized_request_id)
            if result is None:
                raise RuntimeError("completed request was not readable")
            connection.commit()
            return result
        except (RequestConflictError, RequestNotFoundError):
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise RequestConflictError("processing completion conflicts with stored state") from exc
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_result(self, request_id: str) -> RequestResult | None:
        normalized_request_id = require_non_blank(request_id, "request_id")
        with self._connect() as connection:
            return self._read_request_result(connection, normalized_request_id)

    def list_pending(self) -> tuple[ReviewQueueItem, ...]:
        """Compatibility read for callers that predate the bounded queue API."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    r.request_id, r.submitted_by, r.submitted_at,
                    r.claimed_category, r.claimed_amount, r.currency,
                    rc.pending_since, r.version
                FROM reimbursements AS r
                JOIN review_cases AS rc ON rc.request_id = r.request_id
                WHERE r.status = 'pending_review' AND rc.status = 'pending'
                ORDER BY rc.pending_since ASC, r.request_id ASC
                """
            ).fetchall()
        return tuple(
            ReviewQueueItem(
                request_id=row["request_id"],
                submitted_by=row["submitted_by"],
                submitted_at=_timestamp_from_db(row["submitted_at"]),
                claimed_category=row["claimed_category"],
                claimed_amount=Money(
                    amount=Decimal(row["claimed_amount"]),
                    currency=Currency(row["currency"]),
                ),
                pending_since=_timestamp_from_db(row["pending_since"]),
                version=row["version"],
            )
            for row in rows
        )

    def search_pending(
        self,
        query: ReviewQueueQuery,
        *,
        as_of: datetime,
    ) -> ReviewQueuePage:
        """Return a filtered forward keyset page without offset scans."""

        if not isinstance(query, ReviewQueueQuery):
            raise DomainValidationError("query must be a ReviewQueueQuery")
        require_aware_datetime(as_of, "as_of")
        query_fingerprint = _queue_query_fingerprint(query)
        boundary: tuple[str | int, str] | None = None
        snapshot_at = as_of.astimezone(UTC)
        if query.cursor is not None:
            boundary, snapshot_at = self._decode_cursor(
                query.cursor,
                expected_fingerprint=query_fingerprint,
                sort=query.sort,
            )

        where = [
            "r.status = 'pending_review'",
            "rc.status = 'pending'",
            "rc.pending_since <= ?",
        ]
        parameters: list[str | int] = [_timestamp_to_db(snapshot_at)]
        self._append_queue_filters(
            where,
            parameters,
            query=query,
            snapshot_at=snapshot_at,
        )
        if boundary is not None:
            self._append_keyset_boundary(
                where,
                parameters,
                sort=query.sort,
                boundary=boundary,
            )

        sort_expression, direction = _queue_sort_sql(query.sort)
        sql = f"""
            SELECT
                r.request_id, r.submitted_by, r.submitted_at,
                r.claimed_category, r.claimed_amount, r.claimed_amount_minor,
                r.currency, rc.pending_since, r.version,
                e.merchant_name, e.total_amount, e.total_amount_minor,
                e.total_currency, p0.code AS primary_problem_code,
                p0.message AS primary_problem_message
            FROM reimbursements AS r
            JOIN review_cases AS rc ON rc.request_id = r.request_id
            LEFT JOIN extractions AS e ON e.request_id = r.request_id
            LEFT JOIN review_problems AS p0
                ON p0.request_id = r.request_id AND p0.ordinal = 0
            WHERE {" AND ".join(where)}
            ORDER BY {sort_expression} {direction}, r.request_id ASC
            LIMIT ?
        """
        parameters.append(query.page_size + 1)

        with self._connect() as connection:
            connection.execute("BEGIN")
            rows = connection.execute(sql, parameters).fetchall()
            visible_rows = rows[: query.page_size]
            codes_by_request = self._problem_codes_for_rows(connection, visible_rows)
            summary = self._queue_summary(connection, snapshot_at)

        items = tuple(
            self._queue_item_from_row(row, codes_by_request.get(row["request_id"], ()))
            for row in visible_rows
        )
        has_more = len(rows) > query.page_size
        next_cursor = None
        if has_more and visible_rows:
            last_row = visible_rows[-1]
            next_cursor = self._encode_cursor(
                fingerprint=query_fingerprint,
                sort=query.sort,
                snapshot_at=snapshot_at,
                boundary=(_sort_value(last_row, query.sort), last_row["request_id"]),
            )
        return ReviewQueuePage(
            items=items,
            page_size=query.page_size,
            sort=query.sort,
            has_more=has_more,
            next_cursor=next_cursor,
            summary=summary,
        )

    @staticmethod
    def _append_queue_filters(
        where: list[str],
        parameters: list[str | int],
        *,
        query: ReviewQueueQuery,
        snapshot_at: datetime,
    ) -> None:
        if query.search is not None:
            pattern = f"{_escape_like(query.search)}%"
            where.append(
                "(r.request_id LIKE ? ESCAPE '\\' COLLATE NOCASE "
                "OR r.submitted_by LIKE ? ESCAPE '\\' COLLATE NOCASE "
                "OR e.merchant_name LIKE ? ESCAPE '\\' COLLATE NOCASE)"
            )
            parameters.extend((pattern, pattern, pattern))
        if query.category is not None:
            where.append("r.claimed_category = ? COLLATE NOCASE")
            parameters.append(query.category)
        if query.problem_code is not None:
            where.append(
                "EXISTS (SELECT 1 FROM review_problems AS pf "
                "WHERE pf.request_id = r.request_id AND pf.code = ? COLLATE NOCASE)"
            )
            parameters.append(query.problem_code)
        if query.min_amount is not None:
            where.append("r.claimed_amount_minor >= ?")
            parameters.append(_minor_units(query.min_amount.amount))
        if query.max_amount is not None:
            where.append("r.claimed_amount_minor <= ?")
            parameters.append(_minor_units(query.max_amount.amount))
        if query.submitted_from is not None:
            where.append("r.submitted_at >= ?")
            parameters.append(_timestamp_to_db(query.submitted_from))
        if query.submitted_to is not None:
            where.append("r.submitted_at <= ?")
            parameters.append(_timestamp_to_db(query.submitted_to))
        if query.pending_before is not None:
            where.append("rc.pending_since < ?")
            parameters.append(_timestamp_to_db(query.pending_before))
        if query.age_bucket is PendingAgeBucket.UNDER_4H:
            where.append("rc.pending_since > ?")
            parameters.append(_timestamp_to_db(snapshot_at - timedelta(hours=4)))
        elif query.age_bucket is PendingAgeBucket.BETWEEN_4H_AND_24H:
            where.extend(("rc.pending_since <= ?", "rc.pending_since > ?"))
            parameters.extend(
                (
                    _timestamp_to_db(snapshot_at - timedelta(hours=4)),
                    _timestamp_to_db(snapshot_at - timedelta(hours=24)),
                )
            )
        elif query.age_bucket is PendingAgeBucket.OVER_24H:
            where.append("rc.pending_since <= ?")
            parameters.append(_timestamp_to_db(snapshot_at - timedelta(hours=24)))

    @staticmethod
    def _append_keyset_boundary(
        where: list[str],
        parameters: list[str | int],
        *,
        sort: ReviewQueueSort,
        boundary: tuple[str | int, str],
    ) -> None:
        sort_expression, direction = _queue_sort_sql(sort)
        comparison = ">" if direction == "ASC" else "<"
        where.append(
            f"({sort_expression} {comparison} ? "
            f"OR ({sort_expression} = ? AND r.request_id > ?))"
        )
        parameters.extend((boundary[0], boundary[0], boundary[1]))

    @staticmethod
    def _problem_codes_for_rows(
        connection: sqlite3.Connection,
        rows: list[sqlite3.Row],
    ) -> dict[str, tuple[str, ...]]:
        if not rows:
            return {}
        request_ids = tuple(row["request_id"] for row in rows)
        placeholders = ",".join("?" for _item in request_ids)
        problem_rows = connection.execute(
            f"""
            SELECT request_id, code FROM review_problems
            WHERE request_id IN ({placeholders})
            ORDER BY request_id ASC, ordinal ASC
            """,
            request_ids,
        ).fetchall()
        mutable: dict[str, list[str]] = {}
        for row in problem_rows:
            mutable.setdefault(row["request_id"], []).append(row["code"])
        return {request_id: tuple(codes) for request_id, codes in mutable.items()}

    @staticmethod
    def _queue_item_from_row(
        row: sqlite3.Row,
        problem_codes: tuple[str, ...],
    ) -> ReviewQueueItem:
        extracted_amount = None
        if row["total_amount"] is not None:
            extracted_amount = Money(
                amount=Decimal(row["total_amount"]),
                currency=Currency(row["total_currency"]),
            )
        primary_problem = None
        if row["primary_problem_code"] is not None:
            primary_problem = ReviewProblem(
                code=row["primary_problem_code"],
                message=row["primary_problem_message"],
            )
        return ReviewQueueItem(
            request_id=row["request_id"],
            submitted_by=row["submitted_by"],
            submitted_at=_timestamp_from_db(row["submitted_at"]),
            claimed_category=row["claimed_category"],
            claimed_amount=Money(
                amount=Decimal(row["claimed_amount"]),
                currency=Currency(row["currency"]),
            ),
            pending_since=_timestamp_from_db(row["pending_since"]),
            version=row["version"],
            merchant_name=row["merchant_name"],
            extracted_amount=extracted_amount,
            primary_problem=primary_problem,
            problem_codes=problem_codes,
        )

    @staticmethod
    def _queue_summary(
        connection: sqlite3.Connection,
        snapshot_at: datetime,
    ) -> ReviewQueueSummary:
        threshold_minor = _minor_units(_HIGH_VALUE_THRESHOLD.amount)
        mismatch_placeholders = ",".join("?" for _item in _AMOUNT_MISMATCH_CODES)
        row = connection.execute(
            f"""
            SELECT
                COUNT(*) AS total_pending,
                COALESCE(SUM(CASE WHEN rc.pending_since <= ? THEN 1 ELSE 0 END), 0)
                    AS over_24h,
                COALESCE(SUM(CASE WHEN r.claimed_amount_minor > ? THEN 1 ELSE 0 END), 0)
                    AS high_value,
                COALESCE(SUM(CASE WHEN EXISTS (
                    SELECT 1 FROM review_problems AS ps
                    WHERE ps.request_id = r.request_id
                      AND ps.code IN ({mismatch_placeholders})
                ) THEN 1 ELSE 0 END), 0) AS amount_mismatch
            FROM reimbursements AS r
            JOIN review_cases AS rc ON rc.request_id = r.request_id
            WHERE r.status = 'pending_review' AND rc.status = 'pending'
              AND rc.pending_since <= ?
            """,
            (
                _timestamp_to_db(snapshot_at - timedelta(hours=24)),
                threshold_minor,
                *_AMOUNT_MISMATCH_CODES,
                _timestamp_to_db(snapshot_at),
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("pending queue summary query returned no row")
        return ReviewQueueSummary(
            total_pending=row["total_pending"],
            over_24h=row["over_24h"],
            high_value=row["high_value"],
            amount_mismatch=row["amount_mismatch"],
            high_value_threshold=_HIGH_VALUE_THRESHOLD,
            as_of=snapshot_at,
        )

    def _encode_cursor(
        self,
        *,
        fingerprint: str,
        sort: ReviewQueueSort,
        snapshot_at: datetime,
        boundary: tuple[str | int, str],
    ) -> str:
        raw = _canonical_json(
            {
                "as_of": _timestamp_to_db(snapshot_at),
                "fingerprint": fingerprint,
                "key": boundary,
                "sort": sort.value,
                "version": 1,
            }
        ).encode("utf-8")
        signature = hmac.new(self._cursor_secret, raw, hashlib.sha256).digest()
        return f"{_base64url_encode(raw)}.{_base64url_encode(signature)}"

    def _decode_cursor(
        self,
        cursor: str,
        *,
        expected_fingerprint: str,
        sort: ReviewQueueSort,
    ) -> tuple[tuple[str | int, str], datetime]:
        invalid_message = "cursor is invalid or does not match the current queue query"
        try:
            encoded_payload, encoded_signature = cursor.split(".", 1)
            raw = _base64url_decode(encoded_payload)
            signature = _base64url_decode(encoded_signature)
            expected_signature = hmac.new(self._cursor_secret, raw, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError("cursor signature mismatch")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {
                "as_of",
                "fingerprint",
                "key",
                "sort",
                "version",
            }:
                raise ValueError("cursor payload shape mismatch")
            if (
                payload["version"] != 1
                or payload["sort"] != sort.value
                or payload["fingerprint"] != expected_fingerprint
            ):
                raise ValueError("cursor query mismatch")
            boundary = payload["key"]
            if (
                not isinstance(boundary, list)
                or len(boundary) != 2
                or not isinstance(boundary[1], str)
                or not boundary[1].strip()
            ):
                raise ValueError("cursor boundary is invalid")
            if sort in {ReviewQueueSort.AMOUNT_ASC, ReviewQueueSort.AMOUNT_DESC}:
                if not isinstance(boundary[0], int) or isinstance(boundary[0], bool):
                    raise ValueError("amount cursor boundary is invalid")
            elif not isinstance(boundary[0], str):
                raise ValueError("timestamp cursor boundary is invalid")
            snapshot_at = _timestamp_from_db(payload["as_of"])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise DomainValidationError(invalid_message) from exc
        return (boundary[0], boundary[1]), snapshot_at

    def get(self, request_id: str) -> ReviewCaseDetails | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    r.request_id, r.submitted_by, r.submitted_at, r.raw_ocr_text,
                    r.claimed_category, r.claimed_amount, r.currency, r.opened_at,
                    r.status AS reimbursement_status, r.version,
                    rc.status AS review_status, rc.pending_since, rc.source_decision_id
                FROM reimbursements AS r
                JOIN review_cases AS rc ON rc.request_id = r.request_id
                WHERE r.request_id = ?
                """,
                (request_id,),
            ).fetchone()
            if row is None:
                return None

            attachment_rows = connection.execute(
                """
                SELECT location FROM attachments
                WHERE request_id = ? ORDER BY ordinal ASC
                """,
                (request_id,),
            ).fetchall()
            submission = ReimbursementSubmission(
                request_id=row["request_id"],
                submitted_by=row["submitted_by"],
                submitted_at=_timestamp_from_db(row["submitted_at"]),
                raw_ocr_text=row["raw_ocr_text"],
                claimed_category=row["claimed_category"],
                claimed_amount=Money(
                    amount=Decimal(row["claimed_amount"]),
                    currency=Currency(row["currency"]),
                ),
                attachments=tuple(
                    AttachmentReference(location=item["location"]) for item in attachment_rows
                ),
            )
            extraction = self._read_extraction(connection, request_id)
            automated_decision = self._read_automated_decision(
                connection,
                row["source_decision_id"],
            )
            problems = tuple(
                ReviewProblem(
                    code=item["code"],
                    message=item["message"],
                    evidence=_object_from_json(item["evidence_json"]),
                )
                for item in connection.execute(
                    """
                    SELECT code, message, evidence_json
                    FROM review_problems
                    WHERE request_id = ? ORDER BY ordinal ASC
                    """,
                    (request_id,),
                ).fetchall()
            )
            human_decision, reviewed_by = self._read_human_decision(connection, request_id)

        return ReviewCaseDetails(
            submission=submission,
            opened_at=_timestamp_from_db(row["opened_at"]),
            status=ReimbursementStatus(row["reimbursement_status"]),
            version=row["version"],
            review_status=ReviewCaseStatus(row["review_status"]),
            pending_since=_timestamp_from_db(row["pending_since"]),
            extraction=extraction,
            problems=problems,
            automated_decision=automated_decision,
            human_decision=human_decision,
            reviewed_by=reviewed_by,
        )

    def list_business_events(
        self,
        request_id: str,
        query: ReviewEventQuery,
    ) -> ReviewEventPage | None:
        """Return one chronological page without exposing unapproved audit fields."""

        normalized_request_id = require_non_blank(request_id, "request_id")
        if not isinstance(query, ReviewEventQuery):
            raise DomainValidationError("query must be a ReviewEventQuery")
        query_fingerprint = _event_query_fingerprint(normalized_request_id, query)
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM reimbursements WHERE request_id = ?",
                (normalized_request_id,),
            ).fetchone()
            if exists is None:
                return None

            boundary: tuple[str, str] | None = None
            if query.cursor is not None:
                boundary = self._decode_event_cursor(
                    query.cursor,
                    expected_fingerprint=query_fingerprint,
                )
            where = ["request_id = ?", "event_scope = 'business'"]
            parameters: list[str | int] = [normalized_request_id]
            if boundary is not None:
                where.append(
                    "(occurred_at > ? OR (occurred_at = ? AND event_id > ?))"
                )
                parameters.extend((boundary[0], boundary[0], boundary[1]))
            parameters.append(query.page_size + 1)
            rows = connection.execute(
                f"""
                SELECT
                    event_id, request_id, event_type, occurred_at,
                    actor_type, actor_id, correlation_id, payload_json
                FROM audit_events
                WHERE {" AND ".join(where)}
                ORDER BY occurred_at ASC, event_id ASC
                LIMIT ?
                """,
                parameters,
            ).fetchall()

        visible_rows = rows[: query.page_size]
        items = tuple(_business_event_from_row(row) for row in visible_rows)
        has_more = len(rows) > query.page_size
        next_cursor = None
        if has_more and visible_rows:
            last_row = visible_rows[-1]
            next_cursor = self._encode_event_cursor(
                fingerprint=query_fingerprint,
                boundary=(last_row["occurred_at"], last_row["event_id"]),
            )
        return ReviewEventPage(
            items=items,
            page_size=query.page_size,
            has_more=has_more,
            next_cursor=next_cursor,
        )

    def _encode_event_cursor(
        self,
        *,
        fingerprint: str,
        boundary: tuple[str, str],
    ) -> str:
        raw = _canonical_json(
            {
                "fingerprint": fingerprint,
                "key": boundary,
                "kind": "review_business_events",
                "version": 1,
            }
        ).encode("utf-8")
        signature = hmac.new(
            self._event_cursor_secret,
            raw,
            hashlib.sha256,
        ).digest()
        return f"{_base64url_encode(raw)}.{_base64url_encode(signature)}"

    def _decode_event_cursor(
        self,
        cursor: str,
        *,
        expected_fingerprint: str,
    ) -> tuple[str, str]:
        invalid_message = "cursor is invalid or does not match the business-event query"
        try:
            encoded_payload, encoded_signature = cursor.split(".", 1)
            raw = _base64url_decode(encoded_payload)
            signature = _base64url_decode(encoded_signature)
            expected_signature = hmac.new(
                self._event_cursor_secret,
                raw,
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError("cursor signature mismatch")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {
                "fingerprint",
                "key",
                "kind",
                "version",
            }:
                raise ValueError("cursor payload shape mismatch")
            if (
                payload["version"] != 1
                or payload["kind"] != "review_business_events"
                or payload["fingerprint"] != expected_fingerprint
            ):
                raise ValueError("cursor query mismatch")
            boundary = payload["key"]
            if (
                not isinstance(boundary, list)
                or len(boundary) != 2
                or not all(isinstance(value, str) and value.strip() for value in boundary)
            ):
                raise ValueError("cursor boundary is invalid")
            if _timestamp_to_db(_timestamp_from_db(boundary[0])) != boundary[0]:
                raise ValueError("cursor timestamp is not canonical")
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise DomainValidationError(invalid_message) from exc
        return boundary[0], boundary[1]

    def record_human_decision(
        self,
        *,
        decision: HumanDecision,
        reviewer: ReviewerIdentity,
        expected_version: int,
        resulting_status: ReimbursementStatus,
        audit_event: AuditEvent,
    ) -> int:
        """Commit the decision, state transition, and audit event as one unit."""

        self._validate_review_write(
            decision=decision,
            reviewer=reviewer,
            expected_version=expected_version,
            resulting_status=resulting_status,
            audit_event=audit_event,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            state = connection.execute(
                """
                SELECT r.status, r.version, rc.status AS review_status
                FROM reimbursements AS r
                JOIN review_cases AS rc ON rc.request_id = r.request_id
                WHERE r.request_id = ?
                """,
                (decision.request_id,),
            ).fetchone()
            if state is None:
                raise ReviewNotFoundError(f"review case {decision.request_id!r} was not found")
            if (
                state["status"] != ReimbursementStatus.PENDING_REVIEW.value
                or state["review_status"] != ReviewCaseStatus.PENDING.value
                or state["version"] != expected_version
            ):
                raise ReviewConflictError(
                    "review case is no longer pending at the expected version"
                )

            connection.execute(
                """
                INSERT INTO human_decisions (
                    decision_id, request_id, outcome, reviewer_id, reviewer_email,
                    reviewer_display_name, reason, decided_at, expected_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.request_id,
                    decision.outcome.value,
                    reviewer.reviewer_id,
                    reviewer.email,
                    reviewer.display_name,
                    decision.reason,
                    _timestamp_to_db(decision.decided_at),
                    expected_version,
                ),
            )
            reimbursement_update = connection.execute(
                """
                UPDATE reimbursements
                SET status = ?, version = version + 1
                WHERE request_id = ? AND status = 'pending_review' AND version = ?
                """,
                (resulting_status.value, decision.request_id, expected_version),
            )
            review_update = connection.execute(
                """
                UPDATE review_cases
                SET status = 'completed', completed_at = ?
                WHERE request_id = ? AND status = 'pending'
                """,
                (_timestamp_to_db(decision.decided_at), decision.request_id),
            )
            if reimbursement_update.rowcount != 1 or review_update.rowcount != 1:
                raise ReviewConflictError("review case changed while the decision was written")

            self._insert_audit_event(connection, audit_event)
            new_version = expected_version + 1
            connection.commit()
            return new_version
        except (ReviewConflictError, ReviewNotFoundError):
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ReviewConflictError(
                "the review decision conflicts with an existing immutable record"
            ) from exc
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_operation(self, event: OperationalAuditEvent) -> None:
        """Append one sanitized service-operation event in its own transaction."""

        if not isinstance(event, OperationalAuditEvent):
            raise DomainValidationError("event must be an OperationalAuditEvent")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO operational_audit_events (
                    event_id, occurred_at, correlation_id, request_id,
                    actor_type, actor_id, operation_type, http_method, route,
                    status_code, outcome, authentication, duration_ms, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    _timestamp_to_db(event.occurred_at),
                    event.correlation_id,
                    event.request_id,
                    event.actor_type,
                    event.actor_id,
                    event.operation_type,
                    event.http_method,
                    event.route,
                    event.status_code,
                    event.outcome.value,
                    event.authentication.value,
                    event.duration_ms,
                    _canonical_json(event.metadata),
                ),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=5,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if self.journal_mode == "WAL":
            connection.execute("PRAGMA journal_mode = WAL")
        else:
            connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    @staticmethod
    def _insert_audit_event(
        connection: sqlite3.Connection,
        audit_event: AuditEvent,
        *,
        event_scope: str = "business",
    ) -> None:
        if event_scope not in {"business", "technical", "security"}:
            raise DomainValidationError("unsupported audit event scope")
        connection.execute(
            """
            INSERT INTO audit_events (
                event_id, request_id, event_type, occurred_at, actor_type,
                actor_id, correlation_id, event_scope, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_event.event_id,
                audit_event.request_id,
                audit_event.event_type,
                _timestamp_to_db(audit_event.occurred_at),
                audit_event.actor.actor_type,
                audit_event.actor.actor_id,
                audit_event.correlation_id,
                event_scope,
                _canonical_json(audit_event.payload),
            ),
        )

    @staticmethod
    def _insert_terminal_invocation(
        connection: sqlite3.Connection,
        *,
        request_id: str,
        processing_run_id: str,
        invocation_id: str,
        extraction: ExtractionResult,
        completed_at: datetime,
    ) -> None:
        trace = extraction.trace
        status = (
            InvocationStatus.SUCCEEDED.value
            if extraction.status is ExtractionStatus.SUCCEEDED
            else InvocationStatus.FAILED.value
        )
        connection.execute(
            """
            INSERT INTO processing_invocation_attempts (
                invocation_id, processing_run_id, request_id, stage, attempt,
                status, provider, model, prompt_version, prompt_hash, input_hash,
                output_hash, raw_response, error, invoked_at, completed_at,
                duration_ms, parameters_json
            ) VALUES (?, ?, ?, 'primary_extractor', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invocation_id,
                processing_run_id,
                request_id,
                status,
                trace.provider,
                trace.model,
                trace.prompt_version,
                trace.prompt_hash,
                trace.input_hash,
                hashlib.sha256(trace.raw_response.encode("utf-8")).hexdigest(),
                trace.raw_response,
                extraction.error,
                _timestamp_to_db(trace.invoked_at),
                _timestamp_to_db(completed_at),
                trace.duration_ms,
                _canonical_json(trace.parameters),
            ),
        )

    @staticmethod
    def _insert_extraction(
        connection: sqlite3.Connection,
        extraction: ExtractionResult,
        *,
        processing_run_id: str,
        source_invocation_id: str,
    ) -> None:
        trace = extraction.trace
        connection.execute(
            """
            INSERT INTO model_invocation_traces (
                request_id, provider, model, prompt_version, prompt_hash,
                input_hash, raw_response, invoked_at, duration_ms, parameters_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                extraction.request_id,
                trace.provider,
                trace.model,
                trace.prompt_version,
                trace.prompt_hash,
                trace.input_hash,
                trace.raw_response,
                _timestamp_to_db(trace.invoked_at),
                trace.duration_ms,
                _canonical_json(trace.parameters),
            ),
        )
        facts = extraction.facts
        connection.execute(
            """
            INSERT INTO extractions (
                request_id, processing_run_id, source_invocation_id, status,
                receipt_date, total_amount, total_amount_minor, total_currency,
                category, merchant_name, tax_id, evidence_json, warnings_json, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                extraction.request_id,
                processing_run_id,
                source_invocation_id,
                extraction.status.value,
                facts.receipt_date.isoformat() if facts and facts.receipt_date else None,
                _decimal_to_db(facts.total.amount) if facts and facts.total else None,
                _minor_units(facts.total.amount) if facts and facts.total else None,
                facts.total.currency.value if facts and facts.total else None,
                facts.category if facts else None,
                facts.merchant_name if facts else None,
                facts.tax_id if facts else None,
                _canonical_json(facts.evidence) if facts else None,
                _canonical_json(facts.warnings) if facts else None,
                extraction.error,
            ),
        )

    @staticmethod
    def _insert_automated_decision(
        connection: sqlite3.Connection,
        decision: AutomatedDecision,
        *,
        processing_run_id: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO automated_decisions (
                decision_id, request_id, processing_run_id, route, decided_at, policy_version
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                decision.decision_id,
                decision.request_id,
                processing_run_id,
                decision.route.value,
                _timestamp_to_db(decision.decided_at),
                decision.policy_version,
            ),
        )
        connection.executemany(
            """
            INSERT INTO decision_reasons (
                decision_id, ordinal, code, message, evidence_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                (
                    decision.decision_id,
                    ordinal,
                    reason.code,
                    reason.message,
                    _canonical_json(reason.evidence),
                )
                for ordinal, reason in enumerate(decision.reasons)
            ),
        )
        connection.executemany(
            """
            INSERT INTO rule_evaluations (
                decision_id, ordinal, rule_id, rule_version,
                outcome, message, facts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    decision.decision_id,
                    ordinal,
                    evaluation.rule_id,
                    evaluation.rule_version,
                    evaluation.outcome.value,
                    evaluation.message,
                    _canonical_json(evaluation.facts),
                )
                for ordinal, evaluation in enumerate(decision.rule_evaluations)
            ),
        )

    @staticmethod
    def _read_extraction(
        connection: sqlite3.Connection,
        request_id: str,
    ) -> ExtractionResult | None:
        row = connection.execute(
            """
            SELECT
                e.status, e.receipt_date, e.total_amount, e.total_currency,
                e.category, e.merchant_name, e.tax_id, e.evidence_json,
                e.warnings_json, e.error,
                t.provider, t.model, t.prompt_version, t.prompt_hash, t.input_hash,
                t.raw_response, t.invoked_at, t.duration_ms, t.parameters_json
            FROM extractions AS e
            JOIN model_invocation_traces AS t ON t.request_id = e.request_id
            WHERE e.request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        trace = ModelInvocationTrace(
            provider=row["provider"],
            model=row["model"],
            prompt_version=row["prompt_version"],
            prompt_hash=row["prompt_hash"],
            input_hash=row["input_hash"],
            raw_response=row["raw_response"],
            invoked_at=_timestamp_from_db(row["invoked_at"]),
            duration_ms=row["duration_ms"],
            parameters=_object_from_json(row["parameters_json"]),
        )
        status = ExtractionStatus(row["status"])
        facts = None
        if status is ExtractionStatus.SUCCEEDED:
            total = None
            if row["total_amount"] is not None:
                total = Money(
                    amount=Decimal(row["total_amount"]),
                    currency=Currency(row["total_currency"]),
                )
            facts = ReceiptFacts(
                receipt_date=(
                    date.fromisoformat(row["receipt_date"])
                    if row["receipt_date"] is not None
                    else None
                ),
                total=total,
                category=row["category"],
                merchant_name=row["merchant_name"],
                tax_id=row["tax_id"],
                evidence=_object_from_json(row["evidence_json"]),
                warnings=tuple(_object_from_json(row["warnings_json"])),
            )
        return ExtractionResult(
            request_id=request_id,
            status=status,
            trace=trace,
            facts=facts,
            error=row["error"],
        )

    @staticmethod
    def _read_automated_decision(
        connection: sqlite3.Connection,
        decision_id: str,
    ) -> AutomatedDecision:
        row = connection.execute(
            """
            SELECT decision_id, request_id, route, decided_at, policy_version
            FROM automated_decisions WHERE decision_id = ?
            """,
            (decision_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("review case refers to a missing automated decision")
        reasons = tuple(
            DecisionReason(
                code=item["code"],
                message=item["message"],
                evidence=_object_from_json(item["evidence_json"]),
            )
            for item in connection.execute(
                """
                SELECT code, message, evidence_json FROM decision_reasons
                WHERE decision_id = ? ORDER BY ordinal ASC
                """,
                (decision_id,),
            ).fetchall()
        )
        evaluations = tuple(
            RuleEvaluation(
                rule_id=item["rule_id"],
                rule_version=item["rule_version"],
                outcome=RuleOutcome(item["outcome"]),
                message=item["message"],
                facts=_object_from_json(item["facts_json"]),
            )
            for item in connection.execute(
                """
                SELECT rule_id, rule_version, outcome, message, facts_json
                FROM rule_evaluations
                WHERE decision_id = ? ORDER BY ordinal ASC
                """,
                (decision_id,),
            ).fetchall()
        )
        return AutomatedDecision(
            decision_id=row["decision_id"],
            request_id=row["request_id"],
            route=PolicyDecisionRoute(row["route"]),
            decided_at=_timestamp_from_db(row["decided_at"]),
            policy_version=row["policy_version"],
            reasons=reasons,
            rule_evaluations=evaluations,
        )

    @staticmethod
    def _read_human_decision(
        connection: sqlite3.Connection,
        request_id: str,
    ) -> tuple[HumanDecision | None, ReviewerIdentity | None]:
        row = connection.execute(
            """
            SELECT
                decision_id, request_id, outcome, reviewer_id, reviewer_email,
                reviewer_display_name, reason, decided_at
            FROM human_decisions WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            return None, None
        reviewer = ReviewerIdentity(
            reviewer_id=row["reviewer_id"],
            email=row["reviewer_email"],
            display_name=row["reviewer_display_name"],
        )
        return (
            HumanDecision(
                decision_id=row["decision_id"],
                request_id=row["request_id"],
                outcome=ReviewOutcome(row["outcome"]),
                reviewer=reviewer.reviewer_id,
                reason=row["reason"],
                decided_at=_timestamp_from_db(row["decided_at"]),
            ),
            reviewer,
        )

    @classmethod
    def _read_request_result(
        cls,
        connection: sqlite3.Connection,
        request_id: str,
    ) -> RequestResult | None:
        row = connection.execute(
            """
            SELECT
                request_id, submitted_by, submitted_at, raw_ocr_text,
                claimed_category, claimed_amount, currency, opened_at, status, version
            FROM reimbursements WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        attachment_rows = connection.execute(
            "SELECT location FROM attachments WHERE request_id = ? ORDER BY ordinal ASC",
            (request_id,),
        ).fetchall()
        submission = ReimbursementSubmission(
            request_id=row["request_id"],
            submitted_by=row["submitted_by"],
            submitted_at=_timestamp_from_db(row["submitted_at"]),
            raw_ocr_text=row["raw_ocr_text"],
            claimed_category=row["claimed_category"],
            claimed_amount=Money(
                amount=Decimal(row["claimed_amount"]),
                currency=Currency(row["currency"]),
            ),
            attachments=tuple(
                AttachmentReference(location=item["location"]) for item in attachment_rows
            ),
        )

        run_row = connection.execute(
            """
            SELECT
                processing_run_id, run_number, status, pipeline_version,
                input_hash, started_at, completed_at, error
            FROM processing_runs WHERE request_id = ?
            ORDER BY run_number DESC LIMIT 1
            """,
            (request_id,),
        ).fetchone()
        processing_run = None
        if run_row is not None:
            processing_run = ProcessingRunSummary(
                processing_run_id=run_row["processing_run_id"],
                run_number=run_row["run_number"],
                status=ProcessingRunStatus(run_row["status"]),
                pipeline_version=run_row["pipeline_version"],
                input_hash=run_row["input_hash"],
                started_at=_timestamp_from_db(run_row["started_at"]),
                completed_at=(
                    _timestamp_from_db(run_row["completed_at"])
                    if run_row["completed_at"] is not None
                    else None
                ),
                error=run_row["error"],
            )

        extraction_result = cls._read_extraction(connection, request_id)
        extraction_snapshot = None
        if extraction_result is not None:
            invocation_row = connection.execute(
                """
                SELECT
                    pi.invocation_id, pi.processing_run_id, pi.stage, pi.attempt,
                    pi.status, pi.provider, pi.model, pi.prompt_version,
                    pi.prompt_hash, pi.input_hash, pi.output_hash, pi.invoked_at,
                    pi.completed_at, pi.duration_ms, pi.parameters_json, pi.error
                FROM processing_invocation_attempts AS pi
                JOIN extractions AS e ON e.source_invocation_id = pi.invocation_id
                WHERE e.request_id = ?
                """,
                (request_id,),
            ).fetchone()
            if invocation_row is None:
                raise RuntimeError("persisted extraction has no source invocation")
            invocation = InvocationSummary(
                invocation_id=invocation_row["invocation_id"],
                processing_run_id=invocation_row["processing_run_id"],
                stage=invocation_row["stage"],
                attempt=invocation_row["attempt"],
                status=InvocationStatus(invocation_row["status"]),
                provider=invocation_row["provider"],
                model=invocation_row["model"],
                prompt_version=invocation_row["prompt_version"],
                prompt_hash=invocation_row["prompt_hash"],
                input_hash=invocation_row["input_hash"],
                output_hash=invocation_row["output_hash"],
                invoked_at=_timestamp_from_db(invocation_row["invoked_at"]),
                completed_at=(
                    _timestamp_from_db(invocation_row["completed_at"])
                    if invocation_row["completed_at"] is not None
                    else None
                ),
                duration_ms=invocation_row["duration_ms"],
                parameters=_object_from_json(invocation_row["parameters_json"]),
                error=invocation_row["error"],
            )
            extraction_snapshot = ExtractionSnapshot(
                status=extraction_result.status,
                facts=extraction_result.facts,
                error=extraction_result.error,
                invocation=invocation,
            )

        decision_row = connection.execute(
            "SELECT decision_id FROM automated_decisions WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        automated_decision = (
            cls._read_automated_decision(connection, decision_row["decision_id"])
            if decision_row is not None
            else None
        )
        review_row = connection.execute(
            "SELECT status, pending_since FROM review_cases WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        review_status = None
        pending_since = None
        problems: tuple[ReviewProblem, ...] = ()
        if review_row is not None:
            review_status = ReviewCaseStatus(review_row["status"])
            pending_since = _timestamp_from_db(review_row["pending_since"])
            problems = tuple(
                ReviewProblem(
                    code=item["code"],
                    message=item["message"],
                    evidence=_object_from_json(item["evidence_json"]),
                )
                for item in connection.execute(
                    """
                    SELECT code, message, evidence_json FROM review_problems
                    WHERE request_id = ? ORDER BY ordinal ASC
                    """,
                    (request_id,),
                ).fetchall()
            )
        human_decision, reviewed_by = cls._read_human_decision(connection, request_id)
        return RequestResult(
            submission=submission,
            opened_at=_timestamp_from_db(row["opened_at"]),
            status=ReimbursementStatus(row["status"]),
            version=row["version"],
            processing_run=processing_run,
            extraction=extraction_snapshot,
            automated_decision=automated_decision,
            problems=problems,
            review_status=review_status,
            pending_since=pending_since,
            human_decision=human_decision,
            reviewed_by=reviewed_by,
        )

    @staticmethod
    def _validate_workflow_event(
        audit_event: AuditEvent,
        *,
        request_id: str,
        event_type: str,
    ) -> None:
        if not isinstance(audit_event, AuditEvent):
            raise DomainValidationError("audit_event must be an AuditEvent")
        if audit_event.request_id != request_id:
            raise DomainValidationError("audit event request_id does not match")
        if audit_event.event_type != event_type:
            raise DomainValidationError(f"audit event must be {event_type}")

    @staticmethod
    def _invocation_identity_matches_row(
        invocation: InvocationSummary,
        row: sqlite3.Row,
    ) -> bool:
        return (
            invocation.invocation_id == row["invocation_id"]
            and invocation.processing_run_id == row["processing_run_id"]
            and invocation.stage == row["stage"]
            and invocation.attempt == row["attempt"]
            and invocation.provider == row["provider"]
            and invocation.model == row["model"]
            and invocation.prompt_version == row["prompt_version"]
            and invocation.prompt_hash == row["prompt_hash"]
            and invocation.input_hash == row["input_hash"]
        )

    @classmethod
    def _invocation_matches_row(
        cls,
        invocation: InvocationSummary,
        row: sqlite3.Row,
    ) -> bool:
        return cls._invocation_identity_matches_row(invocation, row)

    @classmethod
    def _terminal_invocation_matches_row(
        cls,
        invocation: InvocationSummary,
        raw_response: str,
        row: sqlite3.Row,
    ) -> bool:
        return (
            cls._invocation_identity_matches_row(invocation, row)
            and invocation.status.value == row["status"]
            and invocation.output_hash == row["output_hash"]
            and raw_response == row["raw_response"]
            and invocation.error == row["error"]
            and _timestamp_to_db(invocation.invoked_at) == row["invoked_at"]
            and _timestamp_to_db(invocation.completed_at) == row["completed_at"]
            and invocation.duration_ms == row["duration_ms"]
            and _canonical_json(invocation.parameters) == row["parameters_json"]
        )

    @staticmethod
    def _validate_review_write(
        *,
        decision: HumanDecision,
        reviewer: ReviewerIdentity,
        expected_version: int,
        resulting_status: ReimbursementStatus,
        audit_event: AuditEvent,
    ) -> None:
        if not isinstance(decision, HumanDecision):
            raise DomainValidationError("decision must be a HumanDecision")
        if not isinstance(reviewer, ReviewerIdentity):
            raise DomainValidationError("reviewer must be a ReviewerIdentity")
        if decision.reviewer != reviewer.reviewer_id:
            raise DomainValidationError("decision reviewer does not match authenticated identity")
        if not isinstance(expected_version, int) or isinstance(expected_version, bool):
            raise DomainValidationError("expected_version must be an integer")
        expected_status = {
            ReviewOutcome.APPROVED: ReimbursementStatus.APPROVED_AFTER_REVIEW,
            ReviewOutcome.REJECTED: ReimbursementStatus.REJECTED,
        }[decision.outcome]
        if resulting_status is not expected_status:
            raise DomainValidationError("resulting status does not match review outcome")
        if not isinstance(audit_event, AuditEvent):
            raise DomainValidationError("audit_event must be an AuditEvent")
        if audit_event.request_id != decision.request_id:
            raise DomainValidationError("audit request_id does not match the decision")
        if audit_event.actor.actor_id != reviewer.reviewer_id:
            raise DomainValidationError("audit actor does not match authenticated identity")
        if audit_event.occurred_at != decision.decided_at:
            raise DomainValidationError("audit and decision timestamps must match")


def _business_event_from_row(row: sqlite3.Row) -> ReviewBusinessEvent:
    raw_payload = _object_from_json(row["payload_json"])
    if not isinstance(raw_payload, Mapping):
        raw_payload = {}
    allowed_fields = _BUSINESS_EVENT_PAYLOAD_FIELDS.get(row["event_type"], ())
    sanitized_payload = {
        field_name: raw_payload[field_name]
        for field_name in allowed_fields
        if field_name in raw_payload
        and isinstance(raw_payload[field_name], (str, int, bool))
    }
    return ReviewBusinessEvent(
        event_id=row["event_id"],
        request_id=row["request_id"],
        event_type=row["event_type"],
        occurred_at=_timestamp_from_db(row["occurred_at"]),
        actor=AuditActor(
            actor_type=row["actor_type"],
            actor_id=row["actor_id"],
        ),
        correlation_id=row["correlation_id"],
        payload=sanitized_payload,
    )


def _event_query_fingerprint(request_id: str, query: ReviewEventQuery) -> str:
    payload = {
        "kind": "review_business_events",
        "page_size": query.page_size,
        "request_id": request_id,
        "sort": "occurred_at_asc",
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_value(value: Any) -> Any:
    """Convert immutable domain containers into a stable JSON value tree."""

    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return _decimal_to_db(value)
    if isinstance(value, datetime):
        return _timestamp_to_db(value)
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _object_from_json(raw: str | None) -> Any:
    if raw is None:
        return {}
    return json.loads(raw)


def _decimal_to_db(value: Decimal) -> str:
    return format(value, "f")


def _minor_units(value: Decimal) -> int:
    scaled = value * 100
    integral = scaled.to_integral_value()
    if scaled != integral:
        raise DomainValidationError("money must have at most two decimal places")
    result = int(integral)
    if not 0 <= result <= 9_223_372_036_854_775_807:
        raise DomainValidationError("money exceeds the supported database range")
    return result


def _queue_sort_sql(sort: ReviewQueueSort) -> tuple[str, str]:
    return {
        ReviewQueueSort.PENDING_OLDEST: ("rc.pending_since", "ASC"),
        ReviewQueueSort.PENDING_NEWEST: ("rc.pending_since", "DESC"),
        ReviewQueueSort.AMOUNT_ASC: ("r.claimed_amount_minor", "ASC"),
        ReviewQueueSort.AMOUNT_DESC: ("r.claimed_amount_minor", "DESC"),
        ReviewQueueSort.SUBMITTED_NEWEST: ("r.submitted_at", "DESC"),
    }[sort]


def _sort_value(row: sqlite3.Row, sort: ReviewQueueSort) -> str | int:
    if sort in {ReviewQueueSort.PENDING_OLDEST, ReviewQueueSort.PENDING_NEWEST}:
        return row["pending_since"]
    if sort in {ReviewQueueSort.AMOUNT_ASC, ReviewQueueSort.AMOUNT_DESC}:
        return row["claimed_amount_minor"]
    return row["submitted_at"]


def _queue_query_fingerprint(query: ReviewQueueQuery) -> str:
    payload = {
        "age_bucket": query.age_bucket.value if query.age_bucket is not None else None,
        "category": query.category,
        "max_amount_minor": (
            _minor_units(query.max_amount.amount) if query.max_amount is not None else None
        ),
        "min_amount_minor": (
            _minor_units(query.min_amount.amount) if query.min_amount is not None else None
        ),
        "page_size": query.page_size,
        "pending_before": (
            _timestamp_to_db(query.pending_before) if query.pending_before is not None else None
        ),
        "problem_code": query.problem_code,
        "search": query.search,
        "sort": query.sort.value,
        "submitted_from": (
            _timestamp_to_db(query.submitted_from) if query.submitted_from is not None else None
        ),
        "submitted_to": (
            _timestamp_to_db(query.submitted_to) if query.submitted_to is not None else None
        ),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    encoded = value.encode("ascii")
    padding = b"=" * ((4 - len(encoded) % 4) % 4)
    return base64.b64decode(encoded + padding, altchars=b"-_", validate=True)


def _timestamp_to_db(value: datetime) -> str:
    require_aware_datetime(value, "timestamp")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _timestamp_from_db(raw: str) -> datetime:
    value = datetime.fromisoformat(raw)
    require_aware_datetime(value, "stored timestamp")
    return value
