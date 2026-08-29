from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from harness.contracts import ModelRequest, ModelResponse, ModelSelection
from harness.ports import ModelPort


@dataclass(slots=True)
class RegisteredModel:
    provider: str
    model: str
    adapter_id: str
    adapter: ModelPort
    capabilities: set[str]
    priority: int = 0


@dataclass(slots=True)
class RoutedModelResponse:
    selection: ModelSelection
    response: ModelResponse


class ModelRouter:
    """Select model resources without changing institutional agent identity."""

    def __init__(self):
        self._models: list[RegisteredModel] = []

    def register(self, model: RegisteredModel) -> None:
        self._models = [
            item for item in self._models
            if not (item.provider == model.provider and item.model == model.model)
        ]
        self._models.append(model)

    def _select(self, request: ModelRequest) -> RegisteredModel:
        candidates = [m for m in self._models if request.model_capability in m.capabilities]
        if request.preferred_provider:
            candidates = [m for m in candidates if m.provider == request.preferred_provider]
        if request.preferred_model:
            candidates = [m for m in candidates if m.model == request.preferred_model]
        if not candidates:
            raise LookupError("no compatible model registered")
        return sorted(candidates, key=lambda item: (-item.priority, item.provider, item.model))[0]

    def invoke(self, request: ModelRequest) -> RoutedModelResponse:
        chosen = self._select(request)
        selection = ModelSelection(
            model_selection_id=f"MS-{uuid4()}",
            model_request_id=request.model_request_id,
            provider=chosen.provider,
            model=chosen.model,
            adapter_id=chosen.adapter_id,
            reason="preferred match" if (request.preferred_provider or request.preferred_model) else "highest priority compatible model",
        )
        response = chosen.adapter.invoke(request)
        if response.model_request_id != request.model_request_id or response.run_id != request.run_id:
            raise ValueError("model adapter returned response for another request/run")
        if response.provider != chosen.provider or response.model != chosen.model:
            raise ValueError("model adapter response does not match selected provider/model")
        return RoutedModelResponse(selection=selection, response=response)
