from datetime import datetime

import pytest

from harness.core.freshness.audit import (
    begin_boundary_audit,
    finalize_boundary_audit,
    finalize_runtime_resume_success,
)


def _pending_runtime_record():
    return begin_boundary_audit(
        run_id="R1",
        agent_id="A1",
        tarefa_trabalho_id="MT-1",
        correlation_id="C1",
        boundary="RuntimePort.resume",
        checkpoint_ref="CP-1",
        previous_authority_context_ref="AC-OLD",
        previous_task_context_ref="TC-OLD",
        metadata={
            "versioned_read_set": {
                "reads": [
                    {"source_ref": "AUT-X", "revision_ref": "REV-X-1"},
                    {"source_ref": "TASK", "revision_ref": "REV-TASK-1"},
                ]
            }
        },
    )


def _released_runtime_record():
    return finalize_boundary_audit(
        _pending_runtime_record(),
        status="RELEASED",
        outcome="REVALIDATED_AND_GUARDED",
        authority_context_ref="AC-CURRENT",
        metadata={
            "revision_guard": {
                "guard_id": "RG-1",
                "status": "ACTIVE",
            }
        },
    )


def test_runtime_terminal_success_preserves_full_temporal_history_and_attribution():
    pending = _pending_runtime_record()
    released = finalize_boundary_audit(
        pending,
        status="RELEASED",
        outcome="REVALIDATED_AND_GUARDED",
        authority_context_ref="AC-CURRENT",
        metadata={"revision_guard": {"guard_id": "RG-1", "status": "ACTIVE"}},
    )

    completed = finalize_runtime_resume_success(released)

    assert pending["status"] == "PENDING"
    assert [event.get("outcome") for event in completed["events"]] == [
        None,
        "REVALIDATED_AND_GUARDED",
        "COMPLETED",
    ]
    assert completed["status"] == "RELEASED"
    assert completed["outcome"] == "COMPLETED"

    for key in ("run_id", "agent_id", "tarefa_trabalho_id", "correlation_id", "boundary", "checkpoint_ref"):
        assert completed[key] == released[key]
    assert completed["authority_context_ref"] == "AC-CURRENT"
    assert completed["metadata"]["versioned_read_set"] == released["metadata"]["versioned_read_set"]
    assert completed["metadata"]["revision_guard"] == released["metadata"]["revision_guard"]

    timestamps = [datetime.fromisoformat(event["at"]) for event in completed["events"]]
    assert timestamps == sorted(timestamps)
    assert released["outcome"] == "REVALIDATED_AND_GUARDED"
    assert len(released["events"]) == 2


def test_runtime_terminal_success_is_idempotent_without_duplicate_terminal_event():
    once = finalize_runtime_resume_success(_released_runtime_record())
    twice = finalize_runtime_resume_success(once)

    assert twice == once
    assert [event.get("outcome") for event in twice["events"]].count("COMPLETED") == 1


def test_failed_runtime_trace_cannot_be_rewritten_as_completed():
    released = _released_runtime_record()
    failed = finalize_boundary_audit(
        released,
        status="FAILED",
        outcome="RUNTIME_RESUME_ERROR",
        error=RuntimeError("runtime failed"),
    )
    before = failed.copy()
    before_events = list(failed["events"])

    with pytest.raises(ValueError, match="RELEASED / REVALIDATED_AND_GUARDED"):
        finalize_runtime_resume_success(failed)

    assert failed["outcome"] == "RUNTIME_RESUME_ERROR"
    assert failed["status"] == "FAILED"
    assert failed["events"] == before_events
    assert failed == before


def test_runtime_terminal_success_rejects_wrong_boundary_and_does_not_touch_tool_trace():
    tool_pending = begin_boundary_audit(
        run_id="R1",
        agent_id="A1",
        tarefa_trabalho_id="MT-1",
        correlation_id="C1",
        boundary="ToolPort.invoke",
        previous_authority_context_ref="AC-1",
    )
    tool_released = finalize_boundary_audit(
        tool_pending,
        status="RELEASED",
        outcome="AUTHORIZED_AND_GUARDED",
    )
    tool_completed = finalize_boundary_audit(
        tool_released,
        status="RELEASED",
        outcome="COMPLETED",
    )
    before = tool_completed.copy()
    before_events = list(tool_completed["events"])

    with pytest.raises(ValueError, match="RuntimePort.resume"):
        finalize_runtime_resume_success(tool_completed)

    assert tool_completed == before
    assert tool_completed["events"] == before_events
    assert [event.get("outcome") for event in tool_completed["events"]] == [
        None,
        "AUTHORIZED_AND_GUARDED",
        "COMPLETED",
    ]


def test_runtime_terminal_success_requires_revalidated_and_guarded_release():
    pending = _pending_runtime_record()

    with pytest.raises(ValueError, match="RELEASED / REVALIDATED_AND_GUARDED"):
        finalize_runtime_resume_success(pending)


def test_runtime_terminal_success_rejects_inconsistent_existing_completed_state():
    record = _released_runtime_record()
    record["outcome"] = "COMPLETED"

    with pytest.raises(ValueError, match="inconsistent COMPLETED"):
        finalize_runtime_resume_success(record)
