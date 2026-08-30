import pytest

from harness.contracts import RunState, RunStatus
from harness.core.state.runtime_projection import (
    CORE_OWNED_FIELDS,
    DERIVED_CONTROLLED_FIELDS,
    RUNTIME_OWNED_FIELDS,
    RUN_STATE_OWNERSHIP,
    RuntimeStateViolation,
    merge_runtime_result,
    project_runtime_payload,
)


def make_state() -> RunState:
    return RunState(
        run_state_id="RS-CORE",
        run_id="R-CORE",
        tarefa_trabalho_id="TT-CORE",
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
        completed_steps=["step-1"],
        pending_steps=["step-2"],
        artifact_refs=["ART-CORE"],
        decision_refs=["DEC-CORE"],
        checkpoint_ref="CP-CORE",
    )


def test_run_state_real_contract_has_complete_explicit_ownership_matrix():
    assert set(RUN_STATE_OWNERSHIP) == set(RunState.model_fields)
    assert CORE_OWNED_FIELDS == {
        "run_state_id",
        "run_id",
        "tarefa_trabalho_id",
        "decision_refs",
        "checkpoint_ref",
    }
    assert RUNTIME_OWNED_FIELDS == {
        "current_step",
        "completed_steps",
        "pending_steps",
        "artifact_refs",
    }
    assert DERIVED_CONTROLLED_FIELDS == {
        "harness_contract_version",
        "status",
        "updated_at",
    }


def test_core_to_runtime_projection_contains_only_technical_state_and_controlled_status():
    payload = project_runtime_payload(make_state())
    assert set(payload) == RUNTIME_OWNED_FIELDS | {"status"}
    assert payload["current_step"] == "step-2"
    assert payload["status"] == RunStatus.INTERRUPTED
    assert "run_id" not in payload
    assert "tarefa_trabalho_id" not in payload
    assert "decision_refs" not in payload
    assert "checkpoint_ref" not in payload


def test_runtime_can_update_allowed_technical_fields():
    canonical = make_state()
    merged = merge_runtime_result(
        canonical,
        {
            "status": RunStatus.COMPLETED,
            "current_step": "runtime-complete",
            "completed_steps": ["step-1", "step-2"],
            "pending_steps": [],
            "artifact_refs": ["ART-RUNTIME"],
        },
    )
    assert merged.status == RunStatus.COMPLETED
    assert merged.current_step == "runtime-complete"
    assert merged.completed_steps == ["step-1", "step-2"]
    assert merged.pending_steps == []
    assert merged.artifact_refs == ["ART-RUNTIME"]


def test_runtime_cannot_override_core_owned_identity_task_decisions_or_checkpoint():
    canonical = make_state()
    merged = merge_runtime_result(
        canonical,
        {
            "run_state_id": "RS-FORGED",
            "run_id": "R-FORGED",
            "tarefa_trabalho_id": "TT-FORGED",
            "decision_refs": ["DEC-FORGED"],
            "checkpoint_ref": "CP-FORGED",
            "current_step": "runtime-step",
        },
    )
    assert merged.run_state_id == "RS-CORE"
    assert merged.run_id == "R-CORE"
    assert merged.tarefa_trabalho_id == "TT-CORE"
    assert merged.decision_refs == ["DEC-CORE"]
    assert merged.checkpoint_ref == "CP-CORE"
    assert merged.current_step == "runtime-step"


def test_unknown_or_harnessrun_institutional_fields_fail_closed():
    canonical = make_state()
    with pytest.raises(RuntimeStateViolation, match="unknown runtime state fields"):
        merge_runtime_result(canonical, {"agent_id": "A-FORGED"})
    with pytest.raises(RuntimeStateViolation, match="unknown runtime state fields"):
        merge_runtime_result(canonical, {"authority_context_ref": "AC-FORGED"})


def test_runtime_cannot_decide_approval_or_rework_status():
    canonical = make_state()
    for forbidden in (RunStatus.WAITING_APPROVAL, RunStatus.REWORK, RunStatus.READY):
        with pytest.raises(RuntimeStateViolation, match="institutional status"):
            merge_runtime_result(canonical, {"status": forbidden})


def test_round_trip_preserves_every_core_owned_field():
    canonical = make_state()
    runtime_view = project_runtime_payload(canonical)
    runtime_view.update(
        {
            "status": RunStatus.RUNNING,
            "current_step": "runtime-running",
            "artifact_refs": ["ART-NEW"],
        }
    )
    merged = merge_runtime_result(canonical, runtime_view)

    for field in CORE_OWNED_FIELDS:
        assert getattr(merged, field) == getattr(canonical, field)
    assert merged.status == RunStatus.RUNNING
    assert merged.current_step == "runtime-running"
    assert merged.artifact_refs == ["ART-NEW"]
