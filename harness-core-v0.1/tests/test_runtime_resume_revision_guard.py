from __future__ import annotations

from threading import Thread

import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import ResumeFreshnessGate, read_versioned_for_sensitive_use
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager
from harness.ports import VersionedReadSet
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


def make_run():
    return HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref="AC-OLD",
    )


def prepare_inputs(source):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
    gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )
    return identity, authority, context, gate


def manager_checkpoint(state_port=None):
    port = state_port or InMemoryStateAdapter()
    manager = StateManager(port)
    state = RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state,
        validated_step="step-1",
        resume_instruction="continue",
    )
    return port, manager, checkpoint


class CountingRuntime:
    def __init__(self):
        self.resume_calls = 0

    def execute(self, run, payload):
        raise NotImplementedError

    def resume(self, run, state):
        self.resume_calls += 1
        state.status = RunStatus.COMPLETED
        return state


def test_resume_preparation_read_set_covers_identity_authority_task_and_materialized_context():
    source = InMemorySourceAdapter(records())
    _, _, _, gate = prepare_inputs(source)

    preparation = gate.prepare(make_run())
    refs = set(preparation.versioned_read_set.expected_versions)

    assert {
        "ID-A1",
        "AUT-T",
        "AUT-X",
        "AUT-N",
        "TASK",
        "CTX-T1",
        "CTX-X1",
        "CTX-N1",
    } <= refs
    materialized_sources = {
        ref
        for chain_sources in preparation.context.materialized_source_refs.values()
        for ref in chain_sources
    }
    assert {"CTX-T1", "CTX-X1", "CTX-N1"} <= materialized_sources


class MutateOnAcquireSource(InMemorySourceAdapter):
    """Inject a writer after prepare but before the guard's atomic compare."""

    def __init__(self, initial):
        super().__init__(initial)
        self.mutate_on_acquire: str | None = None

    def acquire_revision_guard(self, expected_versions, owner_ref):
        if self.mutate_on_acquire is not None:
            ref = self.mutate_on_acquire
            self.mutate_on_acquire = None
            self.records[ref]["race_marker"] = "changed-after-prepare"
        return super().acquire_revision_guard(expected_versions, owner_ref)


@pytest.mark.parametrize(
    "source_ref",
    ["ID-A1", "AUT-X", "TASK", "CTX-X1"],
    ids=["stale-identity", "stale-technical-chain", "stale-task", "stale-context"],
)
def test_revision_change_after_prepare_is_rejected_by_same_strong_guard(source_ref):
    source = MutateOnAcquireSource(records())
    _, _, _, gate = prepare_inputs(source)
    runtime = CountingRuntime()
    _, manager, checkpoint = manager_checkpoint()
    source.mutate_on_acquire = source_ref

    with pytest.raises(RevisionConflictError) as exc:
        manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=gate)

    assert exc.value.source_ref == source_ref
    assert runtime.resume_calls == 0


class MutatingReleasedAuditStatePort(InMemoryStateAdapter):
    """Attempts a mutation after guard acquisition and immediately before runtime."""

    def __init__(self, source, source_ref):
        super().__init__()
        self.source = source
        self.source_ref = source_ref
        self.writer_errors = []
        self.attempted = False

    def save_revalidation_record(self, revalidation_id, record):
        super().save_revalidation_record(revalidation_id, record)
        if record.get("status") == "RELEASED" and not self.attempted:
            self.attempted = True
            try:
                self.source.records[self.source_ref]["race_marker"] = "immediately-before-runtime"
            except Exception as exc:
                self.writer_errors.append(exc)


def test_revision_change_immediately_before_runtime_resume_is_excluded_by_active_guard():
    source = InMemorySourceAdapter(records())
    _, _, _, gate = prepare_inputs(source)
    port = MutatingReleasedAuditStatePort(source, "AUT-X")
    _, manager, checkpoint = manager_checkpoint(port)
    runtime = CountingRuntime()

    resumed = manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=gate)

    assert resumed.status == RunStatus.COMPLETED
    assert runtime.resume_calls == 1
    assert len(port.writer_errors) == 1
    assert isinstance(port.writer_errors[0], RevisionGuardActiveError)
    assert "race_marker" not in source.read("AUT-X")


class ConcurrentWriterRuntime(CountingRuntime):
    def __init__(self, source, source_ref):
        super().__init__()
        self.source = source
        self.source_ref = source_ref
        self.writer_errors = []

    def resume(self, run, state):
        self.resume_calls += 1

        def writer():
            try:
                self.source.records[self.source_ref]["during_resume"] = True
            except Exception as exc:
                self.writer_errors.append(exc)

        thread = Thread(target=writer)
        thread.start()
        thread.join(timeout=2)
        state.status = RunStatus.COMPLETED
        return state


def test_concurrent_writer_is_excluded_for_entire_synchronous_runtime_resume_boundary():
    source = InMemorySourceAdapter(records())
    _, _, _, gate = prepare_inputs(source)
    runtime = ConcurrentWriterRuntime(source, "TASK")
    _, manager, checkpoint = manager_checkpoint()

    manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=gate)

    assert runtime.resume_calls == 1
    assert len(runtime.writer_errors) == 1
    assert isinstance(runtime.writer_errors[0], RevisionGuardActiveError)
    assert "during_resume" not in source.read("TASK")

    # The guard lifetime ends with RuntimePort.resume; a later writer can proceed.
    source.records["TASK"]["after_resume"] = True
    assert source.read("TASK")["after_resume"] is True


def test_released_guard_generation_cannot_release_or_replay_over_current_resume_guard():
    source = InMemorySourceAdapter(records())
    old_reads = VersionedReadSet()
    read_versioned_for_sensitive_use(source, "AUT-X", old_reads)
    old_guard = source.acquire_revision_guard(old_reads, "RESUME:R1:CP-1")
    source.release_revision_guard(old_guard)

    current_reads = VersionedReadSet()
    read_versioned_for_sensitive_use(source, "AUT-X", current_reads)
    current_guard = source.acquire_revision_guard(current_reads, "RESUME:R1:CP-1")
    assert current_guard.generation > old_guard.generation

    # Releasing/replaying the stale generation cannot drop the active hold.
    source.release_revision_guard(old_guard)
    with pytest.raises(RevisionGuardActiveError):
        source.records["AUT-X"]["replay"] = True

    source.release_revision_guard(current_guard)
    source.records["AUT-X"]["replay"] = True
    assert source.read("AUT-X")["replay"] is True


def test_repeated_resume_of_completed_checkpoint_is_rejected_before_second_runtime_call():
    source = InMemorySourceAdapter(records())
    identity, authority, context, gate = prepare_inputs(source)
    port, manager, checkpoint = manager_checkpoint()
    runtime = CountingRuntime()

    first = manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=gate)
    assert first.status == RunStatus.COMPLETED
    assert runtime.resume_calls == 1

    second_gate = ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )
    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=second_gate)

    assert exc.value.code == HarnessErrorCode.CHECKPOINT_INVALID
    assert runtime.resume_calls == 1


def test_source_without_strong_revision_capability_fails_closed_before_runtime():
    strong_source = InMemorySourceAdapter(records())
    identity, authority, context, _ = prepare_inputs(strong_source)

    class WeakSource:
        def read(self, source_ref):
            return strong_source.read(source_ref)

    weak = WeakSource()
    gate = ResumeFreshnessGate(
        source=weak,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )
    runtime = CountingRuntime()
    _, manager, checkpoint = manager_checkpoint()

    with pytest.raises(Exception, match="strong revision guard capability"):
        manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=gate)
    assert runtime.resume_calls == 0
