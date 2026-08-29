from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from ._models import ContractModel, utcnow


class ModelRequest(ContractModel):
    model_request_id: str
    run_id: str
    agent_id: str
    task_context_ref: str
    authority_context_ref: str
    messages: list[dict[str, Any]]
    model_capability: str = "general"
    preferred_provider: str | None = None
    preferred_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def refs_and_messages_are_explicit(self):
        for field in ("model_request_id", "run_id", "agent_id", "task_context_ref", "authority_context_ref"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must be explicit")
        if not self.messages:
            raise ValueError("messages must not be empty")
        return self


class ModelSelection(ContractModel):
    model_selection_id: str
    model_request_id: str
    provider: str
    model: str
    adapter_id: str
    reason: str
    selected_at: datetime = Field(default_factory=utcnow)


class ModelResponse(ContractModel):
    model_response_id: str
    model_request_id: str
    run_id: str
    provider: str
    model: str
    content: str
    finish_reason: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    raw_response_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=utcnow)
