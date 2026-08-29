"""P1 acceptance regressions for institutional integrity.

These tests intentionally specify Core-owned invariants. Some are expected to be
RED on WORK_BASE_SHA 530386c35e21066b11ffb5491a52418faae67269.
"""

from __future__ import annotations

import inspect

import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.adapters.tools import FakeToolAdapter
from harness.contracts import HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate, ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager
from harness.core.state.manager import IdempotencyStatus
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry


def _records() -> dict[str, dict]:
    return {
        "ID-A1": {
            "revision_ref": "ID-REV-A",
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
            "revision_ref": "REV-A",
            "loaded_excerpt_refs": ["CTX-T"],
            "allowed_scopes": ["ops:write", "ops:resume"],
            "competence_refs": ["OPS_WRITE"],
        },
        "AUT-X": {
            "revision_ref": "REV-A",
            "loaded_excerpt_refs": ["CTX-X"],
            "allowed_scopes": ["ops:write", "ops:resume"],
            "competence_refs": ["OPS_WRITE"],
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
            "task_state_ref": "TASK-STATE-1",
            "workspace_ref": "WS1",
        },
    }


def _build_resume_material(source: InMemorySourceAdapter, *, run_id: str = "R1"):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve(run_id, identity)
    context = ContextBuilder(source).build(run_id, authority.context, "TASK")
    gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )
    return identity, authority.context, context, gate


def _run(*, run_state_ref: str = "RS-B", tarefa_trabalho_id: str = "TASK-A") -> HarnessRun:
    return HarnessRun(
        run_id="R1",
        tarefa_trabalho_id=tarefa_trabalho_id,
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref=run_state_ref,
        authority_context_ref="AC-OLD",
    )


def _run_for_gate(gate: ResumeFreshnessGate, **kwargs) -> HarnessRun:
    run = _run(**kwargs)
    run.authority_context_ref = gate.previous_authority.authority_context_id
    run.task_context_ref = gate.previous_context.task_context.task_context_id
    return run


class CountingRuntime:
    def __init__(self, *, returned_status: RunStatus = RunStatus.COMPLETED):
        self.resume_calls = 0
        self.returned_status = returned_status

    def execute(self, run, payload):
        raise NotImplementedError

    def resume(self, run, current_state):
        self.resume_calls += 1
        current_state.status = self.returned_status
        return current_state


def _attempt_resume(manager, run, runtime, checkpoint_id, gate):
    try:
        manager.resume(run, runtime, checkpoint_id, freshness_gate=gate)
    except HarnessResolutionError:
        pass


def _checkpoint_fixture(
    *,
    state_run_id: str = "R1",
    state_task_id: str = "TASK-A",
    state_status: RunStatus = RunStatus.INTERRUPTED,
    run_state_id: str = "RS-B",
):
    source = InMemorySourceAdapter(_records())
    _, _, _, gate = _build_resume_material(source)
    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = RunState(
        run_state_id=run_state_id,
        run_id=state_run_id,
        tarefa_trabalho_id=state_task_id,
        status=state_status,
        current_step="step-2",
        completed_steps=["step-1"],
        pending_steps=["step-2"],
        decision_refs=["CORE-DECISION-1"],
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue from step-2",
        evidence_refs=["EV-1"],
    )
    return source, port, manager, state, checkpoint, gate


def test_resume_rejects_run_state_ref_checkpoint_state_mismatch_before_runtime():
    """run.run_state_ref must bind to checkpoint.run_state_ref/state.run_state_id."""
    _, _, manager, _, checkpoint, gate = _checkpoint_fixture(run_state_id="RS-B")
    runtime = CountingRuntime()

    _attempt_resume(manager, _run_for_gate(gate, run_state_ref="RS-A"), runtime, checkpoint.checkpoint_id, gate)

    assert runtime.resume_calls == 0


def test_resume_rejects_run_vs_state_task_mismatch_before_runtime():
    """HarnessRun and RunState must name the same Tarefa de Trabalho."""
    _, _, manager, _, checkpoint, gate = _checkpoint_fixture(state_task_id="TASK-B")
    runtime = CountingRuntime()

    _attempt_resume(manager, _run_for_gate(gate, tarefa_trabalho_id="TASK-A"), runtime, checkpoint.checkpoint_id, gate)

    assert runtime.resume_calls == 0


