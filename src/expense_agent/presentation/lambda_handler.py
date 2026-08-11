"""AWS Lambda entry point for the self-contained assessment deployment."""

from mangum import Mangum

from expense_agent.presentation.main import create_environment_app


def create_lambda_handler() -> Mangum:
    """Adapt the existing ASGI composition root to API Gateway/Lambda events."""

    return Mangum(create_environment_app(), lifespan="off")


handler = create_lambda_handler()
