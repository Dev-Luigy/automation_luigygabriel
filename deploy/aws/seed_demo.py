#!/usr/bin/env python3
"""Seed the three provided synthetic assignment samples through the deployed HTTPS API."""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from getpass import getpass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_ROOT / "examples" / "sample_requests.json"
MAX_RESPONSE_BYTES = 1_048_576
MANAGED_REFERENCE_PATTERN = re.compile(r"^evidence:att_[0-9a-f]{32}$")


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


HTTPS_OPENER = build_opener(_NoRedirectHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", default="reviewer")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--password-stdin", action="store_true")
    arguments = parser.parse_args(argv)
    base_url = _validated_base_url(arguments.base_url)
    password = (
        sys.stdin.readline().rstrip("\r\n")
        if arguments.password_stdin
        else getpass("Reviewer password: ")
    )
    if not password:
        raise SystemExit("Reviewer password must not be empty.")
    basic = base64.b64encode(f"{arguments.username}:{password}".encode()).decode("ascii")
    common_headers = {
        "Authorization": f"Basic {basic}",
        "User-Agent": "expense-agent-sandbox-seeder/1.0",
    }
    session = _json_request(f"{base_url}/api/session", headers=common_headers)
    if session is None:  # Required requests never convert a 404 into None.
        raise AssertionError("session request unexpectedly returned no payload")
    csrf_token = session.get("csrf_token")
    if not isinstance(csrf_token, str) or not csrf_token:
        raise SystemExit("The deployed API did not return a CSRF token.")
    samples = json.loads(arguments.dataset.read_text(encoding="utf-8"))
    if not isinstance(samples, list) or not samples:
        raise SystemExit("The sample dataset must be a non-empty JSON array.")

    for sample in samples:
        if not isinstance(sample, dict) or not isinstance(sample.get("request_id"), str):
            raise SystemExit("Every sample must be an object with a string request_id.")
        request_id = sample["request_id"]
        existing = _json_request(
            f"{base_url}/api/requests/{quote(request_id, safe='')}",
            headers=common_headers,
            allow_not_found=True,
        )
        if existing is not None:
            print(
                f"{request_id}: {existing.get('status', 'unknown')} "
                "(created=False, replayed=True)"
            )
            continue

        uploaded = _json_request(
            f"{base_url}/api/attachments",
            method="POST",
            headers={
                **common_headers,
                "Content-Type": "application/pdf",
                "Origin": base_url,
                "X-Attachment-Filename": "synthetic-assessment-receipt.pdf",
                "X-CSRF-Token": csrf_token,
                "X-Correlation-ID": f"aws-seed-attachment-{request_id}",
            },
            body=_synthetic_receipt_pdf(),
        )
        if uploaded is None:  # Required requests never convert a 404 into None.
            raise AssertionError("attachment upload unexpectedly returned no payload")
        reference = uploaded.get("reference")
        if not isinstance(reference, str) or MANAGED_REFERENCE_PATTERN.fullmatch(reference) is None:
            raise SystemExit("The deployed API returned an invalid managed attachment reference.")

        payload = dict(sample)
        payload["attachments"] = [reference]
        result = _json_request(
            f"{base_url}/api/requests",
            method="POST",
            headers={
                **common_headers,
                "Content-Type": "application/json",
                "Origin": base_url,
                "X-CSRF-Token": csrf_token,
                "X-Correlation-ID": f"aws-seed-intake-{request_id}",
            },
            body=json.dumps(payload, separators=(",", ":")).encode(),
        )
        if result is None:  # Required requests never convert a 404 into None.
            raise AssertionError("intake request unexpectedly returned no payload")
        print(
            f"{request_id}: {result.get('status', 'unknown')} "
            f"(created={result.get('created', False)}, replayed={result.get('replayed', False)})"
        )
    return 0


def _validated_base_url(value: str) -> str:
    normalized = value.rstrip("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise SystemExit("--base-url must be an HTTPS origin without credentials or a path.")
    return normalized


def _json_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str],
    body: bytes | None = None,
    allow_not_found: bool = False,
) -> dict[str, Any] | None:
    if urlsplit(url).scheme != "https":
        raise SystemExit("Refusing to send sandbox credentials over a non-HTTPS URL.")
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with HTTPS_OPENER.open(request, timeout=30) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        if allow_not_found and exc.code == 404:
            discarded = exc.read(MAX_RESPONSE_BYTES + 1)
            if len(discarded) > MAX_RESPONSE_BYTES:
                raise SystemExit("The deployed API returned an unexpectedly large response.")
            return None
        detail = exc.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")
        raise SystemExit(f"API request failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"Could not reach the deployed API: {exc.reason}") from exc
    if len(payload) > MAX_RESPONSE_BYTES:
        raise SystemExit("The deployed API returned an unexpectedly large response.")
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit("The deployed API returned invalid JSON.") from exc
    if not isinstance(decoded, dict):
        raise SystemExit("The deployed API returned an unexpected JSON shape.")
    return decoded


def _synthetic_receipt_pdf() -> bytes:
    """Build one valid blank-page PDF containing only synthetic assessment metadata."""

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    objects = (
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] /Resources << >> >>\nendobj\n"
        ),
        (
            b"4 0 obj\n<< /Producer (Expense Agent sandbox seeder) "
            b"/Title (Synthetic assessment receipt) >>\nendobj\n"
        ),
    )
    document = bytearray(header)
    offsets: list[int] = []
    for item in objects:
        offsets.append(len(document))
        document.extend(item)

    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 4 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(document)


if __name__ == "__main__":
    raise SystemExit(main())
