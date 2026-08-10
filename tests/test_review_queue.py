import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from expense_agent.application.review import (
    PendingAgeBucket,
    ReviewProblem,
    ReviewQueueQuery,
    ReviewQueueSort,
    ReviewService,
)
from expense_agent.domain import (
    AutomatedDecision,
    DecisionReason,
    ExtractionResult,
    ExtractionStatus,
    ModelInvocationTrace,
    Money,
    PolicyDecisionRoute,
    ReceiptFacts,
    ReimbursementCase,
    ReimbursementSubmission,
    RuleEvaluation,
    RuleOutcome,
)
from expense_agent.domain.exceptions import DomainValidationError
from expense_agent.infrastructure.review import SqliteReviewRepository
from expense_agent.presentation.app import create_app
from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    ReviewerCredential,
    hash_password,
)

AS_OF = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)


def _add_case(
    repository: SqliteReviewRepository,
    *,
    request_id: str,
    submitted_by: str,
    submitted_at: datetime,
    pending_since: datetime,
    amount: str,
    extracted_amount: str,
    category: str,
    merchant: str,
    problem_codes: tuple[str, ...],
) -> None:
    submission = ReimbursementSubmission(
        request_id=request_id,
        submitted_by=submitted_by,
        submitted_at=submitted_at,
        raw_ocr_text=f"{merchant} TOTAL {extracted_amount}",
        claimed_category=category,
        claimed_amount=Money.brl(amount),
    )
    automated = AutomatedDecision(
        decision_id=f"AUTO-{request_id}",
        request_id=request_id,
        route=PolicyDecisionRoute.HUMAN_REVIEW,
        decided_at=pending_since,
        policy_version="policy-test-v1",
        reasons=tuple(
            DecisionReason(code=code, message=f"Original evidence for {code}")
            for code in problem_codes
        ),
        rule_evaluations=(
            RuleEvaluation(
                rule_id="review-required",
                rule_version="1",
                outcome=RuleOutcome.REVIEW,
                message="Review required",
            ),
        ),
    )
    case = ReimbursementCase(submission=submission, opened_at=submitted_at)
    case.start_processing()
    case.record_automated_decision(automated)
    extraction = ExtractionResult(
        request_id=request_id,
        status=ExtractionStatus.SUCCEEDED,
        trace=ModelInvocationTrace(
            provider="test-ocr",
            model="test-model",
            prompt_version="v1",
            prompt_hash=f"prompt-{request_id}",
            input_hash=f"input-{request_id}",
            raw_response="original response",
            invoked_at=pending_since,
            duration_ms=10,
        ),
        facts=ReceiptFacts(
            total=Money.brl(extracted_amount),
            category=category,
            merchant_name=merchant,
        ),
    )
    repository.add_pending_case(
        case,
        extraction=extraction,
        problems=tuple(
            ReviewProblem(code=code, message=f"Original evidence for {code}")
            for code in problem_codes
        ),
    )


def _seed_filter_cases(repository: SqliteReviewRepository) -> None:
    _add_case(
        repository,
        request_id="REQ-ALPHA",
        submitted_by="alice@example.com",
        submitted_at=AS_OF - timedelta(days=3),
        pending_since=AS_OF - timedelta(hours=25),
        amount="100.00",
        extracted_amount="90.00",
        category="meals",
        merchant="Cafe Central",
        problem_codes=("TOTAL_MISMATCH", "LOW_CONTRAST"),
    )
    _add_case(
        repository,
        request_id="REQ-BRAVO",
        submitted_by="bob@example.com",
        submitted_at=AS_OF - timedelta(days=2),
        pending_since=AS_OF - timedelta(hours=5),
        amount="2000.00",
        extracted_amount="2000.00",
        category="lodging",
        merchant="Hotel Norte",
        problem_codes=("POLICY_EVIDENCE",),
    )
    _add_case(
        repository,
        request_id="REQ-CHARLIE",
        submitted_by="carol@example.com",
        submitted_at=AS_OF - timedelta(days=1),
        pending_since=AS_OF - timedelta(hours=2),
        amount="2000.01",
        extracted_amount="1999.99",
        category="transport",
        merchant="Taxi Sul",
        problem_codes=("AMOUNT_MISMATCH",),
    )


