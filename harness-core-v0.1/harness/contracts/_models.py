from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, ClassVar
from pydantic import BaseModel, ConfigDict, Field, model_validator

class RunStatus(StrEnum):
    CREATED="CREATED"; READY="READY"; RUNNING="RUNNING"; INTERRUPTED="INTERRUPTED"; WAITING_APPROVAL="WAITING_APPROVAL"; WAITING_EXTERNAL="WAITING_EXTERNAL"; REWORK="REWORK"; FAILED="FAILED"; COMPLETED="COMPLETED"; CANCELLED="CANCELLED"
class RiskLevel(StrEnum): LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"; CRITICAL="CRITICAL"
class VerificationStatus(StrEnum): APPROVED="APPROVED"; REJECTED="REJECTED"; PARTIAL="PARTIAL"; NOT_RUN="NOT_RUN"
class Decision(StrEnum): ALLOW="ALLOW"; DENY="DENY"; REQUIRE_APPROVAL="REQUIRE_APPROVAL"; ESCALATE="ESCALATE"
class ChainType(StrEnum): TACTICAL="TACTICAL"; TECHNICAL="TECHNICAL"; NORMATIVE="NORMATIVE"
class ResolutionStatus(StrEnum): RESOLVED="RESOLVED"; SAME_AS_TACTICAL="SAME_AS_TACTICAL"; NOT_APPLICABLE_JUSTIFIED="NOT_APPLICABLE_JUSTIFICADO"; UNRESOLVED="UNRESOLVED"
class ObligationStatus(StrEnum): PENDING="PENDING"; ACCEPTED="ACCEPTED"; IN_PROGRESS="IN_PROGRESS"; COMPLETED="COMPLETED"; REJECTED="REJECTED"; FAILED="FAILED"
class HarnessErrorCode(StrEnum):
    IDENTITY_UNRESOLVED="IDENTITY_UNRESOLVED"; AUTHORITY_UNRESOLVED="AUTHORITY_UNRESOLVED"; ACTION_FORBIDDEN="ACTION_FORBIDDEN"; APPROVAL_REQUIRED="APPROVAL_REQUIRED"; SCHEMA_INVALID="SCHEMA_INVALID"; CONTRACT_VERSION_UNSUPPORTED="CONTRACT_VERSION_UNSUPPORTED"; TOOL_UNAVAILABLE="TOOL_UNAVAILABLE"; TOOL_TIMEOUT="TOOL_TIMEOUT"; SIDE_EFFECT_UNKNOWN="SIDE_EFFECT_UNKNOWN"; RETRY_BLOCKED="RETRY_BLOCKED"; DELEGATION_FORBIDDEN="DELEGATION_FORBIDDEN"; MAX_HOPS_EXCEEDED="MAX_HOPS_EXCEEDED"; CHECKPOINT_INVALID="CHECKPOINT_INVALID"; VERIFICATION_FAILED="VERIFICATION_FAILED"; MEMORY_ACCESS_DENIED="MEMORY_ACCESS_DENIED"; RUNTIME_UNAVAILABLE="RUNTIME_UNAVAILABLE"; COMPETENCE_INSUFFICIENT="COMPETENCE_INSUFFICIENT"

class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    harness_contract_version: str = Field(default="0.1", pattern=r"^0\.1$")
    CONTRACT_VERSION: ClassVar[str] = "0.1"

def utcnow(): return datetime.now(timezone.utc)

class AgentIdentity(ContractModel):
    agent_id:str; name:str; mission_ref:str; scope_ref:str; organizational_path_ref:str; tactical_authority_ref:str; technical_authority_ref:str; source_ref:str
    normative_authority_ref:str|None=None; capabilities_ref:str|None=None; source_revision_ref:str|None=None; resolved_at:datetime=Field(default_factory=utcnow)
    @model_validator(mode="after")
    def explicit_refs(self):
        for field in ("organizational_path_ref","tactical_authority_ref","technical_authority_ref","source_ref"):
            if not getattr(self,field).strip(): raise ValueError(f"{field} must be explicit")
        return self

class ResolutionChain(ContractModel):
    chain_type:ChainType; status:ResolutionStatus; authority_ref:str|None=None; route_refs:list[str]=Field(default_factory=list); applicable_refs:list[str]=Field(default_factory=list); loaded_excerpt_refs:list[str]=Field(default_factory=list); source_revision_refs:list[str]=Field(default_factory=list); justification:str|None=None
class AuthoritySnapshot(ContractModel):
    snapshot_id:str; identity_source_revision_ref:str|None=None; tactical_source_revision_refs:list[str]=Field(default_factory=list); technical_source_revision_refs:list[str]=Field(default_factory=list); normative_source_revision_refs:list[str]=Field(default_factory=list); captured_at:datetime=Field(default_factory=utcnow)
