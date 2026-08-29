import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.adapters.tools import FakeToolAdapter
from harness.contracts import AuthorityContext, ChainType, ResolutionChain, ResolutionStatus, RiskLevel
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate
from harness.core.state import StateManager
from harness.core.state.manager import IdempotencyStatus
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry


def chain(kind):
    ref = {
        ChainType.TACTICAL: "AUT-T",
        ChainType.TECHNICAL: "AUT-X",
        ChainType.NORMATIVE: "AUT-N",
    }[kind]
    return ResolutionChain(
        chain_type=kind,
        status=ResolutionStatus.RESOLVED,
        authority_ref=ref,
        route_refs=[ref],
        source_revision_refs=["REV-1"],
    )


def authority(*, allowed=None, forbidden=None, competences=None):
    return AuthorityContext(
        authority_context_id="AC-1", run_id="R1", agent_id="A1",
        tactical_authority_refs=["AUT-T"], technical_authority_refs=["AUT-X"], normative_authority_refs=["AUT-N"],
        tactical_chain_trace=chain(ChainType.TACTICAL), technical_chain_trace=chain(ChainType.TECHNICAL), normative_chain_trace=chain(ChainType.NORMATIVE),
        allowed_scopes=list(allowed or []), forbidden_scopes=list(forbidden or []), competence_refs=list(competences or []),
    )


def canonical_source():
    return InMemorySourceAdapter({
        "AUT-T": {"revision_ref": "REV-1"},
        "AUT-X": {"revision_ref": "REV-1"},
        "AUT-N": {"revision_ref": "REV-1"},
    })


def gateway(descriptor, response=None):
    registry = ToolRegistry()
    adapter = FakeToolAdapter(response)
    registry.register(descriptor, adapter)
    return ToolGateway(
        registry,
        StateManager(InMemoryStateAdapter()),
        freshness_gate=AuthorityFreshnessGate(canonical_source()),
    ), adapter


def only_audit(gw):
    records = list(gw.state.state_port._revalidation_records.values())
    assert len(records) == 1
    return records[0]


def test_side_effect_without_core_freshness_gate_fails_closed_before_tool_port():
    descriptor = ToolDescriptor(tool_id="drive.write", action_scope="drive:write", risk_level=RiskLevel.HIGH, side_effect=True)
    registry = ToolRegistry()
    adapter = FakeToolAdapter({"ok": True})
    registry.register(descriptor, adapter)
    gw = ToolGateway(registry, StateManager(InMemoryStateAdapter()))

    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(
            run_id="R1",
            authority=authority(allowed=["drive:write"]),
            tool_id="drive.write",
            payload={"x": 1},
            business_key="DOC-NO-GATE",
        )
    assert "AUTHORITY_UNRESOLVED" in str(exc.value)
    assert adapter.calls == []
    audit = only_audit(gw)
    assert audit["status"] == "BLOCKED"
    assert audit["outcome"] == "FRESHNESS_GATE_INVALID"
    assert audit["previous_revision_refs"]["tactical"] == ["REV-1"]


def test_side_effect_requires_gate_business_key_and_blocks_duplicate():
    descriptor = ToolDescriptor(tool_id="drive.write", action_scope="drive:write", risk_level=RiskLevel.HIGH, side_effect=True, required_competence="DRIVE_WRITE")
    gw, adapter = gateway(descriptor, {"ok": True, "evidence_refs": ["EV-1"]})
    auth = authority(allowed=["drive:write"], competences=["DRIVE_WRITE"])

    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(run_id="R1", authority=auth, tool_id="drive.write", payload={})
    assert "SIDE_EFFECT_UNKNOWN" in str(exc.value)
    assert adapter.calls == []

    result = gw.execute(run_id="R1", authority=auth, tool_id="drive.write", payload={"x": 1}, business_key="DOC-1")
    assert result.decision.value == "ALLOW"
    assert len(adapter.calls) == 1

    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(run_id="R1", authority=auth, tool_id="drive.write", payload={"x": 1}, business_key="DOC-1")
    assert "RETRY_BLOCKED" in str(exc.value)
    assert len(adapter.calls) == 1


