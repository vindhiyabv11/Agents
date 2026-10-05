import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .logging_config import get_logger
from .validator import format_errors, validate_payload

T = TypeVar("T", bound=BaseModel)
log = get_logger()


class StructuredOutputError(Exception):
    """Raised when the model never produces schema-valid output."""


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    func: Callable[..., Any]
    output_model: type[BaseModel]  # contract for the tool's response

    def to_api(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class StructuredAgent:
    def __init__(
        self,
        tools: list[Tool] | None = None,
        max_retries: int = 3,
        max_turns: int = 10,
        model: str | None = None,
    ):
        self.client = OpenAI()  # reads OPENAI_API_KEY
        self.model = model or os.getenv("SCHEMAGUARD_MODEL", "gpt-4o-mini")
        self.tools = {t.name: t for t in (tools or [])}
        self.max_retries = max_retries
        self.max_turns = max_turns

    def run(self, prompt: str, schema: type[T]) -> T:
        emit_tool = {
            "type": "function",
            "function": {
                "name": "emit_result",
                "description": "Submit the final answer. Arguments must match the schema exactly.",
                "parameters": schema.model_json_schema(),
            },
        }
        api_tools = [t.to_api() for t in self.tools.values()] + [emit_tool]
        # Force the structured function only when no other tools are in play
        tool_choice: Any = (
            {"type": "function", "function": {"name": "emit_result"}}
            if not self.tools
            else "auto"
        )

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "Use tools as needed, then finish by calling emit_result.",
            },
            {"role": "user", "content": prompt},
        ]
        failures = 0

        for _turn in range(self.max_turns):
            resp = self.client.chat.completions.create(
                model=self.model,
                tools=api_tools,
                tool_choice=tool_choice,
                messages=messages,
            )
            msg = resp.choices[0].message
            tool_calls = msg.tool_calls or []
            messages.append(self._assistant_message(msg.content, tool_calls))

            final: T | None = None

            for call in tool_calls:
                name = call.function.name

                # Step 1: parse the JSON string the model sent
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError as exc:
                    log.warning(
                        f"JSON parse error in call to {name}",
                        extra={
                            "extra_data": {
                                "source": "model",
                                "error": str(exc),
                                "raw_arguments": call.function.arguments,
                            }
                        },
                    )
                    if name == "emit_result":
                        failures += 1
                    messages.append(
                        self._tool_message(call.id, f"Arguments were not valid JSON: {exc}", True)
                    )
                    continue

                # Step 2: validate / execute
                if name == "emit_result":
                    try:
                        final = validate_payload(
                            schema, args, source="model", attempt=failures + 1
                        )
                    except ValidationError as exc:
                        failures += 1
                        messages.append(
                            self._tool_message(call.id, format_errors(exc), True)
                        )
                else:
                    messages.append(self._run_tool(call.id, name, args, failures + 1))

            if final is not None:
                return final

            if failures > self.max_retries:
                raise StructuredOutputError(
                    f"No valid {schema.__name__} after {failures} failed attempts"
                )

            if not tool_calls:  # model replied with plain text
                messages.append(
                    {"role": "user", "content": "Please call emit_result with valid data."}
                )

        raise StructuredOutputError("Max turns reached without a valid result")

    def _run_tool(
        self, call_id: str, name: str, args: dict[str, Any], attempt: int
    ) -> dict[str, Any]:
        tool = self.tools.get(name)
        if tool is None:
            return self._tool_message(call_id, f"Unknown tool: {name}", True)
        try:
            raw = tool.func(**args)
            validated = validate_payload(
                tool.output_model, raw, source=f"tool:{tool.name}", attempt=attempt
            )
            return self._tool_message(call_id, validated.model_dump_json(), False)
        except ValidationError as exc:
            return self._tool_message(call_id, format_errors(exc), True)
        except Exception as exc:  # noqa: BLE001 - tool code can raise anything
            log.error(f"Tool {tool.name} raised {exc!r}")
            return self._tool_message(call_id, f"Tool error: {exc}", True)

    @staticmethod
    def _assistant_message(content: str | None, tool_calls: list[Any]) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {
                        "name": c.function.name,
                        "arguments": c.function.arguments,
                    },
                }
                for c in tool_calls
            ]
        return message

    @staticmethod
    def _tool_message(call_id: str, content: str, is_error: bool) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "content": f"ERROR: {content}" if is_error else content,
        }
    