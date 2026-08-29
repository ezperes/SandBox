import pytest

from harness.adapters.state import InMemoryStateAdapter
from harness.adapters.tools import FakeToolAdapter
from harness.contracts import AuthorityContext, ChainType, ResolutionChain, ResolutionStatus, RiskLevel
from harness.core.identity import HarnessResolutionError
from harness.core.state import StateManager
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry


def chain(kind):
    return ResolutionChain(chain_type=kind, status=ResolutionStatus.RESOLVED, authority_ref=f"AUT-{kind}", route_refs=[f"SRC-{kind}"])


def authority(*, allowed=None, forbidden=None, competences=None):
    return AuthorityContext(
        authority_context_id="AC-1", run_id="R1", agent_id="A1",
        tactical_authority_refs=["AUT-T"], technical_authority_refs=["AUT-X"], normative_authority_refs=["AUT-N"],
        tactical_chain_trace=chain(ChainType.TACTICAL), technical_chain_trace=chain(ChainType.TECHNICAL), normative_chain_trace=chain(ChainType.NORMATIVE),
        allowed_scopes=list(allowed or []), forbidden_scopes=list(forbidden or []), competence_refs=list(competences or []),
    )


def gateway(descriptor, response=None):
    registry = ToolRegistry()
    adapter = FakeToolAdapter(response)
    registry.register(descriptor, adapter)
    return ToolGateway(registry, StateManager(InMemoryStateAdapter())), adapter


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


def test_forbidden_scope_never_reaches_adapter():
    descriptor = ToolDescriptor(tool_id="tool", action_scope="finance:pay", side_effect=True)
    gw, adapter = gateway(descriptor)
    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(run_id="R1", authority=authority(forbidden=["finance:pay"]), tool_id="tool", payload={}, business_key="P1")
    assert "ACTION_FORBIDDEN" in str(exc.value)
    assert adapter.calls == []


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
