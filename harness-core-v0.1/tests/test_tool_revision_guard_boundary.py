from threading import Thread

import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.contracts import (
    AuthorityContext, ChainType, HarnessRun, ResolutionChain, ResolutionStatus, TaskContext,
)
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate
from harness.core.state import StateManager
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry
from harness.ports import VersionedRead
from harness.ports.versioning import RevisionGuardActiveError


def chain(kind, ref, revision):
    return ResolutionChain(
        chain_type=kind, status=ResolutionStatus.RESOLVED, authority_ref=ref,
        route_refs=[ref], source_revision_refs=[revision],
    )


def authority():
    return AuthorityContext(
        authority_context_id="AC-TOOL", run_id="R1", agent_id="A1",
        tactical_authority_refs=["AUT-T"], technical_authority_refs=["AUT-X"], normative_authority_refs=["AUT-N"],
        tactical_chain_trace=chain(ChainType.TACTICAL, "AUT-T", "T-REV-1"),
        technical_chain_trace=chain(ChainType.TECHNICAL, "AUT-X", "X-REV-1"),
        normative_chain_trace=chain(ChainType.NORMATIVE, "AUT-N", "N-REV-1"),
        allowed_scopes=["ops:write"],
    )


def execution(auth):
    task = TaskContext(
        task_context_id="TC-TOOL", run_id="R1", tarefa_trabalho_id="MT-1",
        current_order="write", task_state_ref="TS-1", authority_context_ref=auth.authority_context_id,
        workspace_ref="WS1", bootstrap_trace_ref="BT-1",
    )
    run = HarnessRun(
        run_id="R1", tarefa_trabalho_id="MT-1", agent_id="A1", correlation_id="C1",
        workspace_ref="WS1", run_state_ref="RS1", authority_context_ref=auth.authority_context_id,
        task_context_ref=task.task_context_id,
    )
    return run, task


def source_records():
    return {
        "AUT-T": {"revision_ref": "T-REV-1"},
        "AUT-X": {"revision_ref": "X-REV-1"},
        "AUT-N": {"revision_ref": "N-REV-1"},
    }


def gateway(source, adapter, state_port=None):
    registry = ToolRegistry()
    registry.register(ToolDescriptor(tool_id="ops.write", action_scope="ops:write", side_effect=True), adapter)
    manager = StateManager(state_port or InMemoryStateAdapter())
    return ToolGateway(registry, manager, freshness_gate=AuthorityFreshnessGate(source)), manager


def invoke(gw, auth, business_key):
    run, task = execution(auth)
    return gw.execute(
        run_id="R1", authority=auth, run=run, task_context=task,
        tool_id="ops.write", payload={"x": 1}, business_key=business_key,
    )


class CountingTool:
    def __init__(self): self.calls = []
    def invoke(self, tool_id, payload):
        self.calls.append((tool_id, dict(payload)))
        return {"ok": True, "evidence_refs": ["EV-1"]}


class MutateOnAcquireSource(InMemorySourceAdapter):
    def __init__(self, records):
        super().__init__(records)
        self.mutated = False
    def acquire_revision_guard(self, expected_versions, owner_ref):
        if not self.mutated:
            self.mutated = True
            self.records["AUT-T"]["revision_ref"] = "T-REV-2"
        return super().acquire_revision_guard(expected_versions, owner_ref)


def test_tool_revision_change_after_freshness_before_guard_conflicts_before_ledger_and_toolport():
    source = MutateOnAcquireSource(source_records())
    adapter = CountingTool(); port = InMemoryStateAdapter(); gw, _ = gateway(source, adapter, port)
    with pytest.raises(HarnessResolutionError, match="strong revision guard rejected"):
        invoke(gw, authority(), "TOOL-RACE-1")
    assert source.mutated is True
    assert source.read("AUT-T")["revision_ref"] == "T-REV-2"
    assert adapter.calls == []
    assert port._idempotency_records == {}


class ConcurrentWriterTool(CountingTool):
    def __init__(self, source):
        super().__init__(); self.source = source; self.writer_errors = []
    def invoke(self, tool_id, payload):
        self.calls.append((tool_id, dict(payload)))
        def writer():
            try:
                self.source.records["AUT-X"]["during_tool"] = True
            except Exception as exc:
                self.writer_errors.append(exc)
        thread = Thread(target=writer); thread.start(); thread.join(timeout=2)
        return {"ok": True, "evidence_refs": ["EV-1"]}


def test_tool_concurrent_writer_is_excluded_for_full_toolport_invoke_boundary():
    source = InMemorySourceAdapter(source_records())
    adapter = ConcurrentWriterTool(source); gw, _ = gateway(source, adapter)
    result = invoke(gw, authority(), "TOOL-RACE-2")
    assert result.output["ok"] is True
    assert len(adapter.calls) == 1
    assert len(adapter.writer_errors) == 1
    assert isinstance(adapter.writer_errors[0], RevisionGuardActiveError)
    assert "during_tool" not in source.read("AUT-X")
    source.records["AUT-X"]["after_tool"] = True
    assert source.read("AUT-X")["after_tool"] is True


class WeakVersionedSource:
    def __init__(self):
        self._strong = InMemorySourceAdapter(source_records())
    def read(self, source_ref):
        return self._strong.read(source_ref)
    def read_versioned(self, source_ref):
        observed = self._strong.read_versioned(source_ref)
        return VersionedRead(
            source_ref=observed.source_ref, payload=observed.payload,
            revision_ref=observed.revision_ref, version_token=observed.version_token,
        )


def test_tool_source_without_compare_and_hold_capability_fails_closed_before_ledger_and_toolport():
    source = WeakVersionedSource(); adapter = CountingTool(); port = InMemoryStateAdapter(); gw, _ = gateway(source, adapter, port)
    with pytest.raises(HarnessResolutionError, match="strong revision guard rejected"):
        invoke(gw, authority(), "TOOL-WEAK-1")
    assert adapter.calls == []
    assert port._idempotency_records == {}
