import pytest
from types import SimpleNamespace
from dataclasses import replace

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.adapters.tools import FakeToolAdapter
from harness.contracts import (
    AuthorityContext,
    AuthoritySnapshot,
    ChainType,
    HarnessRun,
    ResolutionChain,
    ResolutionStatus,
    RiskLevel,
    RunState,
    RunStatus,
    TaskContext,
)
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate, ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry


def _chain(kind: ChainType, ref: str, revision: str) -> ResolutionChain:
    return ResolutionChain(
        chain_type=kind,
        status=ResolutionStatus.RESOLVED,
        authority_ref=ref,
        route_refs=[ref],
        source_revision_refs=[revision],
    )


def _authority(revision: str = "rev-A") -> AuthorityContext:
    return AuthorityContext(
        authority_context_id="AC-STALE",
        run_id="R1",
        agent_id="A1",
        tactical_authority_refs=["AUT-T"],
        technical_authority_refs=["AUT-X"],
        normative_authority_refs=["AUT-N"],
        tactical_chain_trace=_chain(ChainType.TACTICAL, "AUT-T", revision),
        technical_chain_trace=_chain(ChainType.TECHNICAL, "AUT-X", revision),
        normative_chain_trace=_chain(ChainType.NORMATIVE, "AUT-N", revision),
        allowed_scopes=["finance:pay"],
        competence_refs=["PAY"],
    )


def _authority_source(revision: str) -> InMemorySourceAdapter:
    return InMemorySourceAdapter({
        "AUT-T": {"revision_ref": revision, "allowed_scopes": []},
        "AUT-X": {"revision_ref": revision, "allowed_scopes": []},
        "AUT-N": {"revision_ref": revision, "allowed_scopes": []},
    })


def _registry(adapter):
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            tool_id="finance.pay",
            action_scope="finance:pay",
            risk_level=RiskLevel.HIGH,
            side_effect=True,
            required_competence="PAY",
        ),
        adapter,
    )
    return registry


def _resume_records():
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
        "CTX-X1": {"context_ref": "CTX-X1", "estimated_tokens": 10, "required": True},
        "CTX-N1": {"context_ref": "CTX-N1", "estimated_tokens": 10, "required": True},
        "TASK": {
            "tarefa_trabalho_id": "MT-1",
            "current_order": "continue",
            "task_state_ref": "TASK-STATE-1",
            "workspace_ref": "WS1",
        },
    }


def _run(authority_ref="AC-OLD", task_context_ref="TC-OLD") -> HarnessRun:
    return HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref=authority_ref,
        task_context_ref=task_context_ref,
    )


def _interrupted_state() -> RunState:
    return RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
    )


class _ForgedPassGate:
    def prepare(self, run):
        task_context = TaskContext(
            task_context_id="TC-FORGED",
            run_id=run.run_id,
            tarefa_trabalho_id=run.tarefa_trabalho_id,
            current_order="continue",
            task_state_ref="TASK-STATE-1",
            authority_context_ref="AC-FORGED",
            workspace_ref=run.workspace_ref,
            bootstrap_trace_ref="BT-FORGED",
        )
        context = SimpleNamespace(
            task_context=task_context,
            bootstrap=SimpleNamespace(
                trace_id="BT-FORGED",
                tactical_refs=(),
                technical_refs=(),
                normative_refs=(),
            ),
        )
        return SimpleNamespace(
            authority=SimpleNamespace(authority_context_id="AC-FORGED"),
            authority_snapshot=AuthoritySnapshot(snapshot_id="AS-FORGED"),
            context=context,
            changed_chains=frozenset(),
            identity_changed=False,
        )


class _CountingRuntime:
    def __init__(self, inject_decision_ref=None):
        self.resume_calls = 0
        self.inject_decision_ref = inject_decision_ref

    def execute(self, run, payload):
        raise NotImplementedError

    def resume(self, run, state):
        self.resume_calls += 1
        if self.inject_decision_ref:
            state.decision_refs.append(self.inject_decision_ref)
        state.status = RunStatus.COMPLETED
        return state


