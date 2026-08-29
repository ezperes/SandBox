from __future__ import annotations

from uuid import uuid4

from harness.contracts import ModelRequest, ModelResponse


class OpenAIResponsesAdapter:
    """Thin adapter for an injected OpenAI-compatible Responses client.

    The Core never imports the OpenAI SDK. Production composition may inject
    `OpenAI().responses`; tests inject a stub with the same `create` surface.
    """

    def __init__(self, responses_client, *, model: str, provider: str = "openai"):
        self.client = responses_client
        self.model = model
        self.provider = provider

    def invoke(self, request: ModelRequest) -> ModelResponse:
        kwargs = {
            "model": self.model,
            "input": request.messages,
        }
        if request.max_output_tokens is not None:
            kwargs["max_output_tokens"] = request.max_output_tokens
        response = self.client.create(**kwargs)
        usage = getattr(response, "usage", None)
        return ModelResponse(
            model_response_id=f"MRSP-{uuid4()}",
            model_request_id=request.model_request_id,
            run_id=request.run_id,
            provider=self.provider,
            model=self.model,
            content=str(getattr(response, "output_text", "")),
            finish_reason=str(getattr(response, "status", "completed")),
            tokens_in=getattr(usage, "input_tokens", None) if usage else None,
            tokens_out=getattr(usage, "output_tokens", None) if usage else None,
            metadata={"provider_response_id": getattr(response, "id", None)},
        )