def test_resume_rejects_state_owned_by_different_run_before_runtime():
    """A RunState from another run must never reach RuntimePort.resume."""
    _, _, manager, _, checkpoint, gate = _checkpoint_fixture(state_run_id="R2")
    runtime = CountingRuntime()

    _attempt_resume(manager, _run_for_gate(gate), runtime, checkpoint.checkpoint_id, gate)

    assert runtime.resume_calls == 0


def test_resume_rejects_non_resumable_completed_state_before_runtime():
    """A terminal RunState cannot be resumed merely because a checkpoint exists."""
    _, _, manager, _, checkpoint, gate = _checkpoint_fixture(state_status=RunStatus.COMPLETED)
    runtime = CountingRuntime()

    _attempt_resume(manager, _run_for_gate(gate), runtime, checkpoint.checkpoint_id, gate)

    assert runtime.resume_calls == 0


def _tool_gateway(source, port, adapter):
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            tool_id="tool.write",
            action_scope="ops:write",
            side_effect=True,
            required_competence="OPS_WRITE",
        ),
        adapter,
    )
    manager = StateManager(port)
    return ToolGateway(
        registry,
        manager,
        freshness_gate=AuthorityFreshnessGate(source),
    ), manager


def test_tool_gateway_rejects_cross_run_authority_before_tool_port():
    """AuthorityContext.run_id must be bound to the executing run_id."""
    source = InMemorySourceAdapter(_records())
    identity = IdentityResolver(source).resolve("ID-A1")
    cross_run_authority = AuthorityResolver(source).resolve("R2", identity).context
    port = InMemoryStateAdapter()
    adapter = FakeToolAdapter({"ok": True, "evidence_refs": ["EV-1"]})
    gateway, _ = _tool_gateway(source, port, adapter)

    try:
        gateway.execute(
            run_id="R1",
            authority=cross_run_authority,
            tool_id="tool.write",
            payload={"value": 1},
            business_key="CROSS-RUN-1",
        )
    except HarnessResolutionError:
        pass

    assert adapter.calls == []


@pytest.mark.xfail(
    strict=True,
    reason=(
        "NOT_IMPLEMENTABLE_WITH_CURRENT_CONTRACT: ToolGateway.execute receives run_id "
        "but no independent executor agent identity to compare with AuthorityContext.agent_id"
    ),
)
def test_cross_agent_authority_binding_is_representable_at_tool_boundary():
    """Sentinel: the Tool boundary must be able to represent executor A vs authority B."""
    parameters = inspect.signature(ToolGateway.execute).parameters
    identity_inputs = {"agent_id", "executor_agent_id", "run"}.intersection(parameters)
    assert identity_inputs, (
        "ToolGateway.execute cannot represent executor agent A independently from "
        "AuthorityContext.agent_id=B"
    )


def test_runtime_cannot_mutate_core_owned_institutional_run_state_fields():
    """RuntimePort may not rewrite canonical state identity/linkage fields."""
    _, port, manager, state, checkpoint, gate = _checkpoint_fixture()
    canonical = {
        "run_state_id": state.run_state_id,
        "run_id": state.run_id,
        "tarefa_trabalho_id": state.tarefa_trabalho_id,
        "checkpoint_ref": checkpoint.checkpoint_id,
    }

    class MutatingRuntime:
        def execute(self, run, payload):
            raise NotImplementedError

        def resume(self, run, current_state):
            current_state.run_state_id = "RS-FORGED"
            current_state.run_id = "R-FORGED"
            current_state.tarefa_trabalho_id = "TASK-FORGED"
            current_state.checkpoint_ref = "CP-FORGED"
            current_state.decision_refs = ["DECISION-FORGED"]
            current_state.status = RunStatus.COMPLETED
            return current_state

    resumed = manager.resume(_run_for_gate(gate), MutatingRuntime(), checkpoint.checkpoint_id, freshness_gate=gate)

    assert {
        "run_state_id": resumed.run_state_id,
        "run_id": resumed.run_id,
        "tarefa_trabalho_id": resumed.tarefa_trabalho_id,
        "checkpoint_ref": resumed.checkpoint_ref,
    } == canonical
    assert "DECISION-FORGED" not in resumed.decision_refs
    assert port.load_run_state(canonical["run_state_id"]).run_id == canonical["run_id"]
    with pytest.raises(KeyError):
        port.load_run_state("RS-FORGED")


