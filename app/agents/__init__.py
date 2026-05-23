"""Domain agents for the Loan Approval System."""

from app.agents.applicant_profile_agent import ApplicantProfileAgent
from app.agents.compliance_agent import ComplianceActionAgent
from app.agents.financial_risk_agent import FinancialRiskAnalysisAgent
from app.agents.loan_decision_agent import LoanDecisionAgent

__all__ = [
    "ApplicantProfileAgent",
    "FinancialRiskAnalysisAgent",
    "LoanDecisionAgent",
    "ComplianceActionAgent",
]
