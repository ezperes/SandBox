import pytest

from harness.contracts import (
    AuthorityContext,
    ChainType,
    HarnessRun,
    ResolutionChain,
    ResolutionStatus,
    TaskContext,
)
from harness.core.authority.execution_binding import (
    AuthorityExecutionBinding,
    validate_authority_execution_binding,
)
from harness.core.errors import HarnessResolutionError


def _chain(kind: ChainType, ref: str) -> ResolutionChain:
    return ResolutionChain(
        chain_type=kind,
        status=ResolutionStatus.RESOLVED,
        authority_ref=ref,
        route_refs=[ref],
        source_revision_refs=[f"rev-{ref}"],
    )


def _authority(*, run_id: str = "R1", agent_id: str = "A1", context_id: str = "AC-1") -> AuthorityContext:
    return AuthorityContext(
        authority_context_id=context_id,
        run_id=run_id,
        agent_id=agent_id,
        tactical_authority_refs=["AUT-T"],
        technical_authority_refs=["AUT-X"],
        tactical_chain_trace=_chain(ChainType.TACTICAL, "AUT-T"),
        technical_chain_trace=_chain(ChainType.TECHNICAL, "AUT-X"),
        allowed_scopes=["finance:pay"],
        competence_refs=["PAY"],
    )


def _run(
    *,
    run_id: str = "R1",
    agent_id: str = "A1",
    task_id: str = "T1",
    authority_context_ref: str = "AC-1",
    task_context_ref: str | None = "TC-1",
) -> HarnessRun:
    return HarnessRun(
        run_id=run_id,
        tarefa_trabalho_id=task_id,
        agent_id=agent_id,
        correlation_id=f"CORR-{run_id}",
        workspace_ref=f"WS-{run_id}",
        run_state_ref=f"RS-{run_id}",
        authority_context_ref=authority_context_ref,
        task_context_ref=task_context_ref,
    )


def _task_context(
    *,
    run_id: str = "R1",
    task_id: str = "T1",
    context_id: str = "TC-1",
    authority_context_ref: str = "AC-1",
) -> TaskContext:
    return TaskContext(
        task_context_id=context_id,
        run_id=run_id,
        tarefa_trabalho_id=task_id,
        current_order="execute side effect",
        task_state_ref=f"TASKSTATE-{task_id}",
        authority_context_ref=authority_context_ref,
        workspace_ref=f"WS-{run_id}",
        bootstrap_trace_ref="BT-1",
    )


def _assert_blocked(authority: AuthorityContext, run: HarnessRun, task_context: TaskContext, *, boundary: str = "ToolPort.invoke") -> HarnessResolutionError:
    with pytest.raises(HarnessResolutionError) as exc:
        validate_authority_execution_binding(
            authority,
            run=run,
            task_context=task_context,
            boundary=boundary,
        )
    assert exc.value.code.value == "AUTHORITY_UNRESOLVED"
    return exc.value


def test_same_execution_context_passes_and_inputs_remain_immutable():
    authority = _authority()
    run = _run()
    task_context = _task_context()
    before = (
        authority.model_dump(mode="python"),
        run.model_dump(mode="python"),
        task_context.model_dump(mode="python"),
    )

    binding = validate_authority_execution_binding(
        authority,
        run=run,
        task_context=task_context,
        boundary="ToolPort.invoke",
    )

    assert binding == AuthorityExecutionBinding(
        authority_context_id="AC-1",
        run_id="R1",
        agent_id="A1",
        tarefa_trabalho_id="T1",
        task_context_id="TC-1",
        boundary="ToolPort.invoke",
    )
    assert authority.model_dump(mode="python") == before[0]
    assert run.model_dump(mode="python") == before[1]
    assert task_context.model_dump(mode="python") == before[2]


def test_authority_from_other_agent_is_blocked():
    error = _assert_blocked(_authority(agent_id="A1"), _run(agent_id="A2"), _task_context())
    assert "current agent" in error.message


def test_authority_from_other_run_is_blocked():
    error = _assert_blocked(
        _authority(run_id="R1"),
        _run(run_id="R2"),
        _task_context(run_id="R2"),
    )
    assert "current run" in error.message


def test_authority_from_other_task_is_blocked():
    error = _assert_blocked(
        _authority(),
        _run(task_id="T1", task_context_ref="TC-2"),
        _task_context(task_id="T2", context_id="TC-2"),
    )
    assert "current task" in error.message


def test_missing_required_execution_identity_is_blocked():
    run = _run().model_copy(update={"task_context_ref": None})
    error = _assert_blocked(_authority(), run, _task_context())
    assert "missing required execution identity" in error.message
    assert "run.task_context_ref" in error.message


def test_missing_boundary_identity_is_blocked():
    error = _assert_blocked(_authority(), _run(), _task_context(), boundary="   ")
    assert "missing required execution identity: boundary" in error.message


def test_historically_valid_authority_from_different_execution_is_blocked():
    old_authority = _authority(run_id="R-HIST", agent_id="A1", context_id="AC-HIST")
    current_run = _run(
        run_id="R-NOW",
        agent_id="A1",
        task_id="T-NOW",
        authority_context_ref="AC-HIST",
        task_context_ref="TC-NOW",
    )
    current_task = _task_context(
        run_id="R-NOW",
        task_id="T-NOW",
        context_id="TC-NOW",
        authority_context_ref="AC-HIST",
    )

    error = _assert_blocked(old_authority, current_run, current_task)
    assert "current run" in error.message
