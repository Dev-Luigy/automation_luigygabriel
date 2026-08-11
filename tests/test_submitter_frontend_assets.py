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


def test_submitter_portal_has_one_original_and_no_editable_identity() -> None:
    html = _asset("submit.html")

    assert '<form id="submission-form"' in html
    assert html.count('type="file"') == 1
    assert 'accept="image/jpeg,image/png,application/pdf"' in html
    assert 'type="file"' in html and ' multiple' not in html
    assert 'id="submitted-by"' in html
    assert 'name="submitted_by"' not in html
    assert 'id="raw-ocr-text"' in html
    assert '<option value="transportation" data-i18n="categoryTransport">' in html
    assert '<option value="transport"' not in html
    assert 'data-i18n="ocrAssessmentInput"' in html
    assert 'data-i18n="ocrAssessmentHelp"' in html
    assert 'id="tracking-request-id"' in html
    submit_javascript = _asset("submit.js")
    assert "randomHex(32)" in submit_javascript
    assert "crypto.getRandomValues(bytes)" in submit_javascript
    assert "crypto.randomUUID()" not in submit_javascript
    assert "REQ-20260811-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" in html
    assert 'pattern="[A-Za-z0-9][A-Za-z0-9._:-]{0,127}"' in html


def test_submitter_portal_uses_same_origin_authenticated_upload_and_strict_intake() -> None:
    javascript = _asset("submit.js")

    assert 'new URL(path, window.location.origin)' in javascript
    assert 'target.origin !== window.location.origin' in javascript
    assert 'credentials: "same-origin"' in javascript
    assert 'api("/api/session")' in javascript
    assert 'api("/api/attachments", {' in javascript
    assert '"X-Attachment-Filename": safeAttachmentFilename(file)' in javascript
    assert '"X-CSRF-Token": state.csrfToken' in javascript
    assert '"Content-Type": file.type' in javascript
    assert "the browser emits the protected Origin header itself" in javascript
    assert "body: file" in javascript
    assert "payload?.reference ?? payload?.attachment?.reference" in javascript
    assert "attachmentReferencePattern.test(reference)" in javascript

    assert 'api("/api/requests", {' in javascript
    assert '"Content-Type": "application/json"' in javascript
    assert "submitted_by: state.principal.email" in javascript
    assert "submitted_at: state.submittedAt" in javascript
    assert "claimed_amount_brl: values.amount" in javascript
    assert "attachments: [reference]" in javascript
    assert "body: JSON.stringify(payload)" in javascript
    assert "new Date().toISOString()" in javascript


def test_submitter_portal_lookup_is_exact_all_status_and_retry_safe() -> None:
    html = _asset("submit.html")
    javascript = _asset("submit.js")

    assert 'data-i18n="trackerDescription"' in html
    assert "`/api/requests/${encodeURIComponent(normalized)}`" in javascript
    assert "recoverAmbiguousSubmission" in javascript
    assert "`/api/requests/${encodeURIComponent(requestId)}`" in javascript
    assert "if (!state.submittedAt) state.submittedAt = new Date().toISOString();" in javascript
    assert "state.uploaded?.signature === signature" in javascript
    assert 'source === "replay"' in javascript


def test_submitter_portal_has_trilingual_catalog_parity() -> None:
    html = _asset("submit.html")
    javascript = _asset("submit.js")

    english, portuguese, spanish = _catalog_keys(javascript)
    assert english == portuguese == spanish
    assert len(english) >= 100

    catalog_blocks = re.findall(
        r'^  (?:en|"pt-BR"|es): \{\n(.*?)^  \},$',
        javascript,
        flags=re.MULTILINE | re.DOTALL,
    )
    for block in catalog_blocks:
        keys = re.findall(r"^    ([A-Za-z][A-Za-z0-9]*):", block, flags=re.MULTILINE)
        assert len(keys) == len(set(keys))

    html_keys = set(
        re.findall(
            r'data-i18n(?:-placeholder|-aria-label)?="([^"]+)"',
            html,
        )
    )
    assert html_keys <= english
    assert '<option value="pt-BR">' in html
    assert '<option value="en">' in html
    assert '<option value="es">' in html
    assert "navigator.languages" in javascript
    assert "document.documentElement.lang = state.language" in javascript
    assert "function renderIdentity()" in javascript
    assert "renderIdentity();" in javascript
    assert 'elements["identity-name"].textContent = state.principal.displayName' in javascript


def test_submitter_portal_renders_api_values_as_bounded_text() -> None:
    javascript = _asset("submit.js")

    assert ".textContent" in javascript
    assert "document.createElement" in javascript
    assert "safeText(reason.message, 1000)" in javascript
    assert "collectReasons(result)" in javascript
    assert "formatExactMoney" in javascript
    assert "claimed_amount_brl: values.amount" in javascript
    assert "inner" + "HTML" not in javascript
    assert "local" + "Storage" not in javascript
    assert "session" + "Storage" not in javascript
    assert "eval(" not in javascript
    assert "new Function" not in javascript


def test_submitter_portal_is_accessible_responsive_and_dependency_free() -> None:
    html = _asset("submit.html")
    css = _asset("submit.css")

    assert '<a class="skip-link" href="#submission-form"' in html
    assert 'aria-live="polite"' in html
    assert 'role="alert"' in html
    assert 'autocomplete="off"' in html
    assert '<script type="module" src="/assets/submit.js"></script>' in html
    assert '<link rel="stylesheet" href="/assets/submit.css">' in html
    assert "<script>" not in html
    assert "<style" not in html
    assert "http://" not in html and "https://" not in html
    assert "@media (max-width: 700px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
