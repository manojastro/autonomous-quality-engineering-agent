"""Demo: inject a real payments regression, watch the agent block the release, then fix and allow.

Run:  python scripts/create_regression.py
Exit code 0 means every stage behaved as designed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "demo.db"
os.environ["QE_DB_URL"] = f"sqlite:///{DB_PATH.as_posix()}"

from fastapi.testclient import TestClient

from sample_app import payments as pay

from backend.app.db import dispose_engine
from backend.app.main import app

MANIFEST = {
    "title": "Tighten payment validation boundaries",
    "files": [
        {
            "path": "sample_app/payments.py",
            "functions_changed": ["validate_amount", "transaction_fee"],
            "lines_added": 18,
            "lines_deleted": 4,
        }
    ],
}


def stage(title: str) -> None:
    print(f"\n{'=' * 74}\nSTAGE {title}\n{'=' * 74}")


def main() -> int:
    if DB_PATH.exists():
        DB_PATH.unlink()
    pay.set_bug_state(False)

    with TestClient(app) as client:
        stage("1. INJECT REGRESSION (real behaviour change in sample_app/payments.py)")
        state = client.post("/api/v1/bugs/payments/on").json()
        print(f"  bug state file: {state['state_file']}")
        print(f"  active={state['active']} -> validate_amount now accepts amounts above the limit")
        print(f"             transaction_fee now rounds UP instead of half-even")

        stage("2. SUBMIT CHANGE MANIFEST touching payments.validate_amount + transaction_fee")
        change = client.post("/api/v1/changes", json=MANIFEST).json()
        print(f"  change #{change['id']} '{change['title']}' (+{change['lines_added']}/-{change['lines_deleted']} lines)")

        stage("3. ANALYZE: dependency closure, selection, execution, RCA, confidence, gate")
        summary = client.post(f"/api/v1/changes/{change['id']}/analyze").json()

        stage("3a. IMPACTED MODULE CLOSURE (AST import graph)")
        for module in summary["impacted_modules"]:
            reason = next(e["reason"] for e in client.get(f"/api/v1/changes/{change['id']}/impact").json()["impacted_modules"] if e["module"] == module)
            print(f"  {module:26s} <- {reason}")

        stage("3b. TEST SELECTION (focused subset, NOT the whole suite)")
        print(f"  registry total: {summary['total_tests']}  selected: {summary['selected_count']}  reduction: {summary['reduction_pct']}%")
        selection = client.get(f"/api/v1/changes/{change['id']}/selection").json()
        for item in selection["selected"]:
            print(f"    [{item['priority_score']:6.2f}] {item['test_id']:32s} ({item['test_type']})")

        stage("3c. EXECUTION: real pytest subprocess run")
        print(f"  executed={summary['executed_total']} passed={summary['executed_passed']} FAILED={summary['executed_failed']}")
        execution = client.get(f"/api/v1/changes/{change['id']}/execution").json()
        for result in execution["results"]:
            if result["outcome"] not in ("passed", "skipped"):
                print(f"    FAIL {result['node_id']}")

        stage("3d. FAILURE RCA (stack trace + log excerpt + diff + history)")
        failures = client.get(f"/api/v1/changes/{change['id']}/failures").json()
        first = failures["failures"][0]
        rca = first["rca"]
        print(f"  incident:   {rca['incident_id']}")
        print(f"  root cause: {rca['root_cause']}")
        print(f"  confidence: {rca['confidence']}")
        for evidence in rca["evidence"]:
            print(f"  evidence:   {evidence}")
        for rejected in rca["rejected_hypotheses"]:
            print(f"  rejected:   {rejected}")
        boundary = next((f for f in failures["failures"] if f["test_id"] == "payments_boundary_above_limit"), None)
        if boundary:
            print("  stack trace head:")
            for line in boundary["stack_trace"].splitlines()[:3]:
                print(f"    | {line}")

        stage("3e. RELEASE CONFIDENCE (deterministic weighted deduction)")
        confidence = client.get(f"/api/v1/changes/{change['id']}/confidence").json()
        breakdown = confidence["breakdown"]
        print(f"  SCORE: {confidence['score']} / 100")
        for key in ("deduction_failed_results", "deduction_unresolved_failures", "deduction_flakiness", "deduction_security"):
            print(f"    {key:36s} -{breakdown[key]}")

        stage("3f. QUALITY GATE DECISION")
        gate = client.get(f"/api/v1/changes/{change['id']}/gate").json()
        assert gate["decision"] == "block", "gate must BLOCK a release with unresolved payment-boundary failures"
        for reason in gate["reasons"]:
            print(f"  - {reason}")

        stage("4. DISABLE REGRESSION AND RESUBMIT THE FIXED CHANGE")
        off = client.post("/api/v1/bugs/payments/off").json()
        print(f"  bug active={off['active']}")
        fixed_change = client.post("/api/v1/changes", json=MANIFEST).json()
        fixed_summary = client.post(f"/api/v1/changes/{fixed_change['id']}/analyze").json()
        print(f"  rerun: selected={fixed_summary['selected_count']} failed={fixed_summary['executed_failed']} confidence={fixed_summary['confidence']}")
        fixed_gate = client.get(f"/api/v1/changes/{fixed_change['id']}/gate").json()
        assert fixed_gate["decision"] == "allow", "gate must ALLOW once the regression is gone"
        for reason in fixed_gate["reasons"]:
            print(f"  - {reason}")

        stage("5. KPI SNAPSHOT")
        kpis = client.get("/api/v1/kpis").json()
        print(f"  selection precision/recall avg : {kpis['selection_precision_avg']} / {kpis['selection_recall_avg']}")
        print(f"  missed regressions             : {kpis['missed_regressions']}")
        print(f"  flaky classification           : {kpis['flaky_classification']}")
        print(f"  confidence-vs-outcome accuracy : {kpis['confidence_agreement']['accuracy']} over {kpis['confidence_agreement']['evaluated']} decisions")

        stage("DEMO SUMMARY")
        print(f"  REAL failure caught          : {summary['executed_failed']} failing tests on change #{change['id']}")
        print(f"  RCA root cause               : injected payments regression named with {rca['confidence']:.2f} confidence")
        print(f"  suite reduction              : {summary['reduction_pct']}% ({summary['total_tests']} -> {summary['selected_count']} tests)")
        print(f"  gate decision (buggy)        : BLOCK at confidence {summary['confidence']}")
        print(f"  gate decision (after fix)    : ALLOW at confidence {fixed_summary['confidence']}")

    dispose_engine()
    pay.set_bug_state(False)
    if DB_PATH.exists():
        DB_PATH.unlink()
    print("\nDEMO COMPLETE exit=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
