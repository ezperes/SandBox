import pytest

from harness.adapters.sources import InMemorySourceAdapter
from harness.contracts import Decision, ResolutionStatus
from harness.core.authority import AuthorityResolver
from harness.core.identity import HarnessResolutionError, IdentityResolver


def source():
    return InMemorySourceAdapter({
        "LIVRO:A1": {"revision_ref":"rev-id-1", "identity": {
            "agent_id":"A1", "name":"Agente Comercial", "mission_ref":"M1", "scope_ref":"S1",
            "organizational_path_ref":"DEP-COM/DIR-VENDAS/GT-1", "tactical_authority_ref":"AUT-T",
            "technical_authority_ref":"AUT-X", "normative_authority_ref":"AUT-N", "source_ref":"LIVRO:A1",
        }},
        "AUT-T": {"revision_ref":"rev-t", "route_refs":["COMERCIAL"], "allowed_scopes":["ORDER_READ","RETURN_CREATE"], "competence_refs":["SELL"]},
        "AUT-X": {"revision_ref":"rev-x", "route_refs":["TI"], "allowed_scopes":["RETURN_CREATE"], "competence_refs":["RETURN_WORKFLOW"]},
        "AUT-N": {"revision_ref":"rev-n", "route_refs":["DOGMA"], "forbidden_scopes":["DELETE_LEDGER"], "registration_prerogatives":["RETURN_EVENT"]},
    })


def test_identity_resolves_from_canonical_source_with_revision():
    identity = IdentityResolver(source()).resolve("LIVRO:A1")
    assert identity.agent_id == "A1"
    assert identity.source_revision_ref == "rev-id-1"


def test_missing_identity_fails_closed():
    with pytest.raises(HarnessResolutionError):
        IdentityResolver(source()).resolve("LIVRO:MISSING")


def test_authority_resolves_three_chains_and_snapshot():
    s = source()
    identity = IdentityResolver(s).resolve("LIVRO:A1")
    resolved = AuthorityResolver(s).resolve("RUN-1", identity)
    assert resolved.context.tactical_chain_trace.status == ResolutionStatus.RESOLVED
    assert resolved.context.technical_chain_trace.route_refs == ["TI"]
    assert resolved.context.normative_chain_trace.route_refs == ["DOGMA"]
    assert resolved.snapshot.identity_source_revision_ref == "rev-id-1"
    assert resolved.context.authority_snapshot_ref == resolved.snapshot.snapshot_id


def test_deterministic_decision_precedence():
    s = source(); identity = IdentityResolver(s).resolve("LIVRO:A1")
    ctx = AuthorityResolver(s).resolve("RUN-1", identity).context
    assert AuthorityResolver.decide(ctx, "DELETE_LEDGER") == Decision.DENY
    assert AuthorityResolver.decide(ctx, "RETURN_CREATE", required_competence="RETURN_WORKFLOW") == Decision.ALLOW
    assert AuthorityResolver.decide(ctx, "RETURN_CREATE", required_competence="UNKNOWN") == Decision.ESCALATE
    assert AuthorityResolver.decide(ctx, "RETURN_CREATE", approval_required=True) == Decision.REQUIRE_APPROVAL
    assert AuthorityResolver.decide(ctx, "UNKNOWN_SCOPE") == Decision.ESCALATE


def test_same_tactical_chain_is_explicit_not_implicit():
    s = source()
    raw = s.records["LIVRO:A1"]["identity"]
    raw["technical_authority_ref"] = "MESMA_CADEIA_TATICA"
    identity = IdentityResolver(s).resolve("LIVRO:A1")
    resolved = AuthorityResolver(s).resolve("RUN-2", identity)
    assert resolved.context.technical_chain_trace.status == ResolutionStatus.SAME_AS_TACTICAL