class AuthorityContext(ContractModel):
    authority_context_id:str; run_id:str; agent_id:str; tactical_authority_refs:list[str]; technical_authority_refs:list[str]; tactical_chain_trace:ResolutionChain; technical_chain_trace:ResolutionChain
    normative_authority_refs:list[str]=Field(default_factory=list); normative_chain_trace:ResolutionChain|None=None; allowed_scopes:list[str]=Field(default_factory=list); forbidden_scopes:list[str]=Field(default_factory=list); competence_refs:list[str]=Field(default_factory=list); registration_prerogatives:list[str]=Field(default_factory=list); authority_snapshot_ref:str|None=None; resolved_at:datetime=Field(default_factory=utcnow)
class TaskContext(ContractModel):
    task_context_id:str; run_id:str; tarefa_trabalho_id:str; current_order:str; task_state_ref:str; authority_context_ref:str; workspace_ref:str; bootstrap_trace_ref:str
    tactical_context_refs:list[str]=Field(default_factory=list); technical_context_refs:list[str]=Field(default_factory=list); normative_context_refs:list[str]=Field(default_factory=list); procedural_refs:list[str]=Field(default_factory=list); knowledge_refs:list[str]=Field(default_factory=list); risk_refs:list[str]=Field(default_factory=list); memory_refs:list[str]=Field(default_factory=list); built_at:datetime=Field(default_factory=utcnow)
class HarnessRun(ContractModel):
    run_id:str; tarefa_trabalho_id:str; agent_id:str; correlation_id:str; workspace_ref:str; run_state_ref:str; authority_context_ref:str
    status:RunStatus=RunStatus.CREATED; task_context_ref:str|None=None; parent_run_id:str|None=None; created_at:datetime=Field(default_factory=utcnow); updated_at:datetime=Field(default_factory=utcnow)
class RunState(ContractModel):
    run_state_id:str; run_id:str; tarefa_trabalho_id:str; status:RunStatus; current_step:str|None=None; completed_steps:list[str]=Field(default_factory=list); pending_steps:list[str]=Field(default_factory=list); artifact_refs:list[str]=Field(default_factory=list); decision_refs:list[str]=Field(default_factory=list); checkpoint_ref:str|None=None; updated_at:datetime=Field(default_factory=utcnow)
class Checkpoint(ContractModel):
    checkpoint_id:str; run_id:str; run_state_ref:str; validated_step:str; resume_instruction:str; artifact_refs:list[str]=Field(default_factory=list); evidence_refs:list[str]=Field(default_factory=list); created_at:datetime=Field(default_factory=utcnow)
    @model_validator(mode="after")
    def resume_required(self):
        if not self.resume_instruction.strip(): raise ValueError("resume_instruction must be explicit")
        return self
class Evidence(ContractModel):
    evidence_id:str; run_id:str; type:str; subject_ref:str; location_ref:str; produced_by:str; criterion_ref:str|None=None; hash:str|None=None; observed_at:datetime=Field(default_factory=utcnow)
class VerificationResult(ContractModel):
    verification_id:str; run_id:str; subject_ref:str; status:VerificationStatus; verifier_id:str; criterion_refs:list[str]=Field(default_factory=list); evidence_refs:list[str]=Field(default_factory=list); findings:list[str]=Field(default_factory=list); required_rework:list[str]=Field(default_factory=list); verified_at:datetime=Field(default_factory=utcnow)
    @model_validator(mode="after")
    def approved_has_evidence(self):
        if self.status==VerificationStatus.APPROVED and not self.evidence_refs: raise ValueError("APPROVED requires evidence_refs")
        return self
class DomainObligation(ContractModel):
    destination_domain:str; obligation_type:str; status:ObligationStatus=ObligationStatus.PENDING; destination_agent_or_fraction_ref:str|None=None; required_result_ref:str|None=None; evidence_refs:list[str]=Field(default_factory=list)
class CrossDomainEvent(ContractModel):
    cross_domain_event_id:str; correlation_id:str; run_id:str; tarefa_trabalho_id:str; event_type:str; origin_domain:str; origin_agent_id:str; business_object_ref:str; facts:dict[str,Any]
    occurred_at:datetime=Field(default_factory=utcnow); evidence_refs:list[str]=Field(default_factory=list); affected_domains:list[str]=Field(default_factory=list); required_obligations:list[DomainObligation]=Field(default_factory=list)
class InstructionProfile(ContractModel):
    instruction_profile_id:str; run_id:str; agent_id:str; permanent_instruction_refs:list[str]=Field(default_factory=list); tactical_instruction_refs:list[str]=Field(default_factory=list); technical_instruction_refs:list[str]=Field(default_factory=list); normative_instruction_refs:list[str]=Field(default_factory=list); executor_native_projection_ref:str|None=None
class TelemetryEvent(ContractModel):
    telemetry_event_id:str; run_id:str; correlation_id:str; event_type:str; agent_id:str; tarefa_trabalho_id:str; timestamp:datetime=Field(default_factory=utcnow); model:str|None=None; provider:str|None=None; tool_id:str|None=None; latency_ms:int|None=None; tokens_in:int|None=None; tokens_out:int|None=None; cost:float|None=None; retry_count:int|None=None; success:bool|None=None; verification_status:VerificationStatus|None=None; metadata:dict[str,Any]=Field(default_factory=dict)
