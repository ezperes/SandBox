import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.adapters.tools import FakeToolAdapter
from harness.contracts import (
    AuthorityContext,
    ChainType,
    HarnessRun,
    ResolutionChain,
    ResolutionStatus,
    RiskLevel,
    TaskContext,
)
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate
from harness.core.state import StateManager
from harness.core.tools import ToolDescriptor, ToolGateway, ToolRegistry


def _chain(kind: ChainType, ref: str, revision: str) -> ResolutionChain:
    return ResolutionChain(
        chain_type=kind,
        status=ResolutionStatus.RESOLVED,
        authority_ref=ref,
        route_refs=[ref],
        source_revision_refs=[revision],
    )


def _authority(revision: str = "rev-A") -> AuthorityContext:
    return AuthorityContext(
        authority_context_id="AC-FRESH",
        run_id="R1",
        agent_id="A1",
        tactical_authority_refs=["AUT-T"],
        technical_authority_refs=["AUT-X"],
        normative_authority_refs=["AUT-N"],
        tactical_chain_trace=_chain(ChainType.TACTICAL, "AUT-T", revision),
        technical_chain_trace=_chain(ChainType.TECHNICAL, "AUT-X", revision),
        normative_chain_trace=_chain(ChainType.NORMATIVE, "AUT-N", revision),
        allowed_scopes=["finance:pay"],
        competence_refs=["PAY"],
    )


def _execution(authority: AuthorityContext):
    run = HarnessRun(
        run_id="R1",
        tarefa_trabalho_id="TT-1",
        agent_id="A1",
        correlation_id="C1",
        workspace_ref="WS1",
        run_state_ref="RS1",
        authority_context_ref=authority.authority_context_id,
        task_context_ref="TC-1",
    )
    task = TaskContext(
        task_context_id="TC-1",
        run_id="R1",
        tarefa_trabalho_id="TT-1",
        current_order="pay",
        task_state_ref="TS-1",
        authority_context_ref=authority.authority_context_id,
        workspace_ref="WS1",
        bootstrap_trace_ref="BT-1",
    )
    return run, task


def _gateway(source: InMemorySourceAdapter):
    registry = ToolRegistry()
    adapter = FakeToolAdapter({"ok": True, "evidence_refs": ["EV-1"]})
    registry.register(
        ToolDescriptor(
            tool_id="finance.pay",
            action_scope="finance:pay",
            risk_level=RiskLevel.HIGH,
            side_effect=True,
            required_competence="PAY",
        ),
        adapter,
    )
    return ToolGateway(
        registry,
        StateManager(InMemoryStateAdapter()),
        freshness_gate=AuthorityFreshnessGate(source),
    ), adapter


def _source(revision: str = "rev-A") -> InMemorySourceAdapter:
    return InMemorySourceAdapter({
        "AUT-T": {"revision_ref": revision},
        "AUT-X": {"revision_ref": revision},
        "AUT-N": {"revision_ref": revision},
    })


def test_current_authority_revision_allows_side_effect_to_reach_adapter():
    source = _source("rev-A")
    gateway, adapter = _gateway(source)
    authority = _authority("rev-A")
    run, task = _execution(authority)

    result = gateway.execute(
        run_id="R1",
        authority=authority,
        run=run,
        task_context=task,
        tool_id="finance.pay",
        payload={"amount": 10},
        business_key="PAY-1",
    )

    assert result.decision.value == "ALLOW"
    assert len(adapter.calls) == 1


def test_t11_stale_authority_revision_blocks_side_effect_before_adapter():
    source = _source("rev-A")
    gateway, adapter = _gateway(source)
    authority = _authority("rev-A")
    run, task = _execution(authority)

    source.records["AUT-T"]["revision_ref"] = "rev-B"
    source.records["AUT-T"]["allowed_scopes"] = []

    with pytest.raises(HarnessResolutionError) as exc:
        gateway.execute(
            run_id="R1",
            authority=authority,
            run=run,
            task_context=task,
            tool_id="finance.pay",
            payload={"amount": 10},
            business_key="PAY-2",
        )

    assert "AUTHORITY_UNRESOLVED" in str(exc.value)
    assert "stale" in str(exc.value)
    assert adapter.calls == []


def test_missing_revision_fails_closed_before_side_effect():
    source = _source("rev-A")
    source.records["AUT-N"].pop("revision_ref")
    gateway, adapter = _gateway(source)
    authority = _authority("rev-A")
    run, task = _execution(authority)

    with pytest.raises(HarnessResolutionError) as exc:
        gateway.execute(
            run_id="R1",
            authority=authority,
            run=run,
            task_context=task,
            tool_id="finance.pay",
            payload={},
            business_key="PAY-3",
        )

    assert "AUTHORITY_UNRESOLVED" in str(exc.value)
    assert adapter.calls == []
