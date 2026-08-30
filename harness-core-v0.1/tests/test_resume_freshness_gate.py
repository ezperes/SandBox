import pytest

from harness.adapters.runtimes.fake import FakeRuntimeAdapter
from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import ChainType, HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager


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
        "AUT-T": {"revision_ref": "T-REV-1", "loaded_excerpt_refs": ["CTX-T1"], "allowed_scopes": ["ops:resume"]},
        "AUT-X": {"revision_ref": "X-REV-1", "loaded_excerpt_refs": ["CTX-X1"], "allowed_scopes": ["ops:resume"]},
        "AUT-N": {"revision_ref": "N-REV-1", "loaded_excerpt_refs": ["CTX-N1"]},
        "CTX-T1": {"context_ref": "CTX-T1", "estimated_tokens": 10, "required": True},
        "CTX-T2": {"context_ref": "CTX-T2", "estimated_tokens": 12, "required": True},
        "CTX-X1": {"context_ref": "CTX-X1", "estimated_tokens": 10, "required": True},
        "CTX-X2": {"context_ref": "CTX-X2", "estimated_tokens": 12, "required": True},
        "CTX-N1": {"context_ref": "CTX-N1", "estimated_tokens": 10, "required": True},
        "TASK": {
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


def make_freshness(source, identity, authority, context):
    return ResumeFreshnessGate(
        source=source,
        identity_source_ref="ID-A1",
        task_source_ref="TASK",
        previous_identity_revision_ref=identity.source_revision_ref,
        previous_authority=authority.context,
        previous_context=context,
    )


def test_t10_resume_re_resolves_changed_chain_and_rebuilds_only_affected_context_before_runtime():
    source = InMemorySourceAdapter(records())
    identity = IdentityResolver(source).resolve("ID-A1")
    first_authority = AuthorityResolver(source).resolve("R1", identity)
    first_context = ContextBuilder(source).build("R1", first_authority.context, "TASK")

    assert "CTX-T1" in first_context.task_context.tactical_context_refs
    assert "CTX-X1" in first_context.task_context.technical_context_refs

    source.records["AUT-T"] = {
        "revision_ref": "T-REV-2",
        "loaded_excerpt_refs": ["CTX-T2"],
        "allowed_scopes": ["ops:resume"],
    }

    freshness = make_freshness(source, identity, first_authority, first_context)
    preview = freshness.prepare(make_run())
    assert preview.changed_chains == frozenset({ChainType.TACTICAL})
    assert "CTX-T2" in preview.context.task_context.tactical_context_refs
    assert "CTX-X1" in preview.context.task_context.technical_context_refs
    assert preview.authority.tactical_chain_trace.source_revision_refs == ["T-REV-2"]

    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    state = RunState(
        run_state_id="RS1",
        run_id="R1",
        tarefa_trabalho_id="MT-1",
        status=RunStatus.INTERRUPTED,
        current_step="step-2",
    )
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")

    run = make_run()
    resumed = manager.resume(run, FakeRuntimeAdapter(), checkpoint.checkpoint_id, freshness_gate=freshness)

    assert resumed.status == RunStatus.COMPLETED
    assert run.authority_context_ref != "AC-OLD"
    assert run.task_context_ref.startswith("TC-")

    persisted_state = state_port.load_run_state("RS1")
    audit_refs = [ref for ref in persisted_state.decision_refs if ref.startswith("RV-")]
    assert len(audit_refs) == 1
    audit = state_port.load_revalidation_record(audit_refs[0])
    assert audit["status"] == "RELEASED"
    assert audit["outcome"] == "COMPLETED"
    assert [event["status"] for event in audit["events"]] == ["PENDING", "RELEASED", "RELEASED"]
    assert [event.get("outcome") for event in audit["events"]] == [None, "REVALIDATED_AND_GUARDED", "COMPLETED"]
    assert audit["boundary"] == "RuntimePort.resume"
    assert audit["previous_authority_context_ref"] == "AC-OLD"
    assert audit["previous_revision_refs"]["tactical"] == ["T-REV-1"]
    assert audit["previous_task_context"]["task_context_id"] == first_context.task_context.task_context_id
    assert audit["authority_context_ref"] == run.authority_context_ref
    assert audit["authority_snapshot"]["tactical_source_revision_refs"] == ["T-REV-2"]
    assert audit["changed_chains"] == ("TACTICAL",) or audit["changed_chains"] == ["TACTICAL"]
    assert "CTX-T2" in audit["task_context"]["tactical_context_refs"]
    assert audit["bootstrap_trace"]["trace_id"] == audit["task_context"]["bootstrap_trace_ref"]


def test_t07_technical_only_change_rebuilds_only_technical_chain():
    source = InMemorySourceAdapter(records())
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
    source.records["AUT-X"] = {
        "revision_ref": "X-REV-2",
        "loaded_excerpt_refs": ["CTX-X2"],
        "allowed_scopes": ["ops:resume"],
    }

    preview = make_freshness(source, identity, authority, context).prepare(make_run())
    assert preview.changed_chains == frozenset({ChainType.TECHNICAL})
    assert preview.context.task_context.tactical_context_refs == context.task_context.tactical_context_refs
    assert preview.context.task_context.normative_context_refs == context.task_context.normative_context_refs
    assert "CTX-X2" in preview.context.task_context.technical_context_refs
    assert "CTX-X1" not in preview.context.task_context.technical_context_refs


def test_identity_revision_change_is_detected_even_when_authority_refs_are_unchanged():
    source = InMemorySourceAdapter(records())
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
    source.records["ID-A1"]["revision_ref"] = "ID-REV-2"

    preview = make_freshness(source, identity, authority, context).prepare(make_run())
    assert preview.identity_changed is True
    assert preview.changed_chains == frozenset({ChainType.TACTICAL, ChainType.TECHNICAL, ChainType.NORMATIVE})
    assert preview.authority_snapshot.identity_source_revision_ref == "ID-REV-2"


def test_t10_revalidation_evidence_is_persisted_before_runtime_resume():
    source = InMemorySourceAdapter(records())
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
    freshness = make_freshness(source, identity, authority, context)

    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    state = RunState(run_state_id="RS1", run_id="R1", tarefa_trabalho_id="MT-1", status=RunStatus.INTERRUPTED)
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")

    class AuditAwareRuntime:
        def __init__(self): self.resume_calls = 0
        def execute(self, run, payload): raise NotImplementedError
        def resume(self, run, current_state):
            self.resume_calls += 1
            audit_refs = [ref for ref in current_state.decision_refs if ref.startswith("RV-")]
            assert len(audit_refs) == 1
            audit = state_port.load_revalidation_record(audit_refs[0])
            assert audit["status"] == "RELEASED"
            assert audit["outcome"] == "REVALIDATED_AND_GUARDED"
            assert audit["authority_context_ref"] == run.authority_context_ref
            assert audit["task_context"]["task_context_id"] == run.task_context_ref
            current_state.status = RunStatus.COMPLETED
            return current_state

    runtime = AuditAwareRuntime()
    manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=freshness)
    assert runtime.resume_calls == 1


