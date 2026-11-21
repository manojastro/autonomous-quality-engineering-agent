"""Release approval state machine."""
from __future__ import annotations

from typing import Any, Dict, Set

from sqlalchemy.orm import Session

from backend.app.models import utcnow_iso
from backend.app.repositories import ApprovalsRepo, GatesRepo, WorkflowRepo

TRANSITIONS: Dict[str, Set[str]] = {
    "PROPOSED": {"VALIDATING"},
    "VALIDATING": {"EXECUTING", "FAILED"},
    "EXECUTING": {"VERIFYING", "FAILED"},
    "VERIFYING": {"AWAITING_APPROVAL", "COMPLETED", "FAILED"},
    "AWAITING_APPROVAL": {"APPROVED", "ROLLED_BACK"},
    "APPROVED": {"COMPLETED", "ROLLED_BACK"},
    "COMPLETED": set(),
    "FAILED": set(),
    "ROLLED_BACK": set(),
}

TERMINAL_STATES = {"COMPLETED", "FAILED", "ROLLED_BACK"}
BLOCK_OVERRIDE_MIN_JUSTIFICATION = 20


class WorkflowError(RuntimeError):
    """Raised on illegal workflow transitions or invalid overrides."""


class ApprovalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.workflows = WorkflowRepo(session)
        self.gates = GatesRepo(session)
        self.approvals = ApprovalsRepo(session)

    def transition(self, change_id: int, target: str) -> str:
        row = self.workflows.require_by_change(change_id)
        allowed = TRANSITIONS.get(row.state, set())
        if target not in allowed:
            raise WorkflowError(f"illegal transition {row.state} -> {target}")
        row.history_json = list(row.history_json or []) + [{"state": target, "at": utcnow_iso()}]
        row.state = target
        row.updated_at = utcnow_iso()
        self.session.flush()
        return row.state

    def state_of(self, change_id: int) -> str:
        return self.workflows.require_by_change(change_id).state

    def override_gate(self, gate_id: int, action: str, approver: str, justification: str) -> Dict[str, Any]:
        gate = self.gates.require(gate_id)
        if gate.override_status != "open":
            raise WorkflowError("gate decision already overridden")
        workflow = self.workflows.require_by_change(gate.change_id)
        if workflow.state != "AWAITING_APPROVAL":
            raise WorkflowError(f"override requires AWAITING_APPROVAL, found {workflow.state}")
        if gate.decision == "block" and action == "approve":
            if len(justification.strip()) < BLOCK_OVERRIDE_MIN_JUSTIFICATION:
                raise WorkflowError("overriding a blocked release requires a substantive justification")
        target_state = "APPROVED" if action == "approve" else "ROLLED_BACK"
        self.transition(gate.change_id, target_state)
        gate.override_status = f"{action}ed_by:{approver}"
        self.approvals.add(
            workflow_id=workflow.id, gate_decision_id=gate.id, action=action, approver=approver, justification=justification
        )
        self.session.flush()
        return {
            "gate_id": gate.id,
            "previous_decision": gate.decision,
            "action": action,
            "approver": approver,
            "workflow_state": target_state,
            "effective_release": "allowed_with_override" if action == "approve" else "halted",
        }
