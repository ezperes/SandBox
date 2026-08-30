import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import (
    AuthorityContext,
    ChainType,
    HarnessErrorCode,
    HarnessRun,
    ResolutionChain,
    ResolutionStatus,
    RunState,
    RunStatus,
)
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate, ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry


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
        "AUT-T": {
            "revision_ref": "T-REV-1",
            "loaded_excerpt_refs": ["CTX-T1"],
            "allowed_scopes": ["ops:write", "ops:resume"],
        },
        "AUT-X": {
            "revision_ref": "X-REV-1",
            "loaded_excerpt_refs": ["CTX-X1"],
            "allowed_scopes": ["ops:write", "ops:resume"],
        },
        "AUT-N": {
            "revision_ref": "N-REV-1",
            "loaded_excerpt_refs": ["CTX-N1"],
            "allowed_scopes": ["ops:write", "ops:resume"],
        },
        "CTX-T1": {"context_ref": "CTX-T1", "estimated_tokens": 10, "required": True},
        "CTX-X1": {"context_ref": "CTX-X1", "estimated_tokens": 10, "required": True},
        "CTX-N1": {"context_ref": "CTX-N1", "estimated_tokens": 10, "required": True},
        "TASK": {
            "tarefa_trabalho_id": "MT-1",
            "current_order": "continue",
            "task_state_ref": "TASK-STATE-1",
            "workspace_ref": "WS1",
        },
    }


def make_run(*, run_id="R1", agent_id="A1", task_id="MT-1", run_state_ref="RS1"):
    return HarnessRun(
        run_id=run_id,
        tarefa_trabalho_id=task_id,
        agent_id=agent_id,
        correlation_id=f"C-{run_id}",
        workspace_ref="WS1",
        run_state_ref=run_state_ref,
        authority_context_ref="AC-OLD",
    )


def resolved(source, *, run_id="R1"):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve(run_id, identity)
    context = ContextBuilder(source).build(run_id, authority.context, "TASK")
    return identity, authority, context


def make_resume_gate(source, identity, authority, context):
    return ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )


def direct_chain(kind):
    ref, revision = {
        ChainType.TACTICAL: ("AUT-T", "T-REV-1"),
        ChainType.TECHNICAL: ("AUT-X", "X-REV-1"),
        ChainType.NORMATIVE: ("AUT-N", "N-REV-1"),
    }[kind]
    return ResolutionChain(
        chain_type=kind,
        status=ResolutionStatus.RESOLVED,
        authority_ref=ref,
        route_refs=[ref],
        source_revision_refs=[revision],
    )


def direct_authority(*, run_id="R1", agent_id="A1"):
    return AuthorityContext(
        authority_context_id=f"AC-{run_id}-{agent_id}",
        run_id=run_id,
        agent_id=agent_id,
        tactical_authority_refs=["AUT-T"],
        technical_authority_refs=["AUT-X"],
        normative_authority_refs=["AUT-N"],
        tactical_chain_trace=direct_chain(ChainType.TACTICAL),
        technical_chain_trace=direct_chain(ChainType.TECHNICAL),
        normative_chain_trace=direct_chain(ChainType.NORMATIVE),
        allowed_scopes=["ops:write"],
    )


class CountingTool:
    def __init__(self):
        self.calls = []

    def invoke(self, tool_id, payload):
        self.calls.append((tool_id, dict(payload)))
        return {"ok": True, "evidence_refs": [f"EV-{len(self.calls)}"]}


class CountingRuntime:
    def __init__(self):
        self.resume_calls = 0

    def execute(self, run, payload):
        raise NotImplementedError

    def resume(self, run, state):
        self.resume_calls += 1
        state.status = RunStatus.COMPLETED
        return state


def tool_gateway(source, state_port=None):
    registry = ToolRegistry()
    adapter = CountingTool()
    registry.register(
        ToolDescriptor(tool_id="ops.write", action_scope="ops:write", side_effect=True),
        adapter,
    )
    manager = StateManager(state_port or InMemoryStateAdapter())
    return ToolGateway(
        registry,
        manager,
        freshness_gate=AuthorityFreshnessGate(source),
    ), adapter, manager


