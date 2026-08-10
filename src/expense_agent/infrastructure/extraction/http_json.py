"""Optional bounded HTTP+JSON extraction adapter using the standard library."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter_ns
from types import MappingProxyType
from typing import Any, Protocol, Self
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from expense_agent.domain import ExtractionResult, ExtractionStatus, ReimbursementSubmission
from expense_agent.infrastructure.extraction._support import (
    DEFAULT_PROMPT,
    PROMPT_VERSION,
    ResponseValidationError,
    build_trace,
    parse_response_json,
    sha256_text,
)


class HttpResponse(Protocol):
    def read(self, amount: int = -1) -> bytes: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> object: ...


HttpTransport = Callable[[Request, float], HttpResponse]


@dataclass(frozen=True, slots=True)
class HttpJsonExtractorConfig:
    endpoint: str
    provider: str
    model: str
    api_key: str | None = field(default=None, repr=False)
    prompt_version: str = PROMPT_VERSION
    prompt: str = DEFAULT_PROMPT
    timeout_seconds: float = 10.0
    max_response_bytes: int = 256 * 1024
    parameters: Mapping[str, str | int | float | bool | None] = field(
        default_factory=lambda: {"temperature": 0}
    )

    def __post_init__(self) -> None:
        parsed = urlsplit(self.endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("endpoint must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("endpoint must not contain credentials, query, or fragment")
        for name in ("provider", "model", "prompt_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be blank")
            object.__setattr__(self, name, value.strip())
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must not be blank")
        if self.api_key is not None and not self.api_key.strip():
            raise ValueError("api_key must not be blank")
        if self.api_key is not None:
            object.__setattr__(self, "api_key", self.api_key.strip())
        if not 0 < self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 0 and 120")
        if not 1_024 <= self.max_response_bytes <= 4 * 1024 * 1024:
            raise ValueError("max_response_bytes must be between 1024 and 4194304")
        normalized_parameters: dict[str, str | int | float | bool | None] = {}
        for key, value in self.parameters.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("parameter keys must be non-blank strings")
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise ValueError("parameter values must be JSON scalar values")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("floating-point parameter values must be finite")
            normalized_parameters[key.strip()] = value
        object.__setattr__(self, "parameters", MappingProxyType(normalized_parameters))


class HttpJsonReceiptExtractor:
    """Call a configured HTTPS endpoint and validate its response fail-closed."""

    def __init__(
        self,
        config: HttpJsonExtractorConfig,
        *,
        transport: HttpTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or _urlopen

    @property
    def provider(self) -> str:
        return self._config.provider

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def prompt_version(self) -> str:
        return self._config.prompt_version

    @property
    def prompt_hash(self) -> str:
        return sha256_text(self._config.prompt)

    def extract(self, submission: ReimbursementSubmission) -> ExtractionResult:
        request_id = submission.request_id
        raw_ocr_text = submission.raw_ocr_text
        invoked_at = datetime.now(UTC)
        started_ns = perf_counter_ns()
        raw_response = ""
        try:
            request = self._build_request(request_id=request_id, raw_ocr_text=raw_ocr_text)
            with self._transport(request, self._config.timeout_seconds) as response:
                response_bytes = response.read(self._config.max_response_bytes + 1)
            if len(response_bytes) > self._config.max_response_bytes:
                return self._failed(
                    request_id=request_id,
                    raw_ocr_text=raw_ocr_text,
                    raw_response="",
                    invoked_at=invoked_at,
                    started_ns=started_ns,
                    error="provider response exceeds configured byte limit",
                )
            try:
                raw_response = response_bytes.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                return self._failed(
                    request_id=request_id,
                    raw_ocr_text=raw_ocr_text,
                    raw_response="",
                    invoked_at=invoked_at,
                    started_ns=started_ns,
                    error="provider response is not valid UTF-8",
                )
            facts = parse_response_json(raw_response)
        except ResponseValidationError as exc:
            return self._failed(
                request_id=request_id,
                raw_ocr_text=raw_ocr_text,
                raw_response=raw_response,
                invoked_at=invoked_at,
                started_ns=started_ns,
                error=f"provider response validation failed: {exc}",
            )
        except HTTPError as exc:
            return self._failed(
                request_id=request_id,
                raw_ocr_text=raw_ocr_text,
                raw_response=_bounded_http_error_body(exc, self._config.max_response_bytes),
                invoked_at=invoked_at,
                started_ns=started_ns,
                error=f"provider returned HTTP {exc.code}",
            )
        except TimeoutError:
            return self._failed(
                request_id=request_id,
                raw_ocr_text=raw_ocr_text,
                raw_response="",
                invoked_at=invoked_at,
                started_ns=started_ns,
                error="provider request timed out",
            )
        except (URLError, OSError, ValueError, TypeError):
            return self._failed(
                request_id=request_id,
                raw_ocr_text=raw_ocr_text if isinstance(raw_ocr_text, str) else "",
                raw_response=raw_response,
                invoked_at=invoked_at,
                started_ns=started_ns,
                error="provider request failed",
            )

        trace = self._trace(
            raw_ocr_text=raw_ocr_text,
            raw_response=raw_response,
            invoked_at=invoked_at,
            duration_ms=_elapsed_ms(started_ns),
        )
        return ExtractionResult(
            request_id=request_id,
            status=ExtractionStatus.SUCCEEDED,
            trace=trace,
            facts=facts,
        )

    def _build_request(self, *, request_id: str, raw_ocr_text: str) -> Request:
        if not isinstance(raw_ocr_text, str) or not raw_ocr_text.strip():
            raise ValueError("raw_ocr_text must not be blank")
        body: dict[str, Any] = {
            "model": self._config.model,
            "parameters": dict(self._config.parameters),
            "prompt": self._config.prompt,
            "prompt_version": self._config.prompt_version,
            "raw_ocr_text": raw_ocr_text,
            "request_id": request_id,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }
        if self._config.api_key is not None:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return Request(
            self._config.endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )

    def _trace(
        self,
        *,
        raw_ocr_text: str,
        raw_response: str,
        invoked_at: datetime,
        duration_ms: int,
    ):
        return build_trace(
            provider=self._config.provider,
            model=self._config.model,
            prompt_version=self._config.prompt_version,
            prompt=self._config.prompt,
            raw_ocr_text=raw_ocr_text,
            raw_response=raw_response,
            invoked_at=invoked_at,
            duration_ms=duration_ms,
            parameters=self._config.parameters,
        )

    def _failed(
        self,
        *,
        request_id: str,
        raw_ocr_text: str,
        raw_response: str,
        invoked_at: datetime,
        started_ns: int,
        error: str,
    ) -> ExtractionResult:
        return ExtractionResult(
            request_id=request_id,
            status=ExtractionStatus.FAILED,
            trace=self._trace(
                raw_ocr_text=raw_ocr_text,
                raw_response=raw_response,
                invoked_at=invoked_at,
                duration_ms=_elapsed_ms(started_ns),
            ),
            error=error,
        )


def _urlopen(request: Request, timeout: float) -> HttpResponse:
    return urlopen(request, timeout=timeout)


def _bounded_http_error_body(error: HTTPError, max_response_bytes: int) -> str:
    try:
        body = error.read(max_response_bytes + 1)
    except OSError:
        return ""
    if len(body) > max_response_bytes:
        return ""
    try:
        return body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return ""


def _elapsed_ms(started_ns: int) -> int:
    return max(0, (perf_counter_ns() - started_ns) // 1_000_000)
