import pytest

from harness.adapters.runtimes.fake import FakeRuntimeAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.errors import HarnessResolutionError
from harness.core.state import StateManager
from harness.core.state.manager import IdempotencyStatus


def make_run() -> HarnessRun:
    return HarnessRun(run_id="R1", tarefa_trabalho_id="MT-1", agent_id="A1", correlation_id="C1", workspace_ref="WS1", run_state_ref="RS1", authority_context_ref="AC1")


def make_state() -> RunState:
    return RunState(run_state_id="RS1", run_id="R1", tarefa_trabalho_id="MT-1", status=RunStatus.INTERRUPTED, current_step="step-2", completed_steps=["step-1"], pending_steps=["step-2"], artifact_refs=["ART-1"])


class NoOpFreshnessGate:
    def prepare(self, run):
        raise AssertionError("duck-typed freshness gate must never be invoked")


def test_state_port_persists_by_value_not_shared_reference():
    port = InMemoryStateAdapter(); state = make_state(); port.save_run_state(state)
    state.completed_steps.append("mutated-after-save")
    assert port.load_run_state("RS1").completed_steps == ["step-1"]


def test_resume_rejects_duck_typed_noop_freshness_gate_before_runtime_and_persists_block():
    port = InMemoryStateAdapter(); manager = StateManager(port); state = make_state(); manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue from step-2", evidence_refs=["EV-1"])

    class CountingRuntime(FakeRuntimeAdapter):
        def __init__(self):
            super().__init__()
            self.resume_calls = 0

        def resume(self, run, current_state):
            self.resume_calls += 1
            return super().resume(run, current_state)

    runtime = CountingRuntime()
    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=NoOpFreshnessGate())
    assert exc.value.code == HarnessErrorCode.AUTHORITY_UNRESOLVED
    assert runtime.resume_calls == 0

    persisted = port.load_run_state("RS1")
    audit_refs = [ref for ref in persisted.decision_refs if ref.startswith("RV-")]
    assert len(audit_refs) == 1
    audit = port.load_revalidation_record(audit_refs[0])
    assert audit["status"] == "BLOCKED"
    assert audit["outcome"] == "FRESHNESS_GATE_INVALID"


def test_resume_without_freshness_gate_fails_closed_before_runtime_and_persists_block():
    port = InMemoryStateAdapter(); manager = StateManager(port); state = make_state(); manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")
    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run(), FakeRuntimeAdapter(), checkpoint.checkpoint_id)
    assert exc.value.code == HarnessErrorCode.AUTHORITY_UNRESOLVED
    persisted = port.load_run_state("RS1")
    audit_refs = [ref for ref in persisted.decision_refs if ref.startswith("RV-")]
    assert len(audit_refs) == 1
    assert port.load_revalidation_record(audit_refs[0])["status"] == "BLOCKED"


def test_resume_rejects_checkpoint_from_another_run_before_freshness():
    port = InMemoryStateAdapter(); manager = StateManager(port); state = make_state(); manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")
    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run().model_copy(update={"run_id":"R2"}), FakeRuntimeAdapter(), checkpoint.checkpoint_id, freshness_gate=NoOpFreshnessGate())
    assert exc.value.code == HarnessErrorCode.CHECKPOINT_INVALID
    assert port._revalidation_records == {}


def test_idempotency_ledger_completes_and_blocks_duplicate():
    manager = StateManager(InMemoryStateAdapter())
    record = manager.begin_side_effect("R1", "CREATE_PAYMENT", "ORDER-9")
    assert record.status == IdempotencyStatus.PENDING
    done = manager.complete_side_effect(record.key, result={"ok": True}, evidence_refs=["EV-1"])
    assert done.status == IdempotencyStatus.COMPLETED
    assert done.evidence_refs == ["EV-1"]
    with pytest.raises(HarnessResolutionError) as exc:
        manager.begin_side_effect("R1", "CREATE_PAYMENT", "ORDER-9")
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED


def test_unknown_requires_reconciliation_before_retry():
    manager = StateManager(InMemoryStateAdapter())
    record = manager.begin_side_effect("R1", "SEND", "A")
    unknown = manager.fail_side_effect(record.key, "timeout", outcome_unknown=True)
    assert unknown.status == IdempotencyStatus.UNKNOWN and unknown.reconciliation_required
    with pytest.raises(HarnessResolutionError):
        manager.begin_side_effect("R1", "SEND", "A")
    reconciled = manager.reconcile_side_effect(record.key, completed=False)
    assert reconciled.status == IdempotencyStatus.FAILED
    retried = manager.begin_side_effect("R1", "SEND", "A", retry_failed=True)
    assert retried.status == IdempotencyStatus.PENDING and retried.attempt == 2


def test_distinct_business_keys_are_independent():
    manager = StateManager(InMemoryStateAdapter())
    assert manager.begin_side_effect("R1", "SEND", "A").key != manager.begin_side_effect("R1", "SEND", "B").key
