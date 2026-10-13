import json

import pytest

from lifecfo.llm import (
    PROVIDERS,
    ChatMessage,
    LLMError,
    LLMErrorKind,
    LLMSettings,
    OpenAICompatibleClient,
    ToolSpec,
    build_client,
    load_env_file,
)


def settings(**overrides) -> LLMSettings:
    env = {"LIFECFO_LLM_PROVIDER": "groq", "LIFECFO_LLM_MODEL": "test-model",
           "GROQ_API_KEY": "secret-key"}
    env.update(overrides)
    return LLMSettings.from_env(env)


def ok_body(content="hello", tool_calls=None) -> str:
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return json.dumps({"choices": [{"message": message}]})


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": json.loads(body)})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def client(transport, **overrides) -> tuple[OpenAICompatibleClient, list[float]]:
    waits: list[float] = []
    return OpenAICompatibleClient(settings(**overrides), transport, waits.append), waits


def test_default_is_no_llm_and_needs_nothing():
    s = LLMSettings.from_env({})
    assert s.provider == "none" and not s.uses_llm and s.problem is None
    assert build_client(s) is None


@pytest.mark.parametrize(
    ("provider", "key_env", "host"),
    [("gemini", "GEMINI_API_KEY", "generativelanguage.googleapis.com"),
     ("groq", "GROQ_API_KEY", "api.groq.com")],
)
def test_free_hosted_providers_use_their_own_key_and_endpoint(provider, key_env, host):
    s = LLMSettings.from_env({"LIFECFO_LLM_PROVIDER": provider, "LIFECFO_LLM_MODEL": "m",
                              key_env: "k"})
    assert s.uses_llm and host in s.base_url and s.api_key == "k"
    assert PROVIDERS[provider].free


def test_ollama_needs_no_key_and_stays_local():
    s = LLMSettings.from_env({"LIFECFO_LLM_PROVIDER": "ollama", "LIFECFO_LLM_MODEL": "m"})
    assert s.uses_llm and s.api_key is None
    assert s.base_url == "http://localhost:11434/v1"
    assert PROVIDERS["ollama"].local


def test_only_explicit_custom_provider_is_marked_not_free():
    assert [name for name, preset in PROVIDERS.items() if not preset.free] == ["custom"]


@pytest.mark.parametrize(
    ("env", "expected"),
    [({"LIFECFO_LLM_PROVIDER": "groq", "GROQ_API_KEY": "k"}, "LIFECFO_LLM_MODEL"),
     ({"LIFECFO_LLM_PROVIDER": "groq", "LIFECFO_LLM_MODEL": "m"}, "GROQ_API_KEY"),
     ({"LIFECFO_LLM_PROVIDER": "custom", "LIFECFO_LLM_MODEL": "m"}, "LIFECFO_LLM_BASE_URL"),
     ({"LIFECFO_LLM_PROVIDER": "chatgpt"}, "Unknown")],
)
def test_incomplete_configuration_is_reported_not_guessed(env, expected):
    s = LLMSettings.from_env(env)
    assert expected in s.problem
    assert not s.uses_llm


def test_request_shape_and_plain_answer():
    transport = FakeTransport((200, {}, ok_body("hi")))
    c, _ = client(transport)
    tool = ToolSpec(name="t", description="d", parameters={"type": "object", "properties": {}})
    response = c.complete([ChatMessage(role="user", content="q")], [tool])
    assert response.content == "hi" and response.provider == "groq"
    call = transport.calls[0]
    assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    assert call["body"]["model"] == "test-model" and call["body"]["temperature"] == 0
    assert call["body"]["tools"][0]["function"]["name"] == "t"


def test_tool_calls_are_parsed():
    raw = [{"id": "c1", "type": "function",
            "function": {"name": "simulate_income_change", "arguments": '{"percent": -20}'}}]
    c, _ = client(FakeTransport((200, {}, ok_body(None, raw))))
    response = c.complete([ChatMessage(role="user", content="q")])
    assert response.tool_calls[0].name == "simulate_income_change"
    assert response.tool_calls[0].arguments == {"percent": -20}


