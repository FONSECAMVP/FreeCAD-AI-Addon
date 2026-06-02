"""Conversation history — DES-003, REQ-010, REQ-021."""

from __future__ import annotations

import json
from typing import Any


class ConversationHistory:
    def __init__(self, system_prompt: str, max_tokens: int = 8000) -> None:
        self._system = {"role": "system", "content": system_prompt}
        self._history: list[dict[str, Any]] = []
        self._max_tokens = max_tokens

    def add_user(self, content: str) -> None:
        self._history.append({"role": "user", "content": content})
        self._truncate()

    def add_assistant(self, content: str | None, tool_calls: list | None = None) -> None:
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self._history.append(msg)
        self._truncate()

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self._history.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            }
        )
        self._truncate()

    def messages(self) -> list[dict[str, Any]]:
        # REQ-010, DEC-003. OpenAI API contract: `role=assistant` + `content=null`
        # is only valid when `tool_calls` is also present; otherwise the API
        # rejects with "'content' must be string". Coerce None -> "" in that
        # specific case. Regression covered by
        # tests/test_conversation.py::test_assistant_null_content_*.
        out = []
        for msg in [self._system, *self._history]:
            m = dict(msg)
            if m.get("content") is None and "tool_calls" not in m:
                m["content"] = ""
            out.append(m)
        return out

    def clear(self) -> None:
        self._history.clear()

    def _truncate(self) -> None:
        popped = False
        while self._history and self._token_estimate() > self._max_tokens:
            self._history.pop(0)
            popped = True
        if popped:
            # Remove any leading non-user messages exposed by truncation — an
            # orphaned tool or assistant message at the start breaks the OpenAI
            # API ordering invariant (tool messages must follow assistant+tool_calls).
            while self._history and self._history[0]["role"] != "user":
                self._history.pop(0)

    def _token_estimate(self) -> int:
        return len(json.dumps(self.messages())) // 4
