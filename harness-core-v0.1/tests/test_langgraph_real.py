from importlib.metadata import version
from pathlib import Path
from typing import TypedDict
import subprocess
import sys
import textwrap
import tomllib

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from harness.adapters.runtimes.langgraph import LangGraphAdapter
from harness.contracts import HarnessRun, RunStatus


class NativeState(TypedDict, total=False):
    input: str
    run_id: str
    tarefa_trabalho_id: str
    harness_status: str
    current_step: str
    completed_steps: list[str]
    pending_steps: list[str]
    artifact_refs: list[str]
    observed_input_keys: list[str]


def _run() -> HarnessRun:
    return HarnessRun(
        run_id="RUN-REAL-1",
        tarefa_trabalho_id="TT-REAL-1",
        agent_id="AGENT-CANONICAL",
        correlation_id="CORR-REAL-1",
        workspace_ref="WS-REAL-1",
        run_state_ref="RS-REAL-1",
        authority_context_ref="AUTH-CANONICAL",
    )


def _real_graph():
    def step_one(state: NativeState) -> NativeState:
        return {
            "harness_status": "INTERRUPTED",
            "current_step": "step-one",
            "completed_steps": ["step-one"],
            "pending_steps": ["step-two"],
            "artifact_refs": list(state.get("artifact_refs", [])),
            "observed_input_keys": sorted(state.keys()),
        }

    def step_two(state: NativeState) -> NativeState:
        return {
            "harness_status": "COMPLETED",
            "current_step": "step-two",
            "completed_steps": ["step-one", "step-two"],
            "pending_steps": [],
        }

    builder = StateGraph(NativeState)
    builder.add_node("step_one", step_one)
    builder.add_node("step_two", step_two)
    builder.add_edge(START, "step_one")
    builder.add_edge("step_one", "step_two")
    builder.add_edge("step_two", END)
    return builder.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["step_two"],
    )


def test_real_stategraph_interrupt_checkpoint_and_resume_translate_to_canonical_state():
    graph = _real_graph()
    run = _run()
    adapter = LangGraphAdapter(graph)

    interrupted = adapter.execute(run, {"input": "payload", "artifact_refs": ["ART-1"]})

    assert interrupted.status == RunStatus.INTERRUPTED
    assert interrupted.run_id == "RUN-REAL-1"
    assert interrupted.run_state_id == "RS-REAL-1"
    assert interrupted.completed_steps == ["step-one"]
    assert interrupted.pending_steps == ["step-two"]
    assert interrupted.artifact_refs == ["ART-1"]
    assert interrupted.checkpoint_ref is None
    assert interrupted.decision_refs == []

    config = {"configurable": {"thread_id": run.run_id}}
    native_snapshot = graph.get_state(config)
    assert native_snapshot.next == ("step_two",)
    assert native_snapshot.config["configurable"]["thread_id"] == run.run_id
    technical_checkpoint_id = native_snapshot.config["configurable"].get("checkpoint_id")
    assert technical_checkpoint_id
    assert "agent_id" not in native_snapshot.values["observed_input_keys"]
    assert "authority_context_ref" not in native_snapshot.values["observed_input_keys"]

    # These refs represent state owned by the Core, not by LangGraph's checkpointer.
    interrupted.checkpoint_ref = "CP-CANONICAL-1"
    interrupted.decision_refs = ["DEC-CANONICAL-1"]
    assert technical_checkpoint_id != interrupted.checkpoint_ref

    resumed = adapter.resume(run, interrupted)

    assert resumed.status == RunStatus.COMPLETED
    assert resumed.current_step == "step-two"
    assert resumed.completed_steps == ["step-one", "step-two"]
    assert resumed.pending_steps == []
    assert resumed.artifact_refs == ["ART-1"]
    assert resumed.checkpoint_ref == "CP-CANONICAL-1"
    assert resumed.decision_refs == ["DEC-CANONICAL-1"]


def test_langgraph_is_explicitly_pinned_but_not_a_core_dependency():
    assert version("langgraph") == "1.2.11"

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    core_dependencies = pyproject["project"]["dependencies"]
    optional = pyproject["project"]["optional-dependencies"]

    assert not any(dependency.startswith("langgraph") for dependency in core_dependencies)
    assert "langgraph==1.2.11" in optional["langgraph"]
    assert "langgraph==1.2.11" in optional["dev"]


def test_core_fake_runtime_executes_when_langgraph_imports_are_blocked():
    program = textwrap.dedent(
        """
        import builtins

        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == "langgraph" or name.startswith("langgraph."):
                raise ModuleNotFoundError("LangGraph intentionally unavailable")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = blocked_import

        from harness.adapters.runtimes.fake import FakeRuntimeAdapter
        from harness.contracts import HarnessRun, RunStatus

        run = HarnessRun(
            run_id="RUN-NO-LG",
            tarefa_trabalho_id="TT-NO-LG",
            agent_id="AGENT-1",
            correlation_id="CORR-1",
            workspace_ref="WS-1",
            run_state_ref="RS-NO-LG",
            authority_context_ref="AUTH-1",
        )
        state = FakeRuntimeAdapter().execute(run, {"artifact_refs": ["ART-NO-LG"]})
        assert state.status == RunStatus.COMPLETED
        assert state.artifact_refs == ["ART-NO-LG"]
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