@pytest.mark.parametrize(
    ("status", "body", "kind"),
    [(401, "{}", LLMErrorKind.AUTH),
     (403, "{}", LLMErrorKind.AUTH),
     (404, "{}", LLMErrorKind.MODEL_NOT_FOUND),
     (400, '{"error": "model `x` does not exist"}', LLMErrorKind.MODEL_NOT_FOUND),
     (400, '{"error": "bad"}', LLMErrorKind.BAD_RESPONSE),
     (429, '{"error": "You exceeded your current quota"}', LLMErrorKind.QUOTA_EXHAUSTED)],
)
def test_errors_that_are_not_retried(status, body, kind):
    transport = FakeTransport((status, {}, body))
    c, waits = client(transport)
    with pytest.raises(LLMError) as raised:
        c.complete([ChatMessage(role="user", content="q")])
    assert raised.value.kind is kind
    assert len(transport.calls) == 1 and waits == []


def test_rate_limit_is_retried_with_capped_wait_then_succeeds():
    transport = FakeTransport(
        (429, {"Retry-After": "600"}, '{"error": "rate limit"}'),
        (200, {}, ok_body("done")),
    )
    c, waits = client(transport)
    assert c.complete([ChatMessage(role="user", content="q")]).content == "done"
    assert waits == [8.0]  # never waits the full ten minutes


def test_rate_limit_gives_up_after_limited_retries():
    transport = FakeTransport(*[(429, {}, '{"error": "rate limit"}')] * 3)
    c, waits = client(transport)
    with pytest.raises(LLMError) as raised:
        c.complete([ChatMessage(role="user", content="q")])
    assert raised.value.kind is LLMErrorKind.RATE_LIMITED
    assert len(transport.calls) == 3 and waits == [1.0, 2.0]


def test_connection_failure_and_server_errors_are_unavailable():
    transport = FakeTransport(ConnectionRefusedError(), (503, {}, ""), TimeoutError())
    c, _ = client(transport)
    with pytest.raises(LLMError) as raised:
        c.complete([ChatMessage(role="user", content="q")])
    assert raised.value.kind is LLMErrorKind.UNAVAILABLE


@pytest.mark.parametrize("body", ["not json", "{}", '{"choices": []}',
                                  json.dumps({"choices": [{"message": {"tool_calls": [
                                      {"function": {"name": "t", "arguments": "[1]"}}]}}]})])
def test_malformed_responses_are_bad_response(body):
    c, _ = client(FakeTransport((200, {}, body)))
    with pytest.raises(LLMError) as raised:
        c.complete([ChatMessage(role="user", content="q")])
    assert raised.value.kind is LLMErrorKind.BAD_RESPONSE


def test_error_text_never_contains_the_api_key():
    c, _ = client(FakeTransport((401, {}, '{"error": "bad key secret-key"}')))
    with pytest.raises(LLMError) as raised:
        c.complete([ChatMessage(role="user", content="q")])
    assert "secret-key" not in str(raised.value)
    assert "secret-key" not in raised.value.user_message


def test_unconfigured_client_does_not_touch_the_network():
    transport = FakeTransport()
    c, _ = client(transport, LIFECFO_LLM_MODEL="")
    with pytest.raises(LLMError) as raised:
        c.complete([ChatMessage(role="user", content="q")])
    assert raised.value.kind is LLMErrorKind.NOT_CONFIGURED and transport.calls == []


def test_env_file_never_overrides_existing_variables(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nLIFECFO_LLM_PROVIDER=groq\nNEW_LIFECFO_VAR='x'\n",
                        encoding="utf-8")
    monkeypatch.setenv("LIFECFO_LLM_PROVIDER", "none")
    monkeypatch.delenv("NEW_LIFECFO_VAR", raising=False)
    load_env_file(env_file)
    import os

    assert os.environ["LIFECFO_LLM_PROVIDER"] == "none"
    assert os.environ.pop("NEW_LIFECFO_VAR") == "x"
    load_env_file(tmp_path / "missing.env")  # no error
