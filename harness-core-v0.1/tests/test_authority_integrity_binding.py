import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.adapters.tools import FakeToolAdapter
from harness.contracts import (
    AgentIdentity,
    AuthorityContext,
    ChainType,
    HarnessRun,
    ResolutionChain,
    ResolutionStatus,
)
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate
from harness.core.state import StateManager
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry


def identity() -> AgentIdentity:
    return AgentIdentity(
        agent_id="A1",
        name="Agent One",
        mission_ref="M1",
        scope_ref="S1",
        organizational_path_ref="ORG-1",
        tactical_authority_ref="AUT-T",
        technical_authority_ref="AUT-X",
        normative_authority_ref="AUT-N",
        source_ref="ID-A1",
        source_revision_ref="ID-REV-1",
    )


def canonical_source() -> InMemorySourceAdapter:
    return InMemorySourceAdapter({
        "ID-A1": {"revision_ref": "ID-REV-1", "identity": identity().model_dump(mode="json")},
        "AUT-T": {"revision_ref": "REV-1"},
        "AUT-X": {"revision_ref": "REV-1"},
        "AUT-N": {"revision_ref": "REV-1"},
    })


def chain(kind: ChainType) -> ResolutionChain:
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


def authority(*, run_id="R1", agent_id="A1", allowed=None) -> AuthorityContext:
    return AuthorityContext(
        authority_context_id=f"AC-{run_id}-{agent_id}",
        run_id=run_id,
        agent_id=agent_id,
        tactical_authority_refs=["AUT-T"],
        technical_authority_refs=["AUT-X"],
        normative_authority_refs=["AUT-N"],
        tactical_chain_trace=chain(ChainType.TACTICAL),
        technical_chain_trace=chain(ChainType.TECHNICAL),
        normative_chain_trace=chain(ChainType.NORMATIVE),
        allowed_scopes=list(allowed or ["finance:pay"]),
        competence_refs=["PAY"],
    )


def run(*, run_id="R1", agent_id="A1") -> HarnessRun:
    return HarnessRun(
        run_id=run_id,
        tarefa_trabalho_id="MT-1",
        agent_id=agent_id,
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref="AC-R1-A1",
    )


def gateway():
    registry = ToolRegistry()
    adapter = FakeToolAdapter({"ok": True})
    registry.register(
        ToolDescriptor(
            tool_id="finance.pay",
            action_scope="finance:pay",
            side_effect=True,
            required_competence="PAY",
        ),
        adapter,
    )
    state = StateManager(InMemoryStateAdapter())
    return ToolGateway(
        registry,
        state,
        freshness_gate=AuthorityFreshnessGate(canonical_source(), identity()),
    ), adapter, state


def only_audit(state: StateManager):
    records = list(state.state_port._revalidation_records.values())
    assert len(records) == 1
    return records[0]


def test_cross_run_authority_is_blocked_before_freshness_ledger_and_toolport():
    gw, adapter, state = gateway()

    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(
            run_id="R1",
            run=run(run_id="R1", agent_id="A1"),
            authority=authority(run_id="R2", agent_id="A1", allowed=["finance:pay"]),
            tool_id="finance.pay",
            payload={"amount": 10},
            business_key="CROSS-RUN",
        )

    assert exc.value.code.value == "AUTHORITY_UNRESOLVED"
    assert adapter.calls == []
    assert state.state_port._idempotency_records == {}
    audit = only_audit(state)
    assert audit["status"] == "BLOCKED"
    assert audit["outcome"] == "AUTHORITY_RUN_MISMATCH"
    assert audit["decision"] == "ESCALATE"
    assert audit["metadata"]["expected_run_id"] == "R1"
    assert audit["metadata"]["authority_run_id"] == "R2"


def test_cross_agent_authority_with_valid_scope_is_blocked_before_ledger_and_toolport():
    gw, adapter, state = gateway()

    with pytest.raises(HarnessResolutionError) as exc:
        gw.execute(
            run_id="R1",
            run=run(run_id="R1", agent_id="A1"),
            authority=authority(run_id="R1", agent_id="B", allowed=["finance:pay"]),
            tool_id="finance.pay",
            payload={"amount": 10},
            business_key="CROSS-AGENT",
        )

    assert exc.value.code.value == "AUTHORITY_UNRESOLVED"
    assert adapter.calls == []
    assert state.state_port._idempotency_records == {}
    audit = only_audit(state)
    assert audit["status"] == "BLOCKED"
    assert audit["outcome"] == "AUTHORITY_AGENT_MISMATCH"
    assert audit["decision"] == "ESCALATE"
    assert audit["metadata"]["expected_agent_id"] == "A1"
    assert audit["metadata"]["authority_agent_id"] == "B"


def test_current_correctly_bound_authority_preserves_valid_path():
    gw, adapter, state = gateway()
    result = gw.execute(
        run_id="R1",
        run=run(),
        authority=authority(),
        tool_id="finance.pay",
        payload={"amount": 10},
        business_key="BOUND-OK",
    )

    assert result.decision.value == "ALLOW"
    assert len(adapter.calls) == 1
    assert state.get_side_effect("R1:finance.pay:BOUND-OK").status.value == "COMPLETED"


def test_missing_core_run_binding_fails_closed_before_freshness_ledger_and_toolport():
    gw, adapter, state = gateway()

    with pytest.raises(HarnessResolutionError):
        gw.execute(
            run_id="R1",
            run=None,
            authority=authority(),
            tool_id="finance.pay",
            payload={},
            business_key="NO-RUN",
        )

    assert adapter.calls == []
    assert state.state_port._idempotency_records == {}
    audit = only_audit(state)
    assert audit["status"] == "BLOCKED"
    assert audit["outcome"] == "RUN_BINDING_UNRESOLVED"