def test_side_effect_must_fail_closed_when_gateway_has_no_freshness_gate():
    source = _authority_source("rev-B")
    stale = _authority("rev-A")
    adapter = FakeToolAdapter({"ok": True, "evidence_refs": ["EV-1"]})
    gateway = ToolGateway(_registry(adapter), StateManager(InMemoryStateAdapter()))

    gateway.execute(
        run_id="R1",
        authority=stale,
        tool_id="finance.pay",
        payload={"amount": 10},
        business_key="PAY-NO-GATE",
    )

    # Expected security invariant: absence of freshness proof must block the boundary.
    assert adapter.calls == []


def test_mutable_revision_metadata_must_not_upgrade_stale_permissions_to_current():
    source = _authority_source("rev-B")
    stale = _authority("rev-A")

    # Adversarially relabel stale authority data with the current revision while
    # preserving rev-A permissions. The gate currently trusts these mutable refs.
    for chain in (
        stale.tactical_chain_trace,
        stale.technical_chain_trace,
        stale.normative_chain_trace,
    ):
        chain.source_revision_refs = ["rev-B"]

    adapter = FakeToolAdapter({"ok": True, "evidence_refs": ["EV-1"]})
    gateway = ToolGateway(
        _registry(adapter),
        StateManager(InMemoryStateAdapter()),
        freshness_gate=AuthorityFreshnessGate(source),
    )

    gateway.execute(
        run_id="R1",
        authority=stale,
        tool_id="finance.pay",
        payload={"amount": 10},
        business_key="PAY-RELABEL",
    )

    # Expected: current revision metadata alone must not authenticate stale content.
    assert adapter.calls == []


def test_toctou_revision_change_after_check_must_block_external_effect():
    source = _authority_source("rev-A")
    authority = _authority("rev-A")

    class FlipRevisionOnInvoke:
        def __init__(self):
            self.effects = 0

        def invoke(self, tool_id, payload):
            # Canonical authority changes after freshness check but before the
            # simulated external effect performed by the adapter.
            source.records["AUT-T"]["revision_ref"] = "rev-B"
            source.records["AUT-T"]["allowed_scopes"] = []
            self.effects += 1
            return {"ok": True, "evidence_refs": ["EV-TOCTOU"]}

    adapter = FlipRevisionOnInvoke()
    gateway = ToolGateway(
        _registry(adapter),
        StateManager(InMemoryStateAdapter()),
        freshness_gate=AuthorityFreshnessGate(source),
    )

    gateway.execute(
        run_id="R1",
        authority=authority,
        tool_id="finance.pay",
        payload={"amount": 10},
        business_key="PAY-TOCTOU",
    )

    assert adapter.effects == 0


def test_resume_must_reject_non_core_forged_freshness_gate():
    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = _interrupted_state()
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")
    runtime = _CountingRuntime()

    manager.resume(_run(), runtime, checkpoint.checkpoint_id, freshness_gate=_ForgedPassGate())

    # Expected: arbitrary duck-typed objects cannot authorize RuntimePort.resume.
    assert runtime.resume_calls == 0


def test_resume_must_reject_mixed_previous_authority_and_task_context():
    source = InMemorySourceAdapter(_resume_records())
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")

    mismatched_task_context = context.task_context.model_copy(
        update={"authority_context_ref": "AC-DIFFERENT"}
    )
    mismatched_context = replace(context, task_context=mismatched_task_context)
    gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_authority=authority.context,
        previous_context=mismatched_context,
    )

    with pytest.raises(HarnessResolutionError):
        gate.prepare(_run(authority_ref=authority.context.authority_context_id,
                          task_context_ref=mismatched_task_context.task_context_id))


def test_runtime_must_not_inject_core_owned_decision_refs_on_resume():
    source = InMemorySourceAdapter(_resume_records())
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
    gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_authority=authority.context,
        previous_context=context,
    )

    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = _interrupted_state()
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")
    runtime = _CountingRuntime(inject_decision_ref="RUNTIME-INJECTED")

    manager.resume(
        _run(authority_ref=authority.context.authority_context_id,
             task_context_ref=context.task_context.task_context_id),
        runtime,
        checkpoint.checkpoint_id,
        freshness_gate=gate,
    )

    persisted = port.load_run_state("RS1")
    assert "RUNTIME-INJECTED" not in persisted.decision_refs
