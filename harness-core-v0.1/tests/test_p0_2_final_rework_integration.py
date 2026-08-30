from __future__ import annotations

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
from harness.ports.versioning import RevisionConflictError


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
            "allowed_scopes": ["ops:resume"],
        },
        "AUT-X": {
            "revision_ref": "X-REV-1",
            "loaded_excerpt_refs": ["CTX-X1"],
            "allowed_scopes": ["ops:resume"],
        },
        "AUT-N": {
            "revision_ref": "N-REV-1",
            "loaded_excerpt_refs": ["CTX-N1"],
            "allowed_scopes": ["ops:resume"],
        },
        "CTX-T1": {"context_ref": "CTX-T1", "estimated_tokens": 10, "required": True},
        "CTX-X1": {"context_ref": "CTX-X1", "estimated_tokens": 10, "required": True},
        "CTX-N1": {"context_ref": "CTX-N1", "estimated_tokens": 10, "required": True},
        "TASK": {
            "tarefa_trabalho_id": "MT-1",
            "current_order": "continue",
            "task_state_ref": "TASK-STATE-1",
            "workspace_ref": "WS1",
        },
    }


def make_run() -> HarnessRun:
    return HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        agent_id="A1",
        correlation_id="C-R1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref="AC-OLD",
    )


def resolve(source):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
    return identity, authority, context


def gate(source, identity, authority, context):
    return ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )


def interrupted_state():
    return RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
        completed_steps=["step-1"],
        pending_steps=["step-2"],
    )


def checkpoint(manager):
    state = interrupted_state()
    manager.persist(state)
    return manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")


def claim_record(manager, state_port, checkpoint_id):
    cp = state_port.load_checkpoint(checkpoint_id)
    state = state_port.load_run_state(cp.run_state_ref)
    binding = RunStateBindingGuard.ensure_bound(make_run(), state, cp)
    key = manager._effect_key(
        binding.run_id,
        manager._RESUME_OPERATION,
        manager._resume_business_key(binding),
    )
    return manager.get_side_effect(key)


def runtime_records(state_port):
    return [
        record
        for record in state_port.list_revalidation_records("R1")
        if record["boundary"] == "RuntimePort.resume"
    ]


def stale_interrupt(state_port):
    state = state_port.load_run_state("RS1")
    state.status = RunStatus.INTERRUPTED
    state_port.save_run_state(state)


class CountingRuntime:
    def __init__(self, source=None):
        self.calls = 0
        self.source = source
        self.guard_active_during_resume = False
        self._lock = Lock()

    def execute(self, run, payload):
        raise NotImplementedError

    def resume(self, run, state):
        with self._lock:
            self.calls += 1
        if self.source is not None:
            self.guard_active_during_resume = bool(self.source._active_guards)
        state.status = RunStatus.COMPLETED
        return state


class BarrierStateAdapter(InMemoryStateAdapter):
    def __init__(self, parties):
        super().__init__()
        self.barrier = Barrier(parties)
        self.remaining = parties
        self.barrier_lock = Lock()
        self.barrier_enabled = True

    def load_run_state(self, run_state_id):
        state = super().load_run_state(run_state_id)
        wait = False
        with self.barrier_lock:
            if self.barrier_enabled and run_state_id == "RS1" and self.remaining > 0:
                self.remaining -= 1
                wait = True
        if wait:
            self.barrier.wait(timeout=5)
        return state