def interrupted_state(*, run_state_id="RS1", run_id="R1", task_id="MT-1"):
    return RunState(
        run_state_id=run_state_id,
        run_id=run_id,
        tarefa_trabalho_id=task_id,
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
        completed_steps=["step-1"],
        pending_steps=["step-2"],
    )


def prepare_resume_fixture(*, run_id="R1"):
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolved(source, run_id=run_id)
    gate = make_resume_gate(source, identity, authority, context)
    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    state = interrupted_state(run_id=run_id)
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue",
    )
    return source, gate, state_port, manager, checkpoint


def test_red_team_authority_context_must_be_bound_to_run_and_agent_before_toolport():
    """Cross-run/cross-agent authority laundering must fail before side effect."""
    source = InMemorySourceAdapter(records())
    gateway, adapter, _ = tool_gateway(source)

    foreign_authority = direct_authority(run_id="R2", agent_id="A2")
    with pytest.raises(HarnessResolutionError):
        gateway.execute(
            run_id="R1",
            authority=foreign_authority,
            tool_id="ops.write",
            payload={"value": 1},
            business_key="ORDER-1",
        )

    assert adapter.calls == []


def test_red_team_same_real_world_effect_must_not_duplicate_across_runs():
    """Same operation+business key must not be replayed merely by changing run_id."""
    source = InMemorySourceAdapter(records())
    gateway, adapter, _ = tool_gateway(source)

    gateway.execute(
        run_id="R1",
        authority=direct_authority(run_id="R1"),
        tool_id="ops.write",
        payload={"value": 1},
        business_key="ORDER-9",
    )

    with pytest.raises(HarnessResolutionError) as exc:
        gateway.execute(
            run_id="R2",
            authority=direct_authority(run_id="R2"),
            tool_id="ops.write",
            payload={"value": 1},
            business_key="ORDER-9",
        )

    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert len(adapter.calls) == 1


def test_red_team_tool_toctou_revision_flip_after_check_before_invoke_is_blocked():
    """Actually flip canonical revision in the check->ToolPort window."""
    source = InMemorySourceAdapter(records())

    class FlipOnLedgerCreateState(InMemoryStateAdapter):
        def create_idempotency_record(self, key, record):
            source.records["AUT-T"]["revision_ref"] = "T-REV-2"
            return super().create_idempotency_record(key, record)

    gateway, adapter, _ = tool_gateway(source, FlipOnLedgerCreateState())

    with pytest.raises(HarnessResolutionError):
        gateway.execute(
            run_id="R1",
            authority=direct_authority(run_id="R1"),
            tool_id="ops.write",
            payload={"value": 1},
            business_key="TOCTOU-TOOL-1",
        )

    assert source.records["AUT-T"]["revision_ref"] == "T-REV-2"
    assert adapter.calls == []


def test_red_team_resume_rejects_foreign_task_in_runstate_before_runtime():
    source, gate, state_port, manager, _ = prepare_resume_fixture()
    state = interrupted_state(task_id="MT-FOREIGN")
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue",
    )
    runtime = CountingRuntime()

    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=gate)

    assert exc.value.code == HarnessErrorCode.CHECKPOINT_INVALID
    assert runtime.resume_calls == 0


def test_red_team_resume_rejects_foreign_runstate_identity_before_runtime():
    source, gate, state_port, manager, _ = prepare_resume_fixture()
    state = interrupted_state(run_state_id="RS-FOREIGN")
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue",
    )
    runtime = CountingRuntime()

    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run(run_state_ref="RS1"), runtime, checkpoint.checkpoint_id, freshness_gate=gate)

    assert exc.value.code == HarnessErrorCode.CHECKPOINT_INVALID
    assert runtime.resume_calls == 0


def test_red_team_resume_gate_rejects_previous_context_from_other_run():
    source = InMemorySourceAdapter(records())
    identity, authority_r2, context_r2 = resolved(source, run_id="R2")
    gate = make_resume_gate(source, identity, authority_r2, context_r2)

    with pytest.raises(HarnessResolutionError):
        gate.prepare(make_run(run_id="R1"))