def test_forbidden_scope_never_reaches_adapter_and_persists_deny():
    descriptor = ToolDescriptor(tool_id="tool", action_scope="finance:pay", side_effect=True)
    gw, adapter = gateway(descriptor)
    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(run_id="R1", authority=authority(forbidden=["finance:pay"]), tool_id="tool", payload={}, business_key="P1")
    assert "ACTION_FORBIDDEN" in str(exc.value)
    assert adapter.calls == []
    audit = only_audit(gw)
    assert audit["status"] == "BLOCKED"
    assert audit["outcome"] == "DENY"
    assert audit["decision"] == "DENY"
    assert audit["error_code"] == "ACTION_FORBIDDEN"


def test_side_effect_escalate_is_persisted_and_never_reaches_adapter():
    descriptor = ToolDescriptor(tool_id="tool", action_scope="ops:change", side_effect=True, required_competence="OPS_ADMIN")
    gw, adapter = gateway(descriptor)
    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(
            run_id="R1",
            authority=authority(allowed=["ops:change"]),
            tool_id="tool",
            payload={},
            business_key="OPS-1",
        )
    assert "COMPETENCE_INSUFFICIENT" in str(exc.value)
    assert adapter.calls == []
    audit = only_audit(gw)
    assert audit["status"] == "BLOCKED"
    assert audit["outcome"] == "ESCALATE"
    assert audit["decision"] == "ESCALATE"
    assert audit["error_code"] == "COMPETENCE_INSUFFICIENT"


def test_missing_competence_escalates_before_tool_call():
    descriptor = ToolDescriptor(tool_id="tool", action_scope="ops:change", required_competence="OPS_ADMIN")
    gw, adapter = gateway(descriptor)
    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(run_id="R1", authority=authority(allowed=["ops:change"]), tool_id="tool", payload={})
    assert "COMPETENCE_INSUFFICIENT" in str(exc.value)
    assert adapter.calls == []


def test_human_approval_gate_precedes_side_effect():
    descriptor = ToolDescriptor(tool_id="tool", action_scope="publish", side_effect=True, approval_required=True)
    gw, adapter = gateway(descriptor)
    auth = authority(allowed=["publish"])
    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(run_id="R1", authority=auth, tool_id="tool", payload={}, business_key="PUB-1")
    assert "APPROVAL_REQUIRED" in str(exc.value)
    assert adapter.calls == []

    result = gw.execute(run_id="R1", authority=auth, tool_id="tool", payload={}, business_key="PUB-1", approved=True)
    assert result.decision.value == "ALLOW"
    assert len(adapter.calls) == 1


def test_side_effect_toolport_failure_persists_failed_and_unknown_ledger():
    class RaisingAdapter:
        def __init__(self): self.calls = []
        def invoke(self, tool_id, payload):
            self.calls.append((tool_id, dict(payload)))
            raise RuntimeError("provider timeout")

    descriptor = ToolDescriptor(tool_id="tool.fail", action_scope="ops:write", side_effect=True)
    registry = ToolRegistry()
    adapter = RaisingAdapter()
    registry.register(descriptor, adapter)
    manager = StateManager(InMemoryStateAdapter())
    gw = ToolGateway(registry, manager, freshness_gate=AuthorityFreshnessGate(canonical_source()))

    with pytest.raises(RuntimeError, match="provider timeout"):
        gw.execute(
            run_id="R1",
            authority=authority(allowed=["ops:write"]),
            tool_id="tool.fail",
            payload={"x": 1},
            business_key="FAIL-1",
        )
    assert len(adapter.calls) == 1
    audit = only_audit(gw)
    assert audit["status"] == "FAILED"
    assert audit["outcome"] == "TOOLPORT_ERROR"
    key = "R1:tool.fail:FAIL-1"
    assert manager.get_side_effect(key).status == IdempotencyStatus.UNKNOWN
    assert manager.get_side_effect(key).reconciliation_required is True


def test_required_evidence_is_enforced_after_execution():
    descriptor = ToolDescriptor(tool_id="tool", action_scope="read", evidence_required=True)
    gw, adapter = gateway(descriptor, {"ok": True})
    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(run_id="R1", authority=authority(allowed=["read"]), tool_id="tool", payload={})
    assert "VERIFICATION_FAILED" in str(exc.value)
    assert len(adapter.calls) == 1


def test_unregistered_tool_fails_closed():
    gw = ToolGateway(ToolRegistry(), StateManager(InMemoryStateAdapter()))
    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(run_id="R1", authority=authority(), tool_id="missing", payload={})
    assert "TOOL_UNAVAILABLE" in str(exc.value)