def test_same_checkpoint_cannot_silently_duplicate_resume_execution():
    """Reusing CP-1 must not cause a second institutional resume execution."""
    _, _, manager, _, checkpoint, gate = _checkpoint_fixture()

    class ReplaySensitiveRuntime(CountingRuntime):
        def __init__(self):
            super().__init__(returned_status=RunStatus.INTERRUPTED)
            self.institutional_executions = 0

        def resume(self, run, current_state):
            self.institutional_executions += 1
            return super().resume(run, current_state)

    runtime = ReplaySensitiveRuntime()
    run = _run_for_gate(gate)

    _attempt_resume(manager, run, runtime, checkpoint.checkpoint_id, gate)
    _attempt_resume(manager, run, runtime, checkpoint.checkpoint_id, gate)

    assert runtime.resume_calls == 1
    assert runtime.institutional_executions == 1


def test_completed_side_effect_remains_idempotent_across_resume():
    """COMPLETED ledger state must survive resume and block duplicate ToolPort calls."""
    source = InMemorySourceAdapter(_records())
    identity, authority, context, gate = _build_resume_material(source)
    port = InMemoryStateAdapter()
    adapter = FakeToolAdapter({"ok": True, "evidence_refs": ["EV-1"]})
    gateway, manager = _tool_gateway(source, port, adapter)

    gateway.execute(
        run_id="R1",
        authority=authority,
        tool_id="tool.write",
        payload={"value": 1},
        business_key="BUSINESS-42",
    )
    assert len(adapter.calls) == 1

    state = RunState(
        run_state_id="RS-B",
        run_id="R1",
        tarefa_trabalho_id="TASK-A",
        status=RunStatus.INTERRUPTED,
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")
    run = _run()
    run.authority_context_ref = authority.authority_context_id
    run.task_context_ref = context.task_context.task_context_id
    manager.resume(run, CountingRuntime(), checkpoint.checkpoint_id, freshness_gate=gate)

    with pytest.raises(HarnessResolutionError) as exc:
        gateway.execute(
            run_id="R1",
            authority=authority,
            tool_id="tool.write",
            payload={"value": 1},
            business_key="BUSINESS-42",
        )

    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert len(adapter.calls) == 1
    record = manager.get_side_effect("R1:tool.write:BUSINESS-42")
    assert record.status == IdempotencyStatus.COMPLETED


def test_unknown_side_effect_requires_reconciliation_across_resume_without_reexecution():
    """UNKNOWN must survive resume and block automatic retry until reconciliation."""
    source = InMemorySourceAdapter(_records())
    _, authority, context, gate = _build_resume_material(source)
    port = InMemoryStateAdapter()

    class UnknownOutcomeAdapter:
        def __init__(self):
            self.calls = []

        def invoke(self, tool_id, payload):
            self.calls.append((tool_id, dict(payload)))
            raise RuntimeError("provider timeout after uncertain side effect")

    adapter = UnknownOutcomeAdapter()
    gateway, manager = _tool_gateway(source, port, adapter)

    with pytest.raises(RuntimeError):
        gateway.execute(
            run_id="R1",
            authority=authority,
            tool_id="tool.write",
            payload={"value": 1},
            business_key="BUSINESS-UNKNOWN",
        )
    assert len(adapter.calls) == 1

    state = RunState(
        run_state_id="RS-B",
        run_id="R1",
        tarefa_trabalho_id="TASK-A",
        status=RunStatus.INTERRUPTED,
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")
    run = _run()
    run.authority_context_ref = authority.authority_context_id
    run.task_context_ref = context.task_context.task_context_id
    manager.resume(run, CountingRuntime(), checkpoint.checkpoint_id, freshness_gate=gate)

    with pytest.raises(HarnessResolutionError) as exc:
        gateway.execute(
            run_id="R1",
            authority=authority,
            tool_id="tool.write",
            payload={"value": 1},
            business_key="BUSINESS-UNKNOWN",
        )

    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert len(adapter.calls) == 1
    record = manager.get_side_effect("R1:tool.write:BUSINESS-UNKNOWN")
    assert record.status == IdempotencyStatus.UNKNOWN
    assert record.reconciliation_required is True
