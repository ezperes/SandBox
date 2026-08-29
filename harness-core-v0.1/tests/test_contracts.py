import pytest
from pydantic import ValidationError
from harness.contracts import AgentIdentity, AuthorityContext, ChainType, CrossDomainEvent, Decision, DomainObligation, ObligationStatus, ResolutionChain, ResolutionStatus, VerificationResult, VerificationStatus

def chain(kind, status=ResolutionStatus.RESOLVED):
    return ResolutionChain(chain_type=kind, authority_ref="AUT-1", route_refs=["SRC-1"], status=status)

def test_agent_identity_requires_explicit_technical_authority():
    with pytest.raises(ValidationError):
        AgentIdentity(agent_id="A1", name="x", mission_ref="M1", scope_ref="S1", organizational_path_ref="ORG1", tactical_authority_ref="AUT-T", technical_authority_ref="", source_ref="LIVRO")

def test_authority_context_serializes_three_chains():
    ctx = AuthorityContext(authority_context_id="AC1", run_id="R1", agent_id="A1", tactical_authority_refs=["AUT-T"], technical_authority_refs=["AUT-X"], normative_authority_refs=["AUT-N"], tactical_chain_trace=chain(ChainType.TACTICAL), technical_chain_trace=chain(ChainType.TECHNICAL), normative_chain_trace=chain(ChainType.NORMATIVE))
    data = ctx.model_dump(mode="json")
    assert data["tactical_chain_trace"]["chain_type"] == "TACTICAL"
    assert data["technical_chain_trace"]["chain_type"] == "TECHNICAL"
    assert data["normative_chain_trace"]["chain_type"] == "NORMATIVE"

def test_cross_domain_event_preserves_correlation_and_obligation():
    event = CrossDomainEvent(cross_domain_event_id="X1", correlation_id="C1", run_id="R1", tarefa_trabalho_id="MT-1", event_type="RETURN_CREATED", origin_domain="COMMERCIAL", origin_agent_id="A1", business_object_ref="ORDER-1", facts={"reason":"return"}, affected_domains=["FINANCE"], required_obligations=[DomainObligation(destination_domain="FINANCE", obligation_type="REFUND", status=ObligationStatus.PENDING)])
    assert event.correlation_id == "C1"
    assert event.required_obligations[0].destination_domain == "FINANCE"

def test_approved_verification_requires_evidence():
    with pytest.raises(ValidationError):
        VerificationResult(verification_id="V1", run_id="R1", subject_ref="S", status=VerificationStatus.APPROVED, verifier_id="Q1")

def test_decision_enum_contains_escalate():
    assert Decision.ESCALATE.value == "ESCALATE"
