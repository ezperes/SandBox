from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harness.contracts import AuthorityContext, HarnessErrorCode, HarnessRun, ResolutionChain
from harness.core.context import ContextBuildResult
from harness.core.errors import HarnessResolutionError
from harness.ports import SourcePort


@dataclass(frozen=True, slots=True)
class ResumeContextBinding:
    """Validated execution identity for a resumable context."""

    run_id: str
    agent_id: str
    tarefa_trabalho_id: str
    workspace_ref: str
    authority_context_id: str
    task_context_id: str
    bootstrap_trace_ref: str
    identity_source_ref: str
    previous_identity_revision_ref: str
    task_source_ref: str


def _fail(message: str, source_ref: str | None = None) -> None:
    raise HarnessResolutionError(
        HarnessErrorCode.AUTHORITY_UNRESOLVED,
        message,
        source_ref,
    )


def _required(value: Any, label: str, source_ref: str | None = None) -> str:
    text = str(value or "").strip()
    if not text:
        _fail(f"resume context binding requires explicit {label}", source_ref)
    return text


def _same(label: str, expected: str, observed: str, source_ref: str | None = None) -> None:
    if observed != expected:
        _fail(
            f"resume context binding mismatch for {label}: "
            f"expected {expected!r}, observed {observed!r}",
            source_ref,
        )


def _chain_fingerprint(chain: ResolutionChain | None) -> tuple[Any, ...] | None:
    if chain is None:
        return None
    return (
        chain.chain_type.value,
        chain.status.value,
        chain.authority_ref,
        tuple(chain.route_refs),
        tuple(chain.applicable_refs),
        tuple(chain.loaded_excerpt_refs),
        tuple(chain.source_revision_refs),
        chain.justification,
    )


def _validate_bootstrap_authority_lineage(
    previous_authority: AuthorityContext,
    previous_context: ContextBuildResult,
) -> None:
    bootstrap = previous_context.bootstrap
    pairs = (
        (
            "tactical",
            previous_authority.tactical_chain_trace,
            bootstrap.tactical_chain,
        ),
        (
            "technical",
            previous_authority.technical_chain_trace,
            bootstrap.technical_chain,
        ),
        (
            "normative",
            previous_authority.normative_chain_trace,
            bootstrap.normative_chain,
        ),
    )
    for label, authority_chain, bootstrap_chain in pairs:
        if _chain_fingerprint(authority_chain) != _chain_fingerprint(bootstrap_chain):
            _fail(
                f"resume context bootstrap {label} lineage does not match "
                "the previous AuthorityContext"
            )


def validate_previous_resume_binding(
    *,
    run: HarnessRun,
    previous_authority: AuthorityContext,
    previous_context: ContextBuildResult,
    source: SourcePort,
    identity_source_ref: str,
    previous_identity_revision_ref: str,
    task_source_ref: str,
) -> ResumeContextBinding:
    """Fail closed unless all reusable context belongs to this execution.

    Bindings are explicit:
    - Run <-> AuthorityContext: run_id + agent_id
    - Run <-> TaskContext: run_id + tarefa_trabalho_id + workspace_ref
    - TaskContext <-> AuthorityContext: authority_context_ref
    - TaskContext <-> BootstrapResolution: bootstrap_trace_ref
    - BootstrapResolution <-> AuthorityContext: complete chain reference/revision lineage
    - task source <-> Run: tarefa_trabalho_id + workspace_ref
    - identity source: explicit source ref + previously captured revision; the
      freshly resolved identity is subsequently required to match run.agent_id
      by ResumeFreshnessGate.prepare().
    """

    run_id = _required(run.run_id, "HarnessRun.run_id")
    agent_id = _required(run.agent_id, "HarnessRun.agent_id")
    task_id = _required(run.tarefa_trabalho_id, "HarnessRun.tarefa_trabalho_id")
    workspace_ref = _required(run.workspace_ref, "HarnessRun.workspace_ref")
    identity_ref = _required(identity_source_ref, "identity_source_ref")
    identity_revision = _required(
        previous_identity_revision_ref,
        "previous_identity_revision_ref",
        identity_ref,
    )
    task_ref = _required(task_source_ref, "task_source_ref")

    authority_id = _required(
        previous_authority.authority_context_id,
        "AuthorityContext.authority_context_id",
    )
    authority_run_id = _required(
        previous_authority.run_id,
        "AuthorityContext.run_id",
        authority_id,
    )
    authority_agent_id = _required(
        previous_authority.agent_id,
        "AuthorityContext.agent_id",
        authority_id,
    )
    _same("AuthorityContext.run_id", run_id, authority_run_id, authority_id)
    _same("AuthorityContext.agent_id", agent_id, authority_agent_id, authority_id)

    task_context = previous_context.task_context
    task_context_id = _required(
        task_context.task_context_id,
        "TaskContext.task_context_id",
    )
    task_context_run_id = _required(
        task_context.run_id,
        "TaskContext.run_id",
        task_context_id,
    )
    task_context_task_id = _required(
        task_context.tarefa_trabalho_id,
        "TaskContext.tarefa_trabalho_id",
        task_context_id,
    )
    task_context_workspace = _required(
        task_context.workspace_ref,
        "TaskContext.workspace_ref",
        task_context_id,
    )
    task_context_authority = _required(
        task_context.authority_context_ref,
        "TaskContext.authority_context_ref",
        task_context_id,
    )
    bootstrap_trace_ref = _required(
        task_context.bootstrap_trace_ref,
        "TaskContext.bootstrap_trace_ref",
        task_context_id,
    )
    bootstrap_trace_id = _required(
        previous_context.bootstrap.trace_id,
        "BootstrapResolution.trace_id",
    )

    _same("TaskContext.run_id", run_id, task_context_run_id, task_context_id)
    _same(
        "TaskContext.tarefa_trabalho_id",
        task_id,
        task_context_task_id,
        task_context_id,
    )
    _same(
        "TaskContext.workspace_ref",
        workspace_ref,
        task_context_workspace,
        task_context_id,
    )
    _same(
        "TaskContext.authority_context_ref",
        authority_id,
        task_context_authority,
        task_context_id,
    )
    _same(
        "TaskContext.bootstrap_trace_ref",
        bootstrap_trace_id,
        bootstrap_trace_ref,
        task_context_id,
    )

    _validate_bootstrap_authority_lineage(previous_authority, previous_context)

    try:
        current_task = source.read(task_ref)
    except Exception as exc:
        raise HarnessResolutionError(
            HarnessErrorCode.AUTHORITY_UNRESOLVED,
            f"resume task binding source could not be read: {exc}",
            task_ref,
        ) from exc

    current_task_id = _required(
        current_task.get("tarefa_trabalho_id"),
        "task source tarefa_trabalho_id",
        task_ref,
    )
    current_workspace_ref = _required(
        current_task.get("workspace_ref"),
        "task source workspace_ref",
        task_ref,
    )
    _same("task source tarefa_trabalho_id", task_id, current_task_id, task_ref)
    _same("task source workspace_ref", workspace_ref, current_workspace_ref, task_ref)

    return ResumeContextBinding(
        run_id=run_id,
        agent_id=agent_id,
        tarefa_trabalho_id=task_id,
        workspace_ref=workspace_ref,
        authority_context_id=authority_id,
        task_context_id=task_context_id,
        bootstrap_trace_ref=bootstrap_trace_ref,
        identity_source_ref=identity_ref,
        previous_identity_revision_ref=identity_revision,
        task_source_ref=task_ref,
    )


