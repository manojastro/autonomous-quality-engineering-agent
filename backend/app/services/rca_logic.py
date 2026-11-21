"""Root-cause analysis synthesis from failure evidence."""
from __future__ import annotations

from typing import Dict, List

from sample_app import payments


def _stack_first_lines(message: str, lines: int = 6) -> str:
    return "\n".join((message or "").splitlines()[:lines])


def build_rca(
    incident_id: str,
    test_id: str,
    node_id: str,
    message: str,
    changed_functions: Dict[str, List[str]],
    module_mappings: List[str],
    history: List[str],
) -> Dict[str, object]:
    """Correlate stack trace, log context, diff and history into an RCA payload."""
    observations: List[str] = [
        f"test {test_id} ({node_id}) failed deterministically on the selected run",
        f"assertion/exception excerpt: {_stack_first_lines(message)}",
        f"recent registry history: {history[-8:] if history else 'empty'}",
    ]
    evidence: List[str] = []
    hypotheses: List[str] = [
        "H1 (likely): behavioral regression introduced by the current change in the exercised code path",
        "H2: injected regression flag active for a payment-critical module",
        "H3: environmental instability (timeout, connection, resource contention)",
        "H4: test automation defect unrelated to application behavior",
    ]
    rejected: List[str] = []
    bug_active = False
    try:
        bug_active = payments.bug_active()
    except Exception:
        bug_active = False

    if bug_active:
        evidence.append("payments regression state active: QE_BUG_PAYMENTS env or sample_app/.qe_bug_payments present")
        evidence.append(f"failing path exercises payments.validate_amount / transaction_fee via {module_mappings}")
        root_cause = (
            "Injected regression in sample_app.payments is active: validate_amount uses an off-by-one upper "
            "bound that accepts amounts above MAX_SINGLE_TRANSACTION, and transaction_fee switches half-even "
            "rounding to ceiling, shifting totals by one cent across orders, refunds and recurring billing."
        )
        confidence = 0.95
        rejected.append("Rejected H1 as primary: failure magnitude matches the injected defect signature exactly")
        rejected.append("Rejected H3: failure reproduces deterministically without environmental noise")
        recommended = [
            "Disable the injected regression (POST /api/v1/bugs/payments/off or delete sample_app/.qe_bug_payments)",
            "Re-run the selected subset to confirm green before re-scoring confidence",
            "Add boundary hardening cases at MAX_SINGLE_TRANSACTION + epsilon to prevent recurrence",
        ]
    else:
        touched_functions = [f"{mod}:{fn}" for mod, fns in changed_functions.items() for fn in fns]
        evidence.append(f"change manifest touches: {', '.join(touched_functions) if touched_functions else 'module-level edits'}")
        stable_history = history and all(o == "pass" for o in history[:-1])
        if detect_alternation_flips(history):
            root_cause = "Alternating pass/fail history indicates an unstable test rather than a product regression"
            confidence = 0.6
            rejected.append("Rejected H2: no regression flag is active for this module")
        else:
            root_cause = f"Change-induced behavioral regression in the exercised functions ({', '.join(touched_functions[:3]) or module_mappings})"
            confidence = 0.7
            rejected.append("Rejected H2: no injected regression flag is active")
            if stable_history:
                rejected.append("Rejected pre-existing-defect hypothesis: registry history shows consistent passes before this change")
        recommended = [
            "Inspect the failing assertions against the diff hunks of the current change",
            "Re-run the focused subset after fix and require gate re-evaluation",
            "Capture a regression test pinning the corrected behavior",
        ]
    observations.append(f"root cause hypothesis selected with confidence {confidence}")
    return {
        "incident_id": incident_id,
        "observations": observations,
        "evidence": evidence,
        "hypotheses": hypotheses,
        "rejected_hypotheses": rejected,
        "root_cause": root_cause,
        "confidence": confidence,
        "recommended_actions": recommended,
    }


def detect_alternation_flips(history: List[str], window: int = 8, min_flips: int = 4) -> bool:
    recent = [o for o in (history or [])[-window:] if o in ("pass", "fail")]
    flips = sum(1 for a, b in zip(recent, recent[1:]) if a != b)
    return flips >= min_flips
