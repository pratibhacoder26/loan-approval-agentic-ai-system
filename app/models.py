"""Pydantic data models exchanged across the loan-approval pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import (
    DEFAULT_LOAN_TENURE_MAX_MONTHS,
    DEFAULT_LOAN_TENURE_MIN_MONTHS,
    EmploymentType,
    LoanDecision,
    MAX_APPLICANT_AGE,
    MIN_APPLICANT_AGE,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# Input payloads
# ---------------------------------------------------------------------------


class LoanApplication(BaseModel):
    """Raw loan application submitted by the applicant."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    applicant_id: str = Field(default_factory=lambda: f"APP-{uuid4().hex[:10].upper()}")
    full_name: str = Field(..., min_length=2, max_length=120)
    age: int = Field(..., ge=18, le=100)
    income: float = Field(..., gt=0, description="Annual income in local currency")
    employment_type: EmploymentType
    credit_score: int = Field(..., ge=300, le=900)
    loan_amount: float = Field(..., gt=0)
    loan_tenure_months: int = Field(
        ...,
        ge=DEFAULT_LOAN_TENURE_MIN_MONTHS,
        le=DEFAULT_LOAN_TENURE_MAX_MONTHS,
    )
    existing_liabilities: float = Field(0.0, ge=0)
    location: str = Field(..., min_length=2, max_length=120)
    application_timestamp: datetime = Field(default_factory=datetime.utcnow)
    purpose: str | None = Field(None, max_length=240)

    @field_validator("age")
    @classmethod
    def _validate_eligible_age(cls, v: int) -> int:
        if not (MIN_APPLICANT_AGE <= v <= MAX_APPLICANT_AGE):
            # Don't block, but the profile agent will flag eligibility.
            return v
        return v


# ---------------------------------------------------------------------------
# Agent outputs
# ---------------------------------------------------------------------------


class ApplicantProfileOutput(BaseModel):
    """Output of the Applicant Profile Agent."""

    applicant_id: str
    income_stability_score: float = Field(..., ge=0, le=100)
    employment_risk: RiskLevel
    credit_history_summary: str
    application_completeness_flags: list[str] = Field(default_factory=list)
    eligible: bool = True
    notes: str | None = None


class FinancialRiskOutput(BaseModel):
    """Output of the Financial Risk Analysis Agent."""

    applicant_id: str
    debt_to_income_ratio: float = Field(..., ge=0)
    credit_score_risk_level: RiskLevel
    loan_amount_risk: RiskLevel
    anomaly_detected: bool
    anomaly_reasons: list[str] = Field(default_factory=list)
    composite_risk_score: float = Field(..., ge=0, le=100)
    reasoning: str


class LoanDecisionOutput(BaseModel):
    """Output of the Loan Decision Agent."""

    applicant_id: str
    classification: LoanDecision
    risk_score: float = Field(..., ge=0, le=100)
    confidence_level: float = Field(..., ge=0, le=1)
    key_decision_factors: list[str]
    explanation: str


class ComplianceActionOutput(BaseModel):
    """Output of the Compliance & Action Orchestrator Agent."""

    applicant_id: str
    case_id: str
    action_taken: str
    notification_sent: bool
    notification_channel: str
    timestamp: datetime
    summary: str


# ---------------------------------------------------------------------------
# Final orchestrated result
# ---------------------------------------------------------------------------


class LoanDecisionResult(BaseModel):
    """Top-level response returned to the UI."""

    application: LoanApplication
    applicant_profile: ApplicantProfileOutput
    financial_risk: FinancialRiskOutput
    loan_decision: LoanDecisionOutput
    compliance_action: ComplianceActionOutput
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API envelopes
# ---------------------------------------------------------------------------


class ApiSuccess(BaseModel):
    """Successful API response envelope."""

    status: str = "success"
    data: LoanDecisionResult


class ApiError(BaseModel):
    """Failure API response envelope."""

    status: str = "error"
    error_code: str
    message: str
    details: dict[str, Any] | None = None
