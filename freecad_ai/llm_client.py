"""LLM client wrapper — DES-004, REQ-011, REQ-022.

Two providers are supported:
  LLMClient          — OpenAI-compatible (OpenAI, Ollama, LM Studio, etc.)
  AnthropicLLMClient — Anthropic native API (Claude models)

Both expose the same async chat() interface: AsyncIterator[str | ToolCall].
make_llm_client(prefs) returns the right one based on prefs.provider.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openai import APIError, AsyncOpenAI

if TYPE_CHECKING:
    from freecad_ai.preferences import AIPreferences

SYSTEM_PROMPT = (
    "You are a FreeCAD assistant. Help the user design 3D parts and architectural elements "
    "by calling the appropriate tools. "
    "When required parameters for a tool call are missing or ambiguous, ask the user for "
    "the missing information instead of guessing. "
    "Prefer small, focused tool calls over complex sequences. "
    "After each tool call succeeds, briefly confirm what was created."
)


class LLMError(Exception):
    """Wraps provider API errors for safe surfacing to the chat panel."""


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


# ---------------------------------------------------------------------------
# OpenAI-compatible client
# ---------------------------------------------------------------------------

class LLMClient:
    _TIMEOUT = 60.0  # seconds — local models can be slow, but 60s surfaces real failures

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=self._TIMEOUT)
        self._model = model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> AsyncIterator[str | ToolCall]:
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                tools=tools if tools else None,  # type: ignore[arg-type]
                stream=True,
            )
        except APIError as exc:
            raise LLMError(str(exc)) from exc

        # Accumulate fragmented tool call args across chunks
        acc: dict[int, dict] = {}

        try:
            async for chunk in stream:  # type: ignore[union-attr]
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.content:
                    yield delta.content

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in acc:
                            acc[idx] = {"id": "", "name": "", "args_str": ""}
                        if tc.id:
                            acc[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            acc[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            acc[idx]["args_str"] += tc.function.arguments
        except APIError as exc:
            raise LLMError(str(exc)) from exc

        # Yield completed tool calls after stream ends
        for entry in sorted(acc.values(), key=lambda e: e["id"]):
            try:
                args = json.loads(entry["args_str"])
            except json.JSONDecodeError:
                args = {}
            yield ToolCall(id=entry["id"], name=entry["name"], args=args)


# ---------------------------------------------------------------------------
# Anthropic (Claude) client
# ---------------------------------------------------------------------------

def _to_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """Convert OpenAI-format message list to (system_prompt, anthropic_messages).

    Key differences:
    - system role extracted as a plain string (Anthropic separate param)
    - assistant + tool_calls → assistant with tool_use content blocks
    - tool role → user message with tool_result content blocks
      (consecutive tool results are merged into one user message)
    """
    system = ""
    out: list[dict] = []

    for msg in messages:
        role = msg["role"]

        if role == "system":
            system = msg.get("content") or ""
            continue

        if role == "user":
            out.append({"role": "user", "content": msg.get("content") or ""})

        elif role == "assistant":
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                content: list[dict] = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for tc in tool_calls:
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except (json.JSONDecodeError, KeyError):
                        args = {}
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": args,
                    })
                out.append({"role": "assistant", "content": content})
            else:
                out.append({"role": "assistant", "content": msg.get("content") or ""})

        elif role == "tool":
            result_block = {
                "type": "tool_result",
                "tool_use_id": msg["tool_call_id"],
                "content": msg.get("content") or "",
            }
            # Merge consecutive tool results into a single user message —
            # Anthropic requires tool results grouped with the preceding user turn.
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(result_block)
            else:
                out.append({"role": "user", "content": [result_block]})

    return system, out


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    """Convert OpenAI tool schemas to Anthropic format.

    OpenAI: {"type": "function", "function": {"name": ..., "parameters": {...}}}
    Anthropic: {"name": ..., "description": ..., "input_schema": {...}}
    """
    result = []
    for tool in tools:
        func = tool.get("function", tool)
        result.append({
            "name": func["name"],
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


class AnthropicLLMClient:
    _MAX_TOKENS = 4096   # max response tokens (separate from context window)
    _TIMEOUT = 60.0      # seconds — surfaces network/auth errors instead of hanging

    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import AsyncAnthropic  # lazy — not required at module load

        self._client = AsyncAnthropic(api_key=api_key, timeout=self._TIMEOUT)
        self._model = model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> AsyncIterator[str | ToolCall]:
        from anthropic import APIError as AnthropicAPIError  # lazy

        system, anthropic_messages = _to_anthropic_messages(messages)
        anthropic_tools = _to_anthropic_tools(tools) if tools else []

        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._MAX_TOKENS,
            "messages": anthropic_messages,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        # Use non-streaming create() — avoids a deadlock between text_stream and
        # get_final_message() where the underlying SSE stream is consumed by
        # text_stream before tool_use blocks can be extracted.
        try:
            response = await self._client.messages.create(**kwargs)
        except AnthropicAPIError as exc:
            raise LLMError(str(exc)) from exc

        for block in response.content:
            if block.type == "text":
                yield block.text
            elif block.type == "tool_use":
                yield ToolCall(id=block.id, name=block.name, args=block.input)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_llm_client(prefs: AIPreferences) -> LLMClient | AnthropicLLMClient:
    """Return the right client based on prefs.provider."""
    if prefs.provider == "anthropic":
        return AnthropicLLMClient(
            api_key=prefs.anthropic_api_key or "",
            model=prefs.model,
        )
    return LLMClient(
        base_url=prefs.base_url,
        api_key=prefs.api_key or "",
        model=prefs.model,
    )
