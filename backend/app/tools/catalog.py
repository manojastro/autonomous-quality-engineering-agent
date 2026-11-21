"""Concrete tools: dependency scan, selection, execution, RCA, flaky, confidence, gate, bug toggle."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set

from pydantic import BaseModel
from sqlalchemy.orm import Session

from sample_app import payments

from backend.app.analysis.ast_graph import build_dependents, scan_imports
from backend.app.analysis.impact import analyze_change
from backend.app.analysis.risk import order_selection
from backend.app.analysis.selection import STRATEGY, select_tests
from backend.app.config import PROJECT_ROOT, get_settings
from backend.app.models import utcnow_iso
from backend.app.repositories import (
    ChangesRepo,
    ConfidenceRepo,
    ExecutionsRepo,
    FailuresRepo,
    FlakyRepo,
    GatesRepo,
    ImpactsRepo,
    ModulesRepo,
    RcaRepo,
    RegistryRepo,
    SelectionsRepo,
)
from backend.app.services import metrics
from backend.app.services.confidence_math import compute_confidence
from backend.app.services.flaky_classifier import classify
from backend.app.services.gate_rules import decide as gate_decide
from backend.app.services.rca_logic import build_rca
from backend.app.services.runner import PytestRunner
from backend.app.tools.base import ToolDefinition


class ScanDependenciesInput(BaseModel):
    root: str = str(PROJECT_ROOT)


class ScanDependenciesTool(ToolDefinition):
    name = "scan_dependencies_tool"
    description = "AST-scan sample_app imports and return the dependency graph."
    permission = "safe"
    timeout_s = 15
    input_model = ScanDependenciesInput

    def run(self, session: Session, params: ScanDependenciesInput) -> Dict[str, Any]:
        graph = scan_imports(Path(params.root))
        dependents = build_dependents(graph)
        return {
            "graph": {k: sorted(v) for k, v in sorted(graph.items())},
            "dependents": {k: sorted(v) for k, v in sorted(dependents.items())},
            "nodes": len(graph),
            "edges": sum(len(v) for v in graph.values()),
        }


class SelectTestsInput(BaseModel):
    change_id: int


class SelectTestsTool(ToolDefinition):
    name = "select_tests_tool"
    description = "Compute impacted-module closure and select the minimum high-value test set."
    permission = "safe"
    timeout_s = 30
    input_model = SelectTestsInput

    def run(self, session: Session, params: SelectTestsInput) -> Dict[str, Any]:
        change = ChangesRepo(session).require(params.change_id)
        impact = analyze_change(change.manifest_json.get("files", []))
        ImpactsRepo(session).add(params.change_id, impact.payload)
        registry_rows = RegistryRepo(session).all()
        plan = select_tests(registry_rows, impact.impacted_modules)
        by_id = {t.test_id: t for t in registry_rows}
        size_norm = min(1.0, (change.lines_added + change.lines_deleted) / 200.0)
        modules = ModulesRepo(session).all()
        ordered = order_selection(plan["selected"], by_id, modules, size_norm, impact.impacted_modules)
        payload = {
            "strategy": STRATEGY,
            "selected": ordered,
            "skipped": plan["skipped"],
            "precision_inputs": plan["precision_inputs"],
            "impacted_modules": impact.impacted_modules,
        }
        record = SelectionsRepo(session).add(
            params.change_id,
            strategy=STRATEGY,
            total_tests=plan["total_tests"],
            selected_count=plan["selected_count"],
            reduction_pct=plan["reduction_pct"],
            payload_json=payload,
        )
        metrics.incr("qe_selections_total")
        metrics.set_gauge("qe_last_suite_reduction_percent", plan["reduction_pct"])
        return {
            "selection_id": record.id,
            "total_tests": plan["total_tests"],
            "selected_count": plan["selected_count"],
            "reduction_pct": plan["reduction_pct"],
            "impacted_modules": impact.impacted_modules,
            "changed_modules": impact.changed_modules,
            "changed_functions": impact.changed_functions,
            "selected": ordered,
            "skipped": plan["skipped"][:10],
            "skipped_total": len(plan["skipped"]),
            "precision_inputs": plan["precision_inputs"],
        }


class ExecuteTestsInput(BaseModel):
    change_id: int
    selection_id: int
    flaky_env_active: bool = False
    retry_suspects: bool = True


class ExecuteTestsTool(ToolDefinition):
    name = "execute_tests_tool"
    description = "Run the selected subset through the constrained pytest runner."
    permission = "safe"
    timeout_s = 300
    input_model = ExecuteTestsInput

    def run(self, session: Session, params: ExecuteTestsInput) -> Dict[str, Any]:
        selection = SelectionsRepo(session).latest(params.change_id)
        if selection is None or selection.id != params.selection_id:
            raise RunnerError(f"selection {params.selection_id} not current for change {params.change_id}")
        node_ids: List[str] = [item["node_id"] for item in selection.payload_json["selected"]]
        suspects: Set[str] = {row.node_id for row in RegistryRepo(session).all() if row.flakiness_score >= 0.3}
        runner = PytestRunner(timeout_s=get_settings().runner_timeout_s)
        env_extra = {"QE_FLAKY_ACTIVE": "1"} if params.flaky_env_active else None
        report = runner.run_with_retry(node_ids, flaky_suspects=suspects if params.retry_suspects else set(), env_extra=env_extra)
        execution = ExecutionsRepo(session).create(params.change_id, selection_id=selection.id)
        registry_by_node = {row.node_id: row for row in RegistryRepo(session).all()}
        for output in report.outputs:
            reg = registry_by_node.get(output.node_id)
            ExecutionsRepo(session).add_result(
                execution_id=execution.id,
                test_id=reg.test_id if reg else output.node_id,
                node_id=output.node_id,
                outcome=output.outcome,
                duration_s=output.duration_s,
                attempts=2 if output.retried else 1,
                retried_flag=output.retried,
                message=output.message,
            )
            if reg is not None:
                history = list(reg.historical_outcomes_json or [])
                history.append("pass" if output.outcome == "passed" else "fail")
                reg.historical_outcomes_json = history[-12:]
                recent = history[-8:]
                flips = sum(1 for a, b in zip(recent, recent[1:]) if a != b)
                fail_rate = recent.count("fail") / len(recent) if recent else 0.0
                flip_rate = flips / (len(recent) - 1) if len(recent) > 1 else 0.0
                reg.flakiness_score = round(min(1.0, 0.8 * flip_rate + 0.2 * fail_rate), 3)
        execution.total = len(report.outputs)
        execution.passed = report.passed
        execution.failed = report.failed
        execution.retried = sum(1 for o in report.outputs if o.retried)
        execution.duration_s = round(sum(o.duration_s for o in report.outputs), 3)
        execution.status = "completed"
        execution.finished_at = utcnow_iso()
        session.flush()
        metrics.incr("qe_tests_executed_total", float(execution.total))
        if execution.failed:
            metrics.incr("qe_tests_failed_total", float(execution.failed))
        return {
            "execution_id": execution.id,
            "total": execution.total,
            "passed": execution.passed,
            "failed": execution.failed,
            "retried": execution.retried,
            "duration_s": execution.duration_s,
            "results": [
                {
                    "test_id": registry_by_node.get(out.node_id).test_id if out.node_id in registry_by_node else out.node_id,
                    "node_id": out.node_id,
                    "outcome": out.outcome,
                    "duration_s": out.duration_s,
                    "retried_flag": out.retried,
                    "message_tail": out.message[-400:],
                }
                for out in report.outputs
            ],
        }


class AnalyzeFailuresInput(BaseModel):
    change_id: int
    execution_id: int


class AnalyzeFailuresTool(ToolDefinition):
    name = "analyze_failures_tool"
    description = "Collect evidence per failure and synthesize a RootCauseAnalysis."
    permission = "safe"
    timeout_s = 30
    input_model = AnalyzeFailuresInput

    def run(self, session: Session, params: AnalyzeFailuresInput) -> Dict[str, Any]:
        execution = ExecutionsRepo(session).get(params.execution_id)
        if execution is None:
            raise RuntimeError(f"execution {params.execution_id} not found")
        change = ChangesRepo(session).require(params.change_id)
        manifest_functions: Dict[str, List[str]] = {}
        for file_entry in change.manifest_json.get("files", []):
            path = str(file_entry.get("path", "")).replace("\\", "/")
            module = path.split("/")[-1].replace(".py", "")
            if module:
                manifest_functions[f"sample_app.{module}"] = [str(f) for f in file_entry.get("functions_changed", [])]
        results = ExecutionsRepo(session).results(params.execution_id)
        registry_by_node = {row.node_id: row for row in RegistryRepo(session).all()}
        built: List[Dict[str, Any]] = []
        for result in results:
            if result.outcome in ("passed", "skipped"):
                continue
            reg = registry_by_node.get(result.node_id)
            incident_id = f"INC-C{params.change_id}-E{params.execution_id}-{result.test_id}"
            rca_payload = build_rca(
                incident_id=incident_id,
                test_id=result.test_id,
                node_id=result.node_id,
                message=result.message,
                changed_functions=manifest_functions,
                module_mappings=list(reg.module_mappings_json) if reg else [],
                history=list(reg.historical_outcomes_json) if reg else [],
            )
            rca_row = RcaRepo(session).add(incident_id, params.change_id, rca_payload)
            diff_ref = "; ".join(
                f"{f.get('path')} ({', '.join(f.get('functions_changed', []) or ['module'])})" for f in change.manifest_json.get("files", [])
            )
            failure = FailuresRepo(session).add(
                change_id=params.change_id,
                execution_id=params.execution_id,
                test_id=result.test_id,
                node_id=result.node_id,
                stack_trace=result.message[:4000],
                log_excerpt=(result.message or "")[-1200:],
                diff_ref=diff_ref,
                related_history_json=list(reg.historical_outcomes_json)[-8:] if reg else [],
                rca_id=rca_row.id,
            )
            built.append({"failure_id": failure.id, "incident_id": incident_id, "root_cause": rca_payload["root_cause"]})
        return {"failures_analyzed": len(built), "items": built}


class ClassifyFlakyInput(BaseModel):
    change_id: int
    execution_id: int
    test_id: str
    node_id: str
    first_outcome: str
    final_outcome: str
    retried: bool = False
    message: str = ""


class ClassifyFlakyTool(ToolDefinition):
    name = "classify_flaky_tool"
    description = "Classify suspicious outcomes using alternation history and retry signals."
    permission = "safe"
    timeout_s = 15
    input_model = ClassifyFlakyInput

    def run(self, session: Session, params: ClassifyFlakyInput) -> Dict[str, Any]:
        reg_row = next((r for r in RegistryRepo(session).all() if r.node_id == params.node_id), None)
        history = list(reg_row.historical_outcomes_json) if reg_row else []
        outcome = classify(params.first_outcome, params.final_outcome, history, message=params.message, retried=params.retried)
        FlakyRepo(session).add(
            change_id=params.change_id,
            execution_id=params.execution_id,
            test_id=params.test_id,
            classification=str(outcome["classification"]),
            confidence=float(outcome["confidence"]),
            signals_json=dict(outcome["signals"]),
        )
        metrics.incr("qe_flaky_classified_total")
        return outcome


class ComputeConfidenceInput(BaseModel):
    change_id: int


class ComputeConfidenceTool(ToolDefinition):
    name = "compute_confidence_tool"
    description = "Deterministic weighted release-confidence score from persisted artifacts."
    permission = "safe"
    timeout_s = 15
    input_model = ComputeConfidenceInput

    def run(self, session: Session, params: ComputeConfidenceInput) -> Dict[str, Any]:
        execution = ExecutionsRepo(session).latest(params.change_id)
        if execution is None:
            raise RuntimeError(f"no execution for change {params.change_id}")
        impact = ImpactsRepo(session).latest(params.change_id)
        results = [r for r in ExecutionsRepo(session).results(execution.id) if r.outcome != "skipped"]
        passed_ratio = (sum(1 for r in results if r.outcome == "passed") / len(results)) if results else 0.0
        changed_modules = set(impact.payload_json["changed_modules"]) if impact else set()
        registry_rows = RegistryRepo(session).all()
        by_test_id = {t.test_id: t for t in registry_rows}
        passing_ids = {r.test_id for r in results if r.outcome == "passed"}
        covered: Set[str] = set()
        for module in changed_modules:
            for result in results:
                reg = by_test_id.get(result.test_id)
                mappings = set(reg.module_mappings_json or []) if reg else set()
                if module in mappings and result.test_id in passing_ids:
                    covered.add(module)
                    break
        coverage_ratio = (len(covered) / len(changed_modules)) if changed_modules else 1.0
        smoke_ok = any(by_test_id.get(r.test_id) is not None and by_test_id[r.test_id].test_type == "smoke" and r.outcome == "passed" for r in results)
        unresolved = sum(1 for r in results if r.outcome not in ("passed", "skipped"))
        flaky_involved = any(r.retried_flag for r in results)
        flaky_still_failing = any(r.retried_flag and r.outcome not in ("passed", "skipped") for r in results)
        if flaky_involved and not flaky_still_failing:
            flaky_factor = 0.25
        elif flaky_involved:
            flaky_factor = 1.0
        else:
            flaky_factor = 0.0
        sensitive_modules = {m.name for m in ModulesRepo(session).all() if m.security_sensitive}
        security_findings = sum(1 for module in changed_modules if module in sensitive_modules and not any(set((by_test_id.get(r.test_id).module_mappings_json or [])) & {module} for r in results if r.outcome == "passed"))
        security_penalty = min(1.0, 0.5 * security_findings)
        score, breakdown = compute_confidence(passed_ratio, coverage_ratio, smoke_ok, unresolved, flaky_factor, security_penalty)
        breakdown_full = dict(breakdown)
        breakdown_full["flakiness_penalty_factor"] = flaky_factor
        breakdown_full["security_findings"] = security_findings
        ConfidenceRepo(session).add(params.change_id, score, breakdown_full)
        metrics.set_gauge("qe_last_confidence_score", score)
        return {"score": score, "breakdown": breakdown_full}


class EvaluateQualityGateInput(BaseModel):
    change_id: int


class EvaluateQualityGateTool(ToolDefinition):
    name = "evaluate_quality_gate_tool"
    description = "Deterministic quality-gate decision from the confidence score and blocking contexts."
    permission = "safe"
    timeout_s = 15
    input_model = EvaluateQualityGateInput

    def run(self, session: Session, params: EvaluateQualityGateInput) -> Dict[str, Any]:
        confidence = ConfidenceRepo(session).latest(params.change_id)
        if confidence is None:
            raise RuntimeError(f"no confidence score for change {params.change_id}")
        breakdown = confidence.breakdown_json
        critical_failures = self._critical_failures(session, params.change_id)
        verdict = gate_decide(
            score=float(confidence.score),
            unresolved_failures=int(breakdown.get("unresolved_failures", 0)),
            critical_failures=critical_failures,
            security_findings=int(breakdown.get("security_findings", 0)),
            critical_path_missing=bool(breakdown.get("critical_path_validated", 0.0) < 1.0),
        )
        gate = GatesRepo(session).add(params.change_id, verdict["decision"], float(confidence.score), list(verdict["reasons"]))
        metrics.incr_labeled("qe_gate_decisions_total", verdict["decision"])
        return {
            "gate_id": gate.id,
            "decision": gate.decision,
            "score": gate.score,
            "reasons": gate.reasons_json,
            "override_status": gate.override_status,
        }

    def _critical_failures(self, session: Session, change_id: int) -> int:
        execution = ExecutionsRepo(session).latest(change_id)
        if execution is None:
            return 0
        registry_by_test = {t.test_id: t for t in RegistryRepo(session).all()}
        modules_by_name = {m.name: m for m in ModulesRepo(session).all()}
        critical = 0
        for result in ExecutionsRepo(session).results(execution.id):
            if result.outcome in ("passed", "skipped"):
                continue
            reg = registry_by_test.get(result.test_id)
            if reg is None:
                continue
            sensitive = any(
                modules_by_name[m].security_sensitive or modules_by_name[m].criticality >= 5
                for m in reg.module_mappings_json or []
                if m in modules_by_name
            )
            if sensitive or reg.test_type == "smoke":
                critical += 1
        return critical


class TriggerRegressionBugInput(BaseModel):
    active: bool


class TriggerRegressionBugTool(ToolDefinition):
    name = "trigger_regression_bug_tool"
    description = "Toggle the injected payments regression via its state file."
    permission = "mutating"
    timeout_s = 10
    input_model = TriggerRegressionBugInput

    def run(self, session: Session, params: TriggerRegressionBugInput) -> Dict[str, Any]:
        active = payments.set_bug_state(params.active)
        metrics.incr_labeled("qe_bug_toggles_total", "on" if params.active else "off")
        return {"module": "sample_app.payments", "active": bool(active), "state_file": str(payments._BUG_STATE_FILE)}
