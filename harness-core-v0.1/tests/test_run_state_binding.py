import pytest

from harness.contracts import Checkpoint, HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.errors import HarnessResolutionError
from harness.core.state.binding import RunStateBindingGuard


def _run(*, run_id="R1", task_id="T1", run_state_ref="RS1", agent_id="A1") -> HarnessRun:
    return HarnessRun(
        run_id=run_id,
        tarefa_trabalho_id=task_id,
        agent_id=agent_id,
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref=run_state_ref,
        authority_context_ref="AC1",
    )


def _state(*, run_id="R1", task_id="T1", run_state_id="RS1", checkpoint_ref="CP1") -> RunState:
    return RunState(
        run_state_id=run_state_id,
        run_id=run_id,
        tarefa_trabalho_id=task_id,
        status=RunStatus.INTERRUPTED,
        current_step="step-1",
        checkpoint_ref=checkpoint_ref,
    )


def _checkpoint(*, checkpoint_id="CP1", run_id="R1", run_state_ref="RS1") -> Checkpoint:
    return Checkpoint(
        checkpoint_id=checkpoint_id,
        run_id=run_id,
        run_state_ref=run_state_ref,
        validated_step="step-1",
        resume_instruction="resume step-2",
    )


def _assert_blocked(run, state, checkpoint, expected_fragment: str) -> None:
    with pytest.raises(HarnessResolutionError) as exc:
        RunStateBindingGuard.ensure_bound(run, state, checkpoint)
    assert exc.value.code == HarnessErrorCode.CHECKPOINT_INVALID
    assert expected_fragment in str(exc.value)


def test_same_run_task_and_checkpoint_passes():
    binding = RunStateBindingGuard.ensure_bound(_run(), _state(), _checkpoint())

    assert binding.run_id == "R1"
    assert binding.tarefa_trabalho_id == "T1"
    assert binding.run_state_id == "RS1"
    assert binding.checkpoint_id == "CP1"
    assert binding.agent_id == "A1"


def test_different_run_is_blocked():
    _assert_blocked(
        _run(run_id="R1"),
        _state(run_id="R2"),
        _checkpoint(run_id="R2"),
        "RunState.run_id",
    )


def test_different_tarefa_trabalho_is_blocked():
    _assert_blocked(
        _run(task_id="TASK-A"),
        _state(task_id="TASK-B"),
        _checkpoint(),
        "tarefa_trabalho_id",
    )


def test_checkpoint_belonging_to_another_run_is_blocked():
    _assert_blocked(
        _run(run_id="R1"),
        _state(run_id="R1"),
        _checkpoint(run_id="R2"),
        "Checkpoint.run_id",
    )


def test_checkpoint_belonging_to_another_run_state_is_blocked():
    _assert_blocked(
        _run(run_state_ref="RS1"),
        _state(run_state_id="RS1"),
        _checkpoint(run_state_ref="RS2"),
        "Checkpoint.run_state_ref",
    )


@pytest.mark.parametrize(
    ("run", "state", "checkpoint", "expected_fragment"),
    [
        (_run(run_state_ref=""), _state(), _checkpoint(), "HarnessRun.run_state_ref"),
        (_run(), _state(checkpoint_ref=None), _checkpoint(), "RunState.checkpoint_ref"),
    ],
)
def test_required_binding_reference_missing_is_blocked(run, state, checkpoint, expected_fragment):
    _assert_blocked(run, state, checkpoint, expected_fragment)


def test_correct_binding_does_not_mutate_inputs():
    run = _run()
    state = _state()
    checkpoint = _checkpoint()
    before = (
        run.model_dump(mode="json"),
        state.model_dump(mode="json"),
        checkpoint.model_dump(mode="json"),
    )

    RunStateBindingGuard.ensure_bound(run, state, checkpoint)

    after = (
        run.model_dump(mode="json"),
        state.model_dump(mode="json"),
        checkpoint.model_dump(mode="json"),
    )
    assert after == before
