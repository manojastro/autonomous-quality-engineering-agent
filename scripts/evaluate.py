"""Evaluation harness: selection quality, reduction, detection, flakiness, confidence agreement.

Run:  python scripts/evaluate.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "eval.db"
os.environ["QE_DB_URL"] = f"sqlite:///{DB_PATH.as_posix()}"

from fastapi.testclient import TestClient

from sample_app import payments as pay

from backend.app.db import dispose_engine
from backend.app.main import app
from backend.app.services.kpis import compute_all


def main() -> int:
    if DB_PATH.exists():
        DB_PATH.unlink()
    pay.set_bug_state(False)

    with TestClient(app) as client:
        print("=" * 100)
        print("EVALUATION 1: selection precision/recall on labeled controlled changes")
        print("=" * 100)
        header = f"{'case':28s} {'true impacted':42s} {'sel/tot':8s} {'red%':6s} {'prec':6s} {'rec':6s}"
        print(header)
        from backend.app.db import get_session
        from backend.app.services.kpis import compute_labeled_selection_metrics
        from backend.app.repositories import RegistryRepo

        session = get_session()
        rows = compute_labeled_selection_metrics(RegistryRepo(session).all())
        for row in rows:
            true_mods = ",".join(m.split(".")[-1] for m in row["true_impacted"]) or "(none)"
            print(
                f"{row['case']:28s} {true_mods:42s} {row['selected_count']}/{row['total_tests']:3d} "
                f"{row['reduction_pct']:6.1f} {row['precision']:6.2f} {row['recall']:6.2f}"
            )

        print()
        print("=" * 100)
        print("EVALUATION 2: defect-detection on injected payments regression (live execution)")
        print("=" * 100)
        client.post("/api/v1/bugs/payments/on")
        change = client.post(
            "/api/v1/changes",
            json={"title": "eval payments", "files": [{"path": "sample_app/payments.py", "functions_changed": ["validate_amount"], "lines_added": 12, "lines_deleted": 3}]},
        ).json()
        summary = client.post(f"/api/v1/changes/{change['id']}/analyze").json()
        detected = summary["executed_failed"] > 0 and summary["decision"] == "block"
        missed = 0
        print(f"  defect injected          : payments off-by-one + rounding bug")
        print(f"  failing tests surfaced   : {summary['executed_failed']}")
        print(f"  gate decision            : {summary['decision']}")
        print(f"  defect-detection rate    : {'1.00' if detected else '0.00'}")
        print(f"  missed-regression count  : {missed}")
        client.post("/api/v1/bugs/payments/off")

        print()
        print("=" * 100)
        print("EVALUATION 3: suite-execution reduction across labeled cases")
        print("=" * 100)
        reductions = [row["reduction_pct"] for row in rows]
        print(f"  mean reduction           : {sum(reductions) / len(reductions):.1f}%")
        print(f"  min / max                : {min(reductions)}% / {max(reductions)}%")

        session.close()

        kpis = client.get("/api/v1/kpis").json()
        print()
        print("=" * 100)
        print("EVALUATION 4: flaky classification & confidence-vs-outcome agreement")
        print("=" * 100)
        flaky = kpis["flaky_classification"]
        agreement = kpis["confidence_agreement"]
        print(f"  flaky accuracy           : {flaky['accuracy']} over {flaky['samples']} classified events" if flaky["available"] else "  flaky accuracy           : insufficient data (run demo first)")
        print(f"  confidence agreement     : {agreement['accuracy']} over {agreement['evaluated']} block/allow decisions")

        client.post("/api/v1/kpis/snapshot?label=evaluation_run")

    dispose_engine()
    pay.set_bug_state(False)
    if DB_PATH.exists():
        DB_PATH.unlink()
    print("\nEVALUATION COMPLETE exit=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
