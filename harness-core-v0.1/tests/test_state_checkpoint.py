import pytest

from harness.adapters.runtimes.fake import FakeRuntimeAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.identity import HarnessResolutionError
from harness.core.state import StateManager


def make_run() -> HarnessRun:
    return HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref="AC1",
    )


def make_state() -> RunState:
    return RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
        completed_steps=["step-1"],
        pending_steps=["step-2"],
        artifact_refs=["ART-1"],
    )


def test_state_port_persists_by_value_not_shared_reference():
    port = InMemoryStateAdapter()
    state = make_state()
    port.save_run_state(state)
    state.completed_steps.append("mutated-after-save")
    loaded = port.load_run_state("RS1")
    assert loaded.completed_steps == ["step-1"]


def test_checkpoint_persists_and_resume_uses_canonical_state():
    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = make_state()
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue from step-2",
        evidence_refs=["EV-1"],
    )

    resumed = manager.resume(make_run(), FakeRuntimeAdapter(), checkpoint.checkpoint_id)
    assert resumed.status == RunStatus.COMPLETED
    assert resumed.current_step == "fake-runtime-resume-complete"
    assert port.load_run_state("RS1").status == RunStatus.COMPLETED


def test_resume_rejects_checkpoint_from_another_run():
    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = make_state()
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")
    wrong = make_run().model_copy(update={"run_id": "R2"})

    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(wrong, FakeRuntimeAdapter(), checkpoint.checkpoint_id)
    assert exc.value.code == HarnessErrorCode.CHECKPOINT_INVALID


def test_side_effect_idempotency_blocks_duplicate_execution():
    manager = StateManager(InMemoryStateAdapter())
    first = manager.claim_side_effect("R1", "CREATE_PAYMENT", "ORDER-9")
    assert first == "R1:CREATE_PAYMENT:ORDER-9"

    with pytest.raises(HarnessResolutionError) as exc:
        manager.claim_side_effect("R1", "CREATE_PAYMENT", "ORDER-9")
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED


def test_distinct_business_keys_are_independent():
    manager = StateManager(InMemoryStateAdapter())
    assert manager.claim_side_effect("R1", "SEND", "A") != manager.claim_side_effect("R1", "SEND", "B")
