"""LangGraph workflow wiring the four domain agents.

The workflow is intentionally linear — Profile → Risk → Decision → Compliance
— because each agent strictly depends on the previous one's output. The
LangGraph state holds per-node traces so the final response can include a
full audit trail.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents import (
    ApplicantProfileAgent,
    ComplianceActionAgent,
    FinancialRiskAnalysisAgent,
    LoanDecisionAgent,
)
from app.constants import LoanDecision
from app.models import (
    ApplicantProfileOutput,
    ComplianceActionOutput,
    FinancialRiskOutput,
    LoanApplication,
    LoanDecisionOutput,
    LoanDecisionResult,
)
from app.orchestration.state import LoanWorkflowState

logger = logging.getLogger(__name__)


# Node implementations -------------------------------------------------------


async def _profile_node(state: LoanWorkflowState) -> dict[str, Any]:
    agent = ApplicantProfileAgent()
    trace = await agent.run({"application": state["application"]})
    return {
        "applicant_profile_trace": trace,
        "agent_trace": [_summarise(trace)],
    }


async def _risk_node(state: LoanWorkflowState) -> dict[str, Any]:
    agent = FinancialRiskAnalysisAgent()
    trace = await agent.run(
        {
            "application": state["application"],
            "applicant_profile_trace": state["applicant_profile_trace"],
        }
    )
    return {
        "financial_risk_trace": trace,
        "agent_trace": [_summarise(trace)],
    }


async def _decision_node(state: LoanWorkflowState) -> dict[str, Any]:
    agent = LoanDecisionAgent()
    trace = await agent.run(
        {
            "application": state["application"],
            "applicant_profile_trace": state["applicant_profile_trace"],
            "financial_risk_trace": state["financial_risk_trace"],
        }
    )
    return {
        "loan_decision_trace": trace,
        "agent_trace": [_summarise(trace)],
    }


async def _compliance_node(state: LoanWorkflowState) -> dict[str, Any]:
    agent = ComplianceActionAgent()
    trace = await agent.run(
        {
            "application": state["application"],
            "loan_decision_trace": state["loan_decision_trace"],
        }
    )
    return {
        "compliance_trace": trace,
        "agent_trace": [_summarise(trace)],
    }


def _summarise(trace: dict[str, Any]) -> dict[str, Any]:
    """Compact per-node trace entry for the audit log."""
    return {
        "agent": trace["agent"],
        "elapsed_ms": trace["elapsed_ms"],
    }


# Graph builder --------------------------------------------------------------


def build_loan_workflow():
    """Construct and compile the LangGraph state machine."""
    graph: StateGraph = StateGraph(LoanWorkflowState)

    graph.add_node("applicant_profile", _profile_node)
    graph.add_node("financial_risk", _risk_node)
    graph.add_node("loan_decision", _decision_node)
    graph.add_node("compliance", _compliance_node)

    graph.add_edge(START, "applicant_profile")
    graph.add_edge("applicant_profile", "financial_risk")
    graph.add_edge("financial_risk", "loan_decision")
    graph.add_edge("loan_decision", "compliance")
    graph.add_edge("compliance", END)

    return graph.compile(name="LoanApprovalWorkflow")


# Public entry point --------------------------------------------------------


async def run_loan_workflow(application: LoanApplication) -> LoanDecisionResult:
    """Execute the full pipeline and return the consolidated result."""
    workflow = build_loan_workflow()
    final_state: LoanWorkflowState = await workflow.ainvoke(
        {"application": application, "agent_trace": []}
    )

    profile_out = ApplicantProfileOutput.model_validate(
        final_state["applicant_profile_trace"]["output"]["profile"]
    )
    risk_out = FinancialRiskOutput.model_validate(
        final_state["financial_risk_trace"]["output"]["financial_risk"]
    )
    decision_out = LoanDecisionOutput.model_validate(
        final_state["loan_decision_trace"]["output"]["decision"]
    )
    compliance_out = ComplianceActionOutput.model_validate(
        final_state["compliance_trace"]["output"]["compliance_action"]
    )

    logger.info(
        "Workflow complete for %s: %s (risk=%s, confidence=%s)",
        application.applicant_id,
        decision_out.classification.value,
        decision_out.risk_score,
        decision_out.confidence_level,
    )
    # Touch LoanDecision so the enum import isn't optimised away.
    assert isinstance(decision_out.classification, LoanDecision)

    return LoanDecisionResult(
        application=application,
        applicant_profile=profile_out,
        financial_risk=risk_out,
        loan_decision=decision_out,
        compliance_action=compliance_out,
        agent_trace=final_state.get("agent_trace", []),
    )