def validate_prepared_resume_binding(
    *,
    run: HarnessRun,
    authority: AuthorityContext,
    context: ContextBuildResult,
) -> None:
    """Verify the newly prepared objects still bind to the same execution."""

    run_id = _required(run.run_id, "HarnessRun.run_id")
    agent_id = _required(run.agent_id, "HarnessRun.agent_id")
    task_id = _required(run.tarefa_trabalho_id, "HarnessRun.tarefa_trabalho_id")
    workspace_ref = _required(run.workspace_ref, "HarnessRun.workspace_ref")

    authority_id = _required(
        authority.authority_context_id,
        "prepared AuthorityContext.authority_context_id",
    )
    _same(
        "prepared AuthorityContext.run_id",
        run_id,
        _required(authority.run_id, "prepared AuthorityContext.run_id", authority_id),
        authority_id,
    )
    _same(
        "prepared AuthorityContext.agent_id",
        agent_id,
        _required(authority.agent_id, "prepared AuthorityContext.agent_id", authority_id),
        authority_id,
    )

    task_context = context.task_context
    task_context_id = _required(
        task_context.task_context_id,
        "prepared TaskContext.task_context_id",
    )
    _same(
        "prepared TaskContext.run_id",
        run_id,
        _required(task_context.run_id, "prepared TaskContext.run_id", task_context_id),
        task_context_id,
    )
    _same(
        "prepared TaskContext.tarefa_trabalho_id",
        task_id,
        _required(
            task_context.tarefa_trabalho_id,
            "prepared TaskContext.tarefa_trabalho_id",
            task_context_id,
        ),
        task_context_id,
    )
    _same(
        "prepared TaskContext.workspace_ref",
        workspace_ref,
        _required(
            task_context.workspace_ref,
            "prepared TaskContext.workspace_ref",
            task_context_id,
        ),
        task_context_id,
    )
    _same(
        "prepared TaskContext.authority_context_ref",
        authority_id,
        _required(
            task_context.authority_context_ref,
            "prepared TaskContext.authority_context_ref",
            task_context_id,
        ),
        task_context_id,
    )
    bootstrap_trace_id = _required(
        context.bootstrap.trace_id,
        "prepared BootstrapResolution.trace_id",
    )
    _same(
        "prepared TaskContext.bootstrap_trace_ref",
        bootstrap_trace_id,
        _required(
            task_context.bootstrap_trace_ref,
            "prepared TaskContext.bootstrap_trace_ref",
            task_context_id,
        ),
        task_context_id,
    )

    _validate_bootstrap_authority_lineage(authority, context)
