"""Composition root and executable entry point for the assessment HTTP service."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from expense_agent.application import ProcessingService, ReviewService
from expense_agent.application.extraction import ReceiptExtractor
from expense_agent.infrastructure.attachments import FileSystemAttachmentStore
from expense_agent.infrastructure.extraction import (
    DeterministicReceiptExtractor,
    HttpJsonExtractorConfig,
    HttpJsonReceiptExtractor,
)
from expense_agent.infrastructure.review.persistence import SqliteReviewRepository
from expense_agent.presentation.app import create_app
from expense_agent.presentation.config import ExtractorMode, ReviewWebSettings
from expense_agent.presentation.security import (
    BasicAuthenticator,
    CsrfProtector,
    SecurityConfigurationError,
)


def create_receipt_extractor(settings: ReviewWebSettings) -> ReceiptExtractor:
    """Compose the configured extractor without allowing silent fallbacks."""

    extractor_settings = settings.http_json_extractor_settings
    if settings.extractor_mode is ExtractorMode.DETERMINISTIC:
        if extractor_settings is not None:
            raise SecurityConfigurationError(
                "deterministic extractor mode must not include HTTP JSON settings"
            )
        return DeterministicReceiptExtractor()
    if settings.extractor_mode is not ExtractorMode.HTTP_JSON or extractor_settings is None:
        raise SecurityConfigurationError("extractor configuration is inconsistent")

    try:
        config = HttpJsonExtractorConfig(
            endpoint=extractor_settings.endpoint,
            provider=extractor_settings.provider,
            model=extractor_settings.model,
            api_key=extractor_settings.api_key,
            timeout_seconds=extractor_settings.timeout_seconds,
            max_response_bytes=extractor_settings.max_response_bytes,
            parameters=extractor_settings.parameters,
        )
    except ValueError as exc:
        raise SecurityConfigurationError("HTTP JSON extractor configuration is invalid") from exc
    return HttpJsonReceiptExtractor(config)


def create_environment_app() -> FastAPI:
    settings = ReviewWebSettings.from_environment()
    execution_identity = settings.execution_identity
    extractor = create_receipt_extractor(settings)
    repository = SqliteReviewRepository(
        settings.database_path,
        journal_mode=settings.sqlite_journal_mode,
    )
    attachment_store = FileSystemAttachmentStore(
        settings.attachment_root,
        max_bytes=settings.attachment_max_bytes,
    )
    return create_app(
        review_service=ReviewService(
            repository,
            execution_identity=execution_identity,
        ),
        processing_service=ProcessingService(
            repository,
            extractor,
            execution_identity=execution_identity,
        ),
        authenticator=BasicAuthenticator(settings.reviewers),
        csrf=CsrfProtector(settings.csrf_secret),
        require_https=settings.require_https,
        allowed_hosts=settings.allowed_hosts,
        attachment_store=attachment_store,
        attachment_max_bytes=settings.attachment_max_bytes,
        execution_identity=execution_identity,
    )


def run() -> None:
    settings = ReviewWebSettings.from_environment()
    uvicorn.run(
        create_environment_app(),
        host=settings.host,
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips=settings.forwarded_allow_ips,
    )


if __name__ == "__main__":
    run()