def _ids(repository: SqliteReviewRepository, query: ReviewQueueQuery) -> list[str]:
    return [item.request_id for item in repository.search_pending(query, as_of=AS_OF).items]


def test_queue_filters_enrichment_and_global_summary(tmp_path) -> None:
    repository = SqliteReviewRepository(tmp_path / "queue.db")
    _seed_filter_cases(repository)

    page = repository.search_pending(ReviewQueueQuery(), as_of=AS_OF)

    assert [item.request_id for item in page.items] == [
        "REQ-ALPHA",
        "REQ-BRAVO",
        "REQ-CHARLIE",
    ]
    alpha = page.items[0]
    assert alpha.merchant_name == "Cafe Central"
    assert alpha.extracted_amount == Money.brl("90.00")
    assert alpha.primary_problem is not None
    assert alpha.primary_problem.code == "TOTAL_MISMATCH"
    assert alpha.primary_problem.message == "Original evidence for TOTAL_MISMATCH"
    assert alpha.problem_codes == ("TOTAL_MISMATCH", "LOW_CONTRAST")
    assert page.summary.total_pending == 3
    assert page.summary.over_24h == 1
    assert page.summary.high_value == 1
    assert page.summary.amount_mismatch == 2
    assert page.summary.high_value_threshold == Money.brl("2000.00")

    assert _ids(repository, ReviewQueueQuery(search="req-al")) == ["REQ-ALPHA"]
    assert _ids(repository, ReviewQueueQuery(search="ali")) == ["REQ-ALPHA"]
    assert _ids(repository, ReviewQueueQuery(search="Cafe")) == ["REQ-ALPHA"]
    assert _ids(repository, ReviewQueueQuery(category="LODGING")) == ["REQ-BRAVO"]
    assert _ids(repository, ReviewQueueQuery(problem_code="low_contrast")) == ["REQ-ALPHA"]
    assert _ids(
        repository,
        ReviewQueueQuery(min_amount=Money.brl("2000.00"), max_amount=Money.brl("2000.00")),
    ) == ["REQ-BRAVO"]
    assert _ids(repository, ReviewQueueQuery(max_amount=Money.brl("100.00"))) == ["REQ-ALPHA"]
    assert _ids(
        repository,
        ReviewQueueQuery(
            submitted_from=AS_OF - timedelta(days=2, hours=1),
            submitted_to=AS_OF - timedelta(days=1, hours=23),
        ),
    ) == ["REQ-BRAVO"]
    assert _ids(
        repository,
        ReviewQueueQuery(age_bucket=PendingAgeBucket.OVER_24H),
    ) == ["REQ-ALPHA"]
    assert _ids(
        repository,
        ReviewQueueQuery(age_bucket=PendingAgeBucket.BETWEEN_4H_AND_24H),
    ) == ["REQ-BRAVO"]
    assert _ids(
        repository,
        ReviewQueueQuery(age_bucket=PendingAgeBucket.UNDER_4H),
    ) == ["REQ-CHARLIE"]
    assert _ids(
        repository,
        ReviewQueueQuery(pending_before=AS_OF - timedelta(hours=20)),
    ) == ["REQ-ALPHA"]


@pytest.mark.parametrize(
    ("sort", "expected"),
    (
        (
            ReviewQueueSort.PENDING_OLDEST,
            ["REQ-ALPHA", "REQ-BRAVO", "REQ-CHARLIE"],
        ),
        (
            ReviewQueueSort.PENDING_NEWEST,
            ["REQ-CHARLIE", "REQ-BRAVO", "REQ-ALPHA"],
        ),
        (ReviewQueueSort.AMOUNT_ASC, ["REQ-ALPHA", "REQ-BRAVO", "REQ-CHARLIE"]),
        (ReviewQueueSort.AMOUNT_DESC, ["REQ-CHARLIE", "REQ-BRAVO", "REQ-ALPHA"]),
        (
            ReviewQueueSort.SUBMITTED_NEWEST,
            ["REQ-CHARLIE", "REQ-BRAVO", "REQ-ALPHA"],
        ),
    ),
)
def test_all_queue_sorts_are_deterministic(tmp_path, sort, expected) -> None:
    repository = SqliteReviewRepository(tmp_path / f"sort-{sort.value}.db")
    _seed_filter_cases(repository)

    assert _ids(repository, ReviewQueueQuery(sort=sort)) == expected


