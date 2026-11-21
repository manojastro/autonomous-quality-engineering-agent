"""Pipeline orchestration: change intake to gate decision."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.app.agents.agents import (
    ChangeAnalysisAgent,
    CodeDependencyAgent,
    ExecutionAgent,
    FailureRCAAgent,
    FlakyTestAgent,
    QualityGateAgent,
    ReleaseConfidenceAgent,
    RiskBasedTestingAgent,
    TestImpactAgent,
)
from backend.app.repositories import ChangesRepo
from backend.app.services import metrics
from backend.app.services.workflow import ApprovalService

FROZEN_STATES = {"APPROVED", "COMPLETED", "FAILED", "ROLLED_BACK"}


class AnalysisPipeline:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.change_agent = ChangeAnalysisAgent()
        self.dependency_agent = CodeDependencyAgent()
        self.impact_agent = TestImpactAgent()
        self.risk_agent = RiskBasedTestingAgent()
        self.execution_agent = ExecutionAgent()
        self.rca_agent = FailureRCAAgent()
        self.flaky_agent = FlakyTestAgent()
        self.confidence_agent = ReleaseConfidenceAgent()
        self.gate_agent = QualityGateAgent()
        self.workflow = ApprovalService(session)

    def run(self, change_id: int, execute: bool = True) -> Dict[str, Any]:
        ChangesRepo(self.session).require(change_id)
        state = self.workflow.state_of(change_id)
        if state in FROZEN_STATES:
            raise RuntimeError(f"change {change_id} workflow already decided ({state})")
        if state == "PROPOSED":
            self.workflow.transition(change_id, "VALIDATING")
        summary: Dict[str, Any] = {"change_id": change_id}

        summary["change"] = self.change_agent.run(self.session, change_id)
        summary["dependencies"] = self.dependency_agent.run(self.session)

        selection = self.impact_agent.run(self.session, change_id)
        summary["selection"] = {
            "selection_id": selection["selection_id"],
            "impacted_modules": selection["impacted_modules"],
            "selected_count": selection["selected_count"],
            "total_tests": selection["total_tests"],
            "reduction_pct": selection["reduction_pct"],
            "narrative": selection["narrative"],
            "top_risks": [],
        }
        priorities = self.risk_agent.run(self.session, selection)
        summary["selection"]["top_risks"] = priorities["top_risks"]

        if not execute:
            return summary

        if self.workflow.state_of(change_id) == "VALIDATING":
            self.workflow.transition(change_id, "EXECUTING")
        execution = self.execution_agent.run(self.session, change_id, selection["selection_id"])
        summary["execution"] = {
            k: execution[k]
            for k in ("execution_id", "total", "passed", "failed", "retried", "duration_s")
        }
        summary["failures"] = [
            {"node_id": r["node_id"], "outcome": r["outcome"]}
            for r in execution["results"]
            if r["outcome"] not in ("passed", "skipped")
        ]

        if self.workflow.state_of(change_id) == "EXECUTING":
            self.workflow.transition(change_id, "VERIFYING")

        flaky = self.flaky_agent.run(self.session, change_id, execution["execution_id"])
        summary["flaky"] = flaky["classified"]
        rca = self.rca_agent.run(self.session, change_id, execution["execution_id"]) if execution["failed"] else {"failures_analyzed": 0, "items": []}
        summary["rca_count"] = rca["failures_analyzed"]
        summary["root_causes"] = [item["root_cause"] for item in rca["items"]]

        confidence = self.confidence_agent.run(self.session, change_id)
        summary["confidence"] = confidence

        gate = self.gate_agent.run(self.session, change_id)
        summary["gate"] = gate

        if self.workflow.state_of(change_id) == "VERIFYING":
            self.workflow.transition(change_id, "AWAITING_APPROVAL")
        summary["workflow_state"] = self.workflow.state_of(change_id)

        ChangesRepo(self.session).set_status(change_id, "analyzed")
        metrics.incr("qe_changes_analyzed_total")
        return summary
