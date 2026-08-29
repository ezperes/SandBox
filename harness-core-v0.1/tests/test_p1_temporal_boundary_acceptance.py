"""P1 acceptance regressions for temporal trace and TOCTOU boundaries.

The tests are architectural acceptance probes. They do not prescribe locking,
transactions, leases, CAS, snapshots, or any other implementation mechanism.
"""

from __future__ import annotations

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.freshness import AuthorityFreshnessGate, ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager
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
        },
        "AUT-X": {
            "revision_ref": "REV-A",
            "loaded_excerpt_refs": ["CTX-X"],
            "allowed_scopes": ["ops:write", "ops:resume"],
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


def _previous_material(source: InMemorySourceAdapter):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
    gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )
    return identity, authority.context, context, gate


def _run(authority_context_ref: str, task_context_ref: str | None = None) -> HarnessRun:
    return HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="TASK-A",
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref=authority_context_ref,
        task_context_ref=task_context_ref,
    )


def _record_contains_unambiguous_epoch(
    record: object,
    *,
    step: str,
    expected_revision: str,
    expected_context_ref: str,
    other_revision: str,
    other_context_ref: str,
) -> bool:
    text = repr(record)
    return (
        step in text
        and expected_revision in text
        and expected_context_ref in text
        and other_revision not in text
        and other_context_ref not in text
    )


def test_trace_can_attribute_each_completed_step_to_authority_revision_across_resume():
    """After rev-A -> checkpoint -> rev-B -> resume, every step needs temporal attribution."""
    source = InMemorySourceAdapter(_records())
    _, authority_a, context_a, gate = _previous_material(source)

    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="TASK-A",
        status=RunStatus.INTERRUPTED,
        current_step="step-3",
        completed_steps=["step-1", "step-2"],
        pending_steps=["step-3", "step-4"],
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-2",
        resume_instruction="continue from step-3",
    )

    for ref in ("AUT-T", "AUT-X", "AUT-N"):
        source.records[ref]["revision_ref"] = "REV-B"

    class StepsAfterResumeRuntime:
        def execute(self, run, payload):
            raise NotImplementedError

        def resume(self, run, current_state):
            current_state.completed_steps.extend(["step-3", "step-4"])
            current_state.pending_steps = []
            current_state.current_step = "step-4"
            current_state.status = RunStatus.COMPLETED
            return current_state

    run = _run(authority_a.authority_context_id, context_a.task_context.task_context_id)
    resumed = manager.resume(run, StepsAfterResumeRuntime(), checkpoint.checkpoint_id, freshness_gate=gate)
    assert resumed.completed_steps == ["step-1", "step-2", "step-3", "step-4"]
    context_b_ref = run.task_context_ref
    assert context_b_ref is not None
    assert context_b_ref != context_a.task_context.task_context_id

    persisted_artifacts: list[object] = [resumed.model_dump(mode="json")]
    persisted_artifacts.extend(port.list_revalidation_records("R1"))

    epoch_a = ("REV-A", context_a.task_context.task_context_id)
    epoch_b = ("REV-B", context_b_ref)
    expected = {
        "step-1": epoch_a,
        "step-2": epoch_a,
        "step-3": epoch_b,
        "step-4": epoch_b,
    }
    for step, (revision, context_ref) in expected.items():
        other_revision, other_context_ref = epoch_b if revision == "REV-A" else epoch_a
        assert any(
            _record_contains_unambiguous_epoch(
                record,
                step=step,
                expected_revision=revision,
                expected_context_ref=context_ref,
                other_revision=other_revision,
                other_context_ref=other_context_ref,
            )
            for record in persisted_artifacts
        ), (
            f"no persisted evidence can unambiguously attribute {step} to "
            f"authority revision {revision} and context {context_ref}"
        )


class FlipAfterFreshnessSource(InMemorySourceAdapter):
    """Deterministically changes canonical authority after the final freshness read."""

    def __init__(self, records):
        super().__init__(records)
        self.armed = False

    def read(self, source_ref: str):
        raw = super().read(source_ref)
        if self.armed and source_ref == "AUT-N":
            self.records["AUT-T"]["revision_ref"] = "REV-B"
            self.armed = False
        return raw


def test_tool_boundary_blocks_if_authority_changes_after_freshness_before_invoke():
    """freshness rev-A -> source rev-B -> ToolPort must not cross the boundary."""
    source = FlipAfterFreshnessSource(_records())
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity).context

    class ObservingTool:
        def __init__(self):
            self.calls = 0
            self.observed_revision = None

        def invoke(self, tool_id, payload):
            self.calls += 1
            self.observed_revision = source.records["AUT-T"]["revision_ref"]
            return {"ok": True, "evidence_refs": ["EV-1"]}

    adapter = ObservingTool()
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(tool_id="tool.write", action_scope="ops:write", side_effect=True),
        adapter,
    )
    gateway = ToolGateway(
        registry,
        StateManager(InMemoryStateAdapter()),
        freshness_gate=AuthorityFreshnessGate(source),
    )

    source.armed = True
    gateway.execute(
        run_id="R1",
        authority=authority,
        tool_id="tool.write",
        payload={"step": "external-write"},
        business_key="TOCTOU-TOOL",
    )

    assert source.records["AUT-T"]["revision_ref"] == "REV-B"
    assert adapter.calls == 0


class FlipAfterPrepareSource(InMemorySourceAdapter):
    """Changes authority on the final task read inside ResumeFreshnessGate.prepare()."""

    def __init__(self, records):
        super().__init__(records)
        self.armed = False

    def read(self, source_ref: str):
        raw = super().read(source_ref)
        if self.armed and source_ref == "TASK":
            self.records["AUT-T"]["revision_ref"] = "REV-B"
            self.armed = False
        return raw


def test_runtime_boundary_blocks_if_authority_changes_after_prepare_before_resume():
    """prepare rev-A -> source rev-B -> RuntimePort.resume must not cross the boundary."""
    source = FlipAfterPrepareSource(_records())
    _, authority_a, context_a, gate = _previous_material(source)

    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="TASK-A",
        status=RunStatus.INTERRUPTED,
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")

    class ObservingRuntime:
        def __init__(self):
            self.resume_calls = 0
            self.observed_revision = None

        def execute(self, run, payload):
            raise NotImplementedError

        def resume(self, run, current_state):
            self.resume_calls += 1
            self.observed_revision = source.records["AUT-T"]["revision_ref"]
            return current_state

    runtime = ObservingRuntime()
    run = _run(authority_a.authority_context_id, context_a.task_context.task_context_id)

    source.armed = True
    manager.resume(run, runtime, checkpoint.checkpoint_id, freshness_gate=gate)

    assert source.records["AUT-T"]["revision_ref"] == "REV-B"
    assert runtime.resume_calls == 0
