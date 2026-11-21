"""KPI computation: selection quality, reduction, detection, flakiness, confidence agreement."""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.analysis.ground_truth import LABELED_CASES
from backend.app.analysis.impact import analyze_change
from backend.app.analysis.selection import selection_precision_recall, select_tests
from backend.app.models import Execution
from backend.app.repositories import FlakyRepo, GatesRepo, RegistryRepo
from backend.app.services.flaky_classifier import detect_alternation


def compute_labeled_selection_metrics(registry_rows: list) -> List[Dict[str, Any]]:
    by_id = {t.test_id: t for t in registry_rows}
    rows: List[Dict[str, Any]] = []
    for case in LABELED_CASES:
        impact = analyze_change(case["manifest"]["files"])
        plan = select_tests(registry_rows, impact.impacted_modules)
        pr = selection_precision_recall(plan["selected"], by_id, case["true_impacted_modules"])
        rows.append(
            {
                "case": case["name"],
                "true_impacted": case["true_impacted_modules"],
                "predicted_closure": impact.impacted_modules,
                "selected_count": plan["selected_count"],
                "total_tests": plan["total_tests"],
                "reduction_pct": plan["reduction_pct"],
                "precision": pr["precision"],
                "recall": pr["recall"],
            }
        )
    return rows


def flaky_classification_accuracy(session: Session) -> Dict[str, Any]:
    expected = {
        "flaky_search_refresh": "flaky_test",
        "flaky_auth_handshake": "flaky_test",
    }
    reports = FlakyRepo(session).recent(limit=200)
    if not reports:
        return {"available": False, "accuracy": None, "samples": 0}
    correct = 0
    for report in reports:
        truth = expected.get(report.test_id)
        if truth is None:
            truth = "product_defect" if report.classification in ("product_defect", "environment", "automation_defect", "unknown") else report.classification
        if report.classification == truth:
            correct += 1
    return {"available": True, "accuracy": round(correct / len(reports), 3), "samples": len(reports)}


def confidence_outcome_agreement(session: Session) -> Dict[str, Any]:
    gates_repo = GatesRepo(session)
    agreements = 0
    evaluated = 0
    details: List[Dict[str, Any]] = []
    seen_changes: set[int] = set()
    all_executions = list(session.execute(select(Execution)).scalars().all())
    for execution in all_executions:
        if execution.change_id in seen_changes:
            continue
        gate = gates_repo.latest(execution.change_id)
        if gate is None or gate.decision == "review":
            continue
        seen_changes.add(execution.change_id)
        real_defect = execution.failed > 0
        gate_blocks = gate.decision == "block"
        agree = real_defect == gate_blocks
        evaluated += 1
        agreements += 1 if agree else 0
        details.append({"change_id": execution.change_id, "decision": gate.decision, "failed": execution.failed, "agree": agree})
    return {"evaluated": evaluated, "agreements": agreements, "accuracy": round(agreements / evaluated, 3) if evaluated else None, "details": details}


def missed_regressions(session: Session) -> Dict[str, Any]:
    """Failing tests relevant to a labeled impact set that were not selected."""
    registry_rows = RegistryRepo(session).all()
    misses = 0
    for case in LABELED_CASES:
        impact = analyze_change(case["manifest"]["files"])
        plan = select_tests(registry_rows, impact.impacted_modules)
        selected_ids = {item["test_id"] for item in plan["selected"]}
        true_set = set(case["true_impacted_modules"])
        for test in registry_rows:
            maps = set(test.module_mappings_json or [])
            if maps & true_set and test.test_id not in selected_ids:
                misses += 1
    return {"missed_regressions": misses}


def overall_reduction(session: Session) -> Dict[str, Any]:
    from sqlalchemy import select

    from backend.app.models import SelectionRecord

    rows = list(session.execute(select(SelectionRecord)).scalars().all())
    if not rows:
        return {"average_reduction_pct": None, "selection_runs": 0}
    return {
        "average_reduction_pct": round(sum(r.reduction_pct for r in rows) / len(rows), 2),
        "selection_runs": len(rows),
    }


def compute_all(session: Session) -> Dict[str, Any]:
    registry_rows = RegistryRepo(session).all()
    labeled = compute_labeled_selection_metrics(registry_rows)
    precision_values = [row["precision"] for row in labeled]
    recall_values = [row["recall"] for row in labeled]
    kpis: Dict[str, Any] = {
        "labeled_cases": labeled,
        "selection_precision_avg": round(sum(precision_values) / len(precision_values), 3),
        "selection_recall_avg": round(sum(recall_values) / len(recall_values), 3),
        "suite_reduction": overall_reduction(session),
        "missed_regressions": missed_regressions(session)["missed_regressions"],
        "flaky_classification": flaky_classification_accuracy(session),
        "confidence_agreement": confidence_outcome_agreement(session),
        "registry_size": len(registry_rows),
    }
    return kpis
