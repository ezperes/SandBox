from __future__ import annotations

from threading import Barrier, Lock, Thread

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager


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


def _run() -> HarnessRun:
    return HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref="AC-OLD",
    )


def _resolved(source: InMemorySourceAdapter):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
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


class _BarrierStateAdapter(InMemoryStateAdapter):
    """Force every contender to observe the same INTERRUPTED state before proceeding."""

    def __init__(self, parties: int):
        super().__init__()
        self._resume_load_barrier = Barrier(parties)

    def load_run_state(self, run_state_id: str) -> RunState:
        state = super().load_run_state(run_state_id)
        if run_state_id == "RS1":
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
    state = RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
        completed_steps=["step-1"],
        pending_steps=["step-2"],
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue",
    )
    return manager, checkpoint


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
