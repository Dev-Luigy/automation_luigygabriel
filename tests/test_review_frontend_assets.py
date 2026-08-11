import re
from pathlib import Path

STATIC_ROOT = (
    Path(__file__).parents[1]
    / "src"
    / "expense_agent"
    / "presentation"
    / "static"
)


def _asset(name: str) -> str:
    return (STATIC_ROOT / name).read_text(encoding="utf-8")


def _catalog_keys(javascript: str) -> list[set[str]]:
    blocks = re.findall(
        r'^  (?:en|"pt-BR"|es): \{\n(.*?)^  \},$',
        javascript,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert len(blocks) == 3
    return [
        set(re.findall(r"^    ([A-Za-z][A-Za-z0-9]*):", block, flags=re.MULTILINE))
        for block in blocks
    ]


def test_review_console_has_bounded_server_side_discovery_controls() -> None:
    html = _asset("reviews.html")
    javascript = _asset("reviews.js")

    for query_parameter in (
        "search",
        "category",
        "problem_code",
        "min_amount",
        "max_amount",
        "submitted_from",
        "submitted_to",
        "age_bucket",
        "sort",
        "limit",
        "cursor",
    ):
        assert f'["{query_parameter}",' in javascript

    assert 'name="category" type="text"' in html
    assert 'value="client_meal"' in html
    assert 'name="problem_code" type="text"' in html
    assert "cursorHistory.push(state.cursor)" in javascript
    assert "state.cursorHistory.pop()" in javascript
    assert ".map((key) => [key, state.filters[key]])" in javascript
    assert 'value="100"' in html
    assert "}, 350);" in javascript
    assert 'type="checkbox"' not in html
    assert "bulk" not in html.lower()


def test_review_console_supports_all_languages_with_catalog_key_parity() -> None:
    html = _asset("reviews.html")
    javascript = _asset("reviews.js")

    english, portuguese, spanish = _catalog_keys(javascript)
    assert english == portuguese == spanish
    assert len(english) >= 150

    html_keys = set(
        re.findall(
            r'data-i18n(?:-placeholder|-aria-label|-title|-label)?="([^"]+)"',
            html,
        )
    )
    assert html_keys <= english
    assert 'option value="pt-BR"' in html
    assert 'option value="en"' in html
    assert 'option value="es"' in html
    assert "navigator.languages" in javascript
    assert 'document.documentElement.lang = state.language' in javascript


def test_review_console_preserves_evidence_and_uses_safe_browser_state() -> None:
    html = _asset("reviews.html")
    javascript = _asset("reviews.js")

    assert "textContent" in javascript
    assert "innerHTML" not in javascript
    assert "local" + "Storage" not in javascript
    assert "session" + "Storage" not in javascript
    assert "caseData.raw_ocr_text" in javascript
    assert "problem.message" in javascript
    assert "rule.message" in javascript
    assert 'if (value !== null && value !== undefined) node.textContent = value;' in javascript
    assert "body?.detail" not in javascript
    assert 'data-i18n="originalLanguage"' in html
    assert 'data-i18n="attachmentLimitation"' in html
    assert 'attachment?.kind === "managed_evidence"' in javascript
    assert "action.href = attachment.open_url" in javascript
    assert 'action.rel = "noopener"' in javascript
    assert 'action.target = "_blank"' in javascript
    assert "innerHTML" not in javascript


def test_review_console_blocks_approval_when_a_mandatory_rejection_rule_applies() -> None:
    html = _asset("reviews.html")
    javascript = _asset("reviews.js")

    assert 'id="mandatory-rejection-notice"' in html
    assert 'data-i18n="mandatoryRejectionNotice"' in html
    assert 'rule?.outcome === "reject"' in javascript
    assert 'outcome === "approved" && hasMandatoryRejection()' in javascript
    assert 'busy || hasMandatoryRejection()' in javascript


def test_review_console_hides_decision_controls_by_role_and_retries_one_command_key() -> None:
    javascript = _asset("reviews.js")

    assert 'state.roles.includes("reviewer") || state.roles.includes("admin")' in javascript
    assert "const showDecisionControls = isPending && canRecordDecision();" in javascript
    assert 'elements["decision-panel"].hidden = !showDecisionControls;' in javascript
    assert "decisionNav.hidden = !showDecisionControls;" in javascript
    assert "|| !canRecordDecision()" in javascript

    submit_code = javascript[
        javascript.index("async function submitDecision") : javascript.index(
            "function rerenderForLanguage"
        )
    ]
    assert submit_code.count("crypto.randomUUID()") == 1
    assert '"Idempotency-Key": decisionCommand.idempotencyKey' in submit_code
    assert '"If-Match": decisionCommand.etag' in submit_code
    assert submit_code.count("await sendDecision()") == 2


def test_review_console_has_no_dead_product_navigation_and_one_queue_table() -> None:
    html = _asset("reviews.html")

    hrefs = re.findall(r'href="([^"]+)"', html)
    assert hrefs
    assert all(href.startswith(("#", "/assets/")) for href in hrefs)
    assert html.count('<table class="queue-table">') == 1
    assert "RecargaPay" not in html
    assert "ClickUp" not in html


def test_queue_renderer_is_backward_compatible_and_has_distinct_states() -> None:
    html = _asset("reviews.html")
    javascript = _asset("reviews.js")

    assert "Array.isArray(body)" in javascript
    assert "Array.isArray(body?.items)" in javascript
    assert "summary.urgent_pending ?? summary.over_24h" in javascript
    for state_id in ("queue-loading", "queue-error", "queue-empty", "queue-results"):
        assert f'id="{state_id}"' in html
    for view_id in ("table-view", "card-view", "case-dialog"):
        assert f'id="{view_id}"' in html


def test_business_timeline_is_bounded_localized_and_excludes_technical_trace() -> None:
    html = _asset("reviews.html")
    javascript = _asset("reviews.js")

    assert 'href="#timeline-section"' in html
    assert 'data-i18n="businessTimeline"' in html
    for state_id in (
        "timeline-loading",
        "timeline-error",
        "timeline-empty",
        "timeline-content",
    ):
        assert f'id="{state_id}"' in html
    assert 'id="timeline-list"' in html
    assert 'id="retry-timeline"' in html
    assert 'id="timeline-load-more"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-busy="false"' in html

    assert 'new URLSearchParams({ limit: "25" })' in javascript
    assert 'params.set("cursor", cursor)' in javascript
    assert '/events?${params.toString()}' in javascript
    assert "event?.event_type" in javascript
    assert "event?.actor?.type" in javascript
    assert "event?.actor?.id" in javascript
    assert "appendUniqueTimelineEvents" in javascript
    assert 'append: true' in javascript
    assert 'state.timelinePage?.next_cursor' in javascript
    submit_code = javascript[
        javascript.index("async function submitDecision") : javascript.index(
            "function rerenderForLanguage"
        )
    ]
    assert "loadCase(requestId)" in submit_code
    assert "loadQueue({ announceResult: false })" in submit_code
    assert 'elements["case-dialog"].close()' not in submit_code

    whitelist = re.search(
        r"const businessPayloadFields = Object\.freeze\(\[(.*?)\]\);",
        javascript,
        flags=re.DOTALL,
    )
    assert whitelist is not None
    fields = set(re.findall(r'"([a-z_]+)"', whitelist.group(1)))
    assert fields == {
        "from_status",
        "to_status",
        "outcome",
        "reason",
        "request_version",
        "policy_version",
        "route",
        "decision_id",
        "automated_decision_id",
        "extraction_status",
        "attachment_count",
    }
    assert not fields & {
        "raw_response",
        "prompt_hash",
        "input_hash",
        "parameters",
        "provider",
        "model",
    }

    timeline_code = javascript[
        javascript.index("function renderBusinessEvent") : javascript.index(
            "function renderAttachments"
        )
    ]
    assert "textElement" in timeline_code
    assert ".textContent" in timeline_code
    assert "innerHTML" not in timeline_code
    assert "raw_response" not in timeline_code