def test_integrated_concurrent_loser_has_no_trace_and_only_winner_completes_runtime_boundary():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)
    state_port = BarrierStateAdapter(2)
    manager = StateManager(state_port)
    cp = checkpoint(manager)
    runtime = CountingRuntime()
    errors = []
    error_lock = Lock()

    def contender():
        try:
            manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))
        except BaseException as exc:
            with error_lock:
                errors.append(exc)

    threads = [Thread(target=contender) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    assert runtime.calls == 1
    assert len(errors) == 1
    assert isinstance(errors[0], HarnessResolutionError)
    assert errors[0].code == HarnessErrorCode.RETRY_BLOCKED
    traces = runtime_records(state_port)
    assert len(traces) == 1
    assert traces[0]["outcome"] == "COMPLETED"
    assert [event.get("outcome") for event in traces[0]["events"]] == [
        None,
        "REVALIDATED_AND_GUARDED",
        "COMPLETED",
    ]


def test_success_trace_is_terminal_only_after_canonical_state_and_preserves_attribution():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)
    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    cp = checkpoint(manager)
    runtime = CountingRuntime(source)

    resumed = manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))

    assert resumed.status == RunStatus.COMPLETED
    assert state_port.load_run_state("RS1").status == RunStatus.COMPLETED
    assert runtime.guard_active_during_resume is True
    assert source._active_guards == {}
    trace = runtime_records(state_port)[0]
    assert trace["status"] == "RELEASED"
    assert trace["outcome"] == "COMPLETED"
    assert [event.get("outcome") for event in trace["events"]] == [None, "REVALIDATED_AND_GUARDED", "COMPLETED"]
    assert trace["run_id"] == "R1"
    assert trace["agent_id"] == "A1"
    assert trace["tarefa_trabalho_id"] == "MT-1"
    assert trace["correlation_id"] == "C-R1"
    assert trace["authority_context_ref"]
    assert trace["metadata"]["versioned_read_set"]
    assert trace["metadata"]["revision_guard"]
    assert trace["metadata"]["revision_guard_final"]
    claim = claim_record(manager, state_port, cp.checkpoint_id)
    assert claim.status == IdempotencyStatus.COMPLETED


def test_firewall_failure_never_receives_completed_terminal_trace():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)
    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    cp = checkpoint(manager)

    class ForeignStateRuntime(CountingRuntime):
        def resume(self, run, state):
            self.calls += 1
            state.status = RunStatus.COMPLETED
            return state.model_copy(update={"run_state_id": "RS-FOREIGN"})

    runtime = ForeignStateRuntime()
    with pytest.raises(HarnessResolutionError):
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))

    assert runtime.calls == 1
    trace = runtime_records(state_port)[0]
    assert trace["outcome"] == "RUNTIME_RESUME_ERROR"
    assert all(event.get("outcome") != "COMPLETED" for event in trace["events"])
    claim = claim_record(manager, state_port, cp.checkpoint_id)
    assert claim.status == IdempotencyStatus.UNKNOWN
    assert claim.reconciliation_required is True


def test_save_run_state_failure_after_runtime_never_records_completed_and_blocks_replay():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)

    class FailCompletedStateSaveOnce(InMemoryStateAdapter):
        def __init__(self):
            super().__init__()
            self.failed = False

        def save_run_state(self, state):
            if state.status == RunStatus.COMPLETED and not self.failed:
                self.failed = True
                raise RuntimeError("canonical completed state persist failed")
            super().save_run_state(state)

    state_port = FailCompletedStateSaveOnce()
    manager = StateManager(state_port)
    cp = checkpoint(manager)
    runtime = CountingRuntime()

    with pytest.raises(RuntimeError, match="canonical completed state persist failed"):
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))

    assert runtime.calls == 1
    trace = runtime_records(state_port)[0]
    assert trace["outcome"] == "REVALIDATED_AND_GUARDED"
    assert all(event.get("outcome") != "COMPLETED" for event in trace["events"])
    claim = claim_record(manager, state_port, cp.checkpoint_id)
    assert claim.status == IdempotencyStatus.UNKNOWN
    assert claim.reconciliation_required is True
    stale_interrupt(state_port)
    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert runtime.calls == 1


def test_terminal_trace_persist_failure_after_runtime_marks_claim_unknown_and_blocks_replay():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)

    class FailTerminalTraceOnce(InMemoryStateAdapter):
        def __init__(self):
            super().__init__()
            self.failed = False

        def save_revalidation_record(self, revalidation_id, record):
            if record.get("boundary") == "RuntimePort.resume" and record.get("outcome") == "COMPLETED" and not self.failed:
                self.failed = True
                raise RuntimeError("terminal trace persist failed")
            super().save_revalidation_record(revalidation_id, record)

    state_port = FailTerminalTraceOnce()
    manager = StateManager(state_port)
    cp = checkpoint(manager)
    runtime = CountingRuntime()

    with pytest.raises(RuntimeError, match="terminal trace persist failed"):
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))

    assert runtime.calls == 1
    assert state_port.load_run_state("RS1").status == RunStatus.COMPLETED
    trace = runtime_records(state_port)[0]
    assert trace["outcome"] == "REVALIDATED_AND_GUARDED"
    claim = claim_record(manager, state_port, cp.checkpoint_id)
    assert claim.status == IdempotencyStatus.UNKNOWN
    assert claim.reconciliation_required is True
    stale_interrupt(state_port)
    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert runtime.calls == 1


