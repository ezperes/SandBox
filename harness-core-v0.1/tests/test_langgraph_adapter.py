from harness.adapters.runtimes.langgraph import LangGraphAdapter
from harness.contracts import HarnessRun, RunState, RunStatus


class StubGraph:
    def __init__(self):
        self.calls = []

    def invoke(self, input, config):
        self.calls.append((input, config))
        if input is None:
            return {
                "harness_status": "COMPLETED",
                "current_step": "resumed-complete",
                "completed_steps": ["step-1", "step-2"],
            }
        return {
            "harness_status": "INTERRUPTED",
            "current_step": "awaiting-approval",
            "completed_steps": ["step-1"],
            "pending_steps": ["step-2"],
            "artifact_refs": ["ART-1"],
        }


def run():
    return HarnessRun(
        run_id="RUN-1",
        tarefa_trabalho_id="TT-1",
        agent_id="AGT-1",
        correlation_id="CORR-1",
        workspace_ref="WS-1",
        run_state_ref="RS-1",
        authority_context_ref="AC-1",
    )


def test_execute_translates_native_state_without_owning_identity_or_authority():
    graph = StubGraph()
    adapter = LangGraphAdapter(graph)
    result = adapter.execute(run(), {"input": "x"})

    assert result.run_state_id == "RS-1"
    assert result.status == RunStatus.INTERRUPTED
    assert result.current_step == "awaiting-approval"
    assert graph.calls[0][1]["configurable"]["thread_id"] == "RUN-1"
    assert "agent_id" not in graph.calls[0][0]
    assert "authority_context_ref" not in graph.calls[0][0]


def test_resume_uses_existing_langgraph_thread_and_preserves_canonical_refs():
    graph = StubGraph()
    adapter = LangGraphAdapter(graph)
    state = RunState(
        run_state_id="RS-1",
        run_id="RUN-1",
        tarefa_trabalho_id="TT-1",
        status=RunStatus.INTERRUPTED,
        checkpoint_ref="CP-1",
        artifact_refs=["ART-1"],
    )

    resumed = adapter.resume(run(), state)

    assert graph.calls[0][0] is None
    assert resumed.status == RunStatus.COMPLETED
    assert resumed.checkpoint_ref == "CP-1"
    assert resumed.artifact_refs == ["ART-1"]


def test_resume_rejects_foreign_canonical_state_before_runtime_call():
    graph = StubGraph()
    adapter = LangGraphAdapter(graph)
    state = RunState(
        run_state_id="RS-X",
        run_id="RUN-X",
        tarefa_trabalho_id="TT-1",
        status=RunStatus.INTERRUPTED,
    )

    try:
        adapter.resume(run(), state)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "does not belong" in str(exc)
    assert graph.calls == []
