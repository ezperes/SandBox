import pytest

from harness.contracts import RunStatus
from harness.core.state.resume_policy import (
    ResumeStatusDecision,
    ResumeStatusRejected,
    evaluate_resume_status,
    require_resume_status_allowed,
    resume_status_policy_table,
)


def test_interrupted_is_directly_resumable():
    result = require_resume_status_allowed(RunStatus.INTERRUPTED)
    assert result.allowed is True
    assert result.decision == ResumeStatusDecision.ALLOW
    assert result.required_transition is None


def test_waiting_external_is_blocked_until_core_owned_transition():
    result = evaluate_resume_status(RunStatus.WAITING_EXTERNAL)
    assert result.allowed is False
    assert result.decision == ResumeStatusDecision.BLOCK_EXTERNAL_WAIT
    assert result.required_transition == RunStatus.INTERRUPTED
    with pytest.raises(ResumeStatusRejected):
        require_resume_status_allowed(RunStatus.WAITING_EXTERNAL)


def test_waiting_approval_cannot_bypass_approval_gate():
    result = evaluate_resume_status(RunStatus.WAITING_APPROVAL)
    assert result.allowed is False
    assert result.decision == ResumeStatusDecision.BLOCK_APPROVAL_GATE
    assert result.required_transition == RunStatus.INTERRUPTED
    assert "Approval Gate" in result.reason
    with pytest.raises(ResumeStatusRejected):
        require_resume_status_allowed(RunStatus.WAITING_APPROVAL)


@pytest.mark.parametrize(
    "status",
    [RunStatus.COMPLETED, RunStatus.CANCELLED, RunStatus.FAILED],
)
def test_terminal_states_are_blocked(status):
    result = evaluate_resume_status(status)
    assert result.allowed is False
    assert result.decision == ResumeStatusDecision.BLOCK_TERMINAL
    with pytest.raises(ResumeStatusRejected):
        require_resume_status_allowed(status)


def test_running_is_blocked_as_already_active():
    result = evaluate_resume_status(RunStatus.RUNNING)
    assert result.allowed is False
    assert result.decision == ResumeStatusDecision.BLOCK_ACTIVE
    with pytest.raises(ResumeStatusRejected):
        require_resume_status_allowed(RunStatus.RUNNING)


@pytest.mark.parametrize("invalid", ["UNKNOWN", "", None, 123])
def test_invalid_or_unknown_status_fails_closed(invalid):
    result = evaluate_resume_status(invalid)
    assert result.allowed is False
    assert result.status is None
    assert result.decision == ResumeStatusDecision.BLOCK_INVALID
    with pytest.raises(ResumeStatusRejected):
        require_resume_status_allowed(invalid)


def test_created_ready_and_rework_are_not_direct_resume_states():
    created = evaluate_resume_status(RunStatus.CREATED)
    ready = evaluate_resume_status(RunStatus.READY)
    rework = evaluate_resume_status(RunStatus.REWORK)

    assert created.decision == ResumeStatusDecision.BLOCK_NOT_STARTED
    assert ready.decision == ResumeStatusDecision.BLOCK_NOT_STARTED
    assert rework.decision == ResumeStatusDecision.BLOCK_REWORK
    assert rework.required_transition == RunStatus.INTERRUPTED


def test_policy_table_covers_every_canonical_run_status_exactly_once():
    table = resume_status_policy_table()
    assert tuple(item.status for item in table) == tuple(RunStatus)
    assert len(table) == len(RunStatus)
    assert [item.status for item in table if item.allowed] == [RunStatus.INTERRUPTED]
