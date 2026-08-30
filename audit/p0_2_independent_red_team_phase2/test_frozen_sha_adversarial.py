from __future__ import annotations

from pathlib import Path
from threading import Barrier, Lock, Thread

import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.freshness import AuthorityFreshnessGate, ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry
from harness.ports.versioning import RevisionConflictError, RevisionGuardActiveError


def records():
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
        "AUT-T": {
            "revision_ref": "T-REV-1",
            "loaded_excerpt_refs": ["CTX-T1"],
            "allowed_scopes": ["ops:write", "ops:resume"],
        },
        "AUT-X": {
            "revision_ref": "X-REV-1",
            "loaded_excerpt_refs": ["CTX-X1"],
            "allowed_scopes": ["ops:write", "ops:resume"],
        },
        "AUT-N": {
            "revision_ref": "N-REV-1",
            "loaded_excerpt_refs": ["CTX-N1"],
        },
        "CTX-T1": {
            "revision_ref": "CTX-T-REV-1",
            "context_ref": "CTX-T1",
            "estimated_tokens": 10,
            "required": True,
        },
        "CTX-X1": {
            "revision_ref": "CTX-X-REV-1",
            "context_ref": "CTX-X1",
            "estimated_tokens": 10,
            "required": True,
        },
        "CTX-N1": {
            "revision_ref": "CTX-N-REV-1",
            "context_ref": "CTX-N1",
            "estimated_tokens": 10,
            "required": True,
        },
        "TASK": {
            "revision_ref": "TASK-REV-1",
            "tarefa_trabalho_id": "MT-1",
            "current_order": "continue",
            "task_state_ref": "TASK-STATE-1",
            "workspace_ref": "WS1",
        },
    }


def resolved(source, run_id="R1"):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve(run_id, identity)
    context = ContextBuilder(source).build(run_id, authority.context, "TASK")
    return identity, authority, context


def resume_gate(source, identity, authority, context):
    return ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )


def run_for_resume():
    return HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref="AC-OLD",
    )


def checkpoint(manager):
    state = RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED,
        current_step="resume",
    )
    manager.persist(state)
    return manager.checkpoint(
        state,
        validated_step="before-resume",
        resume_instruction="continue",
    )


def tool_execution(source, adapter, *, business_key="EXTERNAL-TOOL"):
    identity, authority, context = resolved(source)
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(tool_id="ops.write", action_scope="ops:write", side_effect=True),
        adapter,
    )
    manager = StateManager(InMemoryStateAdapter())
    gateway = ToolGateway(registry, manager, freshness_gate=AuthorityFreshnessGate(source))
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
    return gateway.execute(
        run_id="R1",
        authority=authority.context,
        run=run,
        task_context=context.task_context,
        tool_id="ops.write",
        payload={"value": 1},
        business_key=business_key,
    )


def test_external_tool_writer_is_blocked_while_toolport_is_physically_running():
    source = InMemorySourceAdapter(records())

    class AttackingTool:
        def __init__(self):
            self.calls = 0
            self.writer_error = None

        def invoke(self, tool_id, payload):
            self.calls += 1
            try:
                source.records["AUT-X"]["red_team_writer"] = True
            except Exception as exc:
                self.writer_error = exc
            return {"ok": True, "evidence_refs": ["EV-RED-TEAM"]}

    adapter = AttackingTool()
    result = tool_execution(source, adapter, business_key="EXTERNAL-TOCTOU-TOOL")

    assert result.output["ok"] is True
    assert adapter.calls == 1
    assert isinstance(adapter.writer_error, RevisionGuardActiveError)
    assert "red_team_writer" not in source.read("AUT-X")


def test_external_runtime_writer_is_blocked_while_runtime_resume_is_physically_running():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolved(source)
    manager = StateManager(InMemoryStateAdapter())
    cp = checkpoint(manager)

    class AttackingRuntime:
        calls = 0
        writer_error = None

        def resume(self, run, state):
            self.calls += 1
            try:
                source.records["TASK"]["red_team_writer"] = True
            except Exception as exc:
                self.writer_error = exc
            state.status = RunStatus.COMPLETED
            return state

    runtime = AttackingRuntime()
    result = manager.resume(
        run_for_resume(),
        runtime,
        cp.checkpoint_id,
        freshness_gate=resume_gate(source, identity, authority, context),
    )

    assert result.status is RunStatus.COMPLETED
    assert runtime.calls == 1
    assert isinstance(runtime.writer_error, RevisionGuardActiveError)
    assert "red_team_writer" not in source.read("TASK")


