import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import BootstrapResolution, ContextBuildResult, ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager


def _records() -> dict[str, dict]:
    return {
        "ID-A": {
            "revision_ref": "ID-REV-A",
            "identity": {
                "agent_id": "AGENT-A",
                "name": "Agent A",
                "mission_ref": "MISSION-A",
                "scope_ref": "SCOPE-A",
                "organizational_path_ref": "ORG-A",
                "tactical_authority_ref": "AUT-T",
                "technical_authority_ref": "AUT-X",
                "normative_authority_ref": "AUT-N",
                "source_ref": "ID-A",
            },
        },
        "AUT-T": {
            "revision_ref": "REV-A",
            "loaded_excerpt_refs": ["CTX-T"],
            "allowed_scopes": ["ops:resume"],
        },
        "AUT-X": {
            "revision_ref": "REV-A",
            "loaded_excerpt_refs": ["CTX-X"],
            "allowed_scopes": ["ops:resume"],
        },
        "AUT-N": {
            "revision_ref": "REV-A",
            "loaded_excerpt_refs": ["CTX-N"],
        },
        "CTX-T": {"context_ref": "CTX-T", "estimated_tokens": 1, "required": True},
        "CTX-X": {"context_ref": "CTX-X", "estimated_tokens": 1, "required": True},
        "CTX-N": {"context_ref": "CTX-N", "estimated_tokens": 1, "required": True},
        "TASK": {
            "tarefa_trabalho_id": "TASK-A",
            "current_order": "continue",
            "task_state_ref": "TASK-STATE-A",
            "workspace_ref": "WS-A",
        },
    }


def _material(source: InMemorySourceAdapter, run_id: str):
    identity = IdentityResolver(source).resolve("ID-A")
    authority = AuthorityResolver(source).resolve(run_id, identity).context
    context = ContextBuilder(source).build(run_id, authority, "TASK")
    return identity, authority, context


def _gate(
    source: InMemorySourceAdapter,
    *,
    run_id: str = "RUN-A",
    previous_authority=None,
    previous_context=None,
) -> ResumeFreshnessGate:
    identity, authority, context = _material(source, run_id)
    return ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=previous_authority or authority,
        previous_context=previous_context or context,
    )


def _run(
    *,
    run_id: str = "RUN-A",
    agent_id: str = "AGENT-A",
    tarefa_trabalho_id: str = "TASK-A",
    workspace_ref: str = "WS-A",
) -> HarnessRun:
    return HarnessRun(
        run_id=run_id,
        tarefa_trabalho_id=tarefa_trabalho_id,
        agent_id=agent_id,
        correlation_id="CORR-A",
        workspace_ref=workspace_ref,
        run_state_ref=f"RS-{run_id}",
        authority_context_ref="AC-PREVIOUS",
        task_context_ref="TC-PREVIOUS",
    )


class CountingRuntime:
    def __init__(self):
        self.resume_calls = 0

    def execute(self, run, payload):
        raise NotImplementedError

    def resume(self, run, current_state):
        self.resume_calls += 1
        current_state.status = RunStatus.COMPLETED
        return current_state


def _resume(gate: ResumeFreshnessGate, run: HarnessRun):
    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = RunState(
        run_state_id=run.run_state_ref,
        run_id=run.run_id,
        tarefa_trabalho_id=run.tarefa_trabalho_id,
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
        completed_steps=["step-1"],
        pending_steps=["step-2"],
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue",
    )
    runtime = CountingRuntime()
    return manager, runtime, checkpoint


def _assert_blocked_before_runtime(gate: ResumeFreshnessGate, run: HarnessRun):
    manager, runtime, checkpoint = _resume(gate, run)
    with pytest.raises(HarnessResolutionError):
        manager.resume(
            run,
            runtime,
            checkpoint.checkpoint_id,
            freshness_gate=gate,
        )
    assert runtime.resume_calls == 0


