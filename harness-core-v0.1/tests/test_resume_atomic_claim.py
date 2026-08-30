from __future__ import annotations

import json
from threading import Barrier, Event, Lock, Thread

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
from harness.ports.versioning import RevisionGuardActiveError


def _records():
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


def _run(*, run_id="R1", task_id="MT-1", run_state_ref="RS1") -> HarnessRun:
    return HarnessRun(
        run_id=run_id,
        tarefa_trabalho_id=task_id,
        agent_id="A1",
        correlation_id=f"C-{run_id}-{run_state_ref}",
        workspace_ref="WS1",
        run_state_ref=run_state_ref,
        authority_context_ref="AC-OLD",
    )


def _resolved(source: InMemorySourceAdapter, *, run_id="R1"):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve(run_id, identity)
    context = ContextBuilder(source).build(run_id, authority.context, "TASK")
    return identity, authority, context


def _gate(source, identity, authority, context):
    return ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )


def _interrupted_state(*, run_state_id="RS1", run_id="R1", task_id="MT-1") -> RunState:
    return RunState(
        run_state_id=run_state_id,
        run_id=run_id,
        tarefa_trabalho_id=task_id,
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
        completed_steps=["step-1"],
        pending_steps=["step-2"],
    )


def _checkpoint(manager: StateManager, state: RunState):
    manager.persist(state)
    return manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue",
    )


class _BarrierStateAdapter(InMemoryStateAdapter):
    """Force selected initial loads to observe persisted INTERRUPTED state before proceeding."""

    def __init__(self, parties: int, *, target_ids=None):
        super().__init__()
        self._resume_load_barrier = Barrier(parties)
        self._barrier_lock = Lock()
        self._barrier_remaining = parties
        self._target_ids = set(target_ids or {"RS1"})

    def load_run_state(self, run_state_id: str) -> RunState:
        state = super().load_run_state(run_state_id)
        should_wait = False
        with self._barrier_lock:
            if run_state_id in self._target_ids and self._barrier_remaining > 0:
                self._barrier_remaining -= 1
                should_wait = True
        if should_wait:
            self._resume_load_barrier.wait(timeout=5)
        return state


class _CountingRuntime:
    def __init__(self):
        self.calls = 0
        self._lock = Lock()

    def execute(self, run, payload):
        raise NotImplementedError

    def resume(self, run, state):
        with self._lock:
            self.calls += 1
        state.status = RunStatus.COMPLETED
        return state


def _checkpointed_manager(parties: int = 2):
    state_port = _BarrierStateAdapter(parties)
    manager = StateManager(state_port)
    checkpoint = _checkpoint(manager, _interrupted_state())
    return manager, checkpoint


def _plain_fixture():
    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    checkpoint = _checkpoint(manager, _interrupted_state())
    return state_port, manager, checkpoint


def _claim_record(manager: StateManager, state_port: InMemoryStateAdapter, run: HarnessRun, checkpoint_id: str):
    checkpoint = state_port.load_checkpoint(checkpoint_id)
    state = state_port.load_run_state(checkpoint.run_state_ref)
    binding = RunStateBindingGuard.ensure_bound(run, state, checkpoint)
    key = manager._effect_key(
        binding.run_id,
        manager._RESUME_OPERATION,
        manager._resume_business_key(binding),
    )
    return manager.get_side_effect(key)


def test_red_team_two_threads_same_checkpoint_cross_runtime_exactly_once():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)
    manager, checkpoint = _checkpointed_manager(parties=2)
    runtime = _CountingRuntime()
    errors: list[BaseException] = []
    errors_lock = Lock()

    def contender():
        try:
            manager.resume(
                _run(),
                runtime,
                checkpoint.checkpoint_id,
                freshness_gate=_gate(source, identity, authority, context),
            )
        except BaseException as exc:
            with errors_lock:
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


