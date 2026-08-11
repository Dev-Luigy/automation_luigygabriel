import base64
import importlib
import json
import sys
from types import SimpleNamespace

from expense_agent.presentation.security import hash_password


def _http_api_event(*, host: str, authorization: str) -> dict[str, object]:
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/reviews",
        "rawQueryString": "",
        "headers": {
            "accept": "text/html",
            "authorization": authorization,
            "host": host,
            "x-forwarded-for": "203.0.113.10",
            "x-forwarded-port": "443",
            "x-forwarded-proto": "https",
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "assessment123",
            "domainName": host,
            "domainPrefix": "assessment123",
            "http": {
                "method": "GET",
                "path": "/reviews",
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.10",
                "userAgent": "pytest",
            },
            "requestId": "lambda-test-request",
            "routeKey": "$default",
            "stage": "$default",
            "time": "11/Aug/2026:12:00:00 +0000",
            "timeEpoch": 1_786_446_000_000,
        },
        "isBase64Encoded": False,
    }


def test_lambda_handler_serves_authenticated_review_ui(monkeypatch, tmp_path) -> None:
    host = "assessment123.execute-api.sa-east-1.amazonaws.com"
    password = "lambda-test-password"
    reviewers = [
        {
            "username": "reviewer",
            "reviewer_id": "assessment:reviewer",
            "email": "reviewer@example.com",
            "display_name": "Assessment Reviewer",
            "password_hash": hash_password(password, iterations=100_000),
        }
    ]
    monkeypatch.setenv("EXPENSE_AGENT_REVIEWERS_JSON", json.dumps(reviewers))
    monkeypatch.setenv("EXPENSE_AGENT_CSRF_SECRET", "lambda-test-csrf-secret-32-bytes-minimum")
    monkeypatch.setenv("EXPENSE_AGENT_DATABASE_PATH", str(tmp_path / "lambda.db"))
    monkeypatch.setenv("EXPENSE_AGENT_SQLITE_JOURNAL_MODE", "DELETE")
    monkeypatch.setenv("EXPENSE_AGENT_REQUIRE_HTTPS", "true")
    monkeypatch.setenv("EXPENSE_AGENT_ALLOWED_HOSTS", host)
    sys.modules.pop("expense_agent.presentation.lambda_handler", None)
    module = importlib.import_module("expense_agent.presentation.lambda_handler")
    basic = base64.b64encode(f"reviewer:{password}".encode()).decode()

    response = module.handler(
        _http_api_event(host=host, authorization=f"Basic {basic}"),
        SimpleNamespace(),
    )

    assert response["statusCode"] == 200
    assert "Human review workspace" in response["body"]
    assert response["headers"]["content-security-policy"].startswith("default-src 'none'")
    assert response["headers"]["strict-transport-security"].startswith("max-age=")