class MutateOnAcquireSource(InMemorySourceAdapter):
    def __init__(self, initial):
        super().__init__(initial)
        self.target = None

    def acquire_revision_guard(self, expected_versions, owner_ref):
        if self.target is not None:
            target = self.target
            self.target = None
            self.records[target]["external_stale_attack"] = True
        return super().acquire_revision_guard(expected_versions, owner_ref)


@pytest.mark.parametrize(
    "source_ref",
    ["ID-A1", "AUT-T", "AUT-X", "AUT-N", "TASK", "CTX-T1", "CTX-X1", "CTX-N1"],
)
def test_external_resume_stale_source_after_prepare_conflicts_before_runtime(source_ref):
    source = MutateOnAcquireSource(records())
    identity, authority, context = resolved(source)
    manager = StateManager(InMemoryStateAdapter())
    cp = checkpoint(manager)

    class MustNotRun:
        calls = 0

        def resume(self, run, state):
            self.calls += 1
            return state

    runtime = MustNotRun()
    source.target = source_ref
    with pytest.raises(RevisionConflictError) as exc:
        manager.resume(
            run_for_resume(),
            runtime,
            cp.checkpoint_id,
            freshness_gate=resume_gate(source, identity, authority, context),
        )
    assert exc.value.source_ref == source_ref
    assert runtime.calls == 0


def test_external_tool_guard_releases_after_tool_exception():
    source = InMemorySourceAdapter(records())

    class FailingTool:
        def invoke(self, tool_id, payload):
            raise RuntimeError("external tool crash")

    with pytest.raises(RuntimeError, match="external tool crash"):
        tool_execution(source, FailingTool(), business_key="EXTERNAL-TOOL-EXCEPTION")

    source.records["AUT-T"]["after_exception"] = True
    assert source.read("AUT-T")["after_exception"] is True


def test_external_runtime_guard_releases_after_runtime_exception():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolved(source)
    manager = StateManager(InMemoryStateAdapter())
    cp = checkpoint(manager)

    class FailingRuntime:
        def resume(self, run, state):
            raise RuntimeError("external runtime crash")

    with pytest.raises(RuntimeError, match="external runtime crash"):
        manager.resume(
            run_for_resume(),
            FailingRuntime(),
            cp.checkpoint_id,
            freshness_gate=resume_gate(source, identity, authority, context),
        )

    source.records["AUT-X"]["after_exception"] = True
    assert source.read("AUT-X")["after_exception"] is True


def test_external_no_parallel_revision_protection_family_in_frozen_production():
    harness_root = Path("harness-core-v0.1/harness")
    forbidden = (
        "RevisionLeasePort",
        "RuntimeResumeFence",
        "RevisionSnapshot",
        "ResumeExecutionToken",
        "RevisionFenceSource",
        "ToolBoundaryFence",
    )
    hits = []
    for path in harness_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for symbol in forbidden:
            if symbol in text:
                hits.append(f"{path}:{symbol}")
    assert hits == []


class SynchronizedLoadStatePort(InMemoryStateAdapter):
    """Force two resume attempts to observe the same INTERRUPTED snapshot."""

    def __init__(self):
        super().__init__()
        self.synchronize_loads = False
        self.barrier = Barrier(2)

    def load_run_state(self, run_state_id):
        state = super().load_run_state(run_state_id)
        if self.synchronize_loads:
            self.barrier.wait(timeout=5)
        return state


def test_external_same_checkpoint_must_not_cross_runtime_resume_concurrently_twice():
    """Exactly one release is allowed for one checkpoint execution identity."""

    source = InMemorySourceAdapter(records())
    identity, authority, context = resolved(source)
    state_port = SynchronizedLoadStatePort()
    manager = StateManager(state_port)
    cp = checkpoint(manager)
    state_port.synchronize_loads = True

    class CountingRuntime:
        def __init__(self):
            self.calls = 0
            self.lock = Lock()

        def resume(self, run, state):
            with self.lock:
                self.calls += 1
            state.status = RunStatus.COMPLETED
            return state

    runtime = CountingRuntime()
    start = Barrier(3)
    errors = []

    def attack():
        try:
            gate = resume_gate(source, identity, authority, context)
            start.wait(timeout=5)
            manager.resume(
                run_for_resume(),
                runtime,
                cp.checkpoint_id,
                freshness_gate=gate,
            )
        except Exception as exc:
            errors.append(exc)

    threads = [Thread(target=attack), Thread(target=attack)]
    for thread in threads:
        thread.start()
    start.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert runtime.calls == 1, (
        "same checkpoint crossed RuntimePort.resume more than once under concurrent replay: "
        f"runtime_calls={runtime.calls}, errors={[type(e).__name__ for e in errors]}"
    )
