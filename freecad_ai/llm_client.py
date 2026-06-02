"""LLM client wrapper — DES-004, REQ-011, REQ-022."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import APIError, AsyncOpenAI

SYSTEM_PROMPT = (
    "You are a FreeCAD assistant. Help the user design 3D parts and architectural elements "
    "by calling the appropriate tools. "
    "When required parameters for a tool call are missing or ambiguous, ask the user for "
    "the missing information instead of guessing. "
    "Prefer small, focused tool calls over complex sequences. "
    "After each tool call succeeds, briefly confirm what was created."
)


class LLMError(Exception):
    """Wraps openai API errors for safe surfacing to the chat panel."""


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
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
