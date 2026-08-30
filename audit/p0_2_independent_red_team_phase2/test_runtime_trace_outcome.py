from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.freshness import ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager


def test_runtime_success_trace_distinguishes_release_from_completed_boundary():
    source = InMemorySourceAdapter({
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
        "AUT-T": {"revision_ref": "T-REV-1", "loaded_excerpt_refs": ["CTX-T"]},
        "AUT-X": {"revision_ref": "X-REV-1", "loaded_excerpt_refs": ["CTX-X"]},
        "AUT-N": {"revision_ref": "N-REV-1", "loaded_excerpt_refs": ["CTX-N"]},
        "CTX-T": {"context_ref": "CTX-T", "estimated_tokens": 1, "required": True},
        "CTX-X": {"context_ref": "CTX-X", "estimated_tokens": 1, "required": True},
        "CTX-N": {"context_ref": "CTX-N", "estimated_tokens": 1, "required": True},
        "TASK": {
            "revision_ref": "TASK-REV-1",
            "tarefa_trabalho_id": "MT-1",
            "current_order": "continue",
            "task_state_ref": "TS-1",
            "workspace_ref": "WS1",
        },
    })
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
    run = HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref=authority.context.authority_context_id,
        task_context_ref=context.task_context.task_context_id,
    )
    port = InMemoryStateAdapter()
    manager = StateManager(port)
    state = RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED,
    )
    manager.persist(state)
    cp = manager.checkpoint(state, validated_step="s1", resume_instruction="continue")

    class SuccessfulRuntime:
        def resume(self, runtime_run, runtime_state):
            runtime_state.status = RunStatus.COMPLETED
            return runtime_state

    resumed = manager.resume(run, SuccessfulRuntime(), cp.checkpoint_id, freshness_gate=gate)
    assert resumed.status is RunStatus.COMPLETED
    rv_ref = next(ref for ref in resumed.decision_refs if ref.startswith("RV-"))
    audit = port.load_revalidation_record(rv_ref)

    assert audit["boundary"] == "RuntimePort.resume"
    assert audit["outcome"] == "COMPLETED", (
        "runtime trace records authorization/guard release but not successful boundary completion: "
        f"outcome={audit['outcome']!r}, events={audit['events']!r}"
    )
    assert audit["events"][-1].get("outcome") == "COMPLETED"
