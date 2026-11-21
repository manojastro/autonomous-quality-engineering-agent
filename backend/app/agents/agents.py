"""Deterministic agent layer: each agent wraps one pipeline concern."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.app.repositories import ChangesRepo, ExecutionsRepo, RegistryRepo, SelectionsRepo
from backend.app.services.llm import LLMAdapter
from backend.app.tools import default_registry


class BaseAgent:
    name = "base"

    def __init__(self, llm: LLMAdapter | None = None) -> None:
        self.llm = llm or LLMAdapter()

    def call_tool(self, session: Session, tool_name: str, payload: Dict[str, Any], change_id: int | None = None) -> Dict[str, Any]:
        result = default_registry.execute(session, tool_name, payload, change_id=change_id)
        if not result["ok"]:
            raise RuntimeError(f"{self.name} failed tool {tool_name}: {result['error']}")
        return result["data"]


class ChangeAnalysisAgent(BaseAgent):
    name = "change_analysis_agent"

    def run(self, session: Session, change_id: int) -> Dict[str, Any]:
        change = ChangesRepo(session).require(change_id)
        files = change.manifest_json.get("files", [])
        functions = sum(len(f.get("functions_changed", []) or []) for f in files)
        size_norm = round(min(1.0, (change.lines_added + change.lines_deleted) / 200.0), 3)
        return {
            "change_id": change.id,
            "files": len(files),
            "functions_touched": functions,
            "lines_added": change.lines_added,
            "lines_deleted": change.lines_deleted,
            "size_norm": size_norm,
        }


class CodeDependencyAgent(BaseAgent):
    name = "code_dependency_agent"

    def run(self, session: Session) -> Dict[str, Any]:
        return self.call_tool(session, "scan_dependencies_tool", {})


class TestImpactAgent(BaseAgent):
    name = "test_impact_agent"

    def run(self, session: Session, change_id: int) -> Dict[str, Any]:
        data = self.call_tool(session, "select_tests_tool", {"change_id": change_id}, change_id=change_id)
        data["narrative"] = self.llm.narrate(
            "selection",
            {
                "impacted_modules": [m.split(".")[-1] for m in data["impacted_modules"]],
                "selected_count": data["selected_count"],
                "total_tests": data["total_tests"],
                "reduction_pct": data["reduction_pct"],
            },
        )
        selection_row = SelectionsRepo(session).latest(change_id)
        if selection_row is not None:
            payload = dict(selection_row.payload_json)
            payload["narrative"] = data["narrative"]
            selection_row.payload_json = payload
            session.flush()
        return data


class RiskBasedTestingAgent(BaseAgent):
    name = "risk_based_testing_agent"

    def run(self, session: Session, selection_data: Dict[str, Any]) -> Dict[str, Any]:
        ordered = sorted(selection_data["selected"], key=lambda item: -item.get("priority_score", 0.0))
        top = [
            {"test_id": item["test_id"], "priority_score": item["priority_score"], "rationale": item["rationale"]}
            for item in ordered[:5]
        ]
        return {"priority_order": [item["test_id"] for item in ordered], "top_risks": top}


class ExecutionAgent(BaseAgent):
    name = "execution_agent"

    def run(self, session: Session, change_id: int, selection_id: int, flaky_env_active: bool = False) -> Dict[str, Any]:
        return self.call_tool(
            session,
            "execute_tests_tool",
            {"change_id": change_id, "selection_id": selection_id, "flaky_env_active": flaky_env_active},
            change_id=change_id,
        )


class FailureRCAAgent(BaseAgent):
    name = "failure_rca_agent"

    def run(self, session: Session, change_id: int, execution_id: int) -> Dict[str, Any]:
        data = self.call_tool(session, "analyze_failures_tool", {"change_id": change_id, "execution_id": execution_id}, change_id=change_id)
        for item in data["items"]:
            item["narrative"] = self.llm.narrate("rca", {"root_cause": item["root_cause"], "test_id": item["incident_id"]})
        return data


class FlakyTestAgent(BaseAgent):
    name = "flaky_test_agent"

    def run(self, session: Session, change_id: int, execution_id: int) -> Dict[str, Any]:
        results = ExecutionsRepo(session).results(execution_id)
        registry_by_node = {t.node_id: t for t in RegistryRepo(session).all()}
        classified: list[dict] = []
        seen: set[str] = set()
        for result in results:
            reg = registry_by_node.get(result.node_id)
            failed = result.outcome not in ("passed", "skipped")
            suspicious = result.retried_flag or failed or (reg is not None and reg.flakiness_score >= 0.3)
            if not suspicious or result.node_id in seen:
                continue
            seen.add(result.node_id)
            first_outcome = "failed" if result.retried_flag or failed else "passed"
            final_outcome = "passed" if result.outcome == "passed" else "failed"
            outcome = self.call_tool(
                session,
                "classify_flaky_tool",
                {
                    "change_id": change_id,
                    "execution_id": execution_id,
                    "test_id": result.test_id,
                    "node_id": result.node_id,
                    "first_outcome": first_outcome,
                    "final_outcome": final_outcome,
                    "retried": result.retried_flag,
                    "message": result.message[:500],
                },
                change_id=change_id,
            )
            classified.append({"test_id": result.test_id, **outcome})
        return {"classified": classified}


class ReleaseConfidenceAgent(BaseAgent):
    name = "release_confidence_agent"

    def run(self, session: Session, change_id: int) -> Dict[str, Any]:
        data = self.call_tool(session, "compute_confidence_tool", {"change_id": change_id}, change_id=change_id)
        data["narrative"] = self.llm.narrate("confidence", {"score": data["score"]})
        return data


class QualityGateAgent(BaseAgent):
    name = "quality_gate_agent"

    def run(self, session: Session, change_id: int) -> Dict[str, Any]:
        data = self.call_tool(session, "evaluate_quality_gate_tool", {"change_id": change_id}, change_id=change_id)
        data["narrative"] = self.llm.narrate("gate", {"decision": data["decision"], "score": data["score"], "reasons": data["reasons"]})
        return data
