"""Composition root and executable entry point for the review web service."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from expense_agent.application.review import ReviewService
from expense_agent.infrastructure.review.persistence import SqliteReviewRepository
from expense_agent.presentation.app import create_app
from expense_agent.presentation.config import ReviewWebSettings
from expense_agent.presentation.security import BasicAuthenticator, CsrfProtector


def create_environment_app() -> FastAPI:
    settings = ReviewWebSettings.from_environment()
    repository = SqliteReviewRepository(settings.database_path)
    return create_app(
        review_service=ReviewService(repository),
        authenticator=BasicAuthenticator(settings.reviewers),
        csrf=CsrfProtector(settings.csrf_secret),
        require_https=settings.require_https,
        allowed_hosts=settings.allowed_hosts,
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
