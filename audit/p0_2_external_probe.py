from __future__ import annotations

from pathlib import Path
from threading import Barrier, Lock, Thread

import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager
from harness.core.state.binding import RunStateBindingGuard
from harness.core.state.manager import IdempotencyStatus


def records():
    return {
        "ID-A1": {"revision_ref": "ID-REV-1", "identity": {"agent_id": "A1", "name": "A1", "mission_ref": "M1", "scope_ref": "S1", "organizational_path_ref": "O1", "tactical_authority_ref": "AUT-T", "technical_authority_ref": "AUT-X", "normative_authority_ref": "AUT-N", "source_ref": "ID-A1"}},
        "AUT-T": {"revision_ref": "T-REV-1", "loaded_excerpt_refs": ["CTX-T"], "allowed_scopes": ["ops:resume"]},
        "AUT-X": {"revision_ref": "X-REV-1", "loaded_excerpt_refs": ["CTX-X"], "allowed_scopes": ["ops:resume"]},
        "AUT-N": {"revision_ref": "N-REV-1", "loaded_excerpt_refs": ["CTX-N"], "allowed_scopes": ["ops:resume"]},
        "CTX-T": {"context_ref": "CTX-T", "estimated_tokens": 10, "required": True},
        "CTX-X": {"context_ref": "CTX-X", "estimated_tokens": 10, "required": True},
        "CTX-N": {"context_ref": "CTX-N", "estimated_tokens": 10, "required": True},
        "TASK": {"tarefa_trabalho_id": "MT-1", "current_order": "continue", "task_state_ref": "TS1", "workspace_ref": "WS1"},
    }


def make_run():
    return HarnessRun(run_id="R1", tarefa_trabalho_id="MT-1", agent_id="A1", correlation_id="C1", workspace_ref="WS1", run_state_ref="RS1", authority_context_ref="AC-OLD")


def resolve(source):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
    return identity, authority, context


def make_gate(source, identity, authority, context):
    return ResumeFreshnessGate(source=source, identity_source_ref="ID-A1", task_source_ref="TASK", previous_identity_revision_ref=identity.source_revision_ref, previous_authority=authority.context, previous_context=context)


def setup(state_port):
    manager = StateManager(state_port)
    state = RunState(run_state_id="RS1", run_id="R1", tarefa_trabalho_id="MT-1", status=RunStatus.INTERRUPTED, current_step="s2", completed_steps=["s1"], pending_steps=["s2"])
    manager.persist(state)
    cp = manager.checkpoint(state, validated_step="s1", resume_instruction="continue")
    return manager, cp


def claim(manager, port, cp):
    persisted_cp = port.load_checkpoint(cp.checkpoint_id)
    state = port.load_run_state(persisted_cp.run_state_ref)
    binding = RunStateBindingGuard.ensure_bound(make_run(), state, persisted_cp)
    key = manager._effect_key(binding.run_id, manager._RESUME_OPERATION, manager._resume_business_key(binding))
    return manager.get_side_effect(key)


class CountingRuntime:
    def __init__(self, source=None):
        self.calls = 0
        self.lock = Lock()
        self.source = source
        self.guard_active = False
    def execute(self, run, payload):
        raise NotImplementedError
    def resume(self, run, state):
        with self.lock:
            self.calls += 1
        if self.source is not None:
            self.guard_active = bool(self.source._active_guards)
        state.status = RunStatus.COMPLETED
        return state


class ConcurrentLoadState(InMemoryStateAdapter):
    def __init__(self, n):
        super().__init__()
        self.barrier = Barrier(n)
        self.remaining = n
        self.mu = Lock()
    def load_run_state(self, run_state_id):
        state = super().load_run_state(run_state_id)
        wait = False
        with self.mu:
            if run_state_id == "RS1" and self.remaining > 0:
                self.remaining -= 1
                wait = True
        if wait:
            self.barrier.wait(timeout=10)
        return state


def test_external_b1_eight_real_concurrent_callers_exactly_one_runtime():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)
    port = ConcurrentLoadState(8)
    manager, cp = setup(port)
    runtime = CountingRuntime()
    errors = []
    lock = Lock()
    def contender():
        try:
            manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=make_gate(source, identity, authority, context))
        except BaseException as exc:
            with lock:
                errors.append(exc)
    threads = [Thread(target=contender) for _ in range(8)]
    for t in threads: t.start()
    for t in threads:
        t.join(timeout=15)
        assert not t.is_alive()
    assert runtime.calls == 1
    assert len(errors) == 7
    assert all(isinstance(e, HarnessResolutionError) and e.code == HarnessErrorCode.RETRY_BLOCKED for e in errors)
    assert claim(manager, port, cp).status == IdempotencyStatus.COMPLETED


def test_external_b2_terminal_trace_and_guard_order():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)
    port = InMemoryStateAdapter()
    manager, cp = setup(port)
    runtime = CountingRuntime(source)
    manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=make_gate(source, identity, authority, context))
    traces = [r for r in port.list_revalidation_records("R1") if r["boundary"] == "RuntimePort.resume"]
    assert len(traces) == 1
    trace = traces[0]
    assert runtime.guard_active is True
    assert port.load_run_state("RS1").status == RunStatus.COMPLETED
    assert [e.get("outcome") for e in trace["events"]] == [None, "REVALIDATED_AND_GUARDED", "COMPLETED"]
    assert trace["outcome"] == "COMPLETED"
    assert trace["run_id"] == "R1" and trace["agent_id"] == "A1" and trace["tarefa_trabalho_id"] == "MT-1" and trace["correlation_id"] == "C1"
    assert trace["authority_context_ref"]
    assert trace["metadata"]["versioned_read_set"] and trace["metadata"]["revision_guard"]


def test_external_post_runtime_terminal_trace_failure_is_fail_closed():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)
    class FailTerminalTrace(InMemoryStateAdapter):
        def __init__(self):
            super().__init__(); self.failed = False
        def save_revalidation_record(self, rid, record):
            if record.get("boundary") == "RuntimePort.resume" and record.get("outcome") == "COMPLETED" and not self.failed:
                self.failed = True
                raise RuntimeError("audit injected terminal trace failure")
            super().save_revalidation_record(rid, record)
    port = FailTerminalTrace()
    manager, cp = setup(port)
    runtime = CountingRuntime()
    with pytest.raises(RuntimeError, match="terminal trace failure"):
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=make_gate(source, identity, authority, context))
    c = claim(manager, port, cp)
    assert runtime.calls == 1
    assert c.status == IdempotencyStatus.UNKNOWN and c.reconciliation_required is True
    stale = port.load_run_state("RS1"); stale.status = RunStatus.INTERRUPTED; port.save_run_state(stale)
    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=make_gate(source, identity, authority, context))
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert runtime.calls == 1


def test_external_convergence_no_second_revision_family_symbols():
    forbidden = {"RevisionLeasePort", "RuntimeResumeFence", "RevisionSnapshot", "ResumeExecutionToken", "RevisionFenceSource", "ToolBoundaryFence"}
    root = Path("harness")
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py"))
    assert not (forbidden & {symbol for symbol in forbidden if symbol in text})
