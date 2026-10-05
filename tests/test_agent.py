import json
from types import SimpleNamespace

import pytest

from schemaguard import agent as agent_module
from schemaguard.agent import StructuredAgent, StructuredOutputError, Tool
from schemaguard.schemas import WeatherReport, WeatherToolOutput

GOOD = {
    "city": "Bengaluru",
    "temperature_c": 29.5,
    "condition": "partly cloudy",
    "humidity_pct": 64,
}
BAD = {**GOOD, "temperature_c": 500}  # violates le=60


def tool_call(name: str, payload, call_id: str) -> SimpleNamespace:
    """Build a fake OpenAI response with one function call.

    If payload is a string it is sent as-is (to simulate broken JSON).
    """
    arguments = payload if isinstance(payload, str) else json.dumps(payload)
    call = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )
    message = SimpleNamespace(content=None, tool_calls=[call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    """Stands in for OpenAI(); returns queued responses in order."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []
        completions = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=completions)

    def _create(self, **kwargs):
        # copy the messages list so later appends don't change our record
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._responses.pop(0)


def make_agent(monkeypatch, responses, **kwargs):
    fake = FakeClient(responses)
    monkeypatch.setattr(agent_module, "OpenAI", lambda: fake)
    return StructuredAgent(**kwargs), fake


def test_recovers_after_invalid_output(monkeypatch, caplog):
    agent, fake = make_agent(
        monkeypatch,
        [tool_call("emit_result", BAD, "t1"), tool_call("emit_result", GOOD, "t2")],
    )

    result = agent.run("Weather in Bengaluru?", WeatherReport)

    assert result.temperature_c == 29.5
    assert len(fake.calls) == 2  # one failure, one success

    # The model was told what went wrong
    feedback = fake.calls[1]["messages"][-1]
    assert feedback["role"] == "tool"
    assert feedback["content"].startswith("ERROR:")
    assert "temperature_c" in feedback["content"]

    # The failure was logged
    assert "Validation failed" in caplog.text


def test_recovers_after_broken_json(monkeypatch):
    agent, fake = make_agent(
        monkeypatch,
        [tool_call("emit_result", "{not valid json", "t1"), tool_call("emit_result", GOOD, "t2")],
    )

    result = agent.run("Weather in Bengaluru?", WeatherReport)

    assert result.city == "Bengaluru"
    feedback = fake.calls[1]["messages"][-1]
    assert "not valid JSON" in feedback["content"]


def test_gives_up_after_max_retries(monkeypatch):
    agent, fake = make_agent(
        monkeypatch,
        [tool_call("emit_result", BAD, f"t{i}") for i in range(5)],
        max_retries=2,
    )

    with pytest.raises(StructuredOutputError):
        agent.run("Weather in Bengaluru?", WeatherReport)

    assert len(fake.calls) == 3  # stops once failures exceed max_retries


def test_invalid_tool_output_is_reported_to_model(monkeypatch):
    weather = Tool(
        name="get_weather",
        description="Get weather.",
        input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
        func=lambda city: {"temp_c": 20, "humidity": 450, "sky": "clear"},  # humidity invalid
        output_model=WeatherToolOutput,
    )
    agent, fake = make_agent(
        monkeypatch,
        [
            tool_call("get_weather", {"city": "Bengaluru"}, "t1"),
            tool_call("emit_result", GOOD, "t2"),
        ],
        tools=[weather],
    )

    result = agent.run("Weather in Bengaluru?", WeatherReport)

    assert result.city == "Bengaluru"
    feedback = fake.calls[1]["messages"][-1]
    assert feedback["content"].startswith("ERROR:")
    assert "humidity" in feedback["content"]
    
    