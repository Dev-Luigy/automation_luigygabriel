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

_HIGH_VALUE_THRESHOLD = Money.brl("2000.00")
_AMOUNT_MISMATCH_CODES = ("AMOUNT_MISMATCH", "TOTAL_MISMATCH")
_BUSINESS_EVENT_PAYLOAD_FIELDS = {
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

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        if str(self.database_path) == ":memory:":
            raise ValueError("use a file-backed SQLite database for the review repository")
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_schema()

    def initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            self._migrate_minor_unit_columns(connection)
            connection.executescript(_QUEUE_SCHEMA)
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
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO reimbursements (
                    request_id, submitted_by, submitted_at, raw_ocr_text,
                    claimed_category, claimed_amount, claimed_amount_minor, currency,
                    opened_at, status, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    submission.request_id,
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
            if extraction is not None:
                self._insert_extraction(connection, extraction)
            self._insert_automated_decision(connection, automated_decision)
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
            where = ["request_id = ?"]
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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=5,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    @staticmethod
    def _insert_audit_event(
        connection: sqlite3.Connection,
        audit_event: AuditEvent,
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events (
                event_id, request_id, event_type, occurred_at, actor_type,
                actor_id, correlation_id, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_event.event_id,
                audit_event.request_id,
                audit_event.event_type,
                _timestamp_to_db(audit_event.occurred_at),
                audit_event.actor.actor_type,
                audit_event.actor.actor_id,
                audit_event.correlation_id,
                _canonical_json(audit_event.payload),
            ),
        )

    @staticmethod
    def _insert_extraction(
        connection: sqlite3.Connection,
        extraction: ExtractionResult,
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
                request_id, status, receipt_date, total_amount, total_amount_minor,
                total_currency, category, merchant_name, tax_id, evidence_json,
                warnings_json, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                extraction.request_id,
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
    ) -> None:
        connection.execute(
            """
            INSERT INTO automated_decisions (
                decision_id, request_id, route, decided_at, policy_version
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                decision.decision_id,
                decision.request_id,
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
