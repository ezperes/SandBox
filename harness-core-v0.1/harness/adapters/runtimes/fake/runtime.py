from typing import Any
from harness.contracts import HarnessRun, RunState, RunStatus

class FakeRuntimeAdapter:
    def execute(self, run: HarnessRun, payload: dict[str, Any]) -> RunState:
        return RunState(run_state_id=run.run_state_ref, run_id=run.run_id, tarefa_trabalho_id=run.tarefa_trabalho_id, status=RunStatus.COMPLETED, current_step="fake-runtime-complete", completed_steps=["fake-runtime-execute"], artifact_refs=list(payload.get("artifact_refs", [])))
    def resume(self, run: HarnessRun, state: RunState) -> RunState:
        state.status = RunStatus.COMPLETED
        state.current_step = "fake-runtime-resume-complete"
        return state
