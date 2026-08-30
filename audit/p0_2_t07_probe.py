from __future__ import annotations

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.freshness import ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager


def test_t07_future_runtime_is_bound_to_new_technical_revision_only():
    source = InMemorySourceAdapter({
        "ID-A1": {
            "revision_ref": "ID-REV-1",
            "identity": {
                "agent_id": "A1", "name": "A1", "mission_ref": "M1", "scope_ref": "S1",
                "organizational_path_ref": "O1", "tactical_authority_ref": "AUT-T",
                "technical_authority_ref": "AUT-X", "normative_authority_ref": "AUT-N",
                "source_ref": "ID-A1",
            },
        },
        "AUT-T": {"revision_ref": "T-REV-1", "loaded_excerpt_refs": ["CTX-T1"], "allowed_scopes": ["ops:resume"]},
        "AUT-X": {"revision_ref": "X-REV-1", "loaded_excerpt_refs": ["CTX-X1"], "allowed_scopes": ["ops:resume"]},
        "AUT-N": {"revision_ref": "N-REV-1", "loaded_excerpt_refs": ["CTX-N1"], "allowed_scopes": ["ops:resume"]},
        "CTX-T1": {"revision_ref": "CTX-T-1", "context_ref": "CTX-T1", "estimated_tokens": 10, "required": True},
        "CTX-X1": {"revision_ref": "CTX-X-1", "context_ref": "CTX-X1", "estimated_tokens": 10, "required": True},
        "CTX-X2": {"revision_ref": "CTX-X-2", "context_ref": "CTX-X2", "estimated_tokens": 10, "required": True},
        "CTX-N1": {"revision_ref": "CTX-N-1", "context_ref": "CTX-N1", "estimated_tokens": 10, "required": True},
        "TASK": {"revision_ref": "TASK-REV-1", "tarefa_trabalho_id": "MT-1", "current_order": "continue", "task_state_ref": "TS1", "workspace_ref": "WS1"},
    })
    identity = IdentityResolver(source).resolve("ID-A1")
    old_authority = AuthorityResolver(source).resolve("R1", identity)
    old_context = ContextBuilder(source).build("R1", old_authority.context, "TASK")

    source.records["AUT-X"] = {
        "revision_ref": "X-REV-2",
        "loaded_excerpt_refs": ["CTX-X2"],
        "allowed_scopes": ["ops:resume"],
    }

    gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=old_authority.context,
        previous_context=old_context,
    )
    run = HarnessRun(
        run_id="R1", tarefa_trabalho_id="MT-1", agent_id="A1", correlation_id="C1",
        workspace_ref="WS1", run_state_ref="RS1", authority_context_ref="AC-OLD",
    )
    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = RunState(
        run_state_id="RS1", run_id="R1", tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED, current_step="resume",
    )
    manager.persist(state)
    cp = manager.checkpoint(state, validated_step="before", resume_instruction="continue")

    class Runtime:
        calls = 0
        def execute(self, run, payload):
            raise NotImplementedError
        def resume(self, run, state):
            self.calls += 1
            assert source._active_guards
            state.status = RunStatus.COMPLETED
            return state

    runtime = Runtime()
    manager.resume(run, runtime, cp.checkpoint_id, freshness_gate=gate)
    assert runtime.calls == 1

    trace = [r for r in port.list_revalidation_records("R1") if r["boundary"] == "RuntimePort.resume"][0]
    assert list(trace["changed_chains"]) == ["TECHNICAL"]
    assert trace["authority_snapshot"]["technical_source_revision_refs"] == ["X-REV-2"]
    assert trace["authority_snapshot"]["tactical_source_revision_refs"] == ["T-REV-1"]
    assert trace["authority_snapshot"]["normative_source_revision_refs"] == ["N-REV-1"]
    assert trace["task_context"]["technical_context_refs"] == ["CTX-X2"]
    assert trace["task_context"]["tactical_context_refs"] == old_context.task_context.tactical_context_refs
    assert trace["task_context"]["normative_context_refs"] == old_context.task_context.normative_context_refs
    assert trace["metadata"]["versioned_read_set"]["expected_versions"]["AUT-X"]["revision_ref"] == "X-REV-2"
    assert trace["outcome"] == "COMPLETED"
