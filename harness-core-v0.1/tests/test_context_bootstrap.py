import pytest

from harness.adapters.sources.in_memory import InMemorySourceAdapter
from harness.contracts import AuthorityContext, ChainType, ResolutionChain, ResolutionStatus
from harness.core.context import BootstrapResolver, ContextBuilder


class CountingSource(InMemorySourceAdapter):
    def __init__(self, records):
        super().__init__(records)
        self.reads = []

    def read(self, source_ref):
        self.reads.append(source_ref)
        return super().read(source_ref)


def chain(kind, refs, status=ResolutionStatus.RESOLVED):
    return ResolutionChain(chain_type=kind, status=status, authority_ref=f"AUT-{kind.value}", applicable_refs=refs)


def authority(technical_refs=("TECH-1",), normative_refs=("NORM-1",)):
    return AuthorityContext(
        authority_context_id="AC-1", run_id="R1", agent_id="A1",
        tactical_authority_refs=["AUT-T"], technical_authority_refs=["AUT-X"], normative_authority_refs=["AUT-N"],
        tactical_chain_trace=chain(ChainType.TACTICAL, ["TACT-REQ", "TACT-OPT"]),
        technical_chain_trace=chain(ChainType.TECHNICAL, list(technical_refs)),
        normative_chain_trace=chain(ChainType.NORMATIVE, list(normative_refs)),
    )


def records():
    return {
        "TASK": {"tarefa_trabalho_id":"TT-1", "current_order":"execute", "task_state_ref":"STATE-1", "workspace_ref":"WS-1"},
        "TACT-REQ": {"excerpt_ref":"CTX-TACT-REQ", "estimated_tokens":40, "priority":10, "required":True},
        "TACT-OPT": {"excerpt_ref":"CTX-TACT-OPT", "estimated_tokens":80, "priority":1},
        "TECH-1": {"excerpt_ref":"CTX-TECH-1", "estimated_tokens":30, "priority":5},
        "TECH-2": {"excerpt_ref":"CTX-TECH-2", "estimated_tokens":35, "priority":9},
        "NORM-1": {"excerpt_ref":"CTX-NORM-1", "estimated_tokens":20, "priority":10, "required":True},
    }


def test_bootstrap_resolves_three_segmented_routes():
    plan = BootstrapResolver().resolve(authority())
    assert "TACT-REQ" in plan.tactical_refs
    assert plan.technical_refs == ("TECH-1",)
    assert plan.normative_refs == ("NORM-1",)


def test_context_builder_materializes_minimum_context_with_provenance():
    source = CountingSource(records())
    result = ContextBuilder(source).build("R1", authority(), "TASK", max_context_tokens=100)
    assert result.task_context.tactical_context_refs == ["CTX-TACT-REQ"]
    assert result.task_context.technical_context_refs == ["CTX-TECH-1"]
    assert result.task_context.normative_context_refs == ["CTX-NORM-1"]
    assert "CTX-TACT-OPT" not in result.provenance
    assert result.provenance["CTX-TECH-1"] == ChainType.TECHNICAL
    assert result.estimated_tokens == 90


def test_partial_rebootstrap_reads_only_changed_chain_context_sources():
    source = CountingSource(records())
    builder = ContextBuilder(source)
    previous = builder.build("R1", authority(), "TASK", max_context_tokens=200)
    source.reads.clear()

    updated = authority(technical_refs=("TECH-2",))
    rebuilt = builder.rebuild_partial(previous, updated, "TASK", {ChainType.TECHNICAL}, max_context_tokens=200)

    assert rebuilt.task_context.tactical_context_refs == previous.task_context.tactical_context_refs
    assert rebuilt.task_context.normative_context_refs == previous.task_context.normative_context_refs
    assert rebuilt.task_context.technical_context_refs == ["CTX-TECH-2"]
    assert source.reads == ["TASK", "TECH-2"]


def test_required_context_fails_closed_when_budget_is_insufficient():
    source = CountingSource(records())
    with pytest.raises(ValueError, match="insufficient"):
        ContextBuilder(source).build("R1", authority(), "TASK", max_context_tokens=30)
