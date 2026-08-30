from datetime import datetime

import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.adapters.tools import FakeToolAdapter
from harness.contracts import HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate, ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager
from harness.core.state.manager import IdempotencyStatus
from harness.core.state.resume_policy import ResumeStatusRejected
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry


def records():
    return {
        "ID-A1": {
            "revision_ref": "ID-REV-1",
            "identity": {
                "agent_id": "A1", "name": "Agent One", "mission_ref": "MISSION-1",
                "scope_ref": "SCOPE-1", "organizational_path_ref": "ORG-1",
                "tactical_authority_ref": "AUT-T", "technical_authority_ref": "AUT-X",
                "normative_authority_ref": "AUT-N", "source_ref": "ID-A1",
            },
        },
        "AUT-T": {"revision_ref": "T-REV-1", "loaded_excerpt_refs": ["CTX-T1"], "allowed_scopes": ["ops:resume", "ops:write"]},
        "AUT-X": {"revision_ref": "X-REV-1", "loaded_excerpt_refs": ["CTX-X1"], "allowed_scopes": ["ops:resume", "ops:write"]},
        "AUT-N": {"revision_ref": "N-REV-1", "loaded_excerpt_refs": ["CTX-N1"]},
        "CTX-T1": {"context_ref": "CTX-T1", "estimated_tokens": 10, "required": True},
        "CTX-T2": {"context_ref": "CTX-T2", "estimated_tokens": 10, "required": True},
        "CTX-X1": {"context_ref": "CTX-X1", "estimated_tokens": 10, "required": True},
        "CTX-N1": {"context_ref": "CTX-N1", "estimated_tokens": 10, "required": True},
        "TASK": {"tarefa_trabalho_id": "MT-1", "current_order": "continue", "task_state_ref": "TASK-STATE-1", "workspace_ref": "WS1"},
    }


def resolve(source, run_id="R1"):
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve(run_id, identity)
    context = ContextBuilder(source).build(run_id, authority.context, "TASK")
    return identity, authority, context


def resume_gate(source, identity, authority, context):
    return ResumeFreshnessGate(
        source=source, identity_source_ref="ID-A1", task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context, previous_context=context,
    )


def make_run(run_id="R1", *, authority_ref=None, task_context_ref=None):
    return HarnessRun(
        run_id=run_id, tarefa_trabalho_id="MT-1", agent_id="A1", correlation_id=f"C-{run_id}",
        workspace_ref="WS1", run_state_ref=f"RS-{run_id}",
        authority_context_ref=authority_ref or f"AC-{run_id}-OLD", task_context_ref=task_context_ref,
    )