def test_n_concurrent_callers_same_checkpoint_have_exactly_one_winner():
    contenders = 8
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)
    manager, checkpoint = _checkpointed_manager(parties=contenders)
    runtime = _CountingRuntime()
    errors: list[BaseException] = []
    errors_lock = Lock()

    def contender():
        try:
            manager.resume(
                _run(),
                runtime,
                checkpoint.checkpoint_id,
                freshness_gate=_gate(source, identity, authority, context),
            )
        except BaseException as exc:
            with errors_lock:
                errors.append(exc)

    threads = [Thread(target=contender) for _ in range(contenders)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    assert runtime.calls == 1
    assert len(errors) == contenders - 1
    assert all(isinstance(exc, HarnessResolutionError) for exc in errors)
    assert all(exc.code == HarnessErrorCode.RETRY_BLOCKED for exc in errors)


def test_second_caller_is_deterministically_blocked_while_winner_is_inside_runtime():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)
    _, manager, checkpoint = _plain_fixture()
    entered = Event()
    release = Event()
    winner_errors: list[BaseException] = []

    class BlockingRuntime(_CountingRuntime):
        def resume(self, run, state):
            with self._lock:
                self.calls += 1
            entered.set()
            assert release.wait(timeout=5)
            state.status = RunStatus.COMPLETED
            return state

    runtime = BlockingRuntime()

    def winner():
        try:
            manager.resume(
                _run(),
                runtime,
                checkpoint.checkpoint_id,
                freshness_gate=_gate(source, identity, authority, context),
            )
        except BaseException as exc:
            winner_errors.append(exc)

    thread = Thread(target=winner)
    thread.start()
    assert entered.wait(timeout=5)

    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(
            _run(),
            runtime,
            checkpoint.checkpoint_id,
            freshness_gate=_gate(source, identity, authority, context),
        )
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert runtime.calls == 1

    release.set()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert winner_errors == []
    assert runtime.calls == 1


def test_different_checkpoints_do_not_share_resume_claim():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)
    state_port = _BarrierStateAdapter(2, target_ids={"RS-A", "RS-B"})
    manager = StateManager(state_port)
    checkpoint_a = _checkpoint(manager, _interrupted_state(run_state_id="RS-A"))
    checkpoint_b = _checkpoint(manager, _interrupted_state(run_state_id="RS-B"))
    runtime = _CountingRuntime()
    errors: list[BaseException] = []
    errors_lock = Lock()

    def resume_one(run_state_ref, checkpoint_id):
        try:
            manager.resume(
                _run(run_state_ref=run_state_ref),
                runtime,
                checkpoint_id,
                freshness_gate=_gate(source, identity, authority, context),
            )
        except BaseException as exc:
            with errors_lock:
                errors.append(exc)

    threads = [
        Thread(target=resume_one, args=("RS-A", checkpoint_a.checkpoint_id)),
        Thread(target=resume_one, args=("RS-B", checkpoint_b.checkpoint_id)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    assert errors == []
    assert runtime.calls == 2


def test_foreign_run_checkpoint_binding_still_blocks_before_claim_and_runtime():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)
    state_port, manager, checkpoint = _plain_fixture()
    runtime = _CountingRuntime()

    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(
            _run(run_id="R2"),
            runtime,
            checkpoint.checkpoint_id,
            freshness_gate=_gate(source, identity, authority, context),
        )
    assert exc.value.code == HarnessErrorCode.CHECKPOINT_INVALID
    assert runtime.calls == 0
    assert state_port._idempotency_records == {}


def test_completed_claim_blocks_replay_even_after_manager_restart_and_stale_status_rewrite():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)
    state_port, manager, checkpoint = _plain_fixture()
    runtime = _CountingRuntime()

    manager.resume(
        _run(),
        runtime,
        checkpoint.checkpoint_id,
        freshness_gate=_gate(source, identity, authority, context),
    )
    assert runtime.calls == 1

    persisted = state_port.load_run_state("RS1")
    persisted.status = RunStatus.INTERRUPTED
    state_port.save_run_state(persisted)
    restarted_manager = StateManager(state_port)

    with pytest.raises(HarnessResolutionError) as exc:
        restarted_manager.resume(
            _run(),
            runtime,
            checkpoint.checkpoint_id,
            freshness_gate=_gate(source, identity, authority, context),
        )
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert runtime.calls == 1

    claim = _claim_record(restarted_manager, state_port, _run(), checkpoint.checkpoint_id)
    assert claim.status == IdempotencyStatus.COMPLETED
    assert claim.reconciliation_required is False


