from dataclasses import replace
import pytest
from harness.adapters.runtimes.fake import FakeRuntimeAdapter
from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import ResumeFreshnessGate
from harness.core.identity import IdentityResolver
from harness.core.state import StateManager


def records():
    return {
        "ID-A1":{"revision_ref":"ID-REV-1","identity":{"agent_id":"A1","name":"Agent One","mission_ref":"MISSION-1","scope_ref":"SCOPE-1","organizational_path_ref":"ORG-1","tactical_authority_ref":"AUT-T","technical_authority_ref":"AUT-X","normative_authority_ref":"AUT-N","source_ref":"ID-A1"}},
        "AUT-T":{"revision_ref":"T-REV-1","loaded_excerpt_refs":["CTX-T"],"allowed_scopes":["ops:resume"]},
        "AUT-X":{"revision_ref":"X-REV-1","loaded_excerpt_refs":["CTX-X"],"allowed_scopes":["ops:resume"]},
        "AUT-N":{"revision_ref":"N-REV-1","loaded_excerpt_refs":["CTX-N"]},
        "CTX-T":{"context_ref":"CTX-T","estimated_tokens":1,"required":True},
        "CTX-X":{"context_ref":"CTX-X","estimated_tokens":1,"required":True},
        "CTX-N":{"context_ref":"CTX-N","estimated_tokens":1,"required":True},
        "TASK":{"tarefa_trabalho_id":"MT-1","current_order":"continue","task_state_ref":"TASK-STATE-1","workspace_ref":"WS1"},
    }


def make_run(**updates):
    run=HarnessRun(run_id="R1",tarefa_trabalho_id="MT-1",agent_id="A1",correlation_id="C1",workspace_ref="WS1",run_state_ref="RS1",authority_context_ref="AC-OLD")
    return run.model_copy(update=updates)


def make_state(**updates):
    state=RunState(run_state_id="RS1",run_id="R1",tarefa_trabalho_id="MT-1",status=RunStatus.INTERRUPTED,current_step="step-2",completed_steps=["step-1"],pending_steps=["step-2"],artifact_refs=["ART-1"])
    return state.model_copy(update=updates)


def make_gate(*, context_run=None, context_task=None, authority_run="R1"):
    source=InMemorySourceAdapter(records()); identity=IdentityResolver(source).resolve("ID-A1")
    authority=AuthorityResolver(source).resolve(authority_run,identity); context=ContextBuilder(source).build(authority_run,authority.context,"TASK")
    if context_run is not None or context_task is not None:
        task_context=context.task_context.model_copy(update={"run_id":context_run or context.task_context.run_id,"tarefa_trabalho_id":context_task or context.task_context.tarefa_trabalho_id})
        context=replace(context,task_context=task_context)
    return ResumeFreshnessGate(source=source,identity_source_ref="ID-A1",task_source_ref="TASK",previous_identity_revision_ref=identity.source_revision_ref,previous_authority=authority.context,previous_context=context)


class CountingRuntime(FakeRuntimeAdapter):
    def __init__(self,updates=None): super().__init__(); self.resume_calls=0; self.updates=dict(updates or {})
    def resume(self,run,state):
        self.resume_calls+=1
        return super().resume(run,state).model_copy(update=self.updates)


def checkpointed(manager,state):
    manager.persist(state); return manager.checkpoint(state,validated_step="step-1",resume_instruction="continue")


def assert_blocked(manager,run,runtime,checkpoint,gate):
    with pytest.raises(HarnessResolutionError) as exc: manager.resume(run,runtime,checkpoint.checkpoint_id,freshness_gate=gate)
    assert exc.value.code==HarnessErrorCode.CHECKPOINT_INVALID; assert runtime.resume_calls==0


def test_run_state_id_different_from_harness_run_ref_blocks_before_runtime():
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state(run_state_id="RS2"))
    assert_blocked(manager,make_run(run_state_ref="RS1"),CountingRuntime(),checkpoint,make_gate())


def test_checkpoint_run_state_ref_must_match_loaded_state_identity():
    class MismatchedLoadPort(InMemoryStateAdapter):
        def load_run_state(self,run_state_id): return super().load_run_state(run_state_id).model_copy(update={"run_state_id":"RS-OTHER"})
    port=MismatchedLoadPort(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state())
    assert_blocked(manager,make_run(),CountingRuntime(),checkpoint,make_gate())


def test_run_state_task_different_from_harness_run_blocks_before_runtime():
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state(tarefa_trabalho_id="MT-OTHER"))
    assert_blocked(manager,make_run(),CountingRuntime(),checkpoint,make_gate())


