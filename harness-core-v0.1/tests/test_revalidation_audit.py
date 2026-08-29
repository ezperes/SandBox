import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.adapters.tools import FakeToolAdapter
from harness.contracts import AuthorityContext, ChainType, ResolutionChain, ResolutionStatus, RiskLevel
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate
from harness.core.state import StateManager
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry


def _chain(kind: ChainType, ref: str, revision: str = "REV-1") -> ResolutionChain:
    return ResolutionChain(
        chain_type=kind,
        status=ResolutionStatus.RESOLVED,
        authority_ref=ref,
        route_refs=[ref],
        source_revision_refs=[revision],
    )


def _authority(*, allowed=None, forbidden=None) -> AuthorityContext:
    return AuthorityContext(
        authority_context_id="AC-AUDIT",
        run_id="R1",
        agent_id="A1",
        tactical_authority_refs=["AUT-T"],
        technical_authority_refs=["AUT-X"],
        normative_authority_refs=["AUT-N"],
        tactical_chain_trace=_chain(ChainType.TACTICAL, "AUT-T"),
        technical_chain_trace=_chain(ChainType.TECHNICAL, "AUT-X"),
        normative_chain_trace=_chain(ChainType.NORMATIVE, "AUT-N"),
        allowed_scopes=list(allowed or []),
        forbidden_scopes=list(forbidden or []),
    )


def _registry(*, side_effect: bool = True, response=None):
    registry = ToolRegistry()
    adapter = FakeToolAdapter(response or {"ok": True, "evidence_refs": ["EV-1"]})
    registry.register(
        ToolDescriptor(
            tool_id="tool.audit",
            action_scope="ops:write" if side_effect else "ops:read",
            risk_level=RiskLevel.HIGH if side_effect else RiskLevel.LOW,
            side_effect=side_effect,
        ),
        adapter,
    )
    return registry, adapter


def _source(revision: str = "REV-1") -> InMemorySourceAdapter:
    return InMemorySourceAdapter({
        "AUT-T": {"revision_ref": revision},
        "AUT-X": {"revision_ref": revision},
        "AUT-N": {"revision_ref": revision},
    })


def test_side_effect_without_freshness_persists_blocked_trace_discoverable_by_run():
    port = InMemoryStateAdapter()
    registry, adapter = _registry(side_effect=True)
    gateway = ToolGateway(registry, StateManager(port))

    with pytest.raises(HarnessResolutionError):
        gateway.execute(
            run_id="R1",
            authority=_authority(allowed=["ops:write"]),
            tool_id="tool.audit",
            payload={},
            business_key="K1",
        )

    assert adapter.calls == []
    records = port.list_revalidation_records("R1")
    assert len(records) == 1
    record = records[0]
    assert record["boundary"] == "ToolPort.invoke"
    assert record["status"] == "BLOCKED"
    assert record["outcome"] == "FRESHNESS_GATE_INVALID"
    assert record["error_code"] == "AUTHORITY_UNRESOLVED"
    assert record["previous_revision_refs"]["tactical"] == ["REV-1"]


def test_stale_side_effect_persists_expected_and_observed_revisions_before_tool_port():
    port = InMemoryStateAdapter()
    source = _source("REV-1")
    registry, adapter = _registry(side_effect=True)
    gateway = ToolGateway(registry, StateManager(port), freshness_gate=AuthorityFreshnessGate(source))
    authority = _authority(allowed=["ops:write"])
    source.records["AUT-T"]["revision_ref"] = "REV-2"

    with pytest.raises(HarnessResolutionError):
        gateway.execute(
            run_id="R1",
            authority=authority,
            tool_id="tool.audit",
            payload={},
            business_key="K2",
        )

    assert adapter.calls == []
    record = port.list_revalidation_records("R1")[0]
    assert record["status"] == "BLOCKED"
    assert record["outcome"] == "FRESHNESS_REJECTED"
    assert record["metadata"]["expected_revision_refs"] == ["REV-1"]
    assert record["metadata"]["observed_revision_ref"] == "REV-2"


def test_non_side_effect_escalation_also_persists_decision_trace():
    port = InMemoryStateAdapter()
    registry, adapter = _registry(side_effect=False)
    gateway = ToolGateway(registry, StateManager(port))

    with pytest.raises(HarnessResolutionError):
        gateway.execute(
            run_id="R1",
            authority=_authority(allowed=[]),
            tool_id="tool.audit",
            payload={},
        )

    assert adapter.calls == []
    record = port.list_revalidation_records("R1")[0]
    assert record["status"] == "BLOCKED"
    assert record["outcome"] == "ESCALATE"
    assert record["decision"] == "ESCALATE"


def test_authorized_tool_persists_release_before_boundary_and_returns_trace_ref():
    port = InMemoryStateAdapter()
    registry, adapter = _registry(side_effect=False)
    gateway = ToolGateway(registry, StateManager(port))
    authority = _authority(allowed=["ops:read"])

    result = gateway.execute(run_id="R1", authority=authority, tool_id="tool.audit", payload={"x": 1})

    assert len(adapter.calls) == 1
    assert result.decision_ref is not None
    record = port.load_revalidation_record(result.decision_ref)
    assert record["status"] == "RELEASED"
    assert record["outcome"] == "COMPLETED"
    assert [event["status"] for event in record["events"]] == ["PENDING", "RELEASED", "RELEASED"]
