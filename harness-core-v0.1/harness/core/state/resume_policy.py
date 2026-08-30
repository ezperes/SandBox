from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from harness.contracts import RunStatus


class ResumeStatusDecision(StrEnum):
    ALLOW = "ALLOW"
    BLOCK_NOT_STARTED = "BLOCK_NOT_STARTED"
    BLOCK_ACTIVE = "BLOCK_ACTIVE"
    BLOCK_APPROVAL_GATE = "BLOCK_APPROVAL_GATE"
    BLOCK_EXTERNAL_WAIT = "BLOCK_EXTERNAL_WAIT"
    BLOCK_REWORK = "BLOCK_REWORK"
    BLOCK_TERMINAL = "BLOCK_TERMINAL"
    BLOCK_INVALID = "BLOCK_INVALID"


@dataclass(frozen=True, slots=True)
class ResumeStatusPolicyResult:
    status: RunStatus | None
    decision: ResumeStatusDecision
    allowed: bool
    reason: str
    required_transition: RunStatus | None = None


class ResumeStatusRejected(RuntimeError):
    """Core-owned rejection raised before RuntimePort.resume may be crossed."""

    def __init__(self, result: ResumeStatusPolicyResult) -> None:
        self.result = result
        status = result.status.value if result.status is not None else "INVALID"
        super().__init__(f"resume blocked for status {status}: {result.reason}")


_POLICY: dict[RunStatus, ResumeStatusPolicyResult] = {
    RunStatus.CREATED: ResumeStatusPolicyResult(
        status=RunStatus.CREATED,
        decision=ResumeStatusDecision.BLOCK_NOT_STARTED,
        allowed=False,
        reason="CREATED is not a resumable checkpoint state; normal start/execute flow is required",
    ),
    RunStatus.READY: ResumeStatusPolicyResult(
        status=RunStatus.READY,
        decision=ResumeStatusDecision.BLOCK_NOT_STARTED,
        allowed=False,
        reason="READY must enter normal start/execute flow; resume is not a start primitive",
    ),
    RunStatus.RUNNING: ResumeStatusPolicyResult(
        status=RunStatus.RUNNING,
        decision=ResumeStatusDecision.BLOCK_ACTIVE,
        allowed=False,
        reason="RUNNING is already active; a second resume would create concurrent/replayed execution",
    ),
    RunStatus.INTERRUPTED: ResumeStatusPolicyResult(
        status=RunStatus.INTERRUPTED,
        decision=ResumeStatusDecision.ALLOW,
        allowed=True,
        reason="INTERRUPTED is the only direct checkpoint-resumable state in Harness Core V0.1",
    ),
    RunStatus.WAITING_APPROVAL: ResumeStatusPolicyResult(
        status=RunStatus.WAITING_APPROVAL,
        decision=ResumeStatusDecision.BLOCK_APPROVAL_GATE,
        allowed=False,
        reason=(
            "WAITING_APPROVAL cannot cross RuntimePort.resume; the Core-owned Approval Gate must "
            "resolve first and transition the run to INTERRUPTED before resume"
        ),
        required_transition=RunStatus.INTERRUPTED,
    ),
    RunStatus.WAITING_EXTERNAL: ResumeStatusPolicyResult(
        status=RunStatus.WAITING_EXTERNAL,
        decision=ResumeStatusDecision.BLOCK_EXTERNAL_WAIT,
        allowed=False,
        reason=(
            "WAITING_EXTERNAL cannot cross RuntimePort.resume until the Core recognizes the external "
            "condition as satisfied and transitions the run to INTERRUPTED"
        ),
        required_transition=RunStatus.INTERRUPTED,
    ),
    RunStatus.REWORK: ResumeStatusPolicyResult(
        status=RunStatus.REWORK,
        decision=ResumeStatusDecision.BLOCK_REWORK,
        allowed=False,
        reason=(
            "REWORK is a work disposition, not a direct resume authorization; Core must explicitly "
            "prepare the rework continuation and transition the run to INTERRUPTED before resume"
        ),
        required_transition=RunStatus.INTERRUPTED,
    ),
    RunStatus.FAILED: ResumeStatusPolicyResult(
        status=RunStatus.FAILED,
        decision=ResumeStatusDecision.BLOCK_TERMINAL,
        allowed=False,
        reason="FAILED is terminal for direct resume; retry/recovery requires an explicit Core-owned lifecycle transition",
    ),
    RunStatus.COMPLETED: ResumeStatusPolicyResult(
        status=RunStatus.COMPLETED,
        decision=ResumeStatusDecision.BLOCK_TERMINAL,
        allowed=False,
        reason="COMPLETED is terminal and must never cross RuntimePort.resume",
    ),
    RunStatus.CANCELLED: ResumeStatusPolicyResult(
        status=RunStatus.CANCELLED,
        decision=ResumeStatusDecision.BLOCK_TERMINAL,
        allowed=False,
        reason="CANCELLED is terminal and must never cross RuntimePort.resume",
    ),
}


def evaluate_resume_status(status: Any) -> ResumeStatusPolicyResult:
    """Return the Core-owned resume decision for a canonical or untrusted status value."""

    try:
        canonical = status if isinstance(status, RunStatus) else RunStatus(status)
    except (TypeError, ValueError):
        return ResumeStatusPolicyResult(
            status=None,
            decision=ResumeStatusDecision.BLOCK_INVALID,
            allowed=False,
            reason="unknown or invalid RunState.status fails closed before RuntimePort.resume",
        )
    return _POLICY[canonical]


def require_resume_status_allowed(status: Any) -> ResumeStatusPolicyResult:
    """Fail closed unless status is explicitly authorized for direct resume."""

    result = evaluate_resume_status(status)
    if not result.allowed:
        raise ResumeStatusRejected(result)
    return result


def resume_status_policy_table() -> tuple[ResumeStatusPolicyResult, ...]:
    """Stable complete policy table for tests, audit documentation, and Integrator wiring."""

    return tuple(_POLICY[status] for status in RunStatus)