def test_stable_sort_and_cursor_pagination_have_no_duplicates(tmp_path) -> None:
    database_path = tmp_path / "pages.db"
    repository = SqliteReviewRepository(database_path)
    for index in range(23):
        _add_case(
            repository,
            request_id=f"REQ-{index:03d}",
            submitted_by=f"employee-{index:03d}@example.com",
            submitted_at=AS_OF - timedelta(days=index % 4),
            pending_since=AS_OF - timedelta(minutes=index + 1),
            amount=f"{(index % 5) * 10 + 9}.99",
            extracted_amount=f"{(index % 5) * 10 + 9}.99",
            category="meals",
            merchant=f"Merchant {index:03d}",
            problem_codes=("POLICY_EVIDENCE",),
        )

    query = ReviewQueueQuery(sort=ReviewQueueSort.AMOUNT_DESC, page_size=10)
    first = repository.search_pending(query, as_of=AS_OF)
    assert first.has_more is True
    assert first.next_cursor is not None

    # A normal new arrival after page one must not enter the frozen cursor traversal.
    _add_case(
        repository,
        request_id="REQ-NEW",
        submitted_by="new@example.com",
        submitted_at=AS_OF + timedelta(seconds=1),
        pending_since=AS_OF + timedelta(seconds=1),
        amount="9999.99",
        extracted_amount="9999.99",
        category="meals",
        merchant="New Merchant",
        problem_codes=("POLICY_EVIDENCE",),
    )

    all_ids = [item.request_id for item in first.items]
    cursor = first.next_cursor
    while cursor is not None:
        page = repository.search_pending(replace(query, cursor=cursor), as_of=AS_OF + timedelta(days=1))
        all_ids.extend(item.request_id for item in page.items)
        cursor = page.next_cursor

    assert len(all_ids) == 23
    assert len(set(all_ids)) == 23
    assert "REQ-NEW" not in all_ids
    expected = sorted(
        (f"REQ-{index:03d}" for index in range(23)),
        key=lambda request_id: (
            -(((int(request_id[-3:]) % 5) * 10 + 9) * 100 + 99),
            request_id,
        ),
    )
    assert all_ids == expected

    # The HMAC key is persisted, so an in-flight cursor survives an adapter restart.
    restarted = SqliteReviewRepository(database_path)
    assert restarted.search_pending(
        replace(query, cursor=first.next_cursor),
        as_of=AS_OF,
    ).items

    with pytest.raises(DomainValidationError, match="cursor"):
        repository.search_pending(
            replace(query, sort=ReviewQueueSort.AMOUNT_ASC, cursor=first.next_cursor),
            as_of=AS_OF,
        )
    assert first.next_cursor is not None
    payload, signature = first.next_cursor.split(".")
    tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(DomainValidationError, match="cursor"):
        repository.search_pending(
            replace(query, cursor=f"{payload}.{tampered_signature}"),
            as_of=AS_OF,
        )


def test_search_finds_a_case_outside_the_first_unfiltered_page(tmp_path) -> None:
    repository = SqliteReviewRepository(tmp_path / "cross-page-search.db")
    for index in range(15):
        _add_case(
            repository,
            request_id=f"REQ-CROSS-PAGE-{index:02d}",
            submitted_by=f"employee-{index:02d}@example.com",
            submitted_at=AS_OF - timedelta(minutes=index + 1),
            pending_since=AS_OF - timedelta(minutes=100 - index),
            amount="50.00",
            extracted_amount="50.00",
            category="meals",
            merchant=f"Merchant {index:02d}",
            problem_codes=("POLICY_EVIDENCE",),
        )

    first_page = repository.search_pending(
        ReviewQueueQuery(page_size=10),
        as_of=AS_OF,
    )
    target_request_id = "REQ-CROSS-PAGE-14"

    assert target_request_id not in {item.request_id for item in first_page.items}
    search_page = repository.search_pending(
        ReviewQueueQuery(search=target_request_id, page_size=10),
        as_of=AS_OF,
    )
    assert [item.request_id for item in search_page.items] == [target_request_id]


