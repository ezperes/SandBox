from types import SimpleNamespace

from harness.adapters.models import FakeModelAdapter, OpenAIResponsesAdapter
from harness.contracts import AgentIdentity, ModelRequest
from harness.core.routing import ModelRouter, RegisteredModel


def request(**overrides):
    base = dict(
        model_request_id="MREQ-1",
        run_id="RUN-1",
        agent_id="AGT-1",
        task_context_ref="TC-1",
        authority_context_ref="AC-1",
        messages=[{"role": "user", "content": "hello"}],
        model_capability="general",
    )
    base.update(overrides)
    return ModelRequest(**base)


def identity():
    return AgentIdentity(
        agent_id="AGT-1", name="Agent", mission_ref="M-1", scope_ref="S-1",
        organizational_path_ref="ORG-1", tactical_authority_ref="TACT-1",
        technical_authority_ref="MESMA_CADEIA_TATICA", source_ref="SRC-1",
    )


def test_router_selects_highest_priority_compatible_model_without_touching_identity():
    agent_before = identity()
    low = FakeModelAdapter(provider="p1", model="m1")
    high = FakeModelAdapter(provider="p2", model="m2")
    router = ModelRouter()
    router.register(RegisteredModel("p1", "m1", "A1", low, {"general"}, priority=1))
    router.register(RegisteredModel("p2", "m2", "A2", high, {"general"}, priority=5))

    result = router.invoke(request())

    assert result.selection.provider == "p2"
    assert result.response.model == "m2"
    assert agent_before == identity()
    assert agent_before.agent_id == "AGT-1"


def test_router_honors_preferred_provider_and_model():
    a = FakeModelAdapter(provider="openai", model="gpt-test")
    b = FakeModelAdapter(provider="other", model="other-test")
    router = ModelRouter()
    router.register(RegisteredModel("openai", "gpt-test", "openai", a, {"general"}, priority=0))
    router.register(RegisteredModel("other", "other-test", "other", b, {"general"}, priority=10))

    result = router.invoke(request(preferred_provider="openai", preferred_model="gpt-test"))
    assert result.selection.provider == "openai"
    assert len(a.calls) == 1
    assert len(b.calls) == 0


def test_openai_responses_adapter_translates_without_sdk_dependency():
    class StubResponses:
        def create(self, **kwargs):
            assert kwargs["model"] == "gpt-test"
            assert kwargs["input"][0]["content"] == "hello"
            return SimpleNamespace(
                id="resp_1", output_text="world", status="completed",
                usage=SimpleNamespace(input_tokens=3, output_tokens=2),
            )

    adapter = OpenAIResponsesAdapter(StubResponses(), model="gpt-test")
    response = adapter.invoke(request())
    assert response.provider == "openai"
    assert response.model == "gpt-test"
    assert response.content == "world"
    assert response.tokens_in == 3
    assert response.tokens_out == 2
    assert response.metadata["provider_response_id"] == "resp_1"


def test_router_rejects_adapter_response_for_wrong_selected_model():
    bad = FakeModelAdapter(provider="wrong", model="wrong")
    router = ModelRouter()
    router.register(RegisteredModel("expected", "expected", "bad", bad, {"general"}))
    try:
        router.invoke(request())
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "selected provider/model" in str(exc)