def test_claim_completion_persist_failure_after_terminal_trace_blocks_replay():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)

    class FailClaimCompleteOnce(InMemoryStateAdapter):
        def __init__(self):
            super().__init__()
            self.failed = False

        def update_idempotency_record(self, key, record):
            if (
                record.get("operation") == "RuntimePort.resume"
                and record.get("status") == "COMPLETED"
                and not self.failed
            ):
                self.failed = True
                raise RuntimeError("claim completed persist failed")
            super().update_idempotency_record(key, record)

    state_port = FailClaimCompleteOnce()
    manager = StateManager(state_port)
    cp = checkpoint(manager)
    runtime = CountingRuntime()

    with pytest.raises(RuntimeError, match="claim completed persist failed"):
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))

    assert runtime.calls == 1
    trace = runtime_records(state_port)[0]
    assert trace["outcome"] == "COMPLETED"
    assert [event.get("outcome") for event in trace["events"]].count("COMPLETED") == 1
    claim = claim_record(manager, state_port, cp.checkpoint_id)
    assert claim.status == IdempotencyStatus.UNKNOWN
    assert claim.reconciliation_required is True
    stale_interrupt(state_port)
    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert runtime.calls == 1


def test_failed_claim_cas_allows_at_most_one_concurrent_retry_winner():
    source = InMemorySourceAdapter(records())
    identity, authority, context = resolve(source)
    state_port = BarrierStateAdapter(2)
    manager = StateManager(state_port)
    cp = checkpoint(manager)

    # Materialize a proven pre-runtime FAILED claim without consuming the race barrier.
    state_port.barrier_enabled = False
    cp_record = state_port.load_checkpoint(cp.checkpoint_id)
    state = state_port.load_run_state(cp_record.run_state_ref)
    binding = RunStateBindingGuard.ensure_bound(make_run(), state, cp_record)
    initial = manager._begin_resume_claim(binding)
    manager.fail_side_effect(initial.key, "pre-runtime failure", outcome_unknown=False)
    state_port.remaining = 2
    state_port.barrier_enabled = True

    runtime = CountingRuntime()
    errors = []
    error_lock = Lock()

    def contender():
        try:
            manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))
        except BaseException as exc:
            with error_lock:
                errors.append(exc)

    threads = [Thread(target=contender) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    assert runtime.calls == 1
    assert len(errors) == 1
    assert isinstance(errors[0], HarnessResolutionError)
    assert errors[0].code == HarnessErrorCode.RETRY_BLOCKED
    claim = claim_record(manager, state_port, cp.checkpoint_id)
    assert claim.status == IdempotencyStatus.COMPLETED
    assert claim.attempt == 2


def test_revision_conflict_at_guard_acquire_blocks_before_runtime_and_keeps_resume_claim_retriable():
    class FlipBeforeAcquireSource(InMemorySourceAdapter):
        def __init__(self, source_records):
            super().__init__(source_records)
            self.flipped = False

        def acquire_revision_guard(self, expected_versions, owner_ref):
            if not self.flipped:
                self.flipped = True
                self.records["AUT-T"]["revision_ref"] = "T-REV-2"
            return super().acquire_revision_guard(expected_versions, owner_ref)

    source = FlipBeforeAcquireSource(records())
    identity, authority, context = resolve(source)
    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    cp = checkpoint(manager)
    runtime = CountingRuntime()

    with pytest.raises(RevisionConflictError):
        manager.resume(make_run(), runtime, cp.checkpoint_id, freshness_gate=gate(source, identity, authority, context))

    assert source.flipped is True
    assert runtime.calls == 0
    claim = claim_record(manager, state_port, cp.checkpoint_id)
    assert claim.status == IdempotencyStatus.FAILED
    assert claim.reconciliation_required is False
    trace = runtime_records(state_port)[0]
    assert trace["outcome"] == "REVISION_GUARD_REJECTED"
    assert all(event.get("outcome") != "COMPLETED" for event in trace["events"])