def checkpointed_state(manager, run_id="R1", *, evidence_refs=None):
    state = RunState(
        run_state_id=f"RS-{run_id}", run_id=run_id, tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED, current_step="resume-side-effect",
        completed_steps=["side-effect"], pending_steps=["resume-side-effect"],
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(
        state, validated_step="side-effect", resume_instruction="resume without replaying proved effects",
        evidence_refs=list(evidence_refs or []),
    )
    return state, checkpoint


def gateway(manager, source, *, tool_id="ops.write"):
    registry = ToolRegistry(); adapter = FakeToolAdapter({"ok": True, "evidence_refs": ["EV-SIDE-EFFECT"]})
    registry.register(ToolDescriptor(tool_id=tool_id, action_scope="ops:write", side_effect=True), adapter)
    return ToolGateway(registry, manager, freshness_gate=AuthorityFreshnessGate(source)), adapter


def tool_call(gw, authority, context, *, run_id="R1", tool_id="ops.write", payload=None, business_key):
    run = make_run(run_id, authority_ref=authority.authority_context_id, task_context_ref=context.task_context.task_context_id)
    return gw.execute(
        run_id=run_id, authority=authority, run=run, task_context=context.task_context,
        tool_id=tool_id, payload=dict(payload or {}), business_key=business_key,
    )


def assert_retry_blocked(call):
    with pytest.raises(HarnessResolutionError) as exc:
        call()
    assert exc.value.code == HarnessErrorCode.RETRY_BLOCKED


def test_completed_side_effect_checkpoint_resume_does_not_repeat_external_effect():
    source = InMemorySourceAdapter(records()); identity, authority, context = resolve(source)
    port = InMemoryStateAdapter(); manager = StateManager(port); gw, adapter = gateway(manager, source)
    first = tool_call(gw, authority.context, context, payload={"value": 1}, business_key="ORDER-1")
    assert len(adapter.calls) == 1
    _, checkpoint = checkpointed_state(manager, evidence_refs=list(first.evidence_refs))

    class ReplayRuntime:
        def resume(self, run, current_state):
            fresh = AuthorityResolver(source).resolve(run.run_id, identity)
            fresh_context = ContextBuilder(source).build(run.run_id, fresh.context, "TASK")
            assert_retry_blocked(lambda: tool_call(gw, fresh.context, fresh_context, run_id=run.run_id, payload={"value": 1}, business_key="ORDER-1"))
            current_state.status = RunStatus.COMPLETED
            return current_state

    manager.resume(make_run(), ReplayRuntime(), checkpoint.checkpoint_id, freshness_gate=resume_gate(source, identity, authority, context))
    assert len(adapter.calls) == 1
    record = manager.get_side_effect(first.idempotency_key)
    assert record.status == IdempotencyStatus.COMPLETED
    assert record.evidence_refs == ["EV-SIDE-EFFECT"]


def test_repeated_resume_of_same_checkpoint_blocks_second_runtime_and_never_duplicates_effect():
    source = InMemorySourceAdapter(records()); identity, authority, context = resolve(source)
    manager = StateManager(InMemoryStateAdapter()); gw, adapter = gateway(manager, source)
    first = tool_call(gw, authority.context, context, business_key="ORDER-REPEAT")
    _, checkpoint = checkpointed_state(manager, evidence_refs=list(first.evidence_refs))

    class ReplayRuntime:
        calls = 0
        def resume(self, run, current_state):
            self.calls += 1
            fresh = AuthorityResolver(source).resolve(run.run_id, identity)
            fresh_context = ContextBuilder(source).build(run.run_id, fresh.context, "TASK")
            assert_retry_blocked(lambda: tool_call(gw, fresh.context, fresh_context, run_id=run.run_id, business_key="ORDER-REPEAT"))
            current_state.status = RunStatus.COMPLETED
            return current_state

    runtime = ReplayRuntime(); run = make_run(); gate = resume_gate(source, identity, authority, context)
    manager.resume(run, runtime, checkpoint.checkpoint_id, freshness_gate=gate)
    with pytest.raises(ResumeStatusRejected):
        manager.resume(run, runtime, checkpoint.checkpoint_id, freshness_gate=gate)
    assert runtime.calls == 1
    assert len(adapter.calls) == 1


def test_existing_pending_blocks_gateway_before_external_effect():
    source = InMemorySourceAdapter(records()); _, authority, context = resolve(source)
    manager = StateManager(InMemoryStateAdapter()); gw, adapter = gateway(manager, source)
    pending = manager.begin_side_effect("R1", "ops.write", "ORDER-PENDING")
    assert pending.status == IdempotencyStatus.PENDING
    assert_retry_blocked(lambda: tool_call(gw, authority.context, context, business_key="ORDER-PENDING"))
    assert adapter.calls == []
    assert manager.get_side_effect(pending.key).status == IdempotencyStatus.PENDING


def test_unknown_never_blind_retries_and_keeps_reconciliation_required():
    source = InMemorySourceAdapter(records()); _, authority, context = resolve(source)
    manager = StateManager(InMemoryStateAdapter()); gw, adapter = gateway(manager, source)
    pending = manager.begin_side_effect("R1", "ops.write", "ORDER-UNKNOWN")
    manager.fail_side_effect(pending.key, "provider timeout", outcome_unknown=True)
    assert_retry_blocked(lambda: tool_call(gw, authority.context, context, business_key="ORDER-UNKNOWN"))
    record = manager.get_side_effect(pending.key)
    assert record.status == IdempotencyStatus.UNKNOWN
    assert record.reconciliation_required is True
    assert adapter.calls == []


def test_failed_retry_requires_explicit_opt_in_and_preserves_attempt_semantics():
    manager = StateManager(InMemoryStateAdapter())
    first = manager.begin_side_effect("R1", "ops.write", "ORDER-FAILED")
    failed = manager.fail_side_effect(first.key, "confirmed provider rejection", outcome_unknown=False)
    assert failed.status == IdempotencyStatus.FAILED
    assert_retry_blocked(lambda: manager.begin_side_effect("R1", "ops.write", "ORDER-FAILED"))
    retried = manager.begin_side_effect("R1", "ops.write", "ORDER-FAILED", retry_failed=True)
    assert retried.status == IdempotencyStatus.PENDING and retried.attempt == 2
    assert retried.error is None and retried.reconciliation_required is False


def test_revision_change_revalidates_resume_but_completed_effect_still_does_not_repeat():
    source = InMemorySourceAdapter(records()); identity, authority, context = resolve(source)
    port = InMemoryStateAdapter(); manager = StateManager(port); gw, adapter = gateway(manager, source)
    first = tool_call(gw, authority.context, context, business_key="ORDER-REVISION")
    _, checkpoint = checkpointed_state(manager, evidence_refs=list(first.evidence_refs))
    source.records["AUT-T"] = {"revision_ref": "T-REV-2", "loaded_excerpt_refs": ["CTX-T2"], "allowed_scopes": ["ops:resume", "ops:write"]}

    class ReplayAfterRevalidationRuntime:
        def resume(self, run, current_state):
            fresh = AuthorityResolver(source).resolve(run.run_id, identity)
            assert fresh.context.tactical_chain_trace.source_revision_refs == ["T-REV-2"]
            fresh_context = ContextBuilder(source).build(run.run_id, fresh.context, "TASK")
            assert_retry_blocked(lambda: tool_call(gw, fresh.context, fresh_context, run_id=run.run_id, business_key="ORDER-REVISION"))
            current_state.status = RunStatus.COMPLETED
            return current_state

    manager.resume(make_run(), ReplayAfterRevalidationRuntime(), checkpoint.checkpoint_id, freshness_gate=resume_gate(source, identity, authority, context))
    assert len(adapter.calls) == 1
    resume_records = [r for r in port.list_revalidation_records("R1") if r["boundary"] == "RuntimePort.resume"]
    assert len(resume_records) == 1 and resume_records[0]["status"] == "RELEASED"
    assert list(resume_records[0]["changed_chains"]) == ["TACTICAL"]


def test_cross_run_same_effect_identity_is_blocked_instead_of_reopened():
    source = InMemorySourceAdapter(records())
    _, authority_r1, context_r1 = resolve(source, "R1"); _, authority_r2, context_r2 = resolve(source, "R2")
    manager = StateManager(InMemoryStateAdapter()); gw, adapter = gateway(manager, source)
    first = tool_call(gw, authority_r1.context, context_r1, run_id="R1", payload={"run": 1}, business_key="SHARED-ORDER")
    assert first.idempotency_key == "ops.write:SHARED-ORDER"
    assert_retry_blocked(lambda: tool_call(gw, authority_r2.context, context_r2, run_id="R2", payload={"run": 2}, business_key="SHARED-ORDER"))
    assert len(adapter.calls) == 1


def test_same_business_key_cannot_bypass_checkpoint_run_binding_on_wrong_resume():
    source = InMemorySourceAdapter(records()); identity, authority, context = resolve(source)
    manager = StateManager(InMemoryStateAdapter()); gw, adapter = gateway(manager, source)
    tool_call(gw, authority.context, context, business_key="BOUND-ORDER"); _, checkpoint = checkpointed_state(manager)

    class MustNotRun:
        calls = 0
        def resume(self, run, current_state): self.calls += 1; return current_state

    runtime = MustNotRun()
    with pytest.raises(HarnessResolutionError) as exc:
        manager.resume(make_run("R2"), runtime, checkpoint.checkpoint_id, freshness_gate=resume_gate(source, identity, authority, context))
    assert exc.value.code == HarnessErrorCode.CHECKPOINT_INVALID
    assert runtime.calls == 0 and len(adapter.calls) == 1


def test_runtime_resume_failure_preserves_completed_effect_and_revalidation_history():
    source = InMemorySourceAdapter(records()); identity, authority, context = resolve(source)
    port = InMemoryStateAdapter(); manager = StateManager(port); gw, adapter = gateway(manager, source)
    first = tool_call(gw, authority.context, context, business_key="ORDER-RUNTIME-FAIL")
    _, checkpoint = checkpointed_state(manager, evidence_refs=list(first.evidence_refs))

    class FailingRuntime:
        def resume(self, run, current_state): raise RuntimeError("runtime crashed after revalidation")

    with pytest.raises(RuntimeError, match="runtime crashed after revalidation"):
        manager.resume(make_run(), FailingRuntime(), checkpoint.checkpoint_id, freshness_gate=resume_gate(source, identity, authority, context))
    ledger = manager.get_side_effect(first.idempotency_key)
    assert ledger.status == IdempotencyStatus.COMPLETED and ledger.evidence_refs == ["EV-SIDE-EFFECT"]
    assert len(adapter.calls) == 1
    assert port.load_checkpoint(checkpoint.checkpoint_id).evidence_refs == ["EV-SIDE-EFFECT"]
    audit = [r for r in port.list_revalidation_records("R1") if r["boundary"] == "RuntimePort.resume"][0]
    assert audit["status"] == "FAILED" and audit["outcome"] == "RUNTIME_RESUME_ERROR"
    assert [event["status"] for event in audit["events"]] == ["PENDING", "RELEASED", "FAILED"]
    assert audit["authority_snapshot"] and audit["task_context"]


def test_temporal_order_of_tool_and_resume_audit_records_remains_traceable():
    source = InMemorySourceAdapter(records()); identity, authority, context = resolve(source)
    port = InMemoryStateAdapter(); manager = StateManager(port); gw, _ = gateway(manager, source)
    tool_call(gw, authority.context, context, business_key="ORDER-TIME"); _, checkpoint = checkpointed_state(manager)

    class CompleteRuntime:
        def resume(self, run, current_state): current_state.status = RunStatus.COMPLETED; return current_state

    manager.resume(make_run(), CompleteRuntime(), checkpoint.checkpoint_id, freshness_gate=resume_gate(source, identity, authority, context))
    audit_records = port.list_revalidation_records("R1")
    assert [r["boundary"] for r in audit_records] == ["ToolPort.invoke", "RuntimePort.resume"]
    created = [datetime.fromisoformat(r["created_at"]) for r in audit_records]
    assert created == sorted(created)
    for record in audit_records:
        event_times = [datetime.fromisoformat(event["at"]) for event in record["events"]]
        assert event_times == sorted(event_times)
        assert datetime.fromisoformat(record["created_at"]) <= event_times[0]
        assert event_times[-1] <= datetime.fromisoformat(record["updated_at"])