def _web_client(repository: SqliteReviewRepository) -> TestClient:
    credential = ReviewerCredential(
        username="reviewer",
        reviewer_id="directory:42",
        email="reviewer@example.com",
        display_name="Review Manager",
        password_hash=hash_password("secret-pass", iterations=100_000),
    )
    app = create_app(
        review_service=ReviewService(repository, clock=lambda: AS_OF),
        authenticator=BasicAuthenticator((credential,)),
        csrf=CsrfProtector("test-csrf-secret-that-is-long-enough"),
        require_https=True,
        allowed_hosts=("testserver",),
    )
    return TestClient(app, base_url="https://testserver")


def test_queue_http_contract_and_invalid_inputs(tmp_path) -> None:
    repository = SqliteReviewRepository(tmp_path / "web-queue.db")
    _seed_filter_cases(repository)
    client = _web_client(repository)
    headers = {"Authorization": "Basic cmV2aWV3ZXI6c2VjcmV0LXBhc3M="}

    response = client.get(
        "/api/reviews",
        params={"sort": "amount_desc", "limit": 10, "category": "meals"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == {
        "limit": 10,
        "sort": "amount_desc",
        "has_more": False,
        "next_cursor": None,
    }
    assert payload["items"][0]["merchant_name"] == "Cafe Central"
    assert payload["items"][0]["extracted_amount"] == {
        "amount": "90.00",
        "currency": "BRL",
    }
    assert payload["items"][0]["primary_problem"]["code"] == "TOTAL_MISMATCH"
    assert payload["items"][0]["problem_codes"] == ["TOTAL_MISMATCH", "LOW_CONTRAST"]
    assert payload["summary"]["scope"] == "all_pending"
    assert payload["summary"]["total_pending"] == 3
    assert payload["summary"]["high_value_threshold"]["amount"] == "2000.00"

    invalid_queries = (
        {"limit": "9"},
        {"limit": "101"},
        {"age_bucket": "old"},
        {"min_amount": "10.01", "max_amount": "10.00"},
        {"min_amount": "1.001"},
        {"submitted_from": "2026-08-01T00:00:00"},
        {"pending_before": AS_OF.isoformat(), "age_bucket": "over_24h"},
        {"cursor": "not-a-signed-cursor"},
        {"unknown_filter": "value"},
    )
    for params in invalid_queries:
        invalid = client.get("/api/reviews", params=params, headers=headers)
        assert invalid.status_code == 422, (params, invalid.text)


def test_minor_unit_migration_and_queue_indexes(tmp_path) -> None:
    database_path = Path(tmp_path) / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE reimbursements (
                request_id TEXT PRIMARY KEY,
                submitted_by TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                raw_ocr_text TEXT NOT NULL,
                claimed_category TEXT NOT NULL,
                claimed_amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL
            );
            CREATE TABLE extractions (
                request_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                receipt_date TEXT,
                total_amount TEXT,
                total_currency TEXT,
                category TEXT,
                merchant_name TEXT,
                tax_id TEXT,
                evidence_json TEXT,
                warnings_json TEXT,
                error TEXT
            );
            INSERT INTO reimbursements VALUES (
                'LEGACY-1', 'legacy@example.com', '2026-08-01T00:00:00+00:00',
                'OCR', 'meals', '10.05', 'BRL', '2026-08-01T00:00:00+00:00',
                'pending_review', 1
            );
            INSERT INTO extractions VALUES (
                'LEGACY-1', 'succeeded', NULL, '9.99', 'BRL', 'meals',
                'Legacy Merchant', NULL, '{}', '[]', NULL
            );
            """
        )

    repository = SqliteReviewRepository(database_path)

    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute(
            "SELECT claimed_amount_minor FROM reimbursements WHERE request_id = 'LEGACY-1'"
        ).fetchone() == (1005,)
        assert connection.execute(
            "SELECT total_amount_minor FROM extractions WHERE request_id = 'LEGACY-1'"
        ).fetchone() == (999,)
        reimbursement_indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(reimbursements)")
        }
        problem_indexes = {row[1] for row in connection.execute("PRAGMA index_list(review_problems)")}
        assert "idx_reimbursements_queue_amount" in reimbursement_indexes
        assert "idx_reimbursements_queue_submitted" in reimbursement_indexes
        assert "idx_review_problems_code_request" in problem_indexes
        plan = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT request_id FROM reimbursements
            WHERE status = 'pending_review' AND claimed_amount_minor > 100
            ORDER BY claimed_amount_minor, request_id LIMIT 10
            """
        ).fetchall()
    assert any("idx_reimbursements_queue_amount" in row[3] for row in plan)
