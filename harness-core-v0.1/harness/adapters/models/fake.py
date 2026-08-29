from __future__ import annotations

from uuid import uuid4

from harness.contracts import ModelRequest, ModelResponse


class FakeModelAdapter:
    def __init__(self, provider: str = "fake", model: str = "fake-general", prefix: str = ""):
        self.provider = provider
        self.model = model
        self.prefix = prefix
        self.calls: list[ModelRequest] = []

    def invoke(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request.model_copy(deep=True))
        last = request.messages[-1]
        content = str(last.get("content", ""))
        return ModelResponse(
            model_response_id=f"MRSP-{uuid4()}",
            model_request_id=request.model_request_id,
            run_id=request.run_id,
            provider=self.provider,
            model=self.model,
            content=f"{self.prefix}{content}",
            finish_reason="stop",
            tokens_in=max(1, len(str(request.messages)) // 4),
            tokens_out=max(1, len(content) // 4),
        )
