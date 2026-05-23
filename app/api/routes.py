"""FastAPI routes exposing the loan-approval pipeline."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.models import ApiError, ApiSuccess, LoanApplication
from app.orchestration import run_loan_workflow

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Lightweight liveness probe."""
    return {"status": "ok"}


@router.post(
    "/api/v1/loan/evaluate",
    tags=["loan"],
    response_model=ApiSuccess,
    responses={
        400: {"model": ApiError, "description": "Validation error"},
        500: {"model": ApiError, "description": "Internal error"},
    },
)
async def evaluate_loan(application: LoanApplication) -> ApiSuccess:
    """Run the full multi-agent pipeline against a loan application."""
    try:
        result = await run_loan_workflow(application)
        return ApiSuccess(data=result)
    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("Validation error: %s", exc)
        return JSONResponse(  # type: ignore[return-value]
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ApiError(
                error_code="VALIDATION_ERROR",
                message=str(exc),
            ).model_dump(),
        )
    except Exception as exc:
        logger.exception("Workflow failed")
        return JSONResponse(  # type: ignore[return-value]
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiError(
                error_code="WORKFLOW_FAILURE",
                message=str(exc),
            ).model_dump(),
        )
