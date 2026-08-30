from __future__ import annotations

from dataclasses import dataclass

from harness.contracts import AuthorityContext, HarnessErrorCode, HarnessRun, TaskContext
from harness.core.errors import HarnessResolutionError


@dataclass(frozen=True, slots=True)
class AuthorityExecutionBinding:
    """Immutable proof that an AuthorityContext matches one execution boundary."""

    authority_context_id: str
    run_id: str
    agent_id: str
    tarefa_trabalho_id: str
    task_context_id: str
    boundary: str


def _required(label: str, value: str | None, source_ref: str | None = None) -> str:
    if value is None or not str(value).strip():
        raise HarnessResolutionError(
            HarnessErrorCode.AUTHORITY_UNRESOLVED,
            f"missing required execution identity: {label}",
            source_ref,
        )
    return str(value)


def _same(label: str, left: str, right: str, source_ref: str) -> None:
    if left != right:
        raise HarnessResolutionError(
            HarnessErrorCode.AUTHORITY_UNRESOLVED,
            f"authority execution binding mismatch: {label}",
            source_ref,
        )


def validate_authority_execution_binding(
    authority: AuthorityContext,
    *,
    run: HarnessRun,
    task_context: TaskContext,
    boundary: str,
) -> AuthorityExecutionBinding:
    """Fail closed unless authority is explicitly bound to the current execution.

    This validator does not decide positive authority and does not infer missing
    execution identity. It only proves that the already-resolved AuthorityContext
    belongs to the supplied current run, agent and task context, then scopes that
    proof to the explicit current boundary.

    AuthorityContext V0.1 has no ``tarefa_trabalho_id`` or boundary field. Task
    ownership is therefore proven through the existing canonical cross-references:
    HarnessRun.authority_context_ref -> AuthorityContext.authority_context_id and
    HarnessRun.task_context_ref -> TaskContext.task_context_id, while run/task IDs
    are required to agree. The boundary is explicit input and is preserved in the
    immutable proof; no authority is granted from the boundary name itself.
    """

    authority_context_id = _required(
        "authority.authority_context_id",
        authority.authority_context_id,
        authority.authority_context_id or None,
    )
    authority_run_id = _required("authority.run_id", authority.run_id, authority_context_id)
    authority_agent_id = _required("authority.agent_id", authority.agent_id, authority_context_id)

    run_id = _required("run.run_id", run.run_id, authority_context_id)
    run_agent_id = _required("run.agent_id", run.agent_id, run_id)
    run_task_id = _required("run.tarefa_trabalho_id", run.tarefa_trabalho_id, run_id)
    run_authority_ref = _required("run.authority_context_ref", run.authority_context_ref, run_id)
    run_task_context_ref = _required("run.task_context_ref", run.task_context_ref, run_id)

    task_context_id = _required("task_context.task_context_id", task_context.task_context_id, run_id)
    task_run_id = _required("task_context.run_id", task_context.run_id, task_context_id)
    task_id = _required("task_context.tarefa_trabalho_id", task_context.tarefa_trabalho_id, task_context_id)
    task_authority_ref = _required(
        "task_context.authority_context_ref",
        task_context.authority_context_ref,
        task_context_id,
    )
    current_boundary = _required("boundary", boundary, authority_context_id)

    _same("authority.run_id != current run", authority_run_id, run_id, authority_context_id)
    _same("authority.agent_id != current agent", authority_agent_id, run_agent_id, authority_context_id)
    _same(
        "run.authority_context_ref != authority.authority_context_id",
        run_authority_ref,
        authority_context_id,
        run_id,
    )
    _same("task_context.run_id != current run", task_run_id, run_id, task_context_id)
    _same("task_context.tarefa_trabalho_id != current task", task_id, run_task_id, task_context_id)
    _same(
        "run.task_context_ref != current task_context",
        run_task_context_ref,
        task_context_id,
        run_id,
    )
    _same(
        "task_context.authority_context_ref != authority.authority_context_id",
        task_authority_ref,
        authority_context_id,
        task_context_id,
    )

    return AuthorityExecutionBinding(
        authority_context_id=authority_context_id,
        run_id=run_id,
        agent_id=run_agent_id,
        tarefa_trabalho_id=run_task_id,
        task_context_id=task_context_id,
        boundary=current_boundary,
    )


__all__ = ["AuthorityExecutionBinding", "validate_authority_execution_binding"]
