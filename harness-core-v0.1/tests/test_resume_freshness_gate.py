from harness.adapters.runtimes.fake import FakeRuntimeAdapter
from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import ChainType, HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.freshness import ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager


def records():
    return {
        "ID-A1": {
            "revision_ref": "ID-REV-1",
            "identity": {
                "agent_id": "A1",
                "name": "Agent One",
                "mission_ref": "MISSION-1",
                "scope_ref": "SCOPE-1",
                "organizational_path_ref": "ORG-1",
                "tactical_authority_ref": "AUT-T",
                "technical_authority_ref": "AUT-X",
                "normative_authority_ref": "AUT-N",
                "source_ref": "ID-A1",
            },
        },
        "AUT-T": {"revision_ref": "T-REV-1", "loaded_excerpt_refs": ["CTX-T1"], "allowed_scopes": ["ops:resume"]},
        "AUT-X": {"revision_ref": "X-REV-1", "loaded_excerpt_refs": ["CTX-X1"], "allowed_scopes": ["ops:resume"]},
        "AUT-N": {"revision_ref": "N-REV-1", "loaded_excerpt_refs": ["CTX-N1"]},
        "CTX-T1": {"context_ref": "CTX-T1", "estimated_tokens": 10, "required": True},
        "CTX-T2": {"context_ref": "CTX-T2", "estimated_tokens": 12, "required": True},
        "CTX-X1": {"context_ref": "CTX-X1", "estimated_tokens": 10, "required": True},
        "CTX-N1": {"context_ref": "CTX-N1", "estimated_tokens": 10, "required": True},
        "TASK": {
            "tarefa_trabalho_id": "MT-1",
            "current_order": "continue",
            "task_state_ref": "TASK-STATE-1",
            "workspace_ref": "WS1",
        },
    }


def make_run():
    return HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref="AC-OLD",
    )


def test_t10_resume_re_resolves_changed_chain_and_rebuilds_only_affected_context_before_runtime():
    source = InMemorySourceAdapter(records())
    identity = IdentityResolver(source).resolve("ID-A1")
    first_authority = AuthorityResolver(source).resolve("R1", identity)
    first_context = ContextBuilder(source).build("R1", first_authority.context, "TASK")

    assert first_context.task_context.tactical_context_refs == ["CTX-T1"]
    assert first_context.task_context.technical_context_refs == ["CTX-X1"]

    # Canonical tactical authority changes while the run is interrupted.
    source.records["AUT-T"] = {
        "revision_ref": "T-REV-2",
        "loaded_excerpt_refs": ["CTX-T2"],
        "allowed_scopes": ["ops:resume"],
    }

    freshness = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_authority=first_authority.context,
        previous_context=first_context,
    )

    preview = freshness.prepare(make_run())
    assert preview.changed_chains == frozenset({ChainType.TACTICAL})
    assert preview.context.task_context.tactical_context_refs == ["CTX-T2"]
    assert preview.context.task_context.technical_context_refs == ["CTX-X1"]
    assert preview.authority.tactical_chain_trace.source_revision_refs == ["T-REV-2"]

    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    state = RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")

    run = make_run()
    resumed = manager.resume(run, FakeRuntimeAdapter(), checkpoint.checkpoint_id, freshness_gate=freshness)

    assert resumed.status == RunStatus.COMPLETED
    assert run.authority_context_ref != "AC-OLD"
    assert run.task_context_ref == preview.context.task_context.task_context_id or run.task_context_ref.startswith("TC-")


def test_t10_resume_with_unresolvable_changed_authority_never_calls_runtime():
    source = InMemorySourceAdapter(records())
    identity = IdentityResolver(source).resolve("ID-A1")
    first_authority = AuthorityResolver(source).resolve("R1", identity)
    first_context = ContextBuilder(source).build("R1", first_authority.context, "TASK")
    del source.records["AUT-T"]

    freshness = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_authority=first_authority.context,
        previous_context=first_context,
    )

    class CountingRuntime:
        def __init__(self): self.resume_calls = 0
        def execute(self, run, payload): raise NotImplementedError
        def resume(self, run, state):
            self.resume_calls += 1
            return state

    runtime = CountingRuntime()
    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    state = RunState(run_state_id="RS1", run_id="R1", tarefa_trabalho_id="MT-1", status=RunStatus.INTERRUPTED)
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")

    import pytest
    from harness.core.errors import HarnessResolutionError
    with pytest.raises(HarnessResolutionError):
        manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=freshness)
    assert runtime.resume_calls == 0