def test_red_team_runtime_cannot_mutate_core_owned_harness_run():
    source, gate, state_port, manager, checkpoint = prepare_resume_fixture()
    run = make_run()

    class MutatingRuntime:
        def execute(self, run, payload):
            raise NotImplementedError

        def resume(self, run, state):
            run.agent_id = "A-ATTACK"
            run.tarefa_trabalho_id = "MT-ATTACK"
            run.authority_context_ref = "AC-ATTACK"
            run.run_state_ref = "RS-ATTACK"
            state.status = RunStatus.COMPLETED
            return state

    manager.resume(run, MutatingRuntime(), checkpoint.checkpoint_id, freshness_gate=gate)

    assert run.agent_id == "A1"
    assert run.tarefa_trabalho_id == "MT-1"
    assert run.run_state_ref == "RS1"
    assert run.authority_context_ref != "AC-ATTACK"


def test_red_team_runtime_cannot_return_foreign_canonical_runstate():
    source, gate, state_port, manager, checkpoint = prepare_resume_fixture()

    class ForeignStateRuntime:
        def execute(self, run, payload):
            raise NotImplementedError

        def resume(self, run, state):
            return state.model_copy(
                update={
                    "run_state_id": "RS-ATTACK",
                    "run_id": "R-ATTACK",
                    "tarefa_trabalho_id": "MT-ATTACK",
                    "status": RunStatus.COMPLETED,
                }
            )

    with pytest.raises(HarnessResolutionError):
        manager.resume(make_run(), ForeignStateRuntime(), checkpoint.checkpoint_id, freshness_gate=gate)

    with pytest.raises(KeyError):
        state_port.load_run_state("RS-ATTACK")


def test_red_team_runtime_resume_toctou_revision_flip_after_revalidation_before_runtime_is_blocked():
    """Actually flip canonical revision after RELEASED audit and before RuntimePort.resume."""
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolved(source)
    gate = make_resume_gate(source, identity, authority, context)

    class FlipAfterReleaseState(InMemoryStateAdapter):
        def save_revalidation_record(self, revalidation_id, record):
            super().save_revalidation_record(revalidation_id, record)
            if record.get("status") == "RELEASED" and record.get("outcome") == "REVALIDATED":
                source.records["AUT-T"]["revision_ref"] = "T-REV-2"

    state_port = FlipAfterReleaseState()
    manager = StateManager(state_port)
    state = interrupted_state()
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue",
    )
    runtime = CountingRuntime()

    with pytest.raises(HarnessResolutionError):
        manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=gate)

    assert source.records["AUT-T"]["revision_ref"] == "T-REV-2"
    assert runtime.resume_calls == 0


def test_red_team_repeated_resume_same_checkpoint_does_not_reenter_runtime():
    source, gate, state_port, manager, checkpoint = prepare_resume_fixture()
    runtime = CountingRuntime()
    run = make_run()

    manager.resume(run, runtime, checkpoint.checkpoint_id, freshness_gate=gate)

    try:
        manager.resume(run, runtime, checkpoint.checkpoint_id, freshness_gate=gate)
    except HarnessResolutionError:
        pass

    assert runtime.resume_calls == 1


def test_red_team_tool_trace_has_complete_actor_task_revision_boundary_time_outcome_attribution():
    source = InMemorySourceAdapter(records())
    gateway, adapter, manager = tool_gateway(source)

    result = gateway.execute(
        run_id="R1",
        authority=direct_authority(run_id="R1", agent_id="A1"),
        tool_id="ops.write",
        payload={"value": 1},
        business_key="TRACE-1",
    )
    audit = manager.state_port.load_revalidation_record(result.decision_ref)

    assert audit["run_id"] == "R1"
    assert audit["agent_id"] == "A1"
    assert audit["tarefa_trabalho_id"] == "MT-1"
    assert audit["boundary"] == "ToolPort.invoke"
    assert audit["outcome"] == "COMPLETED"
    assert audit["freshness_checks"]
    assert all(item["current_revision_ref"] for item in audit["freshness_checks"])
    assert audit["created_at"] <= audit["updated_at"]
    assert audit["events"][0]["status"] == "PENDING"
    assert audit["events"][-1]["outcome"] == "COMPLETED"
