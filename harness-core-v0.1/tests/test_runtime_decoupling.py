from harness.adapters.runtimes.fake import FakeRuntimeAdapter
from harness.contracts import HarnessRun, RunStatus
from harness.ports import RuntimePort

def test_fake_runtime_satisfies_runtime_port_and_core_runs_without_langgraph():
    runtime: RuntimePort = FakeRuntimeAdapter()
    run = HarnessRun(run_id="R1", tarefa_trabalho_id="MT-1", agent_id="A1", correlation_id="C1", workspace_ref="WS1", run_state_ref="RS1", authority_context_ref="AC1")
    state = runtime.execute(run, {"artifact_refs":["ART-1"]})
    assert state.status == RunStatus.COMPLETED
    assert state.artifact_refs == ["ART-1"]