def test_incompatible_run_id_blocks_before_runtime():
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state())
    assert_blocked(manager,make_run(run_id="R2"),CountingRuntime(),checkpoint,make_gate())


def test_resume_gate_previous_context_from_another_run_blocks_before_runtime():
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state())
    assert_blocked(manager,make_run(),CountingRuntime(),checkpoint,make_gate(context_run="R2"))


def test_resume_gate_previous_context_from_another_task_blocks_before_runtime():
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state())
    assert_blocked(manager,make_run(),CountingRuntime(),checkpoint,make_gate(context_task="MT-OTHER"))


def test_resume_gate_previous_authority_from_another_run_blocks_before_runtime():
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state())
    assert_blocked(manager,make_run(),CountingRuntime(),checkpoint,make_gate(authority_run="R2"))


def run_with_runtime_mutation(**updates):
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state(decision_refs=["CORE-1"])); runtime=CountingRuntime(updates)
    resumed=manager.resume(make_run(),runtime,checkpoint.checkpoint_id,freshness_gate=make_gate()); persisted=port.load_run_state("RS1")
    assert runtime.resume_calls==1; return resumed,persisted


def test_runtime_false_run_id_is_not_persisted():
    resumed,persisted=run_with_runtime_mutation(run_id="R-FORGED"); assert resumed.run_id==persisted.run_id=="R1"


def test_runtime_false_task_id_is_not_persisted():
    resumed,persisted=run_with_runtime_mutation(tarefa_trabalho_id="MT-FORGED"); assert resumed.tarefa_trabalho_id==persisted.tarefa_trabalho_id=="MT-1"


def test_runtime_false_checkpoint_ref_is_not_persisted():
    resumed,persisted=run_with_runtime_mutation(checkpoint_ref="CP-FORGED"); assert resumed.checkpoint_ref is None and persisted.checkpoint_ref is None


def test_runtime_false_run_state_id_is_not_persisted():
    resumed,persisted=run_with_runtime_mutation(run_state_id="RS-FORGED"); assert resumed.run_state_id==persisted.run_state_id=="RS1"


def test_runtime_false_decision_refs_remain_core_owned():
    resumed,persisted=run_with_runtime_mutation(decision_refs=["DECISION-FORGED"]); assert "DECISION-FORGED" not in resumed.decision_refs; assert resumed.decision_refs==persisted.decision_refs; assert "CORE-1" in resumed.decision_refs


def test_second_resume_of_same_checkpoint_is_blocked_without_second_runtime_call():
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state()); runtime=CountingRuntime(); run=make_run()
    manager.resume(run,runtime,checkpoint.checkpoint_id,freshness_gate=make_gate()); assert runtime.resume_calls==1; assert port.load_run_state("RS1").checkpoint_ref is None
    with pytest.raises(HarnessResolutionError) as exc: manager.resume(run,runtime,checkpoint.checkpoint_id,freshness_gate=make_gate())
    assert exc.value.code==HarnessErrorCode.CHECKPOINT_INVALID; assert runtime.resume_calls==1


@pytest.mark.parametrize("status",[status for status in RunStatus if status!=RunStatus.INTERRUPTED])
def test_only_interrupted_run_state_is_resumable_in_v01(status):
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state(status=status)); runtime=CountingRuntime()
    with pytest.raises(HarnessResolutionError) as exc: manager.resume(make_run(),runtime,checkpoint.checkpoint_id,freshness_gate=make_gate())
    assert exc.value.code==HarnessErrorCode.CHECKPOINT_INVALID; assert runtime.resume_calls==0


def test_valid_resume_preserves_core_bindings_and_accepts_runtime_progress():
    port=InMemoryStateAdapter(); manager=StateManager(port); checkpoint=checkpointed(manager,make_state())
    runtime=CountingRuntime({"status":RunStatus.COMPLETED,"current_step":"runtime-complete","completed_steps":["step-1","step-2"],"pending_steps":[],"artifact_refs":["ART-RUNTIME"]})
    resumed=manager.resume(make_run(),runtime,checkpoint.checkpoint_id,freshness_gate=make_gate())
    assert runtime.resume_calls==1; assert resumed.run_state_id=="RS1"; assert resumed.run_id=="R1"; assert resumed.tarefa_trabalho_id=="MT-1"; assert resumed.checkpoint_ref is None
    assert resumed.status==RunStatus.COMPLETED; assert resumed.current_step=="runtime-complete"; assert resumed.artifact_refs==["ART-RUNTIME"]
