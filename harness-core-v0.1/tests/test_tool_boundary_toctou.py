from __future__ import annotations

from contextlib import contextmanager
from threading import Event, Thread

import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.adapters.state import InMemoryStateAdapter
from harness.adapters.tools import FakeToolAdapter
from harness.contracts import AuthorityContext, ChainType, ResolutionChain, ResolutionStatus, RiskLevel
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
        authority_context_id="AC-TOCTOU",
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


def _source(revision: str = "rev-A") -> InMemorySourceAdapter:
    return InMemorySourceAdapter({
        "AUT-T": {"revision_ref": revision},
        "AUT-X": {"revision_ref": revision},
        "AUT-N": {"revision_ref": revision},
    })


def _gateway(source, adapter):
    registry = ToolRegistry()
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
    manager = StateManager(InMemoryStateAdapter())
    gateway = ToolGateway(
        registry,
        manager,
        freshness_gate=AuthorityFreshnessGate(source),
    )
    return gateway, manager


def test_plain_check_then_invoke_reproduces_toctou_window():
    """Proves why a final check without a held fence is not sufficient."""
    source = _source("rev-A")
    gate = AuthorityFreshnessGate(source)
    authority = _authority("rev-A")
    adapter = FakeToolAdapter({"ok": True})

    gate.ensure_current(authority)
    source.update_record("AUT-T", {"revision_ref": "rev-B", "allowed_scopes": []})
    adapter.invoke("finance.pay", {"amount": 10})

    assert len(adapter.calls) == 1
    assert source.read("AUT-T")["revision_ref"] == "rev-B"


def test_revision_change_after_early_check_is_caught_after_fence_acquisition():
    class RaceOnFenceSource(InMemorySourceAdapter):
        def __init__(self, records):
            super().__init__(records)
            self.raced = False

        @contextmanager
        def revision_fence(self, expected_revision_refs):
            # Simulate the exact race: early freshness passed at rev-A, then the
            # source advances immediately before the final fenced proof.
            if not self.raced:
                self.update_record("AUT-T", {"revision_ref": "rev-B", "allowed_scopes": []})
                self.raced = True
            with super().revision_fence(expected_revision_refs):
                yield

    source = RaceOnFenceSource({
        "AUT-T": {"revision_ref": "rev-A"},
        "AUT-X": {"revision_ref": "rev-A"},
        "AUT-N": {"revision_ref": "rev-A"},
    })
    adapter = FakeToolAdapter({"ok": True})
    gateway, manager = _gateway(source, adapter)

    with pytest.raises(HarnessResolutionError) as exc:
        gateway.execute(
            run_id="R1",
            authority=_authority("rev-A"),
            tool_id="finance.pay",
            payload={"amount": 10},
            business_key="PAY-RACE",
        )

    assert "AUTHORITY_UNRESOLVED" in str(exc.value)
    assert "stale" in str(exc.value)
    assert adapter.calls == []
    assert manager.state_port._idempotency_records == {}


def test_fence_blocks_revision_writer_until_toolport_returns():
    source = _source("rev-A")
    tool_entered = Event()
    writer_attempted = Event()
    writer_done = Event()

    class ObservingToolAdapter:
        def __init__(self):
            self.calls = []
            self.observed_revision = None

        def invoke(self, tool_id, payload):
            self.calls.append((tool_id, dict(payload)))
            tool_entered.set()
            assert writer_attempted.wait(1.0)
            # Writer has attempted the mutation but must still be blocked by the
            # source fence held by ToolGateway on this thread.
            assert not writer_done.is_set()
            self.observed_revision = source.read("AUT-T")["revision_ref"]
            return {"ok": True, "evidence_refs": ["EV-TOCTOU"]}

    adapter = ObservingToolAdapter()
    gateway, _ = _gateway(source, adapter)

    def mutate_revision():
        assert tool_entered.wait(1.0)
        writer_attempted.set()
        source.update_record("AUT-T", {"revision_ref": "rev-B", "allowed_scopes": []})
        writer_done.set()

    writer = Thread(target=mutate_revision, daemon=True)
    writer.start()
    result = gateway.execute(
        run_id="R1",
        authority=_authority("rev-A"),
        tool_id="finance.pay",
        payload={"amount": 10},
        business_key="PAY-FENCED",
    )
    writer.join(timeout=1.0)

    assert result.decision.value == "ALLOW"
    assert adapter.observed_revision == "rev-A"
    assert writer_done.is_set()
    assert not writer.is_alive()
    assert source.read("AUT-T")["revision_ref"] == "rev-B"


def test_sourceport_read_without_revision_fence_fails_closed_before_ledger_or_tool():
    class ReadOnlySource:
        def __init__(self):
            self.records = {
                "AUT-T": {"revision_ref": "rev-A"},
                "AUT-X": {"revision_ref": "rev-A"},
                "AUT-N": {"revision_ref": "rev-A"},
            }

        def read(self, source_ref):
            return dict(self.records[source_ref])

    source = ReadOnlySource()
    adapter = FakeToolAdapter({"ok": True})
    gateway, manager = _gateway(source, adapter)

    with pytest.raises(HarnessResolutionError) as exc:
        gateway.execute(
            run_id="R1",
            authority=_authority("rev-A"),
            tool_id="finance.pay",
            payload={"amount": 10},
            business_key="PAY-NO-FENCE",
        )

    assert "AUTHORITY_UNRESOLVED" in str(exc.value)
    assert "revision fence" in str(exc.value).lower()
    assert adapter.calls == []
    assert manager.state_port._idempotency_records == {}
    audits = list(manager.state_port._revalidation_records.values())
    assert len(audits) == 1
    assert audits[0]["outcome"] == "REVISION_FENCE_UNAVAILABLE"