def test_same_run_agent_task_context_is_allowed_to_reach_runtime():
    source = InMemorySourceAdapter(_records())
    gate = _gate(source)
    run = _run()
    manager, runtime, checkpoint = _resume(gate, run)

    resumed = manager.resume(
        run,
        runtime,
        checkpoint.checkpoint_id,
        freshness_gate=gate,
    )

    assert runtime.resume_calls == 1
    assert resumed.status == RunStatus.COMPLETED


def test_cross_run_reuse_is_blocked_before_runtime():
    source = InMemorySourceAdapter(_records())
    gate = _gate(source, run_id="RUN-A")

    _assert_blocked_before_runtime(gate, _run(run_id="RUN-B"))


def test_cross_agent_reuse_is_blocked_before_runtime():
    source = InMemorySourceAdapter(_records())
    gate = _gate(source)

    _assert_blocked_before_runtime(gate, _run(agent_id="AGENT-B"))


def test_cross_task_reuse_is_blocked_before_runtime():
    source = InMemorySourceAdapter(_records())
    gate = _gate(source)

    _assert_blocked_before_runtime(
        gate,
        _run(tarefa_trabalho_id="TASK-B"),
    )


def test_old_authority_context_injected_into_new_run_is_blocked():
    source = InMemorySourceAdapter(_records())
    identity, old_authority, _ = _material(source, "RUN-OLD")
    new_authority = AuthorityResolver(source).resolve("RUN-NEW", identity).context
    new_context = ContextBuilder(source).build("RUN-NEW", new_authority, "TASK")
    gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=old_authority,
        previous_context=new_context,
    )

    _assert_blocked_before_runtime(gate, _run(run_id="RUN-NEW"))


def test_old_task_context_injected_into_new_run_is_blocked():
    source = InMemorySourceAdapter(_records())
    identity, _, old_context = _material(source, "RUN-OLD")
    new_authority = AuthorityResolver(source).resolve("RUN-NEW", identity).context
    gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=new_authority,
        previous_context=old_context,
    )

    _assert_blocked_before_runtime(gate, _run(run_id="RUN-NEW"))


def test_missing_mandatory_task_source_binding_fails_closed():
    source = InMemorySourceAdapter(_records())
    gate = _gate(source)
    del source.records["TASK"]["tarefa_trabalho_id"]

    _assert_blocked_before_runtime(gate, _run())


def test_identity_source_now_resolving_another_agent_fails_closed():
    source = InMemorySourceAdapter(_records())
    gate = _gate(source)
    source.records["ID-A"]["identity"]["agent_id"] = "AGENT-B"
    source.records["ID-A"]["revision_ref"] = "ID-REV-B"

    _assert_blocked_before_runtime(gate, _run())


def test_task_source_now_points_to_another_task_fails_closed():
    source = InMemorySourceAdapter(_records())
    gate = _gate(source)
    source.records["TASK"]["tarefa_trabalho_id"] = "TASK-B"

    _assert_blocked_before_runtime(gate, _run())


def test_bootstrap_revision_lineage_must_match_previous_authority():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _material(source, "RUN-A")
    bad_tactical = context.bootstrap.tactical_chain.model_copy(
        update={"source_revision_refs": ["REV-FOREIGN"]}
    )
    bad_bootstrap = BootstrapResolution(
        trace_id=context.bootstrap.trace_id,
        tactical_refs=context.bootstrap.tactical_refs,
        technical_refs=context.bootstrap.technical_refs,
        normative_refs=context.bootstrap.normative_refs,
        tactical_chain=bad_tactical,
        technical_chain=context.bootstrap.technical_chain,
        normative_chain=context.bootstrap.normative_chain,
    )
    bad_context = ContextBuildResult(
        task_context=context.task_context,
        bootstrap=bad_bootstrap,
        provenance=dict(context.provenance),
        token_usage=dict(context.token_usage),
        estimated_tokens=context.estimated_tokens,
    )
    gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority,
        previous_context=bad_context,
    )

    _assert_blocked_before_runtime(gate, _run())
