from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol

from harness.contracts import HarnessRun, RunState, RunStatus


class CompiledGraphPort(Protocol):
    """Minimal LangGraph-compatible surface used by the adapter."""

    def invoke(self, input: dict[str, Any] | None, config: dict[str, Any]) -> dict[str, Any]: ...


class LangGraphAdapter:
    """Translate LangGraph execution mechanics into canonical Harness RunState.

    LangGraph may execute/checkpoint/interrupt, but it never owns institutional
    identity, authority, policy or canonical state semantics.
    """

    def __init__(self, graph: CompiledGraphPort):
        self.graph = graph

    @staticmethod
    def _config(run: HarnessRun) -> dict[str, Any]:
        return {"configurable": {"thread_id": run.run_id}}

    @staticmethod
    def _canonical_state(run: HarnessRun, native: dict[str, Any], prior: RunState | None = None) -> RunState:
        status_raw = native.get("harness_status", RunStatus.COMPLETED)
        status = status_raw if isinstance(status_raw, RunStatus) else RunStatus(status_raw)
        completed = list(native.get("completed_steps", prior.completed_steps if prior else []))
        pending = list(native.get("pending_steps", prior.pending_steps if prior else []))
        artifacts = list(native.get("artifact_refs", prior.artifact_refs if prior else []))
        decisions = list(native.get("decision_refs", prior.decision_refs if prior else []))
        checkpoint_ref = native.get("canonical_checkpoint_ref", prior.checkpoint_ref if prior else None)
        return RunState(
            run_state_id=run.run_state_ref,
            run_id=run.run_id,
            tarefa_trabalho_id=run.tarefa_trabalho_id,
            status=status,
            current_step=native.get("current_step"),
            completed_steps=completed,
            pending_steps=pending,
            artifact_refs=artifacts,
            decision_refs=decisions,
            checkpoint_ref=checkpoint_ref,
        )

    def execute(self, run: HarnessRun, payload: dict[str, Any]) -> RunState:
        native_input = deepcopy(payload)
        native_input["run_id"] = run.run_id
        native_input["tarefa_trabalho_id"] = run.tarefa_trabalho_id
        native = self.graph.invoke(native_input, self._config(run))
        if not isinstance(native, dict):
            raise TypeError("LangGraph adapter requires dict-like graph state")
        return self._canonical_state(run, native)

    def resume(self, run: HarnessRun, state: RunState) -> RunState:
        if state.run_id != run.run_id or state.run_state_id != run.run_state_ref:
            raise ValueError("canonical run state does not belong to run")
        # LangGraph resumes an existing thread when invoked with None. Canonical
        # side-effect idempotency remains outside the runtime in StatePort.
        native = self.graph.invoke(None, self._config(run))
        if not isinstance(native, dict):
            raise TypeError("LangGraph adapter requires dict-like graph state")
        return self._canonical_state(run, native, prior=state)