def test_t10_resume_with_unresolvable_changed_authority_persists_blocked_attempt_before_runtime():
    source = InMemorySourceAdapter(records())
    identity = IdentityResolver(source).resolve("ID-A1")
    first_authority = AuthorityResolver(source).resolve("R1", identity)
    first_context = ContextBuilder(source).build("R1", first_authority.context, "TASK")
    del source.records["AUT-T"]
    freshness = make_freshness(source, identity, first_authority, first_context)

    class CountingRuntime:
        def __init__(self): self.resume_calls = 0
        def execute(self, run, payload): raise NotImplementedError
        def resume(self, run, state):
            self.resume_calls += 1
            return state

    runtime = CountingRuntime()
    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    state = RunState(run_state_id="RS1", run_id="R1", tarefa_trabalho_id="MT-1", status=RunStatus.INTERRUPTED)
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")

    with pytest.raises(HarnessResolutionError):
        manager.resume(make_run(), runtime, checkpoint.checkpoint_id, freshness_gate=freshness)
    assert runtime.resume_calls == 0

    persisted = state_port.load_run_state("RS1")
    audit_refs = [ref for ref in persisted.decision_refs if ref.startswith("RV-")]
    assert len(audit_refs) == 1
    audit = state_port.load_revalidation_record(audit_refs[0])
    assert audit["status"] == "BLOCKED"
    assert audit["outcome"] == "FRESHNESS_REJECTED"
    assert audit["previous_revision_refs"]["tactical"] == ["T-REV-1"]
    assert audit["error_code"] == "AUTHORITY_UNRESOLVED"
    assert [event["status"] for event in audit["events"]] == ["PENDING", "BLOCKED"]


def test_runtime_cannot_inject_decision_refs_on_resume():
    source = InMemorySourceAdapter(records())
    identity = IdentityResolver(source).resolve("ID-A1")
    authority = AuthorityResolver(source).resolve("R1", identity)
    context = ContextBuilder(source).build("R1", authority.context, "TASK")
    freshness = make_freshness(source, identity, authority, context)

    class InjectingRuntime:
        def execute(self, run, payload): raise NotImplementedError
        def resume(self, run, current_state):
            current_state.status = RunStatus.COMPLETED
            current_state.decision_refs.extend(["RV-FORGED", "DECISION-FORGED"])
            return current_state

    state_port = InMemoryStateAdapter()
    manager = StateManager(state_port)
    state = RunState(run_state_id="RS1", run_id="R1", tarefa_trabalho_id="MT-1", status=RunStatus.INTERRUPTED, decision_refs=["CORE-DECISION-1"])
    manager.persist(state)
    checkpoint = manager.checkpoint(state, validated_step="step-1", resume_instruction="continue")

    resumed = manager.resume(make_run(), InjectingRuntime(), checkpoint.checkpoint_id, freshness_gate=freshness)
    assert "RV-FORGED" not in resumed.decision_refs
    assert "DECISION-FORGED" not in resumed.decision_refs
    assert "CORE-DECISION-1" in resumed.decision_refs
    assert len([ref for ref in resumed.decision_refs if ref.startswith("RV-")]) == 1