def test_runtime_exception_after_boundary_marks_unknown_and_forbids_blind_retry():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)
    state_port, manager, checkpoint = _plain_fixture()

    class FailingRuntime(_CountingRuntime):
        def resume(self, run, state):
            with self._lock:
                self.calls += 1
            raise RuntimeError("runtime outcome uncertain")

    runtime = FailingRuntime()
    with pytest.raises(RuntimeError, match="runtime outcome uncertain"):
        manager.resume(
            _run(),
            runtime,
            checkpoint.checkpoint_id,
            freshness_gate=_gate(source, identity, authority, context),
        )
    assert runtime.calls == 1

    claim = _claim_record(manager, state_port, _run(), checkpoint.checkpoint_id)
    assert claim.status == IdempotencyStatus.UNKNOWN
    assert claim.reconciliation_required is True

    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(
            _run(),
            runtime,
            checkpoint.checkpoint_id,
            freshness_gate=_gate(source, identity, authority, context),
        )
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED
    assert runtime.calls == 1


def test_preboundary_revision_guard_rejection_marks_failed_and_one_explicit_reprocess_can_reclaim():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)

    class FlipOnceState(InMemoryStateAdapter):
        def __init__(self):
            super().__init__()
            self.attempted = False

        def save_revalidation_record(self, revalidation_id, record):
            super().save_revalidation_record(revalidation_id, record)
            if (
                not self.attempted
                and record.get("status") == "RELEASED"
                and record.get("outcome") == "REVALIDATED_AND_GUARDED"
            ):
                self.attempted = True
                source.records["AUT-T"]["revision_ref"] = "T-REV-2"

    state_port = FlipOnceState()
    manager = StateManager(state_port)
    checkpoint = _checkpoint(manager, _interrupted_state())
    runtime = _CountingRuntime()

    with pytest.raises(RevisionGuardActiveError):
        manager.resume(
            _run(),
            runtime,
            checkpoint.checkpoint_id,
            freshness_gate=_gate(source, identity, authority, context),
        )
    assert state_port.attempted is True
    assert source.read("AUT-T")["revision_ref"] == "T-REV-1"
    assert runtime.calls == 0

    failed_claim = _claim_record(manager, state_port, _run(), checkpoint.checkpoint_id)
    assert failed_claim.status == IdempotencyStatus.FAILED
    assert failed_claim.reconciliation_required is False
    assert failed_claim.attempt == 1

    manager.resume(
        _run(),
        runtime,
        checkpoint.checkpoint_id,
        freshness_gate=_gate(source, identity, authority, context),
    )
    assert runtime.calls == 1

    completed_claim = _claim_record(manager, state_port, _run(), checkpoint.checkpoint_id)
    assert completed_claim.status == IdempotencyStatus.COMPLETED
    assert completed_claim.attempt == 2


def test_unresolvable_stale_source_never_reaches_runtime_and_claim_remains_safely_retriable():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)
    state_port, manager, checkpoint = _plain_fixture()
    runtime = _CountingRuntime()
    del source.records["AUT-T"]

    with pytest.raises(HarnessResolutionError):
        manager.resume(
            _run(),
            runtime,
            checkpoint.checkpoint_id,
            freshness_gate=_gate(source, identity, authority, context),
        )
    assert runtime.calls == 0

    claim = _claim_record(manager, state_port, _run(), checkpoint.checkpoint_id)
    assert claim.status == IdempotencyStatus.FAILED
    assert claim.reconciliation_required is False


def test_resume_claim_identity_is_exact_run_task_state_checkpoint_tuple():
    source = InMemorySourceAdapter(_records())
    identity, authority, context = _resolved(source)
    state_port, manager, checkpoint = _plain_fixture()
    runtime = _CountingRuntime()

    manager.resume(
        _run(),
        runtime,
        checkpoint.checkpoint_id,
        freshness_gate=_gate(source, identity, authority, context),
    )

    claim = _claim_record(manager, state_port, _run(), checkpoint.checkpoint_id)
    assert claim.run_id == "R1"
    assert claim.operation == "RuntimePort.resume"
    assert json.loads(claim.business_key) == ["MT-1", "RS1", checkpoint.checkpoint_id]
    assert claim.key == manager._effect_key("R1", "RuntimePort.resume", claim.business_key)
